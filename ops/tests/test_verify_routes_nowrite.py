from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "verify_routes_nowrite.py"
SPEC = importlib.util.spec_from_file_location("verify_routes_nowrite", SCRIPT_PATH)
assert SPEC and SPEC.loader
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


PRIVATE_VALUES = (
    "Synthetic Patient",
    "patient-982451",
    "private-token-value",
    "private@example.invalid",
    "1980-01-02",
    "https://private.example.invalid/patients/982451",
)


def smoke_result(
    *,
    failed_checkpoint: int | None = None,
    image_classification: str = "intended",
    patients_view: str = "yes",
    patient_selection: str = "active",
    valid_backend_status: str = "200",
    valid_frontend_status: str = "200",
    missing_backend_status: str = "404",
    missing_frontend_state: str = "not_found",
    missing_clinical_state: str = "not_found",
    unexpected_redirect: bool = False,
    unexpected_api: bool = False,
    unexpected_browser: bool = False,
    backend_forbidden: bool = False,
    frontend_server_error: bool = False,
    server_exit: bool = False,
    write_request: bool = False,
) -> dict[str, object]:
    checkpoints = [True] * len(SMOKE.CHECKPOINTS)
    if failed_checkpoint is not None:
        checkpoints[failed_checkpoint] = False
    return {
        "checkpoints": checkpoints,
        "image_classification": image_classification,
        "patients_view": patients_view,
        "patient_selection": patient_selection,
        "valid_backend_status": valid_backend_status,
        "valid_frontend_status": valid_frontend_status,
        "missing_backend_status": missing_backend_status,
        "missing_frontend_state": missing_frontend_state,
        "missing_clinical_state": missing_clinical_state,
        "unexpected_redirect": unexpected_redirect,
        "unexpected_api": unexpected_api,
        "unexpected_browser": unexpected_browser,
        "backend_forbidden": backend_forbidden,
        "frontend_server_error": frontend_server_error,
        "server_exit": server_exit,
        "write_request": write_request,
        "patient_name": PRIVATE_VALUES[0],
        "patient_id": PRIVATE_VALUES[1],
        "token": PRIVATE_VALUES[2],
        "email": PRIVATE_VALUES[3],
        "date_of_birth": PRIVATE_VALUES[4],
        "url": PRIVATE_VALUES[5],
    }


def output_for(monkeypatch, capsys, result: dict[str, object]) -> tuple[int, str]:
    monkeypatch.setattr(SMOKE, "run_smoke", lambda: result)
    code = SMOKE.main()
    return code, capsys.readouterr().out


def test_successful_200_404_404_sequence_is_checkpoint_only(
    monkeypatch, capsys
) -> None:
    code, output = output_for(monkeypatch, capsys, smoke_result())

    assert code == 0
    assert "checkpoint_01 Intended frontend image/source SHA confirmed: pass" in output
    assert "checkpoint_09 Valid-patient backend API returned 200: pass" in output
    assert "checkpoint_12 Missing-patient backend API returned 404: pass" in output
    assert "checkpoint_15 Missing-clinical backend patient API returned 404: pass" in output
    assert "valid_backend_status: 200" in output
    assert "missing_backend_status: 404" in output
    assert "missing_patient_route: not found" in output
    assert "missing_clinical_route: not found" in output


def test_missing_patients_view_is_blocked_safely(monkeypatch, capsys) -> None:
    result = smoke_result(
        failed_checkpoint=5,
        patients_view="no",
        patient_selection="unknown",
        backend_forbidden=True,
        unexpected_api=True,
    )
    code, output = output_for(monkeypatch, capsys, result)

    assert code == 1
    assert "checkpoint_06 patients.view capability confirmed: fail" in output
    assert "patients_view_present: no" in output
    assert "backend_403: yes" in output


