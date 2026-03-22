import { expect, test, type Locator, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";
import { installClipboardCapture, readClipboardCapture } from "./helpers/clipboard";

const chartingEnabled = process.env.NEXT_PUBLIC_FEATURE_CHARTING_VIEWER === "1";

function getNotesPanel(page: Page) {
  return page
    .locator("section.panel")
    .filter({ has: page.locator(".panel-title", { hasText: "Patient notes" }) });
}

function getPanelInput(panel: Locator, label: string) {
  return panel
    .locator("label", { hasText: label })
    .locator("xpath=..")
    .locator("input");
}

test("patient charting export shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  test.skip(!chartingEnabled, "charting viewer disabled");
  const configRes = await request.get(`${baseUrl}/api/config`);
  const config = (await configRes.json()) as {
    feature_flags?: { charting_viewer?: boolean };
  };
  test.skip(!config?.feature_flags?.charting_viewer, "charting viewer disabled");
  const patientId = await createPatient(request, {
    first_name: "Charting",
    last_name: "ExportGuard",
  });

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/charting`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/charting`));
  await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 15_000 });

  const exportButton = page.getByTestId("charting-export-csv");
  await expect(exportButton).toBeVisible({ timeout: 15_000 });

  const expectedFilename = `charting-${patientId}-export.zip`;
  const routePattern = new RegExp(`/api/patients/${patientId}/charting/export\\?`);

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
        "Content-Type": "application/zip",
        "Content-Disposition": `attachment; filename="${expectedFilename}"`,
      },
      body: Buffer.from("PK\x03\x04charting-export"),
    });
  });

  const downloadPromise = page.waitForEvent("download");
  const clickState = await page.evaluate(() => {
    const button = document.querySelector('[data-testid="charting-export-csv"]');
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Charting export button not found");
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
  await expect(exportButton).toBeDisabled();
  await expect(exportButton).toHaveText("Exporting...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(exportButton).toBeEnabled({ timeout: 15_000 });
  await expect(exportButton).toHaveText("Export CSV");
  await page.unroute(routePattern);
});

test("patient charting export falls back to backend-contract filename without header", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  test.skip(!chartingEnabled, "charting viewer disabled");
  const configRes = await request.get(`${baseUrl}/api/config`);
  const config = (await configRes.json()) as {
    feature_flags?: { charting_viewer?: boolean };
  };
  test.skip(!config?.feature_flags?.charting_viewer, "charting viewer disabled");
  const patientId = await createPatient(request, {
    first_name: "Charting",
    last_name: "ExportFallback",
  });
  const legacyPatientCode = 1012056;

  const metaRoutePattern = new RegExp(`/api/patients/${patientId}/charting/meta(?:\\?.*)?$`);
  await page.route(metaRoutePattern, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        patient_id: patientId,
        legacy_patient_code: legacyPatientCode,
        last_imported_at: "2024-07-04T10:00:00Z",
        source: "r4",
      }),
    });
  });

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/charting`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/charting`));
  await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Legacy code")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(String(legacyPatientCode))).toBeVisible({ timeout: 15_000 });

  const exportButton = page.getByTestId("charting-export-csv");
  await expect(exportButton).toBeVisible({ timeout: 15_000 });

  const expectedFilename = `charting_${legacyPatientCode}_${new Date()
    .toISOString()
    .slice(0, 10)}.zip`;
  const routePattern = new RegExp(`/api/patients/${patientId}/charting/export\\?`);
  await page.route(routePattern, async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "application/zip",
      },
      body: Buffer.from("PK\x03\x04charting-export-fallback"),
    });
  });

  const downloadPromise = page.waitForEvent("download");
  await exportButton.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await page.unroute(routePattern);
  await page.unroute(metaRoutePattern);
});

