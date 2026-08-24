#!/usr/bin/env python3
"""Run the production clinical smoke without writes or patient-data output."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


CHECKPOINTS = (
    "Login completed",
    "/me completed",
    "/me/capabilities completed",
    "clinical.view classified",
    "Suitable active patient selected internally",
    "Clinical page rendered",
    "Odontogram rendered",
    "Upper and lower arches rendered",
    "Tooth selected",
    "Tooth surfaces rendered",
    "Tooth history API completed",
    "Tooth history panel rendered",
    "Treatment-plan API completed",
    "Treatment-plan section rendered",
    "Planned/completed visual state classified",
    "BPE state rendered",
    "Capability-aware write controls classified",
    "No unexpected API error",
    "No browser error",
    "No POST, PUT, PATCH or DELETE request",
    "Final application health",
)


NODE_SMOKE = r"""
const { chromium } = require("@playwright/test");

const checkpoints = Array(21).fill(false);
const writeMethods = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let browser;
let page;
let unexpectedApi = false;
let unexpectedBrowser = false;
let writeRequest = false;
let patientSelection = "unknown";
let clinicalViewState = "unknown";
let clinicalControlState = "unknown";
let visualState = "unknown";
let toothHistoryApiCompleted = false;
let treatmentPlanApiCompleted = false;

function isExpectedOptionalClinicalResponse(urlValue, status) {
  if (status !== 403 && status !== 404) return false;
  try {
    const path = new URL(urlValue).pathname;
    return /^\/api\/patients\/\d+\/charting\/(treatment-plan-items|tooth-state)$/.test(
      path
    );
  } catch {
    return false;
  }
}

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

