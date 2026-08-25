from __future__ import annotations

import importlib.util
import json
import subprocess
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
    browser_event_category: str = "none",
    browser_event_stage: str = "unknown",
    expected_navigation_cancellation: bool = False,
    browser_context_closed: bool = True,
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
        "browser_event_category": browser_event_category,
        "browser_event_stage": browser_event_stage,
        "expected_navigation_cancellation": expected_navigation_cancellation,
        "browser_context_closed": browser_context_closed,
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


def run_browser_policy(body: str) -> dict[str, object]:
    completed = subprocess.run(
        ["node", "-e", SMOKE.BROWSER_POLICY_JS + "\n" + body],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    return json.loads(completed.stdout.strip().splitlines()[-1])


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


def test_delayed_safe_get_settles_before_route_transition() -> None:
    result = run_browser_policy(
        """
(async () => {
  const pending = new Set(["safe-read"]);
  let clock = 0;
  const settled = await waitForRouteReadsToSettle({
    pending,
    now: () => clock,
    delay: async (milliseconds) => {
      clock += milliseconds;
      if (clock >= 150) pending.clear();
    },
    maxWaitMs: 1_000,
    stableMs: 100,
  });
  process.stdout.write(JSON.stringify({settled, clock}));
})().catch(() => process.exit(1));
"""
    )

    assert result["settled"] is True
    assert result["clock"] >= 250


def test_expected_navigation_cancellation_is_classified_safely() -> None:
    result = run_browser_policy(
        """
const result = classifyRouteRequestFailure({
  method: "GET",
  resourceType: "fetch",
  failureKind: "aborted",
  startedStage: "valid_patient_settling",
  currentStage: "missing_patient_navigation",
  safeRead: true,
  superseded: false,
});
process.stdout.write(JSON.stringify(result));
"""
    )

    assert result == {
        "category": "request_failed_navigation_abort",
        "unexpected": False,
        "expectedCancellation": True,
    }


def test_superseded_safe_read_cancellation_is_classified_safely() -> None:
    result = run_browser_policy(
        """
const result = classifyRouteRequestFailure({
  method: "GET",
  resourceType: "xhr",
  failureKind: "failed",
  startedStage: "valid_patient_settling",
  currentStage: "valid_patient_settling",
  safeRead: true,
  superseded: true,
});
process.stdout.write(JSON.stringify(result));
"""
    )

    assert result["category"] == "request_failed_navigation_abort"
    assert result["unexpected"] is False


def test_completed_navigation_proves_late_safe_read_cancellation() -> None:
    result = run_browser_policy(
        """
const result = classifyRouteRequestFailure({
  method: "GET",
  resourceType: "fetch",
  failureKind: "aborted",
  startedStage: "missing_patient_navigation",
  currentStage: "missing_patient_navigation",
  safeRead: true,
  superseded: false,
  navigationCompleted: true,
});
process.stdout.write(JSON.stringify(result));
"""
    )

    assert result["category"] == "request_failed_navigation_abort"
    assert result["unexpected"] is False


def test_genuine_failed_api_read_remains_fatal() -> None:
    result = run_browser_policy(
        """
const result = classifyRouteRequestFailure({
  method: "GET",
  resourceType: "fetch",
  failureKind: "other",
  startedStage: "valid_patient_settling",
  currentStage: "valid_patient_settling",
  safeRead: true,
  superseded: false,
});
process.stdout.write(JSON.stringify(result));
"""
    )

    assert result["category"] == "request_failed_safe_api_read"
    assert result["unexpected"] is True


def test_genuine_static_resource_failure_remains_fatal() -> None:
    result = run_browser_policy(
        """
const result = classifyRouteRequestFailure({
  method: "GET",
  resourceType: "script",
  failureKind: "other",
  startedStage: "missing_patient_navigation",
  currentStage: "missing_patient_navigation",
  safeRead: false,
  superseded: false,
});
process.stdout.write(JSON.stringify(result));
"""
    )

    assert result["category"] == "request_failed_static_resource"
    assert result["unexpected"] is True


def test_page_error_remains_fatal() -> None:
    result = run_browser_policy(
        "process.stdout.write(JSON.stringify(classifyRoutePageError()));"
    )

    assert result == {"category": "page_error", "unexpected": True}


def test_console_error_remains_fatal() -> None:
    result = run_browser_policy(
        'process.stdout.write(JSON.stringify(classifyRouteConsoleEvent("error", "synthetic")));'
    )

    assert result == {"category": "console_other", "unexpected": True}


def test_browser_context_and_authenticated_shell_are_deterministic() -> None:
    context_close = "await context.close().catch(() => {})"
    browser_close = "if (browser) await browser.close().catch(() => {})"

    assert 'window.localStorage.setItem(key, value)' in SMOKE.NODE_SMOKE
    assert '.getByTestId("patient-header")' in SMOKE.NODE_SMOKE
    assert "waitForRouteReadsToSettle" in SMOKE.NODE_SMOKE
    assert "page.removeAllListeners()" in SMOKE.NODE_SMOKE
    assert context_close in SMOKE.NODE_SMOKE
    assert SMOKE.NODE_SMOKE.index(context_close) < SMOKE.NODE_SMOKE.index(browser_close)


def test_fixed_browser_classifications_do_not_expose_event_details(
    monkeypatch, capsys
) -> None:
    result = smoke_result(
        browser_event_category="request_failed_navigation_abort",
        browser_event_stage="missing_patient_navigation",
        expected_navigation_cancellation=True,
    )
    code, output = output_for(monkeypatch, capsys, result)

    assert code == 0
    assert "browser_event_category: request_failed_navigation_abort" in output
    assert "browser_event_stage: missing_patient_navigation" in output
    assert "expected_navigation_cancellation: yes" in output
    for private_value in PRIVATE_VALUES:
        assert private_value not in output
