#!/usr/bin/env python3
"""Run the production patient-record smoke without printing patient data."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any


CHECKPOINTS = (
    "Login completed",
    "Authenticated session confirmed",
    "/me completed",
    "/me/capabilities completed",
    "Patient-list API completed",
    "Suitable active patient selected internally",
    "Patient-list page rendered",
    "Matching patient navigation control found",
    "Patient detail opened",
    "Patient detail page rendered",
    "Patient data request completed",
    "Patient tabs rendered",
    "Audit/history control found",
    "Audit/history loaded",
    "Capability-aware controls rendered consistently",
    "Archived/read-only state classified",
    "No unexpected API 4xx/5xx",
    "No unexpected browser error",
    "No POST, PUT, PATCH or DELETE request issued",
    "Final application health confirmed",
)


NODE_SMOKE = r"""
const { chromium } = require("@playwright/test");

const checkpoints = Array(20).fill(false);
const writeMethods = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let browser;
let page;
let unexpectedApi = false;
let unexpectedBrowser = false;
let writeRequest = false;
let patientSelection = "unknown";

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
  const base = "http://localhost:3000";
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
  checkpoints[1] = true;

  const me = await (await checkedFetch(base, "/api/me", { headers })).json();
  checkpoints[2] = Boolean(me && me.id && me.is_active !== false);
  if (!checkpoints[2]) throw new Error("session unavailable");

  const capabilities = await (
    await checkedFetch(base, "/api/me/capabilities", { headers })
  ).json();
  checkpoints[3] = Array.isArray(capabilities);
  if (!checkpoints[3]) throw new Error("capabilities unavailable");

  const patients = await (
    await checkedFetch(base, "/api/patients?limit=200", { headers })
  ).json();
  checkpoints[4] = Array.isArray(patients);
  if (!checkpoints[4]) throw new Error("patient list unavailable");

  const patient = patients.find(
    (item) => item && Number.isInteger(item.id) && item.id > 0 && !item.deleted_at
  );
  checkpoints[5] = Boolean(patient);
  patientSelection = patient ? "active" : "none";
  if (!patient) throw new Error("no suitable active patient");

  browser = await chromium.launch({ headless: true });
  page = await browser.newPage();
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
    const navigationAbort = Boolean(
      failure && failure.errorText && failure.errorText.includes("ERR_ABORTED")
    );
    if (
      request.url().includes("/api/") &&
      !writeMethods.has(request.method()) &&
      !navigationAbort
    ) {
      unexpectedBrowser = true;
    }
  });
  await page.route("**/api/**", async (route) => {
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

  const listNavigation = await page.goto(base + "/patients", {
    waitUntil: "domcontentloaded",
  });
  await page
    .getByRole("heading", { name: "Patients", exact: true })
    .waitFor({ state: "visible", timeout: 20_000 });
  const firstRow = page.locator("tbody tr").first();
  await firstRow.waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[6] = Boolean(listNavigation && listNavigation.status() < 400);
  const createVisible = await page
    .getByRole("link", { name: "New patient", exact: true })
    .isVisible()
    .catch(() => false);

  const patientLink = firstRow.getByRole("link").first();
  await patientLink.waitFor({ state: "visible", timeout: 10_000 });
  const href = await patientLink.getAttribute("href");
  let matchingNavigation = false;
  try {
    matchingNavigation =
      Boolean(href) && new URL(href, base).pathname === "/patients/" + patient.id;
  } catch {}
  checkpoints[7] = matchingNavigation;
  if (!matchingNavigation) throw new Error("patient list mismatch");

  const patientResponsePromise = page.waitForResponse(
    (response) => {
      const url = new URL(response.url());
      return (
        response.request().method() === "GET" &&
        /^\/api\/patients\/\d+$/.test(url.pathname)
      );
    },
    { timeout: 20_000 }
  );
  await patientLink.click();
  const patientResponse = await patientResponsePromise;
  const patientPayload = patientResponse.ok() ? await patientResponse.json() : null;
  checkpoints[8] =
    new URL(page.url()).pathname === "/patients/" + patient.id;

  await page
    .getByTestId("patient-route-shell")
    .waitFor({ state: "visible", timeout: 20_000 });
  await page
    .getByTestId("patient-header-card")
    .waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[9] = true;
  checkpoints[10] =
    patientResponse.ok() && patientPayload && patientPayload.id === patient.id;

  const tabs = page.getByTestId("patient-tabs");
  const personalTab = page.getByTestId("patient-tab-Personal");
  await tabs.waitFor({ state: "visible", timeout: 20_000 });
  await personalTab.waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[11] = true;

  const auditControl = page.getByRole("link", { name: "Audit", exact: true }).first();
  await auditControl.waitFor({ state: "visible", timeout: 10_000 });
  checkpoints[12] = true;

  const canWrite = capabilities.includes("patients.write");
  try {
    await personalTab.click();
    await page
      .getByText("Patient details", { exact: true })
      .click();
    const fields = page.getByTestId("patient-details-fields");
    await fields.waitFor({ state: "visible", timeout: 10_000 });
    const fieldsDisabled = (await fields.getAttribute("disabled")) !== null;
    const saveVisible = await page
      .getByTestId("patient-save-changes")
      .isVisible()
      .catch(() => false);
    const archiveVisible = await page
      .getByTestId("patient-archive-toggle")
      .isVisible()
      .catch(() => false);
    checkpoints[14] = canWrite
      ? createVisible && saveVisible && archiveVisible && !fieldsDisabled
      : !createVisible && !saveVisible && !archiveVisible && fieldsDisabled;
  } catch {
    checkpoints[14] = false;
  }

  const archivedBadgeVisible = await page
    .getByTestId("patient-archived-badge")
    .isVisible()
    .catch(() => false);
  checkpoints[15] = patientSelection === "active" && !archivedBadgeVisible;

  const auditResponsePromise = page.waitForResponse(
    (response) => {
      const url = new URL(response.url());
      return (
        response.request().method() === "GET" &&
        /^\/api\/patients\/\d+\/audit$/.test(url.pathname)
      );
    },
    { timeout: 20_000 }
  );
  await auditControl.click();
  const auditResponse = await auditResponsePromise;
  await page
    .getByRole("heading", { name: "Audit log", exact: true })
    .waitFor({ state: "visible", timeout: 20_000 });
  await page.locator("table").waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[13] = auditResponse.ok();
})()
  .catch(() => {})
  .finally(async () => {
    const base = "http://localhost:3000";
    try {
      const health = await checkedFetch(base, "/api/health");
      checkpoints[19] = health.ok;
    } catch {}
    checkpoints[16] = !unexpectedApi;
    checkpoints[17] = !unexpectedBrowser;
    checkpoints[18] = !writeRequest;
    if (browser) await browser.close().catch(() => {});
    process.stdout.write(
      JSON.stringify({
        checkpoints,
        patient_selection: patientSelection,
        archived_patient: "not_checked_safely",
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
            f'printf %s "${name}"',
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
        "archived_patient": "not_checked_safely",
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
        "archived_patient": "not_checked_safely",
        "unexpected_api": payload.get("unexpected_api") is not False,
        "unexpected_browser": payload.get("unexpected_browser") is not False,
        "write_request": payload.get("write_request") is True,
    }


def run_smoke() -> dict[str, Any]:
    email = _container_environment("ADMIN_EMAIL")
    password = _container_environment("ADMIN_PASSWORD")
    if not email or not password:
        return _empty_result()

    environment = os.environ.copy()
    environment["SMOKE_ADMIN_EMAIL"] = email
    environment["SMOKE_ADMIN_PASSWORD"] = password
    completed = subprocess.run(
        [
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
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
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
    print("archived_patient_smoke: not checked safely")
    print(
        "unexpected_api_failure: "
        + ("yes" if result["unexpected_api"] else "no")
    )
    print(
        "unexpected_browser_failure: "
        + ("yes" if result["unexpected_browser"] else "no")
    )
    print("write_request_issued: " + ("yes" if result["write_request"] else "no"))
    passed = (
        all(values)
        and result["patient_selection"] == "active"
        and not result["unexpected_api"]
        and not result["unexpected_browser"]
        and not result["write_request"]
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
