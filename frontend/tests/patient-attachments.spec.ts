import path from "path";
import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("patient attachments tab shows an empty-state CTA when no attachments exist", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Docs",
    last_name: `Attach Empty ${Date.now()}`,
  });

  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}/attachments`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByRole("heading", { name: "Attachments" })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText("Loading attachments…")).toHaveCount(0);
  await expect(page.getByText("No attachments yet.")).toBeVisible();
  await expect(page.locator('[data-testid^="attachment-card-"]')).toHaveCount(0);
  await expect(page.getByTestId("attachment-upload")).toBeVisible();
});

test("patient attachments upload, preview, download, delete", async ({ page, request }) => {
  const patientId = await createPatient(request, {
    first_name: "Docs",
    last_name: `Attach ${Date.now()}`,
  });

  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}/attachments`, {
    waitUntil: "domcontentloaded",
  });

  const uploadInput = page
    .getByTestId("attachment-upload")
    .locator("input[type=\"file\"]");
  const fixturePath = path.resolve(
    __dirname,
    "fixtures",
    "sample.pdf"
  );
  await uploadInput.setInputFiles(fixturePath);

  const token = await ensureAuthReady(request);
  let attachmentId: number | null = null;
  await expect
    .poll(
      async () => {
        const response = await request.get(
          `${getBaseUrl()}/api/patients/${patientId}/attachments`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!response.ok()) {
          return null;
        }
        const items = (await response.json()) as {
          id: number;
          original_filename: string;
        }[];
        const match = items.find(
          (item) => item.original_filename === "sample.pdf"
        );
        attachmentId = match?.id ?? null;
        return attachmentId;
      },
      { timeout: 20_000 }
    )
    .not.toBeNull();
  if (attachmentId === null) {
    throw new Error("Attachment id not available after upload");
  }

  const row = page.getByTestId(`attachment-card-${attachmentId}`);
  await expect(row).toBeVisible({ timeout: 15_000 });

  const [previewPage] = await Promise.all([
    page.waitForEvent("popup"),
    page.getByTestId(`attachment-preview-${attachmentId}`).click(),
  ]);
  const previewRes = await request.get(
    `${getBaseUrl()}/api/attachments/${attachmentId}/preview`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  expect(previewRes.ok()).toBeTruthy();
  await previewPage.close();

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTestId(`attachment-download-${attachmentId}`).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/sample\.pdf/i);

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId(`attachment-delete-${attachmentId}`).click();
  await expect(row).toHaveCount(0);
});

test("patient attachment upload survives a stale initial attachments load", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Docs",
    last_name: `Attach Race ${Date.now()}`,
  });

  await primePageAuth(page, request);

  const attachmentsRoutePattern = new RegExp(`/api/patients/${patientId}/attachments$`);
  let releaseInitialLoad!: () => void;
  const releaseInitialLoadPromise = new Promise<void>((resolve) => {
    releaseInitialLoad = resolve;
  });
  let heldInitialLoad = false;
  await page.route(attachmentsRoutePattern, async (route) => {
    if (route.request().method() !== "GET" || heldInitialLoad) {
      await route.continue();
      return;
    }
    heldInitialLoad = true;
    await releaseInitialLoadPromise;
    await route.fulfill({
      status: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify([]),
    });
  });

  await page.goto(`${getBaseUrl()}/patients/${patientId}/attachments`, {
    waitUntil: "domcontentloaded",
  });

  const uploadInput = page
    .getByTestId("attachment-upload")
    .locator('input[type="file"]');
  const fixturePath = path.resolve(__dirname, "fixtures", "sample.pdf");
  await uploadInput.setInputFiles(fixturePath);

  const uploadedRow = page
    .locator('[data-testid^="attachment-card-"]')
    .filter({ has: page.getByText("sample.pdf", { exact: true }) })
    .first();
  await expect(uploadedRow).toBeVisible({ timeout: 15_000 });

  releaseInitialLoad();

  await expect(uploadedRow).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("No attachments yet.")).toHaveCount(0);
  await page.unroute(attachmentsRoutePattern);
});

