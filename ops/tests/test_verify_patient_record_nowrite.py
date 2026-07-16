from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "verify_patient_record_nowrite.py"
SPEC = importlib.util.spec_from_file_location("verify_patient_record_nowrite", SCRIPT_PATH)
assert SPEC and SPEC.loader
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


PRIVATE_VALUES = (
    "Synthetic Patient",
    "patient-12345",
    "1990-01-02",
    "private@example.invalid",
    "07123456789",
    "Secret Street",
)


def smoke_result(
    *,
    failed_checkpoint: int | None = None,
    patient_selection: str = "active",
    unexpected_api: bool = False,
    unexpected_browser: bool = False,
    write_request: bool = False,
) -> dict[str, object]:
    checkpoints = [True] * len(SMOKE.CHECKPOINTS)
    if failed_checkpoint is not None:
        checkpoints[failed_checkpoint] = False
    return {
        "checkpoints": checkpoints,
        "patient_selection": patient_selection,
        "archived_patient": "not_checked_safely",
        "unexpected_api": unexpected_api,
        "unexpected_browser": unexpected_browser,
        "write_request": write_request,
        "patient_name": PRIVATE_VALUES[0],
        "patient_id": PRIVATE_VALUES[1],
        "date_of_birth": PRIVATE_VALUES[2],
        "email": PRIVATE_VALUES[3],
        "phone": PRIVATE_VALUES[4],
        "address": PRIVATE_VALUES[5],
    }


def output_for(monkeypatch, capsys, result: dict[str, object]) -> tuple[int, str]:
    monkeypatch.setattr(SMOKE, "run_smoke", lambda: result)
    code = SMOKE.main()
    return code, capsys.readouterr().out


def test_main_reports_checkpoint_only_success(monkeypatch, capsys) -> None:
    code, output = output_for(monkeypatch, capsys, smoke_result())

    assert code == 0
    assert "checkpoint_01 Login completed: pass" in output
    assert "checkpoint_20 Final application health confirmed: pass" in output
    assert "active_patient_selected: yes" in output
    assert "archived_patient_smoke: not checked safely" in output
    assert "unexpected_api_failure: no" in output
    assert "unexpected_browser_failure: no" in output
    assert "write_request_issued: no" in output


def test_active_patient_detail_and_audit_checkpoints_are_classified_only(
    monkeypatch, capsys
) -> None:
    code, output = output_for(monkeypatch, capsys, smoke_result())

    assert code == 0
    assert "checkpoint_06 Suitable active patient selected internally: pass" in output
    assert "checkpoint_09 Patient detail opened: pass" in output
    assert "checkpoint_10 Patient detail page rendered: pass" in output
    assert "checkpoint_13 Audit/history control found: pass" in output
    assert "checkpoint_14 Audit/history loaded: pass" in output


def test_write_request_detection_causes_failure(monkeypatch, capsys) -> None:
    result = smoke_result(failed_checkpoint=18, write_request=True)
    code, output = output_for(monkeypatch, capsys, result)

    assert code == 1
    assert "checkpoint_19 No POST, PUT, PATCH or DELETE request issued: fail" in output
    assert "write_request_issued: yes" in output


def test_unexpected_api_failure_causes_failure(monkeypatch, capsys) -> None:
    result = smoke_result(failed_checkpoint=16, unexpected_api=True)
    code, output = output_for(monkeypatch, capsys, result)

    assert code == 1
    assert "checkpoint_17 No unexpected API 4xx/5xx: fail" in output
    assert "unexpected_api_failure: yes" in output


def test_browser_failure_causes_failure(monkeypatch, capsys) -> None:
    result = smoke_result(failed_checkpoint=17, unexpected_browser=True)
    code, output = output_for(monkeypatch, capsys, result)

    assert code == 1
    assert "checkpoint_18 No unexpected browser error: fail" in output
    assert "unexpected_browser_failure: yes" in output


def test_missing_suitable_patient_has_clear_safe_classification(monkeypatch, capsys) -> None:
    result = smoke_result(failed_checkpoint=5, patient_selection="none")
    code, output = output_for(monkeypatch, capsys, result)

    assert code == 1
    assert "checkpoint_06 Suitable active patient selected internally: fail" in output
    assert "active_patient_selected: no" in output


def test_output_drops_untrusted_patient_values(monkeypatch, capsys) -> None:
    code, output = output_for(monkeypatch, capsys, smoke_result())

    assert code == 0
    for private_value in PRIVATE_VALUES:
        assert private_value not in output


def test_malformed_runner_payload_fails_without_echoing_it(monkeypatch, capsys) -> None:
    malformed = {"checkpoints": PRIVATE_VALUES, "patient_name": PRIVATE_VALUES[0]}
    code, output = output_for(monkeypatch, capsys, malformed)

    assert code == 1
    assert "checkpoint_01 Login completed: fail" in output
    assert "active_patient_selected: no" in output
    for private_value in PRIVATE_VALUES:
        assert private_value not in output


def test_embedded_browser_smoke_blocks_write_methods_before_network() -> None:
    assert 'page.route("**/api/**"' in SMOKE.NODE_SMOKE
    assert 'route.abort("blockedbyclient")' in SMOKE.NODE_SMOKE
    assert 'new Set(["POST", "PUT", "PATCH", "DELETE"])' in SMOKE.NODE_SMOKE
