#!/usr/bin/env python3
"""Run the production notes smoke without writes or sensitive output."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


CHECKPOINTS = (
    "Login completed",
    "Authenticated session confirmed",
    "/me completed",
    "/me/capabilities completed",
    "notes.view classified",
    "notes.write classified",
    "Global Notes page requested",
    "Global Notes page rendered",
    "Notes-list API completed",
    "Notes table or empty state rendered",
    "Suitable active note selected internally when available",
    "Note detail rendered when available",
    "Patient navigation control classified",
    "Audit control classified",
    "Capability-aware mutation controls classified",
    "Archived/read-only state classified",
    "Patient notes endpoint completed",
    "Appointment notes state classified where safely available",
    "No unexpected API 4xx/5xx",
    "No browser error",
    "No POST, PUT, PATCH or DELETE request issued",
    "Final application health confirmed",
)


NODE_SMOKE = r"""
const { chromium } = require("@playwright/test");

const checkpoints = Array(22).fill(false);
const writeMethods = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let browser;
let unexpectedApi = false;
let unexpectedBrowser = false;
let writeRequest = false;
let notesViewState = "unknown";
let notesWriteState = "unknown";
let noteDetailState = "unknown";
let appointmentNoteState = "unknown";
let patientNavigationState = "unknown";
let auditControlState = "unknown";
let mutationControlState = "unknown";
let archiveState = "unknown";
let patientEndpointState = "unknown";

async function checkedFetch(base, path, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  if (writeMethods.has(method) && path !== "/api/auth/login") {
    writeRequest = true;
    throw new Error("write request blocked");
  }
  let response;
  try {
    response = await fetch(base + path, options);
  } catch (error) {
    if (path.startsWith("/api/")) unexpectedApi = true;
    throw error;
  }
  if (!response.ok) {
    if (path.startsWith("/api/")) unexpectedApi = true;
    throw new Error("request failed");
  }
  return response;
}