test("patient attachments show uploaded-by and uploaded-at metadata", async ({
  page,
  request,
}) => {
  type AttachmentMetadata = {
    id: number;
    original_filename: string;
    created_at: string;
    created_by?: {
      email?: string | null;
    } | null;
  };

  const patientId = await createPatient(request, {
    first_name: "Docs",
    last_name: `Attach Meta ${Date.now()}`,
  });

  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}/attachments`, {
    waitUntil: "domcontentloaded",
  });

  const uploadInput = page
    .getByTestId("attachment-upload")
    .locator('input[type="file"]');
  const fixturePath = path.resolve(__dirname, "fixtures", "sample.pdf");
  await uploadInput.setInputFiles(fixturePath);

  const token = await ensureAuthReady(request);
  let attachment: AttachmentMetadata | null = null;
  await expect
    .poll(
      async () => {
        const response = await request.get(
          `${getBaseUrl()}/api/patients/${patientId}/attachments`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!response.ok()) {
          return null;
        }
        const items = (await response.json()) as AttachmentMetadata[];
        attachment = items.find((item) => item.original_filename === "sample.pdf") ?? null;
        return attachment?.id ?? null;
      },
      { timeout: 20_000 }
    )
    .not.toBeNull();
  if (attachment === null) {
    throw new Error("Attachment metadata not available after upload");
  }
  const resolvedAttachment = attachment as AttachmentMetadata;

  const row = page.getByTestId(`attachment-card-${resolvedAttachment.id}`);
  await expect(row).toBeVisible({ timeout: 15_000 });

  const expectedUploadedAt = await page.evaluate((createdAt) => {
    return new Date(createdAt).toLocaleString("en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  }, resolvedAttachment.created_at);
  const expectedUploadedBy = resolvedAttachment.created_by?.email ?? "—";

  await expect(row).toContainText("sample.pdf");
  await expect(row).toContainText(`Uploaded ${expectedUploadedAt} by ${expectedUploadedBy}`);
});

test("patient attachment upload shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Docs",
    last_name: `Attach Upload ${Date.now()}`,
  });

  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}/attachments`, {
    waitUntil: "domcontentloaded",
  });

  const uploadLabel = page.getByTestId("attachment-upload");
  const uploadInput = uploadLabel.locator('input[type="file"]');
  await expect(uploadLabel).toContainText("Upload document");

  let requestCount = 0;
  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  const routePattern = new RegExp(`/api/patients/${patientId}/attachments$`);

  await page.route(routePattern, async (route, request) => {
    if (request.method() !== "POST") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenRequest();
    }
    await releaseResponsePromise;
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        id: 99_002,
        patient_id: patientId,
        original_filename: "upload-proof.pdf",
        content_type: "application/pdf",
        byte_size: 34,
        created_at: "2026-03-18T12:34:56Z",
        created_by: {
          id: 1,
          email: "admin@example.com",
          role: "superadmin",
        },
      }),
    });
  });

  await page.evaluate(() => {
    const input = document.querySelector(
      '[data-testid="attachment-upload"] input[type="file"]'
    );
    if (!(input instanceof HTMLInputElement)) {
      throw new Error("Upload input not found");
    }
    const pdfBytes = new Uint8Array([
      0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x34, 0x0a, 0x25, 0x25, 0x45, 0x4f, 0x46,
    ]);
    const file = new File([pdfBytes], "upload-proof.pdf", {
      type: "application/pdf",
    });
    const triggerUpload = () => {
      const transfer = new DataTransfer();
      transfer.items.add(file);
      Object.defineProperty(input, "files", {
        configurable: true,
        value: transfer.files,
      });
      input.dispatchEvent(new Event("change", { bubbles: true }));
    };
    triggerUpload();
    triggerUpload();
  });
  await seenRequestPromise;

  await expect(uploadLabel).toContainText("Uploading...");
  await expect(uploadInput).toBeDisabled();
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();

  await expect(page.getByTestId("attachment-card-99002")).toBeVisible({ timeout: 15_000 });
  await expect(uploadLabel).toContainText("Upload document");
  await expect(uploadInput).toBeEnabled({ timeout: 15_000 });
  await page.unroute(routePattern);
});

