from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "verify_clinical_nowrite.py"
SPEC = importlib.util.spec_from_file_location("verify_clinical_nowrite", SCRIPT_PATH)
assert SPEC and SPEC.loader
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


PRIVATE_VALUES = (
    "Synthetic Patient",
    "patient-98765",
    "sensitive tooth note",
    "private treatment description",
    "appointment-123",
    "https://private.invalid/patients/98765",
    "/private/clinical/path",
    "synthetic-password",
)


def smoke_result(
    *,
    failed_checkpoint: int | None = None,
    patient_selection: str = "active",
    clinical_view: str = "present",
    clinical_controls: str = "write",
    visual_state: str = "planned-absent/completed-absent",
    tooth_history_api_completed: bool = True,
    treatment_plan_api_completed: bool = True,
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
        "clinical_view": clinical_view,
        "clinical_controls": clinical_controls,
        "visual_state": visual_state,
        "tooth_history_api_completed": tooth_history_api_completed,
        "treatment_plan_api_completed": treatment_plan_api_completed,
        "unexpected_api": unexpected_api,
        "unexpected_browser": unexpected_browser,
        "write_request": write_request,
        "patient_name": PRIVATE_VALUES[0],
        "patient_id": PRIVATE_VALUES[1],
        "tooth_note": PRIVATE_VALUES[2],
        "treatment_description": PRIVATE_VALUES[3],
        "appointment_id": PRIVATE_VALUES[4],
        "url": PRIVATE_VALUES[5],
        "path": PRIVATE_VALUES[6],
        "password": PRIVATE_VALUES[7],
    }


def output_for(monkeypatch, capsys, result: dict[str, object]) -> tuple[int, str]:
    monkeypatch.setattr(SMOKE, "run_smoke", lambda: result)
    code = SMOKE.main()
    return code, capsys.readouterr().out


def test_main_reports_safe_21_checkpoint_success(monkeypatch, capsys) -> None:
    code, output = output_for(monkeypatch, capsys, smoke_result())

    assert code == 0
    assert "checkpoint_01 Login completed: pass" in output
    assert "checkpoint_21 Final application health: pass" in output
    assert "active_patient_selected: yes" in output
    assert "clinical_view: present" in output
    assert "clinical_controls: write" in output
    assert "visual_state: planned-absent/completed-absent" in output
    assert "tooth_history_api_completed: yes" in output
    assert "treatment_plan_api_completed: yes" in output
    assert "unexpected_api_failure: no" in output
    assert "unexpected_browser_failure: no" in output
    assert "write_request_issued: no" in output


def test_optional_planned_and_completed_content_is_classified_safely(
    monkeypatch, capsys
) -> None:
    for visual_state in (
        "planned-present/completed-present",
        "planned-present/completed-absent",
        "planned-absent/completed-present",
        "planned-absent/completed-absent",
    ):
        code, output = output_for(
            monkeypatch, capsys, smoke_result(visual_state=visual_state)
        )
        assert code == 0
        assert f"visual_state: {visual_state}" in output


def test_read_only_controls_are_a_valid_classification(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch, capsys, smoke_result(clinical_controls="read-only")
    )

    assert code == 0
    assert "clinical_controls: read-only" in output


def test_missing_clinical_view_fails_safely(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(failed_checkpoint=3, clinical_view="missing"),
    )

    assert code == 1
    assert "checkpoint_04 clinical.view classified: fail" in output
    assert "clinical_view: missing" in output


def test_missing_suitable_patient_fails_without_identifier(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(failed_checkpoint=4, patient_selection="none"),
    )

    assert code == 1
    assert "checkpoint_05 Suitable active patient selected internally: fail" in output
    assert "active_patient_selected: no" in output


def test_api_and_browser_failures_are_critical(monkeypatch, capsys) -> None:
    api_code, api_output = output_for(
        monkeypatch,
        capsys,
        smoke_result(failed_checkpoint=17, unexpected_api=True),
    )
    browser_code, browser_output = output_for(
        monkeypatch,
        capsys,
        smoke_result(failed_checkpoint=18, unexpected_browser=True),
    )

    assert api_code == 1
    assert "checkpoint_18 No unexpected API error: fail" in api_output
    assert "unexpected_api_failure: yes" in api_output
    assert browser_code == 1
    assert "checkpoint_19 No browser error: fail" in browser_output
    assert "unexpected_browser_failure: yes" in browser_output