async function waitUntil(predicate, timeout = 20_000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (await predicate()) return true;
    await new Promise((resolve) => setTimeout(resolve, 100));
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
  if (!checkpoints[0]) throw new Error("login incomplete");

  const token = login.access_token;
  const headers = { Authorization: "Bearer " + token };
  const me = await (await checkedFetch(base, "/api/me", { headers })).json();
  checkpoints[1] = Boolean(me && me.id && me.is_active !== false);
  if (!checkpoints[1]) throw new Error("session unavailable");

  const capabilities = await (
    await checkedFetch(base, "/api/me/capabilities", { headers })
  ).json();
  checkpoints[2] = Array.isArray(capabilities);
  if (!checkpoints[2]) throw new Error("capabilities unavailable");
  const canViewClinical = capabilities.includes("clinical.view");
  const canWriteClinical = capabilities.includes("clinical.write");
  clinicalViewState = canViewClinical ? "present" : "missing";
  checkpoints[3] = canViewClinical;
  if (!checkpoints[3]) throw new Error("clinical view unavailable");
  const expectedControlState = canWriteClinical ? "write" : "read-only";

  const patients = await (
    await checkedFetch(base, "/api/patients?limit=200", { headers })
  ).json();
  const patient = Array.isArray(patients)
    ? patients.find(
        (item) => item && Number.isInteger(item.id) && item.id > 0 && !item.deleted_at
      )
    : null;
  checkpoints[4] = Boolean(patient);
  patientSelection = patient ? "active" : "none";
  if (!patient) throw new Error("no suitable active patient");

  browser = await chromium.launch({ headless: true });
  page = await browser.newPage();
  page.on("pageerror", () => {
    unexpectedBrowser = true;
  });
  page.on("console", (message) => {
    const text = message.text();
    const locationUrl = message.location().url;
    const benignExtraAttributes =
      message.type() === "error" &&
      text.startsWith("Warning: Extra attributes from the server");
    const expectedOptionalResourceFailure =
      message.type() === "error" &&
      text.startsWith("Failed to load resource") &&
      isExpectedOptionalClinicalResponse(locationUrl, 404);
    if (
      message.type() === "error" &&
      !benignExtraAttributes &&
      !expectedOptionalResourceFailure
    ) {
      unexpectedBrowser = true;
    }
  });
  page.on("response", (response) => {
    if (
      response.url().includes("/api/") &&
      response.status() >= 400 &&
      !isExpectedOptionalClinicalResponse(response.url(), response.status())
    ) {
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
    if (
      request.url().includes("/api/") &&
      !blockedWrite &&
      !navigationAbort
    ) {
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
      "dental_pms_token=" +
      encodeURIComponent(tokenValue) +
      "; Path=/; SameSite=Lax";
  }, token);

  const summaryResponsePromise = page.waitForResponse(
    (response) => {
      const url = new URL(response.url());
      return (
        response.request().method() === "GET" &&
        /^\/api\/patients\/\d+\/clinical\/summary$/.test(url.pathname)
      );
    },
    { timeout: 20_000 }
  );
  const toothHistoryResponsePromise = page.waitForResponse(
    (response) => {
      const url = new URL(response.url());
      return (
        response.request().method() === "GET" &&
        /^\/api\/patients\/\d+\/tooth-history$/.test(url.pathname)
      );
    },
    { timeout: 20_000 }
  );
  const navigation = await page.goto(base + "/patients/" + patient.id + "/clinical", {
    waitUntil: "domcontentloaded",
  });
  const clinicalSection = page.getByTestId("patient-clinical-section");
  await clinicalSection.waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[5] = Boolean(navigation && navigation.status() < 400);

  const chart = page.getByTestId("clinical-chart");
  await chart.waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[6] = true;
  const upperArch = page.getByTestId("clinical-upper-arch");
  const lowerArch = page.getByTestId("clinical-lower-arch");
  await upperArch.waitFor({ state: "visible", timeout: 20_000 });
  await lowerArch.waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[7] = true;

  const firstTooth = page.locator('[data-testid^="tooth-button-"]').first();
  await firstTooth.waitFor({ state: "visible", timeout: 20_000 });
  if ((await firstTooth.getAttribute("data-selected")) !== "true") {
    await firstTooth.click();
  }
  checkpoints[8] = await waitUntil(
    async () => (await firstTooth.getAttribute("data-selected")) === "true"
  );
  checkpoints[9] = (await firstTooth.locator('[data-testid^="tooth-surface-"]').count()) >= 5;

  const summaryResponse = await summaryResponsePromise;
  treatmentPlanApiCompleted = summaryResponse.ok();
  checkpoints[12] = treatmentPlanApiCompleted;
  const toothHistoryResponse = await toothHistoryResponsePromise;
  toothHistoryApiCompleted = toothHistoryResponse.ok();
  checkpoints[10] = toothHistoryApiCompleted;
  await page
    .getByTestId("patient-tooth-history")
    .waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[11] = true;

  const chartContent = page.getByTestId("clinical-chart-content");
  const plannedState = await chartContent.getAttribute("data-planned-state");
  const completedState = await chartContent.getAttribute("data-completed-state");
  const stateValues = new Set(["present", "absent"]);
  checkpoints[14] = stateValues.has(plannedState) && stateValues.has(completedState);
  visualState = checkpoints[14]
    ? "planned-" + plannedState + "/completed-" + completedState
    : "unknown";

  await page
    .getByTestId("patient-bpe-panel")
    .waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[15] = true;
  const bpeInput = page.locator('[data-testid^="patient-bpe-score-"]').first();
  const bpeInputDisabled = await bpeInput.isDisabled();

  await page.getByRole("button", { name: /^Treatment plan/ }).click();
  await page
    .getByTestId("patient-treatment-plan-section")
    .waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[13] = true;
  const addPlanButton = page.getByTestId("patient-treatment-plan-open");
  const addPlanDisabled = await addPlanButton.isDisabled();
  const modeConverged = await waitUntil(
    async () =>
      (await clinicalSection.getAttribute("data-clinical-mode")) === expectedControlState
  );
  clinicalControlState = modeConverged ? expectedControlState : "unknown";
  checkpoints[16] =
    modeConverged &&
    (canWriteClinical
      ? !bpeInputDisabled && !addPlanDisabled
      : bpeInputDisabled && addPlanDisabled);
})()
  .catch(() => {})
  .finally(async () => {
    const base = process.env.SMOKE_FRONTEND_BASE_URL || "http://localhost:3000";
    try {
      const health = await checkedFetch(base, "/api/health");
      checkpoints[20] = health.ok;
    } catch {}
    checkpoints[17] = !unexpectedApi;
    checkpoints[18] = !unexpectedBrowser;
    checkpoints[19] = !writeRequest;
    if (browser) await browser.close().catch(() => {});
    process.stdout.write(
      JSON.stringify({
        checkpoints,
        patient_selection: patientSelection,
        clinical_view: clinicalViewState,
        clinical_controls: clinicalControlState,
        visual_state: visualState,
        tooth_history_api_completed: toothHistoryApiCompleted,
        treatment_plan_api_completed: treatmentPlanApiCompleted,
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
        "patient_selection": "unknown",
        "clinical_view": "unknown",
        "clinical_controls": "unknown",
        "visual_state": "unknown",
        "tooth_history_api_completed": False,
        "treatment_plan_api_completed": False,
        "unexpected_api": True,
        "unexpected_browser": True,
        "write_request": False,
    }


def _normalise_result(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _empty_result()
    checkpoints = payload.get("checkpoints")
    if not isinstance(checkpoints, list) or len(checkpoints) != len(CHECKPOINTS):
        return _empty_result()
    return {
        "checkpoints": [value is True for value in checkpoints],
        "patient_selection": (
            payload.get("patient_selection")
            if payload.get("patient_selection") in {"active", "none", "unknown"}
            else "unknown"
        ),
        "clinical_view": (
            payload.get("clinical_view")
            if payload.get("clinical_view") in {"present", "missing", "unknown"}
            else "unknown"
        ),
        "clinical_controls": (
            payload.get("clinical_controls")
            if payload.get("clinical_controls") in {"write", "read-only", "unknown"}
            else "unknown"
        ),
        "visual_state": (
            payload.get("visual_state")
            if payload.get("visual_state")
            in {
                "planned-present/completed-present",
                "planned-present/completed-absent",
                "planned-absent/completed-present",
                "planned-absent/completed-absent",
                "unknown",
            }
            else "unknown"
        ),
        "tooth_history_api_completed": payload.get("tooth_history_api_completed") is True,
        "treatment_plan_api_completed": payload.get("treatment_plan_api_completed") is True,
        "unexpected_api": payload.get("unexpected_api") is not False,
        "unexpected_browser": payload.get("unexpected_browser") is not False,
        "write_request": payload.get("write_request") is True,
    }


def run_smoke() -> dict[str, Any]:
    local_mode = os.environ.get("CLINICAL_SMOKE_LOCAL") == "1"
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
        cwd=(Path(__file__).resolve().parents[1] / "frontend")
        if local_mode
        else None,
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
    print(
        "active_patient_selected: "
        + ("yes" if result["patient_selection"] == "active" else "no")
    )
    print("clinical_view: " + result["clinical_view"])
    print("clinical_controls: " + result["clinical_controls"])
    print("visual_state: " + result["visual_state"])
    print(
        "tooth_history_api_completed: "
        + ("yes" if result["tooth_history_api_completed"] else "no")
    )
    print(
        "treatment_plan_api_completed: "
        + ("yes" if result["treatment_plan_api_completed"] else "no")
    )
    print(
        "unexpected_api_failure: " + ("yes" if result["unexpected_api"] else "no")
    )
    print(
        "unexpected_browser_failure: "
        + ("yes" if result["unexpected_browser"] else "no")
    )
    print("write_request_issued: " + ("yes" if result["write_request"] else "no"))
    passed = (
        all(values)
        and result["patient_selection"] == "active"
        and result["clinical_view"] == "present"
        and result["clinical_controls"] in {"write", "read-only"}
        and result["visual_state"] != "unknown"
        and result["tooth_history_api_completed"]
        and result["treatment_plan_api_completed"]
        and not result["unexpected_api"]
        and not result["unexpected_browser"]
        and not result["write_request"]
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
