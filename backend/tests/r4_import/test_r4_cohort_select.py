from app.scripts import r4_cohort_select


def test_parse_domains_csv_defaults_include_treatment_plan_items():
    assert r4_cohort_select._parse_domains_csv(None) == [
        "perioprobe",
        "bpe",
        "bpe_furcation",
        "treatment_notes",
        "treatment_plan_items",
    ]


def test_select_cohort_union(monkeypatch):
    monkeypatch.setattr(
        r4_cohort_select,
        "_build_domain_codes",
        lambda domain, **kwargs: {
            "perioprobe": [5, 3, 3],
            "bpe": [7, 3],
            "bpe_furcation": [9],
        }[domain],
    )
    report = r4_cohort_select.select_cohort(
        domains=["perioprobe", "bpe", "bpe_furcation"],
        date_from="2017-01-01",
        date_to="2026-02-01",
        limit=10,
        mode="union",
    )
    assert report["domain_counts"] == {"perioprobe": 2, "bpe": 2, "bpe_furcation": 1}
    assert report["patient_codes"] == [3, 5, 7, 9]


def test_select_cohort_intersection(monkeypatch):
    monkeypatch.setattr(
        r4_cohort_select,
        "_build_domain_codes",
        lambda domain, **kwargs: {
            "perioprobe": [1, 2, 3],
            "bpe": [2, 3, 4],
            "bpe_furcation": [3, 4, 5],
        }[domain],
    )
    report = r4_cohort_select.select_cohort(
        domains=["perioprobe", "bpe", "bpe_furcation"],
        date_from="2017-01-01",
        date_to="2026-02-01",
        limit=10,
        mode="intersection",
    )
    assert report["patient_codes"] == [3]


def test_select_cohort_applies_exclusions_before_limit(monkeypatch):
    monkeypatch.setattr(
        r4_cohort_select,
        "_build_domain_codes",
        lambda domain, **kwargs: list(range(1, 11)),
    )
    report = r4_cohort_select.select_cohort(
        domains=["bpe"],
        date_from="2017-01-01",
        date_to="2026-02-01",
        limit=5,
        mode="union",
        excluded_patient_codes={1, 2, 3},
    )
    assert report["patient_codes"] == [4, 5, 6, 7, 8]
    assert report["candidates_before_exclude"] == 10
    assert report["exclude_input_count"] == 3
    assert report["excluded_candidates_count"] == 3
    assert report["exclude_count"] == 3
    assert report["remaining_after_exclude"] == 7
    assert report["selected_count"] == 5


def test_select_cohort_exclude_all_raises(monkeypatch):
    monkeypatch.setattr(
        r4_cohort_select,
        "_build_domain_codes",
        lambda domain, **kwargs: [1, 2, 3],
    )
    try:
        r4_cohort_select.select_cohort(
            domains=["bpe"],
            date_from="2017-01-01",
            date_to="2026-02-01",
            limit=10,
            mode="union",
            excluded_patient_codes={1, 2, 3},
        )
    except RuntimeError as exc:
        assert "Exclusion removed all candidate patient codes" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")


def test_select_cohort_hashed_order_changes_with_seed_and_is_deterministic(monkeypatch):
    monkeypatch.setattr(
        r4_cohort_select,
        "_build_domain_codes",
        lambda domain, **kwargs: list(range(1, 101)),
    )
    first = r4_cohort_select.select_cohort(
        domains=["bpe"],
        date_from="2017-01-01",
        date_to="2026-02-01",
        limit=10,
        mode="union",
        order="hashed",
        seed=1,
    )
    second = r4_cohort_select.select_cohort(
        domains=["bpe"],
        date_from="2017-01-01",
        date_to="2026-02-01",
        limit=10,
        mode="union",
        order="hashed",
        seed=1,
    )
    third = r4_cohort_select.select_cohort(
        domains=["bpe"],
        date_from="2017-01-01",
        date_to="2026-02-01",
        limit=10,
        mode="union",
        order="hashed",
        seed=2,
    )
    assert first["patient_codes"] == second["patient_codes"]
    assert first["patient_codes"] != third["patient_codes"]


def test_select_cohort_hashed_order_requires_seed(monkeypatch):
    monkeypatch.setattr(
        r4_cohort_select,
        "_build_domain_codes",
        lambda domain, **kwargs: [1, 2, 3],
    )
    try:
        r4_cohort_select.select_cohort(
            domains=["bpe"],
            date_from="2017-01-01",
            date_to="2026-02-01",
            limit=10,
            mode="union",
            order="hashed",
            seed=None,
        )
    except RuntimeError as exc:
        assert "--seed is required when --order=hashed." in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")


def test_parse_domains_csv_accepts_treatment_notes():
    assert r4_cohort_select._parse_domains_csv("treatment_notes") == ["treatment_notes"]


def test_select_cohort_active_patients_mode_applies_exclusions_and_limit(monkeypatch):
    monkeypatch.setattr(
        r4_cohort_select,
        "_build_active_patient_codes",
        lambda **kwargs: list(range(1000, 1010)),
    )
    report = r4_cohort_select.select_cohort(
        domains=["bpe"],
        date_from=None,
        date_to="2026-02-01",
        limit=3,
        mode="active_patients",
        excluded_patient_codes={1000, 1001},
        order="asc",
        active_months=24,
    )
    assert report["patient_codes"] == [1002, 1003, 1004]
    assert report["candidates_before_exclude"] == 10
    assert report["excluded_candidates_count"] == 2
    assert report["remaining_after_exclude"] == 8
    assert report["selected_count"] == 3
    assert report["active_from"] == "2024-02-01"
    assert report["active_to"] == "2026-02-01"
    assert report["active_months"] == 24


def test_select_cohort_non_active_requires_date_from(monkeypatch):
    monkeypatch.setattr(
        r4_cohort_select,
        "_build_domain_codes",
        lambda domain, **kwargs: [1],
    )
    try:
        r4_cohort_select.select_cohort(
            domains=["bpe"],
            date_from=None,
            date_to="2026-02-01",
            limit=10,
            mode="union",
        )
    except RuntimeError as exc:
        assert "--date-from is required unless --mode=active_patients." in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")


def test_parse_exclude_patient_codes_file_csv_and_newline(tmp_path):
    path = tmp_path / "exclude.csv"
    path.write_text("1,3\n2\n3\n", encoding="utf-8")
    assert r4_cohort_select._parse_exclude_patient_codes_file(str(path)) == {1, 2, 3}


def test_main_writes_output_csv(monkeypatch, tmp_path):
    out = tmp_path / "codes.csv"
    monkeypatch.setattr(
        r4_cohort_select,
        "select_cohort",
        lambda **kwargs: {
            "domains": ["perioprobe", "bpe", "bpe_furcation"],
            "mode": "union",
            "date_from": "2017-01-01",
            "date_to": "2026-02-01",
            "limit": 3,
            "order": "asc",
            "seed": None,
            "candidates_before_exclude": 3,
            "exclude_input_count": 0,
            "excluded_candidates_count": 0,
            "exclude_count": 0,
            "remaining_after_exclude": 3,
            "selected_count": 3,
            "domain_counts": {"perioprobe": 2, "bpe": 1, "bpe_furcation": 1},
            "cohort_size": 3,
            "patient_codes": [1000000, 1000001, 1000002],
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "r4_cohort_select.py",
            "--date-from",
            "2017-01-01",
            "--date-to",
            "2026-02-01",
            "--output",
            str(out),
        ],
    )
    assert r4_cohort_select.main() == 0
    assert out.read_text(encoding="utf-8") == "1000000,1000001,1000002\n"
