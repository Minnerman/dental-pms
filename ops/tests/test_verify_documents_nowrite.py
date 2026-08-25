from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "verify_documents_nowrite.py"
SPEC = importlib.util.spec_from_file_location("verify_documents_nowrite", SCRIPT_PATH)
assert SPEC and SPEC.loader
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


PRIVATE_VALUES = (
    "Synthetic Patient",
    "patient-98765",
    "private-document.pdf",
    "document-54321",
    "attachment-12345",
    "template-67890",
    "sensitive document text",
    "https://private.invalid/documents/54321",
    "/private/document/path",
    "synthetic-password",
    "private response body",
)


def smoke_result(
    *,
    failed_checkpoint: int | None = None,
    documents_download: str = "present",
    documents_upload: str = "present",
    documents_delete: str = "present",
    document_state: str = "populated",
    attachment_state: str = "populated",
    document_metadata: str = "checked",
    attachment_metadata: str = "checked",
    download_controls: str = "available",
    upload_controls: str = "write",
    delete_controls: str = "write",
    lifecycle_state: str = "active",
    unexpected_api: bool = False,
    unexpected_browser: bool = False,
    write_request: bool = False,
    audited_endpoint: bool = False,
    context_closed: bool = True,
) -> dict[str, object]:
    checkpoints = [True] * len(SMOKE.CHECKPOINTS)
    if failed_checkpoint is not None:
        checkpoints[failed_checkpoint] = False
    return {
        "checkpoints": checkpoints,
        "documents_download": documents_download,
        "documents_upload": documents_upload,
        "documents_delete": documents_delete,
        "document_state": document_state,
        "attachment_state": attachment_state,
        "document_metadata": document_metadata,
        "attachment_metadata": attachment_metadata,
        "download_controls": download_controls,
        "upload_controls": upload_controls,
        "delete_controls": delete_controls,
        "lifecycle_state": lifecycle_state,
        "unexpected_api": unexpected_api,
        "unexpected_browser": unexpected_browser,
        "write_request": write_request,
        "audited_endpoint": audited_endpoint,
        "context_closed": context_closed,
        "patient_name": PRIVATE_VALUES[0],
        "patient_id": PRIVATE_VALUES[1],
        "filename": PRIVATE_VALUES[2],
        "document_id": PRIVATE_VALUES[3],
        "attachment_id": PRIVATE_VALUES[4],
        "template_id": PRIVATE_VALUES[5],
        "document_text": PRIVATE_VALUES[6],
        "url": PRIVATE_VALUES[7],
        "path": PRIVATE_VALUES[8],
        "password": PRIVATE_VALUES[9],
        "response_body": PRIVATE_VALUES[10],
    }


def output_for(monkeypatch, capsys, result: dict[str, object]) -> tuple[int, str]:
    monkeypatch.setattr(SMOKE, "run_smoke", lambda: result)
    code = SMOKE.main()
    return code, capsys.readouterr().out


def test_main_reports_safe_26_checkpoint_success(monkeypatch, capsys) -> None:
    code, output = output_for(monkeypatch, capsys, smoke_result())

    assert code == 0
    assert "checkpoint_01 Login completed: pass" in output
    assert "checkpoint_26 Final application health confirmed: pass" in output
    assert "documents_download: present" in output
    assert "document_state: populated" in output
    assert "attachment_state: populated" in output
    assert "write_request_issued: no" in output
    assert "audited_endpoint_invoked: no" in output
    assert "browser_context_closed: yes" in output


def test_empty_lists_are_safe_classifications(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(
            document_state="empty",
            attachment_state="empty",
            document_metadata="not-checked-safely",
            attachment_metadata="not-checked-safely",
            download_controls="not-checked-safely",
        ),
    )

    assert code == 0
    assert "document_state: empty" in output
    assert "document_metadata: not-checked-safely" in output
    assert "attachment_metadata: not-checked-safely" in output


def test_read_only_controls_are_a_valid_classification(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(
            documents_upload="missing",
            documents_delete="missing",
            upload_controls="read-only",
            delete_controls="read-only",
        ),
    )

    assert code == 0
    assert "documents_upload: missing" in output
    assert "upload_controls: read-only" in output
    assert "delete_controls: read-only" in output


def test_missing_download_capability_fails_safely(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(failed_checkpoint=4, documents_download="missing"),
    )

    assert code == 1
    assert "checkpoint_05 documents.download classified: fail" in output
    assert "documents_download: missing" in output


