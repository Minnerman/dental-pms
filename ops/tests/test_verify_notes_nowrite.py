from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "verify_notes_nowrite.py"
SPEC = importlib.util.spec_from_file_location("verify_notes_nowrite", SCRIPT_PATH)
assert SPEC and SPEC.loader
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


PRIVATE_VALUES = (
    "Synthetic Patient",
    "patient-98765",
    "sensitive note body",
    "note-54321",
    "appointment-123",
    "https://private.invalid/notes/54321",
    "/private/notes/path",
    "synthetic-password",
    "request body content",
)


def smoke_result(
    *,
    failed_checkpoint: int | None = None,
    notes_view: str = "present",
    notes_write: str = "present",
    note_detail: str = "checked",
    appointment_note: str = "checked",
    patient_navigation: str = "available",
    audit_control: str = "available",
    mutation_controls: str = "write",
    archive_state: str = "active-write",
    patient_endpoint: str = "checked",
    unexpected_api: bool = False,
    unexpected_browser: bool = False,
    write_request: bool = False,
) -> dict[str, object]:
    checkpoints = [True] * len(SMOKE.CHECKPOINTS)
    if failed_checkpoint is not None:
        checkpoints[failed_checkpoint] = False
    return {
        "checkpoints": checkpoints,
        "notes_view": notes_view,
        "notes_write": notes_write,
        "note_detail": note_detail,
        "appointment_note": appointment_note,
        "patient_navigation": patient_navigation,
        "audit_control": audit_control,
        "mutation_controls": mutation_controls,
        "archive_state": archive_state,
        "patient_endpoint": patient_endpoint,
        "unexpected_api": unexpected_api,
        "unexpected_browser": unexpected_browser,
        "write_request": write_request,
        "patient_name": PRIVATE_VALUES[0],
        "patient_id": PRIVATE_VALUES[1],
        "note_body": PRIVATE_VALUES[2],
        "note_id": PRIVATE_VALUES[3],
        "appointment_id": PRIVATE_VALUES[4],
        "url": PRIVATE_VALUES[5],
        "path": PRIVATE_VALUES[6],
        "password": PRIVATE_VALUES[7],
        "request_body": PRIVATE_VALUES[8],
    }


def output_for(monkeypatch, capsys, result: dict[str, object]) -> tuple[int, str]:
    monkeypatch.setattr(SMOKE, "run_smoke", lambda: result)
    code = SMOKE.main()
    return code, capsys.readouterr().out


def test_main_reports_safe_22_checkpoint_success(monkeypatch, capsys) -> None:
    code, output = output_for(monkeypatch, capsys, smoke_result())

    assert code == 0
    assert "checkpoint_01 Login completed: pass" in output
    assert "checkpoint_22 Final application health confirmed: pass" in output
    assert "notes_view: present" in output
    assert "notes_write: present" in output
    assert "note_detail_smoke: checked" in output
    assert "appointment_note_smoke: checked" in output
    assert "mutation_controls: write" in output
    assert "unexpected_api_failure: no" in output
    assert "unexpected_browser_failure: no" in output
    assert "write_request_issued: no" in output


def test_empty_notes_and_missing_appointment_note_are_safe_classifications(
    monkeypatch, capsys
) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(
            note_detail="not-checked-safely",
            appointment_note="not-checked-safely",
            patient_navigation="not-checked-safely",
            audit_control="not-checked-safely",
            archive_state="not-checked-safely",
            patient_endpoint="not-checked-safely",
        ),
    )

    assert code == 0
    assert "note_detail_smoke: not-checked-safely" in output
    assert "appointment_note_smoke: not-checked-safely" in output


def test_read_only_controls_are_a_valid_classification(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(
            notes_write="missing",
            mutation_controls="read-only",
            archive_state="read-only",
        ),
    )

    assert code == 0
    assert "notes_write: missing" in output
    assert "mutation_controls: read-only" in output


def test_missing_notes_view_fails_safely(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(failed_checkpoint=4, notes_view="missing"),
    )

    assert code == 1
    assert "checkpoint_05 notes.view classified: fail" in output
    assert "notes_view: missing" in output


def test_api_and_browser_failures_are_critical(monkeypatch, capsys) -> None:
    api_code, api_output = output_for(
        monkeypatch,
        capsys,
        smoke_result(failed_checkpoint=18, unexpected_api=True),
    )
    browser_code, browser_output = output_for(
        monkeypatch,
        capsys,
        smoke_result(failed_checkpoint=19, unexpected_browser=True),
    )

    assert api_code == 1
    assert "checkpoint_19 No unexpected API 4xx/5xx: fail" in api_output
    assert "unexpected_api_failure: yes" in api_output
    assert browser_code == 1
    assert "checkpoint_20 No browser error: fail" in browser_output
    assert "unexpected_browser_failure: yes" in browser_output


def test_write_request_detection_is_critical(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(failed_checkpoint=20, write_request=True),
    )

    assert code == 1
    assert "checkpoint_21 No POST, PUT, PATCH or DELETE request issued: fail" in output
    assert "write_request_issued: yes" in output


def test_output_drops_all_untrusted_private_values(monkeypatch, capsys) -> None:
    code, output = output_for(monkeypatch, capsys, smoke_result())

    assert code == 0
    for private_value in PRIVATE_VALUES:
        assert private_value not in output


def test_malformed_payload_fails_without_echoing_it(monkeypatch, capsys) -> None:
    malformed = {"checkpoints": PRIVATE_VALUES, "note_body": PRIVATE_VALUES[2]}
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


def test_only_login_is_exempt_from_direct_write_block() -> None:
    assert 'path !== "/api/auth/login"' in SMOKE.NODE_SMOKE
    assert "if (writeMethods.has(method)" in SMOKE.NODE_SMOKE


def test_no_sensitive_fields_are_part_of_normalised_output() -> None:
    normalised = SMOKE._normalise_result(smoke_result())

    assert set(normalised) == {
        "checkpoints",
        "notes_view",
        "notes_write",
        "note_detail",
        "appointment_note",
        "patient_navigation",
        "audit_control",
        "mutation_controls",
        "archive_state",
        "patient_endpoint",
        "unexpected_api",
        "unexpected_browser",
        "write_request",
    }


def test_local_candidate_mode_uses_frontend_node_without_compose(monkeypatch) -> None:
    expected = smoke_result()
    calls: list[tuple[list[str], object]] = []

    class Completed:
        stdout = __import__("json").dumps(expected)

    def fake_run(command, **kwargs):
        calls.append((command, kwargs.get("cwd")))
        return Completed()

    monkeypatch.setenv("NOTES_SMOKE_LOCAL", "1")
    monkeypatch.setenv("SMOKE_ADMIN_EMAIL", "synthetic@example.invalid")
    monkeypatch.setenv("SMOKE_ADMIN_PASSWORD", "synthetic-password")
    monkeypatch.setattr(SMOKE.subprocess, "run", fake_run)

    result = SMOKE.run_smoke()

    assert result["checkpoints"] == [True] * 22
    assert calls[0][0][:2] == ["node", "-e"]
    assert calls[0][1].name == "frontend"
