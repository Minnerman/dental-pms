import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("recalls worklist mark completed shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Recall",
    last_name: `Complete ${Date.now()}`,
  });
  const token = await ensureAuthReady(request);
  const recallNotes = `Recalls complete proof ${Date.now()}`;

  const recallResponse = await request.post(`${baseUrl}/api/patients/${patientId}/recalls`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: "exam",
      due_date: "2026-03-22",
      status: "due",
      notes: recallNotes,
    },
  });
  expect(recallResponse.ok()).toBeTruthy();
  const recall = (await recallResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/recalls`, { waitUntil: "domcontentloaded" });

  const recallRow = page.locator("table tbody tr").filter({ hasText: recallNotes }).first();
  await expect(recallRow).toBeVisible({ timeout: 15_000 });
  const completeButton = recallRow.getByTestId(`recalls-complete-${recall.id}`);
  await expect(completeButton).toBeVisible();

  const routePattern = new RegExp(`/api/patients/${patientId}/recalls/${recall.id}$`);
  let requestCount = 0;
  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });

  await page.route(routePattern, async (route, routedRequest) => {
    if (routedRequest.method() !== "PATCH") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      expect(routedRequest.postDataJSON()).toMatchObject({
        status: "completed",
      });
      seenRequest();
    }
    await releaseResponsePromise;
    await route.continue();
  });

  const statusResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().endsWith(`/api/patients/${patientId}/recalls/${recall.id}`)
  );

  const clickState = await completeButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Mark completed button not found");
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
  await expect(completeButton).toBeDisabled();
  await expect(completeButton).toHaveText("Updating...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();
  const statusResponse = await statusResponsePromise;
  expect(statusResponse.ok()).toBeTruthy();

  await expect(recallRow).toHaveCount(0, { timeout: 15_000 });
  await page.unroute(routePattern);
});
