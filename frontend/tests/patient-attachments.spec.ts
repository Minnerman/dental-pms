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

  const row = page.locator(".card", { hasText: "sample.pdf" }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });

  const uploadResponse = await page.waitForResponse(
    (response) =>
      response.url().includes(`/api/patients/${patientId}/attachments`) &&
      response.request().method() === "POST"
  );
  const created = (await uploadResponse.json()) as { id: number };

  const [previewPage] = await Promise.all([
    page.waitForEvent("popup"),
    row.getByRole("button", { name: "Preview" }).click(),
  ]);
  const token = await ensureAuthReady(request);
  const previewRes = await request.get(
    `${getBaseUrl()}/api/attachments/${created.id}/preview`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  expect(previewRes.ok()).toBeTruthy();
  await previewPage.close();

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    row.getByRole("button", { name: "Download" }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/sample\.pdf/i);

  page.once("dialog", (dialog) => dialog.accept());
  await row.getByRole("button", { name: "Delete" }).click();
  await expect(row).toHaveCount(0);
});