def test_write_request_detection_is_critical(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(failed_checkpoint=19, write_request=True),
    )

    assert code == 1
    assert "checkpoint_20 No POST, PUT, PATCH or DELETE request: fail" in output
    assert "write_request_issued: yes" in output


def test_api_completion_classifications_are_required(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(
            failed_checkpoint=10,
            tooth_history_api_completed=False,
        ),
    )
    assert code == 1
    assert "tooth_history_api_completed: no" in output

    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(
            failed_checkpoint=12,
            treatment_plan_api_completed=False,
        ),
    )
    assert code == 1
    assert "treatment_plan_api_completed: no" in output


def test_output_drops_all_untrusted_private_values(monkeypatch, capsys) -> None:
    code, output = output_for(monkeypatch, capsys, smoke_result())

    assert code == 0
    for private_value in PRIVATE_VALUES:
        assert private_value not in output


def test_malformed_payload_fails_without_echoing_it(monkeypatch, capsys) -> None:
    malformed = {"checkpoints": PRIVATE_VALUES, "patient_name": PRIVATE_VALUES[0]}
    code, output = output_for(monkeypatch, capsys, malformed)

    assert code == 1
    assert "checkpoint_01 Login completed: fail" in output
    for private_value in PRIVATE_VALUES:
        assert private_value not in output


def test_browser_write_methods_are_blocked_before_any_network_request() -> None:
    route = SMOKE.NODE_SMOKE.index('page.route("**/*"')
    method_check = SMOKE.NODE_SMOKE.index(
        "if (writeMethods.has(route.request().method()))", route
    )
    abort = SMOKE.NODE_SMOKE.index('route.abort("blockedbyclient")', method_check)
    continuation = SMOKE.NODE_SMOKE.index("route.continue()", abort)

    assert route < method_check < abort < continuation
    assert 'new Set(["POST", "PUT", "PATCH", "DELETE"])' in SMOKE.NODE_SMOKE


def test_only_known_optional_clinical_403_and_404_responses_are_tolerated() -> None:
    assert "function isExpectedOptionalClinicalResponse" in SMOKE.NODE_SMOKE
    assert 'status !== 403 && status !== 404' in SMOKE.NODE_SMOKE
    assert "(treatment-plan-items|tooth-state)" in SMOKE.NODE_SMOKE
    assert "!isExpectedOptionalClinicalResponse(response.url(), response.status())" in (
        SMOKE.NODE_SMOKE
    )


def test_capability_convergence_precedes_control_classification() -> None:
    expected = SMOKE.NODE_SMOKE.index("const expectedControlState")
    navigation = SMOKE.NODE_SMOKE.index("const navigation = await page.goto")
    convergence = SMOKE.NODE_SMOKE.index("const modeConverged = await waitUntil")
    checkpoint = SMOKE.NODE_SMOKE.index("checkpoints[16] =")

    assert expected < navigation < convergence < checkpoint


def test_local_candidate_mode_uses_frontend_node_without_compose(monkeypatch) -> None:
    expected = smoke_result()
    calls: list[tuple[list[str], object]] = []

    class Completed:
        stdout = __import__("json").dumps(expected)

    def fake_run(command, **kwargs):
        calls.append((command, kwargs.get("cwd")))
        return Completed()

    monkeypatch.setenv("CLINICAL_SMOKE_LOCAL", "1")
    monkeypatch.setenv("SMOKE_ADMIN_EMAIL", "synthetic@example.invalid")
    monkeypatch.setenv("SMOKE_ADMIN_PASSWORD", "synthetic-password")
    monkeypatch.setattr(SMOKE.subprocess, "run", fake_run)

    result = SMOKE.run_smoke()

    assert result["checkpoints"] == [True] * 21
    assert calls[0][0][:2] == ["node", "-e"]
    assert calls[0][1].name == "frontend"
