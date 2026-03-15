import { expect, test, type Page } from "@playwright/test";

import { getBaseUrl, primePageAuth } from "./helpers/auth";

async function waitForAppointmentsPage(page: Page) {
  await expect(page.getByTestId("appointments-page")).toBeVisible({ timeout: 20_000 });
  await expect(page).not.toHaveURL(/\/login|\/change-password/);
}

async function switchToDayView(page: Page) {
  const explicit = page.getByTestId("appointments-calendar-view-day");
  if (await explicit.count()) {
    await explicit.click();
    return;
  }
  const fallback = page
    .locator(".rbc-toolbar button")
    .filter({ hasText: /^day$/i })
    .first();
  await expect(fallback).toBeVisible({ timeout: 10_000 });
  await fallback.click();
}

test("visit run sheet download uses a deterministic filename fallback and in-flight state", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const date = "2026-03-17";
  const routePattern = /\/api\/appointments\/run-sheet\.pdf\?/;

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/appointments?date=${date}&view=day`, {
    waitUntil: "domcontentloaded",
  });
  await waitForAppointmentsPage(page);
  await page.getByTestId("appointments-view-calendar").click();
  await switchToDayView(page);
  await page.getByRole("button", { name: "Visits" }).click();

  const runSheetButton = page.getByTestId("appointments-download-run-sheet");
  await expect(runSheetButton).toBeVisible({ timeout: 15_000 });

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
        "Content-Disposition": 'attachment; filename="run-sheet.pdf"',
      },
      body: Buffer.from("%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"),
    });
  });

  const downloadPromise = page.waitForEvent("download");
  await runSheetButton.click();
  await seenRequestPromise;

  await expect(runSheetButton).toBeDisabled();
  await expect(runSheetButton).toHaveText("Downloading run sheet...");

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(`run-sheet-visit-${date}.pdf`);

  await expect(runSheetButton).toBeEnabled({ timeout: 15_000 });
  await expect(runSheetButton).toHaveText("Download run sheet");
  await page.unroute(routePattern);
});
