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
    monkeypatch.setattr(r4_parity_run.r4_perioprobe_parity_pack, "build_parity_report", _build_no_data)

    report = r4_parity_run.run_parity(
        patient_codes=[1000],
        domains=["bpe", "perioprobe"],
        date_from=None,
        date_to=None,
        row_limit=10,
        output_dir=str(tmp_path),
    )

    assert report["domain_summaries"]["bpe"]["status"] == "pass"
    assert report["domain_summaries"]["perioprobe"]["status"] == "no_data"
    assert report["overall"]["status"] == "pass"
    assert report["overall"]["has_data"] is True
    assert (tmp_path / "bpe.json").exists()
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
