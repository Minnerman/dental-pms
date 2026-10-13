import { expect, test } from "@playwright/test";
import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test.use({ channel: "chromium" });
test.setTimeout(60_000);

test("printing a recall creates a clinical note opening the exact saved PDF; cancel creates none", async ({ page, request }, testInfo) => {
  const base = getBaseUrl();
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: "PrintedRecall" });
  const token = await ensureAuthReady(request);
  const headers = { Authorization: `Bearer ${token}` };
  const templates = await (await request.get(`${base}/api/document-templates`, { headers })).json();
  const template = templates.find((row: {name: string}) => row.name === "Recall - 6 months");
  const created = await request.post(`${base}/api/patients/${patientId}/documents`, { headers, data: { template_id: template.id } });
  expect(created.status()).toBe(201);
  const document = await created.json();
  const original = await (await request.get(`${base}/api/patient-documents/${document.id}/download?format=pdf`, { headers })).body();
  await primePageAuth(page, request);
  await page.goto(`${base}/patients/${patientId}/documents`);
  await expect(page.getByRole("button", { name: "Email recall (off)" })).toBeDisabled();
  await page.getByTestId(`document-print-${document.id}`).click();
  await expect(page).toHaveURL(/document-copies\/\d+$/);
  await expect(page.getByTestId("confirm-document-print")).toBeDisabled();
  let notes = await (await request.get(`${base}/api/patients/${patientId}/notes`, { headers })).json();
  expect(notes).toHaveLength(0);
  // Leaving the preview without confirming (including a cancelled print dialog) records nothing.
  await page.getByRole("link", { name: "Back to patient documents" }).click();
  await page.getByTestId(`document-print-${document.id}`).click();
  await expect(page.locator('iframe[title="Saved document PDF"]')).toBeVisible();
  await page.getByTestId("open-print-dialog").click();
  await page.getByTestId("confirm-document-print").click();
  await expect(page.getByRole("status")).toHaveText("Printed and recorded in clinical notes.");
  notes = await (await request.get(`${base}/api/patients/${patientId}/notes`, { headers })).json();
  expect(notes).toHaveLength(1);
  expect(notes[0].note_type).toBe("clinical");
  const copyId = notes[0].document_copy_id;
  const pdf = await request.get(`${base}/api/document-copies/${copyId}/pdf`, { headers });
  expect(await pdf.body()).toEqual(original);
  await page.goto(`${base}/notes?note=${notes[0].id}`);
  await expect(page.getByTestId("note-detail-readonly")).toBeVisible();
  await expect(page.getByTestId("note-detail-archive")).toHaveCount(0);
  await page.getByRole("link", { name: /Printed: Recall - 6 months/ }).click();
  await expect(page).toHaveURL(new RegExp(`/document-copies/${copyId}$`));
  await expect(page.getByRole("status")).toHaveText("Printed and recorded in clinical notes.");
  await page.screenshot({ path: testInfo.outputPath("saved-recall-copy.png"), fullPage: true });
});

test("both Clindamycin strengths populate separately and require a patient quantity", async ({ page, request }) => {
  const base = getBaseUrl();
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: "PrescriptionQuantity" });
  await primePageAuth(page, request);
  await page.goto(`${base}/patients/${patientId}/documents`);
  await page.getByTestId("patient-document-template-select").selectOption({ label: "Private Prescription - typed (Prescription)" });
  const library = page.getByTestId("prescription-saved-template");
  for (const strength of ["150", "300"]) {
    await library.selectOption({ label: `Clindamycin ${strength} mg capsules` });
    await expect(page.getByTestId("prescription-medicine")).toHaveValue(`Clindamycin ${strength} mg capsules`);
    await expect(page.getByTestId("prescription-directions")).toHaveValue("Take one capsule every six hours.");
    await expect(page.getByTestId("prescription-quantity")).toHaveValue("");
    await page.getByTestId("patient-document-save").click();
    await expect(page.getByText(/Enter quantity before previewing or saving/i)).toBeVisible();
  }
});

test("liquid amoxicillin choices use 5 mL three times a day and require total supply", async ({ page, request }) => {
  const base = getBaseUrl();
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: "LiquidPrescription" });
  await primePageAuth(page, request);
  await page.goto(`${base}/patients/${patientId}/documents`);
  await page.getByTestId("patient-document-template-select").selectOption({ label: "Private Prescription - typed (Prescription)" });
  const library = page.getByTestId("prescription-saved-template");
  for (const medicine of ["Amoxicillin 250 mg/5 mL oral suspension (sugar free)", "Amoxicillin 500 mg/5 mL oral suspension"]) {
    await library.selectOption({ label: medicine });
    await expect(page.getByTestId("prescription-medicine")).toHaveValue(medicine);
    await expect(page.getByTestId("prescription-directions")).toHaveValue("Take 5 mL three times a day.");
    await expect(page.getByTestId("prescription-quantity")).toHaveValue("");
    await expect(page.getByText("Enter the total volume to supply in mL.")).toBeVisible();
    await page.getByTestId("patient-document-save").click();
    await expect(page.getByText(/Enter quantity before previewing or saving/i)).toBeVisible();
    // Choosing the next liquid must clear the previous patient's/draft's supply.
    await page.getByTestId("prescription-quantity").fill("100 mL");
  }
  await page.getByTestId("prescription-prescriber_name").fill("Synthetic Dentist");
  await page.getByTestId("prescription-prescriber_gdc").fill("TEST ONLY");
  await page.getByTestId("patient-document-preview").click();
  await expect(page.locator("textarea[readonly]")).toHaveValue(/Take 5 mL three times a day\./);
  await expect(page.locator("textarea[readonly]")).toHaveValue(/Quantity: 100 mL/);
});