test("patient attachment download shows in-flight state and honors header filename", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Docs",
    last_name: `Attach Download ${Date.now()}`,
  });

  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}/attachments`, {
    waitUntil: "domcontentloaded",
  });

  const uploadInput = page
    .getByTestId("attachment-upload")
    .locator("input[type=\"file\"]");
  const fixturePath = path.resolve(__dirname, "fixtures", "sample.pdf");
  await uploadInput.setInputFiles(fixturePath);

  const token = await ensureAuthReady(request);
  let attachmentId: number | null = null;
  await expect
    .poll(
      async () => {
        const response = await request.get(
          `${getBaseUrl()}/api/patients/${patientId}/attachments`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!response.ok()) {
          return null;
        }
        const items = (await response.json()) as {
          id: number;
          original_filename: string;
        }[];
        const match = items.find((item) => item.original_filename === "sample.pdf");
        attachmentId = match?.id ?? null;
        return attachmentId;
      },
      { timeout: 20_000 }
    )
    .not.toBeNull();
  if (attachmentId === null) {
    throw new Error("Attachment id not available after upload");
  }

  const downloadButton = page.getByTestId(`attachment-download-${attachmentId}`);
  await expect(downloadButton).toBeVisible({ timeout: 15_000 });

  const expectedFilename = "attachment-header-proof.pdf";
  const routePattern = new RegExp(`/api/attachments/${attachmentId}/download$`);

  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  let requestCount = 0;

  await page.route(routePattern, async (route) => {
    requestCount += 1;
    if (requestCount === 1) {
      seenRequest();
    }
    await releaseResponsePromise;
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": `attachment; filename="${expectedFilename}"`,
      },
      body: Buffer.from("%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"),
    });
  });

  const downloadPromise = page.waitForEvent("download");
  const clickState = await page.evaluate((id) => {
    const button = document.querySelector(`[data-testid="attachment-download-${id}"]`);
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Download button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  }, attachmentId);
  await seenRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(downloadButton).toBeDisabled();
  await expect(downloadButton).toHaveText("Downloading...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(downloadButton).toBeEnabled({ timeout: 15_000 });
  await expect(downloadButton).toHaveText("Download");
  await page.unroute(routePattern);
});

test("patient attachment download falls back to backend-sanitized filename without header", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Docs",
    last_name: `Attach Fallback ${Date.now()}`,
  });

  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}/attachments`, {
    waitUntil: "domcontentloaded",
  });

  const originalFilename = "Attachment fallback proof.pdf";
  const uploadInput = page
    .getByTestId("attachment-upload")
    .locator("input[type=\"file\"]");
  await uploadInput.setInputFiles({
    name: originalFilename,
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"),
  });

  const token = await ensureAuthReady(request);
  let attachmentId: number | null = null;
  await expect
    .poll(
      async () => {
        const response = await request.get(
          `${getBaseUrl()}/api/patients/${patientId}/attachments`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!response.ok()) {
          return null;
        }
        const items = (await response.json()) as {
          id: number;
          original_filename: string;
        }[];
        const match = items.find((item) => item.original_filename === originalFilename);
        attachmentId = match?.id ?? null;
        return attachmentId;
      },
      { timeout: 20_000 }
    )
    .not.toBeNull();
  if (attachmentId === null) {
    throw new Error("Attachment id not available after upload");
  }

  const downloadButton = page.getByTestId(`attachment-download-${attachmentId}`);
  await expect(downloadButton).toBeVisible({ timeout: 15_000 });

  const expectedFilename = "Attachment_fallback_proof.pdf";
  const routePattern = new RegExp(`/api/attachments/${attachmentId}/download$`);

  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });

  await page.route(routePattern, async (route) => {
    seenRequest();
    await releaseResponsePromise;
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
      },
      body: Buffer.from("%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"),
    });
  });

  const downloadPromise = page.waitForEvent("download");
  await downloadButton.click();
  await seenRequestPromise;

  await expect(downloadButton).toBeDisabled();
  await expect(downloadButton).toHaveText("Downloading...");

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(downloadButton).toBeEnabled({ timeout: 15_000 });
  await expect(downloadButton).toHaveText("Download");
  await page.unroute(routePattern);
});