test("patient charting review pack shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  test.skip(!chartingEnabled, "charting viewer disabled");
  const configRes = await request.get(`${baseUrl}/api/config`);
  const config = (await configRes.json()) as {
    feature_flags?: { charting_viewer?: boolean };
  };
  test.skip(!config?.feature_flags?.charting_viewer, "charting viewer disabled");
  const patientId = await createPatient(request, {
    first_name: "Charting",
    last_name: "ReviewPackGuard",
  });

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/charting`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/charting`));
  await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 15_000 });

  const reviewPackButton = page.getByTestId("charting-review-pack-generate");
  await expect(reviewPackButton).toBeVisible({ timeout: 15_000 });

  const expectedFilename = `charting-review-pack-${patientId}.zip`;
  const routePattern = new RegExp(`/api/patients/${patientId}/charting/export\\?`);

  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  let requestCount = 0;
  let seenUrl = "";

  await page.route(routePattern, async (route) => {
    requestCount += 1;
    seenUrl = decodeURIComponent(route.request().url());
    if (requestCount === 1) {
      seenRequest();
    }
    await releaseResponsePromise;
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": `attachment; filename="${expectedFilename}"`,
      },
      body: Buffer.from("PK\x03\x04charting-review-pack"),
    });
  });

  const downloadPromise = page.waitForEvent("download");
  const clickState = await page.evaluate(() => {
    const button = document.querySelector('[data-testid="charting-review-pack-generate"]');
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Charting review-pack button not found");
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
  expect(seenUrl).toContain(
    "entities=perio_probes,bpe,bpe_furcations,patient_notes,tooth_surfaces"
  );
  await expect(reviewPackButton).toBeDisabled();
  await expect(reviewPackButton).toHaveText("Generating...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(page.getByText("Review pack ready. Share links exclude text search by default."))
    .toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Review pack links")).toBeVisible();
  const reviewPackLinks = await page.locator("input.input").evaluateAll((elements) =>
    elements.map((element) => (element as HTMLInputElement).value)
  );
  expect(
    reviewPackLinks.filter((value) => value.includes(`/patients/${patientId}/charting?`))
      .length
  ).toBe(4);
  await expect(reviewPackButton).toBeEnabled({ timeout: 15_000 });
  await expect(reviewPackButton).toHaveText("Generate review pack");
  await page.unroute(routePattern);
});

test("patient charting review pack notes link excludes text search by default", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  test.skip(!chartingEnabled, "charting viewer disabled");
  const configRes = await request.get(`${baseUrl}/api/config`);
  const config = (await configRes.json()) as {
    feature_flags?: { charting_viewer?: boolean };
  };
  test.skip(!config?.feature_flags?.charting_viewer, "charting viewer disabled");
  const patientId = await createPatient(request, {
    first_name: "Charting",
    last_name: "ReviewPackLinks",
  });

  await primePageAuth(page, request);
  await installClipboardCapture(page, "reviewPackNotesLink");
  await page.goto(`${baseUrl}/patients/${patientId}/charting`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/charting`));
  await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 15_000 });

  const notesPanel = getNotesPanel(page);
  await expect(notesPanel).toBeVisible({ timeout: 15_000 });

  const fromInput = getPanelInput(notesPanel, "From");
  const toInput = getPanelInput(notesPanel, "To");
  await expect(fromInput).toBeVisible({ timeout: 15_000 });
  await expect(toInput).toBeVisible({ timeout: 15_000 });
  await fromInput.fill("2024-07-02");
  await toInput.fill("2024-07-03");
  await notesPanel.getByPlaceholder("Find text...").fill("note 1");
  await notesPanel.getByLabel("Include text search in link").check();

  const expectedFilename = `charting-review-pack-links-${patientId}.zip`;
  const routePattern = new RegExp(`/api/patients/${patientId}/charting/export\\?`);
  await page.route(routePattern, async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": `attachment; filename="${expectedFilename}"`,
      },
      body: Buffer.from("PK\x03\x04charting-review-pack-links"),
    });
  });

  const downloadPromise = page.waitForEvent("download");
  await page.getByTestId("charting-review-pack-generate").click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(page.getByText("Review pack ready. Share links exclude text search by default."))
    .toBeVisible({ timeout: 15_000 });

  const copyNotesLinkButton = page.getByTestId("charting-review-pack-copy-patient-notes");
  await expect(copyNotesLinkButton).toBeVisible({ timeout: 15_000 });
  await copyNotesLinkButton.focus();
  await page.keyboard.press("Enter");
  const copied = await readClipboardCapture(page, "reviewPackNotesLink");
  expect(copied).not.toBeNull();
  if (copied) {
    expect(copied).toContain(`/patients/${patientId}/charting?`);
    expect(copied).toContain("charting_notes_from=2024-07-02");
    expect(copied).toContain("charting_notes_to=2024-07-03");
    expect(copied).toContain("v=1");
    expect(copied).not.toContain("charting_notes_q=");
    expect(copied).not.toContain("charting_notes_q_inc=1");
  }
  await page.unroute(routePattern);
});