def test_api_browser_write_and_audited_endpoint_failures_are_critical(
    monkeypatch,
    capsys,
) -> None:
    scenarios = (
        (21, {"unexpected_api": True}, "unexpected_api_failure: yes"),
        (22, {"unexpected_browser": True}, "unexpected_browser_failure: yes"),
        (23, {"write_request": True}, "write_request_issued: yes"),
        (24, {"audited_endpoint": True}, "audited_endpoint_invoked: yes"),
    )
    for checkpoint, options, marker in scenarios:
        code, output = output_for(
            monkeypatch,
            capsys,
            smoke_result(failed_checkpoint=checkpoint, **options),
        )
        assert code == 1
        assert marker in output


def test_context_cleanup_failure_is_critical(monkeypatch, capsys) -> None:
    code, output = output_for(
        monkeypatch,
        capsys,
        smoke_result(failed_checkpoint=22, context_closed=False),
    )

    assert code == 1
    assert "browser_context_closed: no" in output


def test_output_drops_all_untrusted_private_values(monkeypatch, capsys) -> None:
    code, output = output_for(monkeypatch, capsys, smoke_result())

    assert code == 0
    for private_value in PRIVATE_VALUES:
        assert private_value not in output


def test_malformed_payload_fails_without_echoing_it(monkeypatch, capsys) -> None:
    malformed = {"checkpoints": PRIVATE_VALUES, "filename": PRIVATE_VALUES[2]}
    code, output = output_for(monkeypatch, capsys, malformed)

    assert code == 1
    assert "checkpoint_01 Login completed: fail" in output
    for private_value in PRIVATE_VALUES:
        assert private_value not in output


def test_browser_writes_and_audited_reads_are_blocked_before_network() -> None:
    route = SMOKE.NODE_SMOKE.index('page.route("**/*"')
    method_check = SMOKE.NODE_SMOKE.index(
        "if (writeMethods.has(request.method()))",
        route,
    )
    write_abort = SMOKE.NODE_SMOKE.index('route.abort("blockedbyclient")', method_check)
    audited_check = SMOKE.NODE_SMOKE.index("if (isAuditedDocumentEndpoint", write_abort)
    audited_abort = SMOKE.NODE_SMOKE.index('route.abort("blockedbyclient")', audited_check)
    continuation = SMOKE.NODE_SMOKE.index("route.continue()", audited_abort)

    assert route < method_check < write_abort < audited_check < audited_abort < continuation
    assert 'new Set(["POST", "PUT", "PATCH", "DELETE"])' in SMOKE.NODE_SMOKE
    assert "/(download|preview)$" in SMOKE.NODE_SMOKE


def test_only_login_is_exempt_from_direct_write_block() -> None:
    assert 'path !== "/api/auth/login"' in SMOKE.NODE_SMOKE
    assert "if (writeMethods.has(method)" in SMOKE.NODE_SMOKE


def test_normalised_output_contains_fixed_classifications_only() -> None:
    normalised = SMOKE._normalise_result(smoke_result())

    assert set(normalised) == {
        "checkpoints",
        "documents_download",
        "documents_upload",
        "documents_delete",
        "document_state",
        "attachment_state",
        "document_metadata",
        "attachment_metadata",
        "download_controls",
        "upload_controls",
        "delete_controls",
        "lifecycle_state",
        "unexpected_api",
        "unexpected_browser",
        "write_request",
        "audited_endpoint",
        "context_closed",
    }


def test_local_candidate_mode_uses_frontend_node_without_compose(monkeypatch) -> None:
    expected = smoke_result()
    calls: list[tuple[list[str], object]] = []

    class Completed:
        stdout = __import__("json").dumps(expected)

    def fake_run(command, **kwargs):
        calls.append((command, kwargs.get("cwd")))
        return Completed()

    monkeypatch.setenv("DOCUMENTS_SMOKE_LOCAL", "1")
    monkeypatch.setenv("SMOKE_ADMIN_EMAIL", "synthetic@example.invalid")
    monkeypatch.setenv("SMOKE_ADMIN_PASSWORD", "synthetic-password")
    monkeypatch.setattr(SMOKE.subprocess, "run", fake_run)

    result = SMOKE.run_smoke()

    assert result["checkpoints"] == [True] * 26
    assert calls[0][0][:2] == ["node", "-e"]
    assert calls[0][1].name == "frontend"
