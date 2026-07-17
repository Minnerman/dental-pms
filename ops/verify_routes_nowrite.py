#!/usr/bin/env python3
"""Verify patient route behavior without printing or changing patient data."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any


CHECKPOINTS = (
    "Intended frontend image/source SHA confirmed",
    "Login completed",
    "Authenticated session confirmed",
    "/me completed",
    "/me/capabilities completed",
    "patients.view capability confirmed",
    "Active patient-list API completed",
    "Valid active-patient discovery classified internally",
    "Valid-patient backend API returned 200",
    "Valid-patient frontend route returned 200",
    "Valid-patient frontend page rendered",
    "Missing-patient backend API returned 404",
    "Missing-patient frontend route completed without redirect or 500",
    "Missing-patient frontend not-found state rendered",
    "Missing-clinical backend patient API returned 404",
    "Missing-clinical frontend route completed without redirect or 500",
    "Missing-clinical frontend not-found state rendered",
    "No unexpected redirect detected",
    "No unexpected API status detected",
    "No unexpected browser error detected",
    "No POST, PUT, PATCH or DELETE request issued",
    "Final application health and server readiness confirmed",
)


NODE_SMOKE = r"""
const { chromium } = require("@playwright/test");

const checkpoints = Array(22).fill(false);
const writeMethods = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let browser;
let page;
let unexpectedApi = false;
let unexpectedBrowser = false;
let unexpectedRedirect = false;
let writeRequest = false;
let backendForbidden = false;
let frontendServerError = false;
let serverExit = false;
let patientsView = "unknown";
let patientSelection = "unknown";
let validBackendStatus = "not_checked_safely";
let validFrontendStatus = "not_checked_safely";
let missingBackendStatus = "unknown";
let missingFrontendState = "unknown";
let missingClinicalState = "unknown";

async function checkedFetch(base, path, options = {}, expectedStatuses = [200]) {
  const method = String(options.method || "GET").toUpperCase();
  if (writeMethods.has(method) && path !== "/api/auth/login") {
    writeRequest = true;
    throw new Error("write request blocked");
  }
  let response;
  try {
    response = await fetch(base + path, {...options, redirect: "manual"});
  } catch {
    unexpectedApi = true;
    throw new Error("request failed");
  }
  if ([301, 302, 303, 307, 308].includes(response.status)) {
    unexpectedRedirect = true;
  }
  if (response.status === 403) backendForbidden = true;
  if (response.status >= 500) frontendServerError = true;
  if (!expectedStatuses.includes(response.status)) {
    unexpectedApi = true;
    throw new Error("unexpected status");
  }
  return response;
}