def test_empty_patient_list_is_classified_without_identity(
    monkeypatch, capsys
) -> None:
    result = smoke_result(
        failed_checkpoint=8,
        patient_selection="none",
        valid_backend_status="not_checked_safely",
        valid_frontend_status="not_checked_safely",
    )
    code, output = output_for(monkeypatch, capsys, result)

    assert code == 1
    assert "valid_active_patient_discovered: no" in output
    assert "valid_backend_status: not checked safely" in output
    assert "valid_frontend_status: not checked safely" in output


def test_archived_or_inaccessible_patient_is_not_selected(
    monkeypatch, capsys
) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(
            failed_checkpoint=10,
            patient_selection="none",
            valid_backend_status="not_checked_safely",
            valid_frontend_status="not_checked_safely",
        ),
    )

    assert code == 1
    assert "valid_active_patient_discovered: no" in output
    assert "!item.archived_at" in SMOKE.NODE_SMOKE
    assert "item.is_archived !== true" in SMOKE.NODE_SMOKE
    assert 'item.status !== "archived"' in SMOKE.NODE_SMOKE


def test_unexpected_redirect_fails_explicitly(monkeypatch, capsys) -> None:
    result = smoke_result(failed_checkpoint=17, unexpected_redirect=True)
    code, output = output_for(monkeypatch, capsys, result)

    assert code == 1
    assert "checkpoint_18 No unexpected redirect detected: fail" in output
    assert "unexpected_redirect: yes" in output


def test_backend_403_fails_without_printing_response(monkeypatch, capsys) -> None:
    result = smoke_result(
        failed_checkpoint=18,
        unexpected_api=True,
        backend_forbidden=True,
    )
    code, output = output_for(monkeypatch, capsys, result)

    assert code == 1
    assert "checkpoint_19 No unexpected API status detected: fail" in output
    assert "backend_403: yes" in output


def test_frontend_500_fails_explicitly(monkeypatch, capsys) -> None:
    result = smoke_result(
        failed_checkpoint=18,
        unexpected_api=True,
        frontend_server_error=True,
    )
    code, output = output_for(monkeypatch, capsys, result)

    assert code == 1
    assert "frontend_500: yes" in output
    assert "unexpected_api_failure: yes" in output


def test_wrong_image_sha_short_circuits_before_browser(monkeypatch) -> None:
    monkeypatch.setattr(SMOKE, "_expected_sha", lambda: "candidate-sha")
    monkeypatch.setattr(
        SMOKE,
        "_container_environment",
        lambda service, name: "control-sha"
        if service == "frontend" and name == "NEXT_PUBLIC_BUILD_SHA"
        else "unused",
    )

    result = SMOKE.run_smoke()

    assert result["image_classification"] == "mismatch"
    assert not any(result["checkpoints"])
    assert result["write_request"] is False


def test_sensitive_values_are_never_printed(monkeypatch, capsys) -> None:
    code, output = output_for(monkeypatch, capsys, smoke_result())

    assert code == 0
    for private_value in PRIVATE_VALUES:
        assert private_value not in output
    assert "http://" not in output
    assert "https://" not in output


def test_malformed_runner_output_is_redacted(monkeypatch, capsys) -> None:
    malformed = {
        "checkpoints": PRIVATE_VALUES,
        "patient_id": PRIVATE_VALUES[1],
        "token": PRIVATE_VALUES[2],
        "url": PRIVATE_VALUES[5],
    }
    code, output = output_for(monkeypatch, capsys, malformed)

    assert code == 1
    assert "diagnostic_image: unknown" in output
    for private_value in PRIVATE_VALUES:
        assert private_value not in output


def test_embedded_browser_smoke_blocks_all_write_methods() -> None:
    assert 'new Set(["POST", "PUT", "PATCH", "DELETE"])' in SMOKE.NODE_SMOKE
    assert 'page.route("**/*"' in SMOKE.NODE_SMOKE
    assert 'route.abort("blockedbyclient")' in SMOKE.NODE_SMOKE
