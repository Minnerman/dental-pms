import path from "path";
import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

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

  await page.route(routePattern, async (route) => {
    seenRequest();
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
