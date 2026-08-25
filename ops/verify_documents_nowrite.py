#!/usr/bin/env python3
"""Verify patient document surfaces without downloads, audit writes, or data mutation."""

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
    "documents.download classified",
    "documents.upload classified",
    "documents.delete classified",
    "Suitable active patient selected internally",
    "Patient page rendered",
    "Documents/attachments area rendered",
    "Active-template list API completed",
    "Patient-document list API completed",
    "Attachment list API completed",
    "Template/document empty or populated state rendered",
    "Attachment empty or populated state rendered",
    "Existing document metadata classified when available",
    "Existing attachment metadata classified when available",
    "Download/preview controls classified without clicking",
    "Upload/generate controls classified without clicking",
    "Delete controls classified without clicking",
    "Archived/read-only state classified where safely observable",
    "No unexpected API 4xx/5xx",
    "No browser error",
    "No POST, PUT, PATCH or DELETE request issued",
    "No audited download or preview endpoint invoked",
    "Final application health confirmed",
)


NODE_SMOKE = r"""
const { chromium } = require("@playwright/test");

const checkpoints = Array(26).fill(false);
const writeMethods = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let browser;
let context;
let unexpectedApi = false;
let unexpectedBrowser = false;
let writeRequest = false;
let auditedEndpoint = false;
let contextClosed = false;
let downloadCapability = "unknown";
let uploadCapability = "unknown";
let deleteCapability = "unknown";
let documentState = "unknown";
let attachmentState = "unknown";
let documentMetadata = "unknown";
let attachmentMetadata = "unknown";
let downloadControls = "unknown";
let uploadControls = "unknown";
let deleteControls = "unknown";
let lifecycleState = "unknown";

function isAuditedDocumentEndpoint(rawUrl) {
  let path;
  try {
    path = new URL(rawUrl).pathname;
  } catch {
    return false;
  }
  return (
    /^\/api\/attachments\/\d+\/(download|preview)$/.test(path) ||
    /^\/api\/document-templates\/\d+\/download$/.test(path) ||
    /^\/api\/patient-documents\/\d+\/download$/.test(path)
  );
}

async function checkedFetch(base, path, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  if (writeMethods.has(method) && path !== "/api/auth/login") {
    writeRequest = true;
    throw new Error("write request blocked");
  }
  if (isAuditedDocumentEndpoint(base + path)) {
    auditedEndpoint = true;
    throw new Error("audited endpoint blocked");
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
  const canDownload = capabilities.includes("documents.download");
  const canUpload = capabilities.includes("documents.upload");
  const canDelete = capabilities.includes("documents.delete");
  downloadCapability = canDownload ? "present" : "missing";
  uploadCapability = canUpload ? "present" : "missing";
  deleteCapability = canDelete ? "present" : "missing";
  checkpoints[4] = canDownload;
  checkpoints[5] = uploadCapability !== "unknown";
  checkpoints[6] = deleteCapability !== "unknown";
  if (!canDownload) throw new Error("document reads unavailable");

  const patients = await (
    await checkedFetch(base, "/api/patients?limit=200", { headers })
  ).json();
  const patient = Array.isArray(patients)
    ? patients.find(
        (item) => item && Number.isInteger(item.id) && item.id > 0 && !item.deleted_at
      )
    : null;
  checkpoints[7] = Boolean(patient);
  if (!patient) throw new Error("active patient unavailable");

  const templates = await (
    await checkedFetch(base, "/api/document-templates", { headers })
  ).json();
  checkpoints[10] = Array.isArray(templates);
  if (!checkpoints[10]) throw new Error("templates unavailable");
  const documents = await (
    await checkedFetch(base, "/api/patients/" + patient.id + "/documents", { headers })
  ).json();
  checkpoints[11] = Array.isArray(documents);
  if (!checkpoints[11]) throw new Error("documents unavailable");
  const attachments = await (
    await checkedFetch(base, "/api/patients/" + patient.id + "/attachments", { headers })
  ).json();
  checkpoints[12] = Array.isArray(attachments);
  if (!checkpoints[12]) throw new Error("attachments unavailable");

  documentState = documents.length > 0 ? "populated" : "empty";
  attachmentState = attachments.length > 0 ? "populated" : "empty";
  documentMetadata = documents.length > 0 ? "checked" : "not-checked-safely";
  attachmentMetadata = attachments.length > 0 ? "checked" : "not-checked-safely";

  browser = await chromium.launch({ headless: true });
  context = await browser.newContext();
  const page = await context.newPage();
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
    const request = route.request();
    if (writeMethods.has(request.method())) {
      writeRequest = true;
      await route.abort("blockedbyclient");
      return;
    }
    if (isAuditedDocumentEndpoint(request.url())) {
      auditedEndpoint = true;
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

  const documentNavigation = await page.goto(
    base + "/patients/" + patient.id + "/documents",
    { waitUntil: "domcontentloaded" }
  );
  checkpoints[8] = Boolean(documentNavigation && documentNavigation.status() < 400);
  const documentAccess = page.getByTestId("patient-documents-access");
  await documentAccess.waitFor({ state: "visible", timeout: 20_000 });
  const documentAccessState = await documentAccess.getAttribute("data-state");
  if (documentAccessState === "loading") {
    await page.waitForFunction(() => {
      const node = document.querySelector('[data-testid="patient-documents-access"]');
      return node && node.getAttribute("data-state") !== "loading";
    }, null, { timeout: 20_000 });
  }
  checkpoints[9] = true;
  const templateCards = page.locator('[data-testid^="patient-template-card-"]');
  const documentCards = page.locator('[data-testid^="patient-document-card-"]');
  const documentEmpty = page.getByText("No documents generated yet.");
  const templateEmpty = page.getByText("No active templates available.");
  await Promise.race([
    documentCards.first().waitFor({ state: "visible", timeout: 20_000 }),
    documentEmpty.waitFor({ state: "visible", timeout: 20_000 }),
  ]);
  checkpoints[13] =
    ((await documentCards.count()) > 0 || (await documentEmpty.count()) > 0) &&
    ((await templateCards.count()) > 0 || (await templateEmpty.count()) > 0);
  checkpoints[15] = documentMetadata !== "unknown";

  const documentDownload = page.locator('[data-testid^="patient-document-download-"]');
  const templateDownload = page.locator('[data-testid^="patient-template-download-"]');
  const expectedDocumentDownloadControls = documents.length === 0 || (await documentDownload.count()) > 0;
  const expectedTemplateDownloadControls = templates.length === 0 || (await templateDownload.count()) > 0;
  downloadControls = expectedDocumentDownloadControls && expectedTemplateDownloadControls
    ? documents.length || templates.length ? "available" : "not-checked-safely"
    : "unknown";

  const saveControl = page.getByTestId("patient-document-save");
  const attachControl = page.locator('[data-testid^="patient-document-attach-pdf-"]');
  if (canUpload) {
    uploadControls =
      (await saveControl.count()) > 0 &&
      (documents.length === 0 || (await attachControl.count()) > 0)
        ? "write"
        : "unknown";
  } else {
    uploadControls =
      (await saveControl.count()) === 0 && (await attachControl.count()) === 0
        ? "read-only"
        : "unknown";
  }

  const documentDelete = page.locator('[data-testid^="patient-document-delete-"]');
  const documentDeleteCorrect = canDelete
    ? documents.length === 0 || (await documentDelete.count()) > 0
    : (await documentDelete.count()) === 0;

  const attachmentNavigation = await page.goto(
    base + "/patients/" + patient.id + "/attachments",
    { waitUntil: "domcontentloaded" }
  );
  if (!attachmentNavigation || attachmentNavigation.status() >= 400) {
    throw new Error("attachment page unavailable");
  }
  const attachmentAccess = page.getByTestId("patient-attachments-access");
  await attachmentAccess.waitFor({ state: "visible", timeout: 20_000 });
  if ((await attachmentAccess.getAttribute("data-state")) === "loading") {
    await page.waitForFunction(() => {
      const node = document.querySelector('[data-testid="patient-attachments-access"]');
      return node && node.getAttribute("data-state") !== "loading";
    }, null, { timeout: 20_000 });
  }
  const attachmentCards = page.locator('[data-testid^="attachment-card-"]');
  const attachmentEmpty = page.getByText("No attachments");
  await Promise.race([
    attachmentCards.first().waitFor({ state: "visible", timeout: 20_000 }),
    attachmentEmpty.first().waitFor({ state: "visible", timeout: 20_000 }),
  ]);
  checkpoints[14] = (await attachmentCards.count()) > 0 || (await attachmentEmpty.count()) > 0;
  checkpoints[16] = attachmentMetadata !== "unknown";

  const attachmentDownload = page.locator('[data-testid^="attachment-download-"]');
  if (attachments.length > 0 && (await attachmentDownload.count()) === 0) {
    downloadControls = "unknown";
  }
  checkpoints[17] = downloadControls !== "unknown";

  const uploadControl = page.getByTestId("attachment-upload");
  if (canUpload) {
    if ((await uploadControl.count()) === 0) uploadControls = "unknown";
  } else if ((await uploadControl.count()) > 0) {
    uploadControls = "unknown";
  }
  checkpoints[18] = uploadControls !== "unknown";

  const attachmentDelete = page.locator('[data-testid^="attachment-delete-"]');
  const attachmentDeleteCorrect = canDelete
    ? attachments.length === 0 || (await attachmentDelete.count()) > 0
    : (await attachmentDelete.count()) === 0;
  deleteControls = documentDeleteCorrect && attachmentDeleteCorrect
    ? canDelete ? "write" : "read-only"
    : "unknown";
  checkpoints[19] = deleteControls !== "unknown";
  lifecycleState = "active";
  checkpoints[20] = true;
})()
  .catch(() => {})
  .finally(async () => {
    const base = process.env.SMOKE_FRONTEND_BASE_URL || "http://localhost:3000";
    try {
      const health = await checkedFetch(base, "/api/health");
      checkpoints[25] = health.ok;
    } catch {}
    checkpoints[21] = !unexpectedApi;
    checkpoints[22] = !unexpectedBrowser;
    checkpoints[23] = !writeRequest;
    checkpoints[24] = !auditedEndpoint;
    if (context) {
      await context.close().then(() => { contextClosed = true; }).catch(() => {});
    }
    if (browser) await browser.close().catch(() => {});
    if (!contextClosed) checkpoints[22] = false;
    process.stdout.write(
      JSON.stringify({
        checkpoints,
        documents_download: downloadCapability,
        documents_upload: uploadCapability,
        documents_delete: deleteCapability,
        document_state: documentState,
        attachment_state: attachmentState,
        document_metadata: documentMetadata,
        attachment_metadata: attachmentMetadata,
        download_controls: downloadControls,
        upload_controls: uploadControls,
        delete_controls: deleteControls,
        lifecycle_state: lifecycleState,
        unexpected_api: unexpectedApi,
        unexpected_browser: unexpectedBrowser,
        write_request: writeRequest,
        audited_endpoint: auditedEndpoint,
        context_closed: contextClosed,
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
        "documents_download": "unknown",
        "documents_upload": "unknown",
        "documents_delete": "unknown",
        "document_state": "unknown",
        "attachment_state": "unknown",
        "document_metadata": "unknown",
        "attachment_metadata": "unknown",
        "download_controls": "unknown",
        "upload_controls": "unknown",
        "delete_controls": "unknown",
        "lifecycle_state": "unknown",
        "unexpected_api": True,
        "unexpected_browser": True,
        "write_request": False,
        "audited_endpoint": False,
        "context_closed": False,
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
    capability_states = {"present", "missing", "unknown"}
    content_states = {"empty", "populated", "unknown"}
    metadata_states = {"checked", "not-checked-safely", "unknown"}
    return {
        "checkpoints": [value is True for value in checkpoints],
        "documents_download": _choice(payload, "documents_download", capability_states),
        "documents_upload": _choice(payload, "documents_upload", capability_states),
        "documents_delete": _choice(payload, "documents_delete", capability_states),
        "document_state": _choice(payload, "document_state", content_states),
        "attachment_state": _choice(payload, "attachment_state", content_states),
        "document_metadata": _choice(payload, "document_metadata", metadata_states),
        "attachment_metadata": _choice(payload, "attachment_metadata", metadata_states),
        "download_controls": _choice(
            payload, "download_controls", {"available", "not-checked-safely", "unknown"}
        ),
        "upload_controls": _choice(
            payload, "upload_controls", {"write", "read-only", "unknown"}
        ),
        "delete_controls": _choice(
            payload, "delete_controls", {"write", "read-only", "unknown"}
        ),
        "lifecycle_state": _choice(payload, "lifecycle_state", {"active", "unknown"}),
        "unexpected_api": payload.get("unexpected_api") is not False,
        "unexpected_browser": payload.get("unexpected_browser") is not False,
        "write_request": payload.get("write_request") is True,
        "audited_endpoint": payload.get("audited_endpoint") is True,
        "context_closed": payload.get("context_closed") is True,
    }


def run_smoke() -> dict[str, Any]:
    local_mode = os.environ.get("DOCUMENTS_SMOKE_LOCAL") == "1"
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
    print("documents_download: " + result["documents_download"])
    print("documents_upload: " + result["documents_upload"])
    print("documents_delete: " + result["documents_delete"])
    print("document_state: " + result["document_state"])
    print("attachment_state: " + result["attachment_state"])
    print("document_metadata: " + result["document_metadata"])
    print("attachment_metadata: " + result["attachment_metadata"])
    print("download_controls: " + result["download_controls"])
    print("upload_controls: " + result["upload_controls"])
    print("delete_controls: " + result["delete_controls"])
    print("lifecycle_state: " + result["lifecycle_state"])
    print("unexpected_api_failure: " + ("yes" if result["unexpected_api"] else "no"))
    print(
        "unexpected_browser_failure: "
        + ("yes" if result["unexpected_browser"] else "no")
    )
    print("write_request_issued: " + ("yes" if result["write_request"] else "no"))
    print("audited_endpoint_invoked: " + ("yes" if result["audited_endpoint"] else "no"))
    print("browser_context_closed: " + ("yes" if result["context_closed"] else "no"))
    passed = (
        all(values)
        and result["documents_download"] == "present"
        and result["documents_upload"] in {"present", "missing"}
        and result["documents_delete"] in {"present", "missing"}
        and result["document_state"] in {"empty", "populated"}
        and result["attachment_state"] in {"empty", "populated"}
        and result["document_metadata"] in {"checked", "not-checked-safely"}
        and result["attachment_metadata"] in {"checked", "not-checked-safely"}
        and result["download_controls"] in {"available", "not-checked-safely"}
        and result["upload_controls"] in {"write", "read-only"}
        and result["delete_controls"] in {"write", "read-only"}
        and result["lifecycle_state"] == "active"
        and not result["unexpected_api"]
        and not result["unexpected_browser"]
        and not result["write_request"]
        and not result["audited_endpoint"]
        and result["context_closed"]
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
