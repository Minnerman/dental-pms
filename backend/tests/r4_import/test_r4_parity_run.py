import json
from pathlib import Path

from app.scripts import r4_parity_run


class _DummySession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_parse_domains_csv_defaults_all():
    assert r4_parity_run._parse_domains_csv(None) == [
        "bpe",
        "bpe_furcation",
        "perioprobe",
        "patient_notes",
        "treatment_notes",
    ]


def test_parse_domains_csv_rejects_unknown():
    try:
        r4_parity_run._parse_domains_csv("bpe,unknown")
    except RuntimeError as exc:
        assert "Unsupported domain" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")


def test_run_parity_aggregates_statuses(monkeypatch, tmp_path: Path):
    def _build_with_data(*args, **kwargs):
        return {
            "patients": [
                {
                    "patient_code": 1000,
                    "sqlserver_total_rows": 1,
                    "latest_match": True,
                    "latest_digest_match": True,
                }
            ]
        }

    def _build_no_data(*args, **kwargs):
        return {
            "patients": [
                {
                    "patient_code": 1000,
                    "sqlserver_total_rows": 0,
                    "latest_match": None,
                    "latest_digest_match": None,
                }
            ]
        }

    monkeypatch.setattr(r4_parity_run, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(r4_parity_run.r4_bpe_parity_pack, "build_parity_report", _build_with_data)
    monkeypatch.setattr(
        r4_parity_run.r4_bpe_furcation_parity_pack, "build_parity_report", _build_with_data
    )
    monkeypatch.setattr(r4_parity_run.r4_perioprobe_parity_pack, "build_parity_report", _build_no_data)

    report = r4_parity_run.run_parity(
        patient_codes=[1000],
        domains=["bpe", "bpe_furcation", "perioprobe"],
        date_from=None,
        date_to=None,
        row_limit=10,
        output_dir=str(tmp_path),
    )

    assert report["domain_summaries"]["bpe"]["status"] == "pass"
    assert report["domain_summaries"]["bpe_furcation"]["status"] == "pass"
    assert report["domain_summaries"]["perioprobe"]["status"] == "no_data"
    assert report["overall"]["status"] == "pass"
    assert report["overall"]["has_data"] is True
    assert (tmp_path / "bpe.json").exists()
    assert (tmp_path / "bpe_furcation.json").exists()
    assert (tmp_path / "perioprobe.json").exists()


def test_main_writes_output_json(monkeypatch, tmp_path: Path):
    out = tmp_path / "combined.json"

    def _fake_run_parity(**kwargs):
        return {"overall": {"status": "pass"}, "domain_reports": {}, "domain_summaries": {}}

    monkeypatch.setattr(r4_parity_run, "run_parity", _fake_run_parity)
    monkeypatch.setattr(
        "sys.argv",
        [
            "r4_parity_run.py",
            "--patient-codes",
            "1000",
            "--output-json",
            str(out),
        ],
    )
    assert r4_parity_run.main() == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["overall"]["status"] == "pass"


def test_main_accepts_patient_codes_file_csv(monkeypatch, tmp_path: Path):
    out = tmp_path / "combined.json"
    codes = tmp_path / "codes.csv"
    codes.write_text("1002,1001,1002\n", encoding="utf-8")
    called: dict[str, object] = {}

    def _fake_run_parity(**kwargs):
        called.update(kwargs)
        return {"overall": {"status": "pass"}, "domain_reports": {}, "domain_summaries": {}}

    monkeypatch.setattr(r4_parity_run, "run_parity", _fake_run_parity)
    monkeypatch.setattr(
        "sys.argv",
        [
            "r4_parity_run.py",
            "--patient-codes-file",
            str(codes),
            "--output-json",
            str(out),
        ],
    )
    assert r4_parity_run.main() == 0
    assert called["patient_codes"] == [1001, 1002]


def test_main_accepts_patient_codes_file_newline(monkeypatch, tmp_path: Path):
    out = tmp_path / "combined.json"
    codes = tmp_path / "codes.txt"
    codes.write_text("1003\n1001\n# comment\n1003\n", encoding="utf-8")
    called: dict[str, object] = {}

    def _fake_run_parity(**kwargs):
        called.update(kwargs)
        return {"overall": {"status": "pass"}, "domain_reports": {}, "domain_summaries": {}}

    monkeypatch.setattr(r4_parity_run, "run_parity", _fake_run_parity)
    monkeypatch.setattr(
        "sys.argv",
        [
            "r4_parity_run.py",
            "--patient-codes-file",
            str(codes),
            "--output-json",
            str(out),
        ],
    )
    assert r4_parity_run.main() == 0
    assert called["patient_codes"] == [1001, 1003]


def test_main_rejects_patient_codes_and_file_together(monkeypatch, tmp_path: Path):
    out = tmp_path / "combined.json"
    codes = tmp_path / "codes.csv"
    codes.write_text("1001\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "r4_parity_run.py",
            "--patient-codes",
            "1001",
            "--patient-codes-file",
            str(codes),
            "--output-json",
            str(out),
        ],
    )
    try:
        r4_parity_run.main()
    except SystemExit as exc:
        assert exc.code == 2
    else:  # pragma: no cover
        raise AssertionError("expected SystemExit")