test("patient attachment preview shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Docs",
    last_name: `Attach Preview ${Date.now()}`,
  });

  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}/attachments`, {
    waitUntil: "domcontentloaded",
  });

  const uploadInput = page
    .getByTestId("attachment-upload")
    .locator('input[type="file"]');
  const fixturePath = path.resolve(__dirname, "fixtures", "sample.pdf");
  await uploadInput.setInputFiles(fixturePath);

  const token = await ensureAuthReady(request);
  let attachmentId: number | null = null;
  await expect
    .poll(
      async () => {
        const response = await request.get(
          `${getBaseUrl()}/api/patients/${patientId}/attachments`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!response.ok()) {
          return null;
        }
        const items = (await response.json()) as {
          id: number;
          original_filename: string;
        }[];
        const match = items.find((item) => item.original_filename === "sample.pdf");
        attachmentId = match?.id ?? null;
        return attachmentId;
      },
      { timeout: 20_000 }
    )
    .not.toBeNull();
  if (attachmentId === null) {
    throw new Error("Attachment id not available after upload");
  }

  const previewButton = page.getByTestId(`attachment-preview-${attachmentId}`);
  await expect(previewButton).toBeVisible({ timeout: 15_000 });

  await page.evaluate(() => {
    const state = window as typeof window & { __previewOpenCount?: number };
    state.__previewOpenCount = 0;
    window.open = () => {
      state.__previewOpenCount = (state.__previewOpenCount ?? 0) + 1;
      return null;
    };
  });

  let requestCount = 0;
  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  const routePattern = new RegExp(`/api/attachments/${attachmentId}/preview$`);

  await page.route(routePattern, async (route) => {
    requestCount += 1;
    if (requestCount === 1) {
      seenRequest();
    }
    await releaseResponsePromise;
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
      },
      body: Buffer.from("%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"),
    });
  });

  await page.evaluate((id) => {
    const button = document.querySelector(`[data-testid="attachment-preview-${id}"]`);
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Preview button not found");
    }
    button.click();
    button.click();
  }, attachmentId);
  await seenRequestPromise;

  await expect(previewButton).toBeDisabled();
  await expect(previewButton).toHaveText("Opening...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();

  await expect
    .poll(
      async () =>
        page.evaluate(
          () => (window as typeof window & { __previewOpenCount?: number }).__previewOpenCount ?? 0
        ),
      { timeout: 15_000 }
    )
    .toBe(1);
  await expect(previewButton).toBeEnabled({ timeout: 15_000 });
  await expect(previewButton).toHaveText("Preview");
  await page.unroute(routePattern);
});

test("patient attachment delete shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Docs",
    last_name: `Attach Delete ${Date.now()}`,
  });

  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}/attachments`, {
    waitUntil: "domcontentloaded",
  });

  const uploadInput = page
    .getByTestId("attachment-upload")
    .locator('input[type="file"]');
  const fixturePath = path.resolve(__dirname, "fixtures", "sample.pdf");
  await uploadInput.setInputFiles(fixturePath);

  const token = await ensureAuthReady(request);
  let attachmentId: number | null = null;
  await expect
    .poll(
      async () => {
        const response = await request.get(
          `${getBaseUrl()}/api/patients/${patientId}/attachments`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!response.ok()) {
          return null;
        }
        const items = (await response.json()) as {
          id: number;
          original_filename: string;
        }[];
        const match = items.find((item) => item.original_filename === "sample.pdf");
        attachmentId = match?.id ?? null;
        return attachmentId;
      },
      { timeout: 20_000 }
    )
    .not.toBeNull();
  if (attachmentId === null) {
    throw new Error("Attachment id not available after upload");
  }

  const row = page.getByTestId(`attachment-card-${attachmentId}`);
  const deleteButton = page.getByTestId(`attachment-delete-${attachmentId}`);
  await expect(row).toBeVisible({ timeout: 15_000 });
  await expect(deleteButton).toBeVisible();

  await page.evaluate(() => {
    window.confirm = () => true;
  });

  let requestCount = 0;
  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  const routePattern = new RegExp(`/api/attachments/${attachmentId}$`);

  await page.route(routePattern, async (route, routedRequest) => {
    if (routedRequest.method() !== "DELETE") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenRequest();
    }
    await releaseResponsePromise;
    await route.fulfill({
      status: 204,
      body: "",
    });
  });

  await page.evaluate((id) => {
    const button = document.querySelector(`[data-testid="attachment-delete-${id}"]`);
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Delete button not found");
    }
    button.click();
    button.click();
  }, attachmentId);
  await seenRequestPromise;

  await expect(deleteButton).toBeDisabled();
  await expect(deleteButton).toHaveText("Deleting...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();

  await expect(row).toHaveCount(0);
  await page.unroute(routePattern);
});
