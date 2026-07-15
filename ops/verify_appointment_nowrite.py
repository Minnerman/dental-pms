#!/usr/bin/env python3
"""Run the production appointment smoke without printing appointment data."""

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
    "Appointment list request completed",
    "Suitable appointment selected",
    "Appointment date confirmed non-empty",
    "Diary page request completed",
    "Diary/calendar rendered",
    "Appointment event selector found",
    "Appointment context menu opened",
    "Appointment Open control found",
    "Appointment detail opened",
    "Capability-aware controls rendered",
    "Appointment history loaded",
    "No unexpected browser error",
    "No unexpected API 4xx/5xx",
    "No write request issued",
)


NODE_SMOKE = r"""
const { chromium } = require("@playwright/test");

const checkpoints = Array(18).fill(false);
let browser;
let unexpectedApi = false;
let unexpectedBrowser = false;
let writeIssued = false;

async function checkedFetch(base, path, options = {}) {
  const response = await fetch(base + path, options);
  if (!response.ok) {
    if (path.startsWith("/api/")) unexpectedApi = true;
    throw new Error("request failed");
  }
  return response;
}

(async () => {
  const base = "http://localhost:3000";
  let ready = false;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      const response = await fetch(base + "/api/health");
      if (response.ok) {
        ready = true;
        break;
      }
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  if (!ready) throw new Error("frontend not ready");

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

  const appointments = await (
    await checkedFetch(base, "/api/appointments", { headers })
  ).json();
  checkpoints[4] = Array.isArray(appointments);
  const patients = await (
    await checkedFetch(base, "/api/patients?limit=200", { headers })
  ).json();
  const activePatientIds = new Set(
    Array.isArray(patients)
      ? patients
          .filter((item) => item && item.id && !item.deleted_at)
          .map((item) => item.id)
      : []
  );
  const appointment = Array.isArray(appointments)
    ? appointments.find(
        (item) =>
          item &&
          item.id &&
          item.starts_at &&
          !item.deleted_at &&
          item.patient &&
          activePatientIds.has(item.patient.id)
      )
    : null;
  checkpoints[5] = Boolean(appointment);
  if (!appointment) throw new Error("appointment unavailable");

  const startsAt = new Date(appointment.starts_at);
  if (Number.isNaN(startsAt.getTime())) throw new Error("appointment date invalid");
  const pad = (value) => String(value).padStart(2, "0");
  const dateKey =
    startsAt.getUTCFullYear() +
    "-" +
    pad(startsAt.getUTCMonth() + 1) +
    "-" +
    pad(startsAt.getUTCDate());
  const datedAppointments = await (
    await checkedFetch(base, "/api/appointments?date=" + dateKey, { headers })
  ).json();
  checkpoints[6] =
    Array.isArray(datedAppointments) &&
    datedAppointments.some((item) => item && item.id === appointment.id);
  if (!checkpoints[6]) throw new Error("appointment date empty");

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
  page.on("request", (request) => {
    if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method())) {
      writeIssued = true;
    }
  });
  await page.addInitScript((tokenValue) => {
    localStorage.setItem("dental_pms_token", tokenValue);
    localStorage.setItem("dental_pms_appointments_view", "calendar");
    document.cookie =
      "dental_pms_token=" +
      encodeURIComponent(tokenValue) +
      "; Path=/; SameSite=Lax";
  }, token);

  const navigation = await page.goto(
    base +
      "/appointments?date=" +
      dateKey +
      "&view=day&appointment=" +
      appointment.id,
    { waitUntil: "domcontentloaded" }
  );
  checkpoints[7] = Boolean(navigation && navigation.status() < 400);

  await page
    .getByTestId("appointments-page")
    .waitFor({ state: "visible", timeout: 20_000 });
  await page
    .getByTestId("appointments-calendar-toolbar")
    .waitFor({ state: "visible", timeout: 20_000 });
  const dateInput = page.getByTestId("appointments-jump-date-input");
  await dateInput.waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[8] = (await dateInput.inputValue()) === dateKey;

  const event = page.getByTestId("appointment-event-" + appointment.id);
  await event.waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[9] = true;

  await event.click({ button: "right" });
  const contextMenu = page.getByTestId("appointments-context-menu");
  await contextMenu.waitFor({ state: "visible", timeout: 10_000 });
  checkpoints[10] = true;

  const openControl = contextMenu.getByTestId("appointments-context-open");
  await openControl.waitFor({ state: "visible", timeout: 10_000 });
  checkpoints[11] = true;
  await openControl.click();

  const detail = page.getByTestId("appointment-detail-panel");
  await detail.waitFor({ state: "visible", timeout: 10_000 });
  checkpoints[12] = true;

  const canEdit =
    capabilities.includes("appointments.write") ||
    capabilities.includes("appointments.cancel") ||
    capabilities.includes("appointments.reschedule");
  const editVisible = await detail
    .getByTestId("appointment-detail-edit")
    .isVisible()
    .catch(() => false);
  const closeVisible = await detail
    .getByTestId("appointment-detail-close")
    .isVisible()
    .catch(() => false);
  checkpoints[13] = closeVisible && (canEdit ? editVisible : !editVisible);

  const historyToggle = detail.getByTestId("appointment-history-toggle");
  await historyToggle.waitFor({ state: "visible", timeout: 10_000 });
  const historyResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      response.url().includes("/api/audit/appointments/"),
    { timeout: 10_000 }
  );
  await historyToggle.click();
  checkpoints[14] = (await historyResponse).ok();
})()
  .catch(() => {})
  .finally(async () => {
    if (browser) await browser.close().catch(() => {});
    checkpoints[15] = !unexpectedBrowser;
    checkpoints[16] = !unexpectedApi;
    checkpoints[17] = !writeIssued;
    process.stdout.write(
      JSON.stringify({
        checkpoints,
        unexpected_api: unexpectedApi,
        unexpected_browser: unexpectedBrowser,
        write_request: writeIssued,
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
        "unexpected_api": True,
        "unexpected_browser": True,
        "write_request": False,
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
    if not isinstance(payload, dict):
        return _empty_result()
    return payload


def main() -> int:
    result = run_smoke()
    values = result.get("checkpoints")
    if not isinstance(values, list) or len(values) != len(CHECKPOINTS):
        values = [False] * len(CHECKPOINTS)

    for index, (label, passed) in enumerate(zip(CHECKPOINTS, values), start=1):
        print(f"checkpoint_{index:02d} {label}: {'pass' if passed else 'fail'}")
    print(
        "unexpected_api_failure: "
        + ("yes" if result.get("unexpected_api", True) else "no")
    )
    print(
        "unexpected_browser_failure: "
        + ("yes" if result.get("unexpected_browser", True) else "no")
    )
    print("write_request_issued: " + ("yes" if result.get("write_request") else "no"))
    return 0 if all(bool(value) for value in values) else 1


if __name__ == "__main__":
    sys.exit(main())
