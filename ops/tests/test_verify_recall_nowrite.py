from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "verify_recall_nowrite.py"
SPEC = importlib.util.spec_from_file_location("verify_recall_nowrite", SCRIPT_PATH)
assert SPEC and SPEC.loader
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


PRIVATE_VALUES = (
    "Synthetic Patient",
    "patient-12345",
    "recall-98765",
    "2040-12-31",
    "private@example.invalid",
    "private contact outcome",
)


def smoke_result(
    *,
    failed_checkpoint: int | None = None,
    recall_selection: str = "suitable",
    recall_row: str = "checked",
    mutation_controls: str = "write",
    booking_control: str = "available",
    export_controls: str = "available",
    version_compatibility: str = "compatible",
    unexpected_api: bool = False,
    unexpected_browser: bool = False,
    write_request: bool = False,
) -> dict[str, object]:
    checkpoints = [True] * len(SMOKE.CHECKPOINTS)
    if failed_checkpoint is not None:
        checkpoints[failed_checkpoint] = False
    return {
        "checkpoints": checkpoints,
        "recall_selection": recall_selection,
        "recall_row": recall_row,
        "mutation_controls": mutation_controls,
        "booking_control": booking_control,
        "export_controls": export_controls,
        "version_compatibility": version_compatibility,
        "unexpected_api": unexpected_api,
        "unexpected_browser": unexpected_browser,
        "write_request": write_request,
        "patient_name": PRIVATE_VALUES[0],
        "patient_id": PRIVATE_VALUES[1],
        "recall_id": PRIVATE_VALUES[2],
        "due_date": PRIVATE_VALUES[3],
        "email": PRIVATE_VALUES[4],
        "outcome": PRIVATE_VALUES[5],
    }


def output_for(monkeypatch, capsys, result: dict[str, object]) -> tuple[int, str]:
    monkeypatch.setattr(SMOKE, "run_smoke", lambda: result)
    code = SMOKE.main()
    return code, capsys.readouterr().out


def test_main_reports_checkpoint_only_success(monkeypatch, capsys) -> None:
    code, output = output_for(monkeypatch, capsys, smoke_result())

    assert code == 0
    assert "checkpoint_01 Login completed: pass" in output
    assert "checkpoint_21 Final application health confirmed: pass" in output
    assert "suitable_recall_found: yes" in output
    assert "recall_row_smoke: pass" in output
    assert "write_request_issued: no" in output


def test_empty_recall_list_is_a_safe_success(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(
            recall_selection="none",
            recall_row="not_checked_safely",
            mutation_controls="write_no_row",
            booking_control="available_no_row",
        ),
    )

    assert code == 0
    assert "suitable_recall_found: no" in output
    assert "recall_row_smoke: not checked safely" in output


def test_suitable_recall_is_classified_without_identity(monkeypatch, capsys) -> None:
    code, output = output_for(monkeypatch, capsys, smoke_result())

    assert code == 0
    assert "checkpoint_10 Suitable recall selection classified internally: pass" in output
    assert "checkpoint_11 Recall row state rendered: pass" in output
    for private_value in PRIVATE_VALUES:
        assert private_value not in output


def test_capability_controls_are_classified(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(mutation_controls="read_only", booking_control="unavailable"),
    )

    assert code == 0
    assert "mutation_controls: read only" in output
    assert "booking_control: unavailable" in output


def test_export_controls_are_classified(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch, capsys, smoke_result(export_controls="unavailable")
    )

    assert code == 0
    assert "checkpoint_16 Export controls classified: pass" in output
    assert "export_controls: unavailable" in output


def test_write_request_detection_causes_failure(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(failed_checkpoint=19, write_request=True),
    )

    assert code == 1
    assert "checkpoint_20 No POST, PUT, PATCH or DELETE request issued: fail" in output
    assert "write_request_issued: yes" in output


def test_unexpected_api_failure_causes_failure(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(failed_checkpoint=17, unexpected_api=True),
    )

    assert code == 1
    assert "checkpoint_18 No unexpected API 4xx/5xx: fail" in output
    assert "unexpected_api_failure: yes" in output


def test_browser_failure_causes_failure(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(failed_checkpoint=18, unexpected_browser=True),
    )

    assert code == 1
    assert "checkpoint_19 No unexpected browser error: fail" in output
    assert "unexpected_browser_failure: yes" in output


def test_output_redacts_all_untrusted_values(monkeypatch, capsys) -> None:
    code, output = output_for(monkeypatch, capsys, smoke_result())

    assert code == 0
    for private_value in PRIVATE_VALUES:
        assert private_value not in output


def test_malformed_payload_fails_without_echoing_values(monkeypatch, capsys) -> None:
    malformed = {"checkpoints": PRIVATE_VALUES, "patient_name": PRIVATE_VALUES[0]}
    code, output = output_for(monkeypatch, capsys, malformed)

    assert code == 1
    assert "checkpoint_01 Login completed: fail" in output
    for private_value in PRIVATE_VALUES:
        assert private_value not in output


def test_embedded_browser_smoke_blocks_write_methods_before_network() -> None:
    assert 'page.route("**/api/**"' in SMOKE.NODE_SMOKE
    assert 'route.abort("blockedbyclient")' in SMOKE.NODE_SMOKE
    assert 'new Set(["POST", "PUT", "PATCH", "DELETE"])' in SMOKE.NODE_SMOKE
