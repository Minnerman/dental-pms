#!/usr/bin/env python3
"""Run the production patient-ledger smoke without printing patient data."""

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
    "Patient page request completed",
    "Patient page rendered",
    "Financial tab found",
    "Financial tab opened",
    "Ledger navigation control found",
    "Ledger view opened",
    "Ledger API request completed",
    "Balance API request completed",
    "Ledger container rendered",
    "Balance state rendered",
    "Capability-aware controls rendered",
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
  const base = "http://127.0.0.1:3000";
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

  const patients = await (
    await checkedFetch(base, "/api/patients?limit=200", { headers })
  ).json();
  const patient = Array.isArray(patients)
    ? patients.find((item) => item && item.id && !item.deleted_at)
    : null;
  if (!patient) throw new Error("patient unavailable");

  const ledgerEntries = await (
    await checkedFetch(base, "/api/patients/" + patient.id + "/ledger?limit=200", {
      headers,
    })
  ).json();
  checkpoints[10] = Array.isArray(ledgerEntries);

  const balance = await (
    await checkedFetch(base, "/api/patients/" + patient.id + "/balance", { headers })
  ).json();
  checkpoints[11] = Boolean(balance && typeof balance.balance_pence === "number");

  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.on("pageerror", () => {
    unexpectedBrowser = true;
  });
  page.on("console", (message) => {
    const text = message.text();
    const benignExtraAttributes =
      message.type() === "error" && text.startsWith("Warning: Extra attributes from the server");
    if (message.type() === "error" && !benignExtraAttributes) unexpectedBrowser = true;
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
    document.cookie =
      "dental_pms_token=" + encodeURIComponent(tokenValue) + "; Path=/; SameSite=Lax";
  }, token);

  const navigation = await page.goto(base + "/patients/" + patient.id, {
    waitUntil: "domcontentloaded",
  });
  checkpoints[4] = Boolean(navigation && navigation.status() < 400);

  const patientTabs = page.getByTestId("patient-tabs");
  await patientTabs.waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[5] = true;

  const financialTab = page.getByTestId("patient-tab-Financial");
  await financialTab.waitFor({ state: "visible", timeout: 20_000 });
  checkpoints[6] = true;
  await financialTab.click();
  checkpoints[7] = (await financialTab.getAttribute("aria-selected")) === "true";

  const ledgerControl = page.getByTestId("patient-financial-ledger");
  await ledgerControl.waitFor({ state: "visible", timeout: 10_000 });
  checkpoints[8] = true;
  await ledgerControl.click();
  checkpoints[9] = (await ledgerControl.getAttribute("aria-selected")) === "true";

  const balanceState = page.getByTestId("patient-ledger-balance");
  await balanceState.waitFor({ state: "visible", timeout: 10_000 });
  checkpoints[12] = checkpoints[9];
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const text = await balanceState.textContent();
    if (text && !text.includes("unavailable")) {
      checkpoints[13] = true;
      break;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }

  const paymentVisible = await page
    .getByRole("button", { name: "Add payment", exact: true })
    .isVisible()
    .catch(() => false);
  const adjustmentVisible = await page
    .getByRole("button", { name: "Add adjustment", exact: true })
    .isVisible()
    .catch(() => false);
  const canWrite = capabilities.includes("billing.payments.write");
  checkpoints[14] = canWrite
    ? paymentVisible && adjustmentVisible
    : !paymentVisible && !adjustmentVisible;
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
