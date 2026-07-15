from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "verify_appointment_nowrite.py"
SPEC = importlib.util.spec_from_file_location("verify_appointment_nowrite", SCRIPT_PATH)
assert SPEC and SPEC.loader
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


def smoke_result(*, failed_checkpoint: int | None = None) -> dict[str, object]:
    checkpoints = [True] * len(SMOKE.CHECKPOINTS)
    if failed_checkpoint is not None:
        checkpoints[failed_checkpoint] = False
    return {
        "checkpoints": checkpoints,
        "unexpected_api": False,
        "unexpected_browser": False,
        "write_request": False,
    }


def test_main_reports_checkpoint_only_success(monkeypatch, capsys) -> None:
    monkeypatch.setattr(SMOKE, "run_smoke", lambda: smoke_result())

    assert SMOKE.main() == 0

    output = capsys.readouterr().out
    assert "checkpoint_01 Login completed: pass" in output
    assert "checkpoint_18 No write request issued: pass" in output
    assert "unexpected_api_failure: no" in output
    assert "unexpected_browser_failure: no" in output
    assert "write_request_issued: no" in output


def test_main_fails_when_context_menu_is_not_opened(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        SMOKE,
        "run_smoke",
        lambda: smoke_result(failed_checkpoint=10),
    )

    assert SMOKE.main() == 1
    assert "checkpoint_11 Appointment context menu opened: fail" in capsys.readouterr().out
