import { expect, test, type Page } from "@playwright/test";

import { getBaseUrl, primePageAuth } from "./helpers/auth";
import { createPatient } from "./helpers/api";

async function waitForPatientNotesTab(page: Page, patientId: string) {
  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/clinical`));
  await expect(page.getByTestId("patient-tabs")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("patient-tab-Notes")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Loading patient…")).toHaveCount(0);
}

test("patient notes tab allows selecting admin note type on create", async ({ page, request }) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `NOTE${unique}`,
  });
  const noteBody = `Patient admin note ${unique}`;

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientNotesTab(page, patientId);

  await page.getByTestId("patient-tab-Notes").click();
  await expect(page.getByTestId("patient-tab-Notes")).toHaveAttribute("aria-selected", "true");

  await page.getByTestId("patient-note-type-select").selectOption("admin");
  await page.getByPlaceholder("Write a clinical or admin note...").fill(noteBody);

  const createRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === "POST" && request.url().includes(`/api/patients/${patientId}/notes`)
  );
  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/patients/${patientId}/notes`)
  );

  await page.getByRole("button", { name: "Add note" }).click();

  const createRequest = await createRequestPromise;
  const createResponse = await createResponsePromise;
  expect(createResponse.ok()).toBeTruthy();
  const createdNote = (await createResponse.json()) as { id: number };
  expect(createRequest.postDataJSON()).toMatchObject({
    body: noteBody,
    note_type: "admin",
  });

  const noteCard = page.getByText(noteBody, { exact: true }).locator("xpath=..");
  await expect(noteCard).toBeVisible({ timeout: 15_000 });
  await expect(noteCard.getByText("Admin", { exact: true })).toBeVisible({ timeout: 15_000 });

  await page.getByTestId(`patient-note-open-${createdNote.id}`).click();
  await expect(page).toHaveURL(new RegExp(`/notes\\?note=${createdNote.id}\\b`), {
    timeout: 15_000,
  });
  await expect(page.getByTestId("note-detail-type")).toHaveValue("admin");
  await expect(page.getByTestId("note-detail-body")).toHaveValue(noteBody);
});