async function frontendReady(base) {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      const response = await fetch(base + "/api/health");
      if (response.ok) return true;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

(async () => {
  const base = process.env.SMOKE_FRONTEND_BASE_URL || "http://localhost:3000";
  if (!(await frontendReady(base))) throw new Error("frontend not ready");

  const loginResponse = await checkedFetch(base, "/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: process.env.SMOKE_ADMIN_EMAIL,
      password: process.env.SMOKE_ADMIN_PASSWORD,
    }),
  });
  const login = await loginResponse.json();
  checkpoints[0] = Boolean(login.access_token) && !login.must_change_password;
  checkpoints[1] = Boolean(login.access_token);
  if (!checkpoints[0] || !checkpoints[1]) throw new Error("login incomplete");

  const token = login.access_token;
  const headers = { Authorization: "Bearer " + token };
  const me = await (await checkedFetch(base, "/api/me", { headers })).json();
  checkpoints[2] = Boolean(me && me.id && me.is_active !== false);
  if (!checkpoints[2]) throw new Error("session unavailable");

  const capabilities = await (
    await checkedFetch(base, "/api/me/capabilities", { headers })
  ).json();
  checkpoints[3] = Array.isArray(capabilities);
  if (!checkpoints[3]) throw new Error("capabilities unavailable");
  const canViewNotes = capabilities.includes("notes.view");
  const canWriteNotes = capabilities.includes("notes.write");
  const canViewPatients = capabilities.includes("patients.view");
  notesViewState = canViewNotes ? "present" : "missing";
  notesWriteState = canWriteNotes ? "present" : "missing";
  checkpoints[4] = canViewNotes;
  checkpoints[5] = notesWriteState !== "unknown";
  if (!canViewNotes) throw new Error("notes view unavailable");

  const directNotes = await (
    await checkedFetch(base, "/api/notes?limit=200", { headers })
  ).json();
  if (!Array.isArray(directNotes)) throw new Error("notes list unavailable");
  const activeNote = directNotes.find(
    (item) => item && Number.isInteger(item.id) && item.id > 0 &&
      Number.isInteger(item.patient_id) && item.patient_id > 0 && !item.deleted_at
  );

  if (activeNote) {
    await checkedFetch(base, "/api/patients/" + activeNote.patient_id + "/notes", {
      headers,
    });
    patientEndpointState = "checked";
    checkpoints[16] = true;
  } else if (canViewPatients) {
    const patients = await (
      await checkedFetch(base, "/api/patients?limit=200", { headers })
    ).json();
    const patient = Array.isArray(patients)
      ? patients.find(
          (item) => item && Number.isInteger(item.id) && item.id > 0 && !item.deleted_at
        )
      : null;
    if (patient) {
      await checkedFetch(base, "/api/patients/" + patient.id + "/notes", { headers });
      patientEndpointState = "checked";
    } else {
      patientEndpointState = "not-checked-safely";
    }
    checkpoints[16] = true;
  } else {
    patientEndpointState = "not-checked-safely";
    checkpoints[16] = true;
  }

  if (activeNote && Number.isInteger(activeNote.appointment_id)) {
    await checkedFetch(
      base,
      "/api/appointments/" + activeNote.appointment_id + "/notes",
      { headers }
    );
    appointmentNoteState = "checked";
  } else {
    appointmentNoteState = "not-checked-safely";
  }
  checkpoints[17] = true;

  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.on("pageerror", () => {
    unexpectedBrowser = true;
  });
  page.on("console", (message) => {
    const text = message.text();
    const benignExtraAttributes =
      message.type() === "error" &&
      text.startsWith("Warning: Extra attributes from the server");
    if (message.type() === "error" && !benignExtraAttributes) {
      unexpectedBrowser = true;
    }
  });
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 400) {
      unexpectedApi = true;
    }
  });
  page.on("requestfailed", (request) => {
    const failure = request.failure();
    const blockedWrite =
      writeMethods.has(request.method()) &&
      Boolean(failure && failure.errorText && failure.errorText.includes("BLOCKED_BY_CLIENT"));
    const navigationAbort = Boolean(
      failure && failure.errorText && failure.errorText.includes("ERR_ABORTED")
    );
    if (request.url().includes("/api/") && !blockedWrite && !navigationAbort) {
      unexpectedBrowser = true;
    }
  });
  await page.route("**/*", async (route) => {
    if (writeMethods.has(route.request().method())) {
      writeRequest = true;
      await route.abort("blockedbyclient");
      return;
    }
    await route.continue();
  });
  await page.addInitScript((tokenValue) => {
    localStorage.setItem("dental_pms_token", tokenValue);
    document.cookie =
      "dental_pms_token=" + encodeURIComponent(tokenValue) + "; Path=/; SameSite=Lax";
  }, token);

  const listResponsePromise = page.waitForResponse(
    (response) => {
      const url = new URL(response.url());
      return response.request().method() === "GET" && url.pathname === "/api/notes";
    },
    { timeout: 20_000 }
  );
  const navigation = await page.goto(base + "/notes", { waitUntil: "domcontentloaded" });
  checkpoints[6] = Boolean(navigation && navigation.status() < 400);
  const worklist = page.getByTestId("notes-worklist");
  await worklist.waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[7] = true;
  const listResponse = await listResponsePromise;
  checkpoints[8] = listResponse.ok();
  const emptyState = page.getByTestId("notes-empty-state");
  const detail = page.getByTestId("note-detail");
  await Promise.race([
    emptyState.waitFor({ state: "visible", timeout: 20_000 }),
    detail.waitFor({ state: "visible", timeout: 20_000 }),
  ]);
  checkpoints[9] = (await emptyState.count()) > 0 || (await detail.count()) > 0;

  const detailAvailable = (await detail.count()) > 0;
  noteDetailState = detailAvailable ? "checked" : "not-checked-safely";
  checkpoints[10] = true;
  checkpoints[11] = true;

  if (detailAvailable) {
    const patientLink = worklist.locator('a[href^="/patients/"]').first();
    patientNavigationState = (await patientLink.count()) > 0 ? "available" : "unavailable";
    const auditLink = page.getByTestId("note-detail-audit");
    auditControlState = (await auditLink.count()) > 0 ? "available" : "missing";
    checkpoints[12] = patientNavigationState !== "unknown";
    checkpoints[13] = auditControlState === "available";

    const capabilityMode = await page
      .getByTestId("notes-capability-state")
      .getAttribute("data-state");
    const editBody = page.getByTestId("note-detail-body");
    const archiveButton = page.getByTestId("note-detail-archive");
    const readOnlyDetail = page.getByTestId("note-detail-readonly");
    if (canWriteNotes) {
      const activeWritable =
        (await editBody.count()) > 0 && (await archiveButton.count()) > 0;
      const archivedWritable =
        (await editBody.count()) === 0 &&
        (await readOnlyDetail.count()) > 0 &&
        (await archiveButton.count()) > 0;
      checkpoints[14] = capabilityMode === "write" && (activeWritable || archivedWritable);
      archiveState = archivedWritable ? "archived-read-only" : "active-write";
      mutationControlState = checkpoints[14] ? "write" : "unknown";
    } else {
      checkpoints[14] =
        capabilityMode === "read-only" &&
        (await readOnlyDetail.count()) > 0 &&
        (await editBody.count()) === 0 &&
        (await archiveButton.count()) === 0;
      archiveState = "read-only";
      mutationControlState = checkpoints[14] ? "read-only" : "unknown";
    }
    checkpoints[15] = archiveState !== "unknown";
  } else {
    patientNavigationState = "not-checked-safely";
    auditControlState = "not-checked-safely";
    mutationControlState = canWriteNotes ? "write" : "read-only";
    archiveState = "not-checked-safely";
    checkpoints[12] = true;
    checkpoints[13] = true;
    checkpoints[14] = true;
    checkpoints[15] = true;
  }
})()
  .catch(() => {})
  .finally(async () => {
    const base = process.env.SMOKE_FRONTEND_BASE_URL || "http://localhost:3000";
    try {
      const health = await checkedFetch(base, "/api/health");
      checkpoints[21] = health.ok;
    } catch {}
    checkpoints[18] = !unexpectedApi;
    checkpoints[19] = !unexpectedBrowser;
    checkpoints[20] = !writeRequest;
    if (browser) await browser.close().catch(() => {});
    process.stdout.write(
      JSON.stringify({
        checkpoints,
        notes_view: notesViewState,
        notes_write: notesWriteState,
        note_detail: noteDetailState,
        appointment_note: appointmentNoteState,
        patient_navigation: patientNavigationState,
        audit_control: auditControlState,
        mutation_controls: mutationControlState,
        archive_state: archiveState,
        patient_endpoint: patientEndpointState,
        unexpected_api: unexpectedApi,
        unexpected_browser: unexpectedBrowser,
        write_request: writeRequest,
      }) + "\n"
    );
    process.exit(checkpoints.every(Boolean) ? 0 : 1);
  });
