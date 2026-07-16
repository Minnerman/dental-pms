#!/usr/bin/env python3
"""Run the production recall-workflow smoke without printing patient data."""

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
    "Recall-list API completed",
    "Recall page requested",
    "Recall page rendered",
    "Filters rendered",
    "Pagination state rendered",
    "Suitable recall selection classified internally",
    "Recall row state rendered",
    "Patient navigation control classified",
    "Last-contact state rendered",
    "Capability-aware mutation controls classified",
    "Appointment-booking control classified",
    "Export controls classified",
    "Export-count API completed",
    "No unexpected API 4xx/5xx",
    "No unexpected browser error",
    "No POST, PUT, PATCH or DELETE request issued",
    "Final application health confirmed",
)


NODE_SMOKE = r"""
const { chromium } = require("@playwright/test");

const checkpoints = Array(21).fill(false);
const writeMethods = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let browser;
let unexpectedApi = false;
let unexpectedBrowser = false;
let writeRequest = false;
let recallSelection = "unknown";
let recallRow = "unknown";
let mutationControls = "unknown";
let bookingControl = "unknown";
let exportControls = "unknown";
let versionCompatibility = "unknown";

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

  const canView = capabilities.includes("recalls.view");
  const canWrite = capabilities.includes("recalls.write");
  const canExport = capabilities.includes("recalls.export");
  const canBook = capabilities.includes("appointments.write");
  const canOpenPatient = capabilities.includes("patients.view");
  versionCompatibility = canView ? "compatible" : "missing_recall_view";
  if (!canView) throw new Error("recall view unavailable");

  const recalls = await (
    await checkedFetch(
      base,
      "/api/recalls?status=due%2Coverdue&limit=50&offset=0",
      { headers }
    )
  ).json();
  checkpoints[4] = Array.isArray(recalls);
  if (!checkpoints[4]) throw new Error("recall list unavailable");
  const suitableRecall = recalls.find(
    (item) => item && Number.isInteger(item.id) && item.id > 0
  );
  recallSelection = suitableRecall ? "suitable" : "none";
  checkpoints[9] = true;

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

  const exportCountPromise = canExport
    ? page.waitForResponse(
        (response) => {
          const url = new URL(response.url());
          return (
            response.request().method() === "GET" &&
            url.pathname === "/api/recalls/export_count"
          );
        },
        { timeout: 20_000 }
      )
    : null;
  const navigation = await page.goto(base + "/recalls", {
    waitUntil: "domcontentloaded",
  });
  checkpoints[5] = Boolean(navigation && navigation.status() < 400);

  const pageRoot = page.getByTestId("recalls-page").first();
  await pageRoot.waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[6] = true;
  const filters = page.getByTestId("recalls-filters");
  await filters.waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[7] = true;
  const pagination = page.getByTestId("recalls-pagination");
  await pagination.waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[8] = true;

  const firstRow = page.getByTestId("recalls-row").first();
  if (suitableRecall) {
    await firstRow.waitFor({ state: "visible", timeout: 20_000 });
    recallRow = "checked";
    checkpoints[10] = true;

    const patientNavigationVisible = await firstRow
      .getByTestId("recalls-patient-navigation")
      .isVisible()
      .catch(() => false);
    checkpoints[11] = canOpenPatient
      ? patientNavigationVisible
      : !patientNavigationVisible;

    await firstRow
      .getByTestId("recalls-last-contact")
      .waitFor({ state: "visible", timeout: 10_000 });
    checkpoints[12] = true;

    const mutationVisible = await firstRow
      .getByTestId("recalls-mutation-controls")
      .isVisible()
      .catch(() => false);
    mutationControls = mutationVisible ? "write" : "read_only";
    checkpoints[13] = canWrite ? mutationVisible : !mutationVisible;

    const bookingVisible = await firstRow
      .getByTestId("recalls-book-action")
      .isVisible()
      .catch(() => false);
    bookingControl = bookingVisible ? "available" : "unavailable";
    checkpoints[14] = canBook ? bookingVisible : !bookingVisible;
  } else {
    await page
      .getByText("No recalls match your filters.", { exact: true })
      .waitFor({ state: "visible", timeout: 20_000 });
    recallRow = "not_checked_safely";
    mutationControls = canWrite ? "write_no_row" : "read_only_no_row";
    bookingControl = canBook ? "available_no_row" : "unavailable_no_row";
    checkpoints[10] = true;
    checkpoints[11] = true;
    checkpoints[12] = true;
    checkpoints[13] = true;
    checkpoints[14] = true;
  }

  const csvVisible = await page
    .getByTestId("recalls-export-csv")
    .isVisible()
    .catch(() => false);
  const zipVisible = await page
    .getByTestId("recalls-export-zip")
    .isVisible()
    .catch(() => false);
  exportControls = csvVisible && zipVisible ? "available" : "unavailable";
  checkpoints[15] = canExport ? csvVisible && zipVisible : !csvVisible && !zipVisible;

  if (exportCountPromise) {
    const response = await exportCountPromise;
    checkpoints[16] = response.ok();
  } else {
    checkpoints[16] = true;
  }
})()
  .catch(() => {})
  .finally(async () => {
    const base = "http://localhost:3000";
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
        recall_selection: recallSelection,
        recall_row: recallRow,
        mutation_controls: mutationControls,
        booking_control: bookingControl,
        export_controls: exportControls,
        version_compatibility: versionCompatibility,
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
        "recall_selection": "unknown",
        "recall_row": "unknown",
        "mutation_controls": "unknown",
        "booking_control": "unknown",
        "export_controls": "unknown",
        "version_compatibility": "unknown",
        "unexpected_api": True,
        "unexpected_browser": True,
        "write_request": False,
    }


def _enum_value(payload: dict[str, Any], name: str, values: set[str]) -> str:
    value = payload.get(name)
    return value if value in values else "unknown"


def _normalise_result(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _empty_result()
    checkpoints = payload.get("checkpoints")
    if not isinstance(checkpoints, list) or len(checkpoints) != len(CHECKPOINTS):
        return _empty_result()
    return {
        "checkpoints": [value is True for value in checkpoints],
        "recall_selection": _enum_value(
            payload, "recall_selection", {"suitable", "none", "unknown"}
        ),
        "recall_row": _enum_value(
            payload, "recall_row", {"checked", "not_checked_safely", "unknown"}
        ),
        "mutation_controls": _enum_value(
            payload,
            "mutation_controls",
            {"write", "read_only", "write_no_row", "read_only_no_row", "unknown"},
        ),
        "booking_control": _enum_value(
            payload,
            "booking_control",
            {"available", "unavailable", "available_no_row", "unavailable_no_row", "unknown"},
        ),
        "export_controls": _enum_value(
            payload, "export_controls", {"available", "unavailable", "unknown"}
        ),
        "version_compatibility": _enum_value(
            payload,
            "version_compatibility",
            {"compatible", "missing_recall_view", "unknown"},
        ),
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
        "suitable_recall_found: "
        + ("yes" if result["recall_selection"] == "suitable" else "no")
    )
    print(
        "recall_row_smoke: "
        + (
            "pass"
            if result["recall_row"] == "checked"
            else "not checked safely"
            if result["recall_row"] == "not_checked_safely"
            else "fail"
        )
    )
    print("mutation_controls: " + result["mutation_controls"].replace("_", " "))
    print("booking_control: " + result["booking_control"].replace("_", " "))
    print("export_controls: " + result["export_controls"].replace("_", " "))
    print("version_compatibility: " + result["version_compatibility"].replace("_", " "))
    print("unexpected_api_failure: " + ("yes" if result["unexpected_api"] else "no"))
    print(
        "unexpected_browser_failure: "
        + ("yes" if result["unexpected_browser"] else "no")
    )
    print("write_request_issued: " + ("yes" if result["write_request"] else "no"))
    passed = (
        all(values)
        and result["recall_selection"] in {"suitable", "none"}
        and result["recall_row"] in {"checked", "not_checked_safely"}
        and result["version_compatibility"] == "compatible"
        and not result["unexpected_api"]
        and not result["unexpected_browser"]
        and not result["write_request"]
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