async function frontendReady(base) {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      const response = await fetch(base + "/api/health", {redirect: "manual"});
      if (response.ok) return true;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

async function renderNotFound(base, path, expectedState) {
  const navigation = await page.goto(base + path, {
    waitUntil: "domcontentloaded",
  });
  const status = navigation ? navigation.status() : 0;
  if ([301, 302, 303, 307, 308].includes(status)) unexpectedRedirect = true;
  if (status >= 500) frontendServerError = true;
  if (![200, 404].includes(status)) return false;
  await page
    .getByText("This page could not be found.", {exact: true})
    .waitFor({state: "visible", timeout: 20_000});
  if (expectedState === "patient") missingFrontendState = "not_found";
  if (expectedState === "clinical") missingClinicalState = "not_found";
  return true;
}

(async () => {
  const port = process.env.SMOKE_FRONTEND_PORT || "3000";
  const frontendBase = "http://127.0.0.1:" + port;
  const backendBase =
    process.env.SMOKE_BACKEND_BASE || "http://backend:8000";
  checkpoints[0] = process.env.SMOKE_IMAGE_MATCH === "yes";
  if (!checkpoints[0]) throw new Error("image mismatch");
  if (!(await frontendReady(frontendBase))) {
    serverExit = true;
    throw new Error("frontend not ready");
  }

  const loginResponse = await checkedFetch(
    frontendBase,
    "/api/auth/login",
    {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        email: process.env.SMOKE_ADMIN_EMAIL,
        password: process.env.SMOKE_ADMIN_PASSWORD,
      }),
    },
    [200]
  );
  const login = await loginResponse.json();
  checkpoints[1] = Boolean(login.access_token);
  if (!checkpoints[1]) throw new Error("login incomplete");
  const token = login.access_token;
  const headers = {Authorization: "Bearer " + token};
  checkpoints[2] = true;

  const me = await (
    await checkedFetch(frontendBase, "/api/me", {headers}, [200])
  ).json();
  checkpoints[3] = Boolean(me && me.id && me.is_active !== false);
  if (!checkpoints[3]) throw new Error("session unavailable");

  const capabilities = await (
    await checkedFetch(
      frontendBase,
      "/api/me/capabilities",
      {headers},
      [200]
    )
  ).json();
  checkpoints[4] = Array.isArray(capabilities);
  if (!checkpoints[4]) throw new Error("capabilities unavailable");
  const canView = capabilities.includes("patients.view");
  patientsView = canView ? "yes" : "no";
  checkpoints[5] = canView;
  if (!canView) {
    backendForbidden = true;
    throw new Error("patient view unavailable");
  }

  const patients = await (
    await checkedFetch(
      frontendBase,
      "/api/patients?limit=200",
      {headers},
      [200]
    )
  ).json();
  checkpoints[6] = Array.isArray(patients);
  if (!checkpoints[6]) throw new Error("patient list unavailable");
  const patient = patients.find(
    (item) =>
      item &&
      Number.isInteger(item.id) &&
      item.id > 0 &&
      !item.deleted_at &&
      !item.archived_at &&
      item.is_archived !== true &&
      item.is_active !== false &&
      item.status !== "archived"
  );
  patientSelection = patient ? "active" : "none";
  checkpoints[7] = true;

  let impossible = 2147483647;
  if (patients.some((item) => item && item.id === impossible)) {
    impossible -= 1;
  }

  if (patient) {
    const validBackend = await checkedFetch(
      backendBase,
      "/patients/" + patient.id,
      {headers},
      [200]
    );
    validBackendStatus = String(validBackend.status);
    await validBackend.arrayBuffer();
    checkpoints[8] = validBackend.status === 200;
  }

  const missingBackend = await checkedFetch(
    backendBase,
    "/patients/" + impossible,
    {headers},
    [404]
  );
  missingBackendStatus = String(missingBackend.status);
  await missingBackend.arrayBuffer();
  checkpoints[11] = missingBackend.status === 404;

  browser = await chromium.launch({headless: true});
  const context = await browser.newContext({
    extraHTTPHeaders: {Authorization: "Bearer " + token},
  });
  await context.addCookies([
    {
      name: "dental_pms_token",
      value: token,
      url: frontendBase,
      sameSite: "Lax",
    },
  ]);
  page = await context.newPage();
  page.on("pageerror", () => {
    unexpectedBrowser = true;
  });
  page.on("console", (message) => {
    const text = message.text();
    const benignExtraAttributes =
      message.type() === "error" &&
      text.startsWith("Warning: Extra attributes from the server");
    const benignExpectedNotFound =
      message.type() === "error" &&
      ((text.includes("Failed to load resource") && text.includes("404")) ||
        text.includes("NEXT_NOT_FOUND"));
    if (
      message.type() === "error" &&
      !benignExtraAttributes &&
      !benignExpectedNotFound
    ) {
      unexpectedBrowser = true;
    }
  });
  page.on("response", (response) => {
    const status = response.status();
    if ([301, 302, 303, 307, 308].includes(status)) {
      unexpectedRedirect = true;
    }
    if (status >= 500) {
      frontendServerError = true;
      unexpectedApi = true;
    }
  });
  page.on("requestfailed", (request) => {
    const failure = request.failure();
    const navigationAbort = Boolean(
      failure &&
        failure.errorText &&
        failure.errorText.includes("ERR_ABORTED")
    );
    if (!navigationAbort && !writeMethods.has(request.method())) {
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

  if (patient) {
    const validNavigation = await page.goto(
      frontendBase + "/patients/" + patient.id,
      {waitUntil: "domcontentloaded"}
    );
    validFrontendStatus = validNavigation
      ? String(validNavigation.status())
      : "unavailable";
    checkpoints[9] = Boolean(
      validNavigation && validNavigation.status() === 200
    );
    await page.locator("body").waitFor({state: "visible", timeout: 20_000});
    const validNotFound = await page
      .getByText("This page could not be found.", {exact: true})
      .isVisible()
      .catch(() => false);
    checkpoints[10] = !validNotFound;
  }

  checkpoints[12] = await renderNotFound(
    frontendBase,
    "/patients/" + impossible,
    "patient"
  );
  checkpoints[13] = missingFrontendState === "not_found";

  const missingClinicalBackend = await checkedFetch(
    backendBase,
    "/patients/" + impossible,
    {headers},
    [404]
  );
  await missingClinicalBackend.arrayBuffer();
  checkpoints[14] = missingClinicalBackend.status === 404;
  checkpoints[15] = await renderNotFound(
    frontendBase,
    "/patients/" + impossible + "/clinical",
    "clinical"
  );
  checkpoints[16] = missingClinicalState === "not_found";
})()
  .catch(() => {})
  .finally(async () => {
    const port = process.env.SMOKE_FRONTEND_PORT || "3000";
    const frontendBase = "http://127.0.0.1:" + port;
    try {
      const health = await fetch(frontendBase + "/api/health", {
        redirect: "manual",
      });
      checkpoints[21] = health.ok;
      if (!health.ok) serverExit = true;
    } catch {
      serverExit = true;
    }
    checkpoints[17] = !unexpectedRedirect;
    checkpoints[18] = !unexpectedApi && !backendForbidden && !frontendServerError;
    checkpoints[19] = !unexpectedBrowser;
    checkpoints[20] = !writeRequest;
    if (browser) await browser.close().catch(() => {});
    process.stdout.write(
      JSON.stringify({
        checkpoints,
        patients_view: patientsView,
        patient_selection: patientSelection,
        valid_backend_status: validBackendStatus,
        valid_frontend_status: validFrontendStatus,
        missing_backend_status: missingBackendStatus,
        missing_frontend_state: missingFrontendState,
        missing_clinical_state: missingClinicalState,
        unexpected_redirect: unexpectedRedirect,
        unexpected_api: unexpectedApi,
        unexpected_browser: unexpectedBrowser,
        backend_forbidden: backendForbidden,
        frontend_server_error: frontendServerError,
        server_exit: serverExit,
        write_request: writeRequest,
      }) + "\n"
    );
    process.exit(
      checkpoints.every(Boolean) && patientSelection === "active" ? 0 : 1
    );
  });
"""


def _exec_command(
    service: str,
    command: list[str],
    *,
    environment_names: tuple[str, ...] = (),
) -> list[str]:
    container = os.environ.get(
        "ROUTE_SMOKE_FRONTEND_CONTAINER"
        if service == "frontend"
        else "ROUTE_SMOKE_BACKEND_CONTAINER",
        "",
    ).strip()
    env_args = [value for name in environment_names for value in ("-e", name)]
    if container:
        return ["docker", "exec", *env_args, container, *command]
    return ["docker", "compose", "exec", "-T", *env_args, service, *command]


def _container_environment(service: str, name: str) -> str:
    result = subprocess.run(
        _exec_command(
            service,
            ["sh", "-lc", f'printf %s "${name}"'],
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else ""


def _expected_sha() -> str:
    override = os.environ.get("ROUTE_SMOKE_EXPECTED_SHA", "").strip()
    if override:
        return override
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _empty_result(image_classification: str = "unknown") -> dict[str, Any]:
    return {
        "checkpoints": [False] * len(CHECKPOINTS),
        "image_classification": image_classification,
        "patients_view": "unknown",
        "patient_selection": "unknown",
        "valid_backend_status": "not_checked_safely",
        "valid_frontend_status": "not_checked_safely",
        "missing_backend_status": "unknown",
        "missing_frontend_state": "unknown",
        "missing_clinical_state": "unknown",
        "unexpected_redirect": False,
        "unexpected_api": True,
        "unexpected_browser": True,
        "backend_forbidden": False,
        "frontend_server_error": False,
        "server_exit": True,
        "write_request": False,
    }


def _normalise_result(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _empty_result()
    checkpoints = payload.get("checkpoints")
    if not isinstance(checkpoints, list) or len(checkpoints) != len(CHECKPOINTS):
        return _empty_result()

    def choice(name: str, allowed: set[str], fallback: str) -> str:
        value = payload.get(name)
        return value if isinstance(value, str) and value in allowed else fallback

    return {
        "checkpoints": [value is True for value in checkpoints],
        "image_classification": choice(
            "image_classification", {"intended", "mismatch", "unknown"}, "unknown"
        ),
        "patients_view": choice(
            "patients_view", {"yes", "no", "unknown"}, "unknown"
        ),
        "patient_selection": choice(
            "patient_selection", {"active", "none", "unknown"}, "unknown"
        ),
        "valid_backend_status": choice(
            "valid_backend_status", {"200", "not_checked_safely"}, "unknown"
        ),
        "valid_frontend_status": choice(
            "valid_frontend_status",
            {"200", "not_checked_safely", "unavailable"},
            "unknown",
        ),
        "missing_backend_status": choice(
            "missing_backend_status", {"404", "unknown"}, "unknown"
        ),
        "missing_frontend_state": choice(
            "missing_frontend_state", {"not_found", "unknown"}, "unknown"
        ),
        "missing_clinical_state": choice(
            "missing_clinical_state", {"not_found", "unknown"}, "unknown"
        ),
        "unexpected_redirect": payload.get("unexpected_redirect") is True,
        "unexpected_api": payload.get("unexpected_api") is not False,
        "unexpected_browser": payload.get("unexpected_browser") is not False,
        "backend_forbidden": payload.get("backend_forbidden") is True,
        "frontend_server_error": payload.get("frontend_server_error") is True,
        "server_exit": payload.get("server_exit") is not False,
        "write_request": payload.get("write_request") is True,
    }


def run_smoke() -> dict[str, Any]:
    expected_sha = _expected_sha()
    runtime_sha = _container_environment("frontend", "NEXT_PUBLIC_BUILD_SHA")
    if not expected_sha or not runtime_sha:
        return _empty_result("unknown")
    if runtime_sha != expected_sha:
        return _empty_result("mismatch")

    email = _container_environment("backend", "ADMIN_EMAIL")
    password = _container_environment("backend", "ADMIN_PASSWORD")
    if not email or not password:
        return _empty_result("intended")

    environment = os.environ.copy()
    environment["SMOKE_ADMIN_EMAIL"] = email
    environment["SMOKE_ADMIN_PASSWORD"] = password
    environment["SMOKE_IMAGE_MATCH"] = "yes"
    environment["SMOKE_FRONTEND_PORT"] = os.environ.get(
        "ROUTE_SMOKE_FRONTEND_PORT", "3000"
    )
    backend_base = os.environ.get("ROUTE_SMOKE_BACKEND_BASE", "").strip()
    environment_names = (
        "SMOKE_ADMIN_EMAIL",
        "SMOKE_ADMIN_PASSWORD",
        "SMOKE_IMAGE_MATCH",
        "SMOKE_FRONTEND_PORT",
    )
    if backend_base:
        environment["SMOKE_BACKEND_BASE"] = backend_base
        environment_names += ("SMOKE_BACKEND_BASE",)

    completed = subprocess.run(
        _exec_command(
            "frontend",
            ["node", "-e", NODE_SMOKE],
            environment_names=environment_names,
        ),
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return _empty_result("intended")
    if isinstance(payload, dict):
        payload["image_classification"] = "intended"
    return _normalise_result(payload)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _safe_status(value: str) -> str:
    return value.replace("_", " ")


def main() -> int:
    result = _normalise_result(run_smoke())
    values = result["checkpoints"]

    for index, (label, passed) in enumerate(zip(CHECKPOINTS, values), start=1):
        print(f"checkpoint_{index:02d} {label}: {'pass' if passed else 'fail'}")
    print("diagnostic_image: " + result["image_classification"])
    print("patients_view_present: " + result["patients_view"])
    print(
        "valid_active_patient_discovered: "
        + ("yes" if result["patient_selection"] == "active" else "no")
    )
    print(
        "valid_backend_status: " + _safe_status(result["valid_backend_status"])
    )
    print(
        "valid_frontend_status: " + _safe_status(result["valid_frontend_status"])
    )
    print(
        "missing_backend_status: "
        + _safe_status(result["missing_backend_status"])
    )
    print(
        "missing_patient_route: "
        + _safe_status(result["missing_frontend_state"])
    )
    print(
        "missing_clinical_route: "
        + _safe_status(result["missing_clinical_state"])
    )
    print("unexpected_redirect: " + _yes_no(result["unexpected_redirect"]))
    print("backend_403: " + _yes_no(result["backend_forbidden"]))
    print("frontend_500: " + _yes_no(result["frontend_server_error"]))
    print("temporary_server_exit: " + _yes_no(result["server_exit"]))
    print("unexpected_api_failure: " + _yes_no(result["unexpected_api"]))
    print("unexpected_browser_failure: " + _yes_no(result["unexpected_browser"]))
    print("write_request_issued: " + _yes_no(result["write_request"]))

    passed = (
        all(values)
        and result["image_classification"] == "intended"
        and result["patients_view"] == "yes"
        and result["patient_selection"] == "active"
        and result["valid_backend_status"] == "200"
        and result["valid_frontend_status"] == "200"
        and result["missing_backend_status"] == "404"
        and result["missing_frontend_state"] == "not_found"
        and result["missing_clinical_state"] == "not_found"
        and not result["unexpected_redirect"]
        and not result["backend_forbidden"]
        and not result["frontend_server_error"]
        and not result["server_exit"]
        and not result["unexpected_api"]
        and not result["unexpected_browser"]
        and not result["write_request"]
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