"""


def _container_environment(name: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "backend",
            "sh",
            "-lc",
            f'printf %s "${{{name}}}"',
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else ""


def _empty_result() -> dict[str, Any]:
    return {
        "checkpoints": [False] * len(CHECKPOINTS),
        "notes_view": "unknown",
        "notes_write": "unknown",
        "note_detail": "unknown",
        "appointment_note": "unknown",
        "patient_navigation": "unknown",
        "audit_control": "unknown",
        "mutation_controls": "unknown",
        "archive_state": "unknown",
        "patient_endpoint": "unknown",
        "unexpected_api": True,
        "unexpected_browser": True,
        "write_request": False,
    }


def _choice(payload: dict[str, Any], key: str, allowed: set[str]) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) and value in allowed else "unknown"


def _normalise_result(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _empty_result()
    checkpoints = payload.get("checkpoints")
    if not isinstance(checkpoints, list) or len(checkpoints) != len(CHECKPOINTS):
        return _empty_result()
    return {
        "checkpoints": [value is True for value in checkpoints],
        "notes_view": _choice(payload, "notes_view", {"present", "missing", "unknown"}),
        "notes_write": _choice(payload, "notes_write", {"present", "missing", "unknown"}),
        "note_detail": _choice(
            payload, "note_detail", {"checked", "not-checked-safely", "unknown"}
        ),
        "appointment_note": _choice(
            payload, "appointment_note", {"checked", "not-checked-safely", "unknown"}
        ),
        "patient_navigation": _choice(
            payload,
            "patient_navigation",
            {"available", "unavailable", "not-checked-safely", "unknown"},
        ),
        "audit_control": _choice(
            payload,
            "audit_control",
            {"available", "not-checked-safely", "missing", "unknown"},
        ),
        "mutation_controls": _choice(
            payload, "mutation_controls", {"write", "read-only", "unknown"}
        ),
        "archive_state": _choice(
            payload,
            "archive_state",
            {"active-write", "archived-read-only", "read-only", "not-checked-safely", "unknown"},
        ),
        "patient_endpoint": _choice(
            payload, "patient_endpoint", {"checked", "not-checked-safely", "unknown"}
        ),
        "unexpected_api": payload.get("unexpected_api") is not False,
        "unexpected_browser": payload.get("unexpected_browser") is not False,
        "write_request": payload.get("write_request") is True,
    }


def run_smoke() -> dict[str, Any]:
    local_mode = os.environ.get("NOTES_SMOKE_LOCAL") == "1"
    email = (
        os.environ.get("SMOKE_ADMIN_EMAIL", "")
        if local_mode
        else _container_environment("ADMIN_EMAIL")
    )
    password = (
        os.environ.get("SMOKE_ADMIN_PASSWORD", "")
        if local_mode
        else _container_environment("ADMIN_PASSWORD")
    )
    if not email or not password:
        return _empty_result()

    environment = os.environ.copy()
    environment["SMOKE_ADMIN_EMAIL"] = email
    environment["SMOKE_ADMIN_PASSWORD"] = password
    command = (
        ["node", "-e", NODE_SMOKE]
        if local_mode
        else [
            "docker",
            "compose",
            "exec",
            "-T",
            "-e",
            "SMOKE_ADMIN_EMAIL",
            "-e",
            "SMOKE_ADMIN_PASSWORD",
            "frontend",
            "node",
            "-e",
            NODE_SMOKE,
        ]
    )
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        cwd=(Path(__file__).resolve().parents[1] / "frontend") if local_mode else None,
    )
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return _empty_result()
    return _normalise_result(payload)


def main() -> int:
    result = _normalise_result(run_smoke())
    values = result["checkpoints"]
    for index, (label, passed) in enumerate(zip(CHECKPOINTS, values), start=1):
        print(f"checkpoint_{index:02d} {label}: {'pass' if passed else 'fail'}")
    print("notes_view: " + result["notes_view"])
    print("notes_write: " + result["notes_write"])
    print("note_detail_smoke: " + result["note_detail"])
    print("appointment_note_smoke: " + result["appointment_note"])
    print("patient_navigation: " + result["patient_navigation"])
    print("audit_control: " + result["audit_control"])
    print("mutation_controls: " + result["mutation_controls"])
    print("archive_state: " + result["archive_state"])
    print("patient_notes_endpoint: " + result["patient_endpoint"])
    print("unexpected_api_failure: " + ("yes" if result["unexpected_api"] else "no"))
    print(
        "unexpected_browser_failure: "
        + ("yes" if result["unexpected_browser"] else "no")
    )
    print("write_request_issued: " + ("yes" if result["write_request"] else "no"))
    passed = (
        all(values)
        and result["notes_view"] == "present"
        and result["notes_write"] in {"present", "missing"}
        and result["note_detail"] in {"checked", "not-checked-safely"}
        and result["appointment_note"] in {"checked", "not-checked-safely"}
        and result["audit_control"] in {"available", "not-checked-safely"}
        and result["mutation_controls"] in {"write", "read-only"}
        and result["archive_state"] != "unknown"
        and result["patient_endpoint"] in {"checked", "not-checked-safely"}
        and not result["unexpected_api"]
        and not result["unexpected_browser"]
        and not result["write_request"]
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
