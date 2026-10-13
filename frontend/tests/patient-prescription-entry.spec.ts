import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("type a prescription, review changes, save its snapshot and download a PDF", async ({ page, request }, testInfo) => {
  const base = getBaseUrl();
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: "PrescriptionEntry" });
  const token = await ensureAuthReady(request);
  const headers = { Authorization: `Bearer ${token}` };
  const templatesResponse = await request.get(`${base}/api/document-templates`, { headers });
  expect(templatesResponse.ok()).toBeTruthy();
  const templates = await templatesResponse.json() as { id: number; name: string; content: string }[];
  const template = templates.find((row) => row.name === "Private Prescription - typed")!;
  const recall = templates.find((row) => row.name === "Recall - 6 months")!;
  expect(template).toBeTruthy();
  expect(recall).toBeTruthy();
  await primePageAuth(page, request);
  await page.goto(`${base}/patients/${patientId}/documents`);
  const select = page.getByTestId("patient-document-template-select");
  await select.selectOption(String(template.id));
  await page.getByTestId("patient-document-preview").click();
  await expect(page.getByText("Enter medicine name, strength and form before previewing or saving.")).toBeVisible();
  const details = {
    medicine: "Synthetic medicine - no clinical use",
    directions: "Synthetic directions\nSecond line",
    quantity: "Synthetic quantity",
    prescriber_name: "Synthetic Prescriber",
    prescriber_gdc: "TEST-ONLY",
  };
  for (const [key, value] of Object.entries(details)) {
    await page.getByTestId(`prescription-${key}`).fill(value);
  }
  const preview = page.locator("textarea[readonly]");
  await page.getByTestId("patient-document-preview").click();
  await expect(preview).toHaveValue(new RegExp(details.medicine));
  await expect(preview).toHaveValue(/Synthetic PrescriptionEntry/);
  await page.getByTestId("prescription-directions").fill("Revised synthetic directions");
  await expect(preview).toHaveCount(0);
  await page.getByTestId("patient-document-preview").click();
  await expect(preview).toHaveValue(/Revised synthetic directions/);
  await page.screenshot({ path: testInfo.outputPath("prescription-preview.png"), fullPage: true });
  const savedResponse = page.waitForResponse((response) =>
    response.url().endsWith(`/api/patients/${patientId}/documents`) && response.request().method() === "POST"
  );
  await page.getByTestId("patient-document-save").click();
  const response = await savedResponse;
  expect(response.status()).toBe(201);
  const saved = await response.json();
  expect(saved.rendered_content).toContain("Revised synthetic directions");
  expect(saved.rendered_content).toContain(details.medicine);
  for (const key of Object.keys(details)) await expect(page.getByTestId(`prescription-${key}`)).toHaveValue("");
  const downloadEvent = page.waitForEvent("download");
  await page.getByTestId(`patient-document-download-pdf-${saved.id}`).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  const path = await download.path();
  expect(path).toBeTruthy();
  expect((await readFile(path!)).subarray(0, 5).toString()).toBe("%PDF-");
  const unchanged = await request.get(`${base}/api/document-templates/${template.id}`, { headers });
  expect((await unchanged.json()).content).toBe(template.content);
  await page.getByTestId("prescription-medicine").fill("Discard this synthetic draft");
  await select.selectOption(String(recall.id));
  await expect(page.getByTestId("prescription-medicine")).toHaveCount(0);
  await select.selectOption(String(template.id));
  await expect(page.getByTestId("prescription-medicine")).toHaveValue("");
});
