from app.scripts import r4_cohort_select


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
