import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("recalls contact log save shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const token = await ensureAuthReady(request);
  const unique = Date.now();
  const patientId = await createPatient(request, {
    first_name: "Recall",
    last_name: `Contact Hardening ${unique}`,
  });
  const dueDate = new Date().toISOString().slice(0, 10);
  const recallNotes = `Recall contact hardening proof ${unique}`;
  const recallResponse = await request.post(`${baseUrl}/api/patients/${patientId}/recalls`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: "exam",
      due_date: dueDate,
      notes: recallNotes,
    },
  });
  expect(recallResponse.ok()).toBeTruthy();
  const recall = (await recallResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/recalls`, { waitUntil: "domcontentloaded" });

  const row = page.locator("tr", { hasText: recallNotes });
  await expect(row).toBeVisible({ timeout: 15_000 });

  await row.getByRole("button", { name: "Log contact" }).click();

  const modalHeading = page.getByRole("heading", { name: "Log contact" });
  const saveButton = page.getByTestId("recalls-contact-save");
  const outcomeField = page.locator('label:has-text("Outcome") + input');
  const noteField = page.locator('label:has-text("Note") + textarea');
  const outcome = `Spoke to patient ${unique}`;
  const note = `Recall contact note ${unique}`;

  await expect(modalHeading).toBeVisible({ timeout: 15_000 });
  await expect(saveButton).toBeEnabled();
  await outcomeField.fill(outcome);
  await noteField.fill(note);

  const routePattern = new RegExp(`/api/recalls/${recall.id}/contact$`);
  let requestCount = 0;
  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseRequest!: () => void;
  const releaseRequestPromise = new Promise<void>((resolve) => {
    releaseRequest = resolve;
  });

  await page.route(routePattern, async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      expect(route.request().postDataJSON()).toMatchObject({
        method: "phone",
        other_detail: null,
        outcome,
        note,
      });
      seenRequest();
      await releaseRequestPromise;
    }
    await route.continue();
  });

  const saveResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/api/recalls/${recall.id}/contact`)
  );

  const clickState = await saveButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Recall contact save button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(saveButton).toBeDisabled();
  await expect(saveButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseRequest();

  const saveResponse = await saveResponsePromise;
  expect(saveResponse.ok()).toBeTruthy();
  await page.unroute(routePattern);

  await expect(modalHeading).toHaveCount(0, { timeout: 15_000 });

  const verifyResponse = await request.get(
    `${baseUrl}/api/recalls?status=due,overdue&limit=50&offset=0`,
    {
      headers: { Authorization: `Bearer ${token}` },
    }
  );
  expect(verifyResponse.ok()).toBeTruthy();
  const recalls = (await verifyResponse.json()) as Array<{
    id: number;
    last_contacted_at?: string | null;
    last_contact_channel?: string | null;
    last_contact_outcome?: string | null;
    last_contact_note?: string | null;
  }>;
  const updatedRecall = recalls.find((item) => item.id === recall.id);
  expect(updatedRecall).toBeTruthy();
  expect(updatedRecall?.last_contacted_at).toBeTruthy();
  expect(updatedRecall?.last_contact_channel).toBe("phone");
  expect(updatedRecall?.last_contact_outcome).toBe(outcome);
  expect(updatedRecall?.last_contact_note).toBe(note);
});
