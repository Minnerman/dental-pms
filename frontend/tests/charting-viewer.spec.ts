import { test, expect } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

const chartingEnabled = process.env.NEXT_PUBLIC_FEATURE_CHARTING_VIEWER === "1";

test("charting viewer renders read-only sections", async ({ page, request }) => {
  test.skip(!chartingEnabled, "charting viewer disabled");
  const baseUrl = getBaseUrl();
  const configRes = await request.get(`${baseUrl}/api/config`);
  const config = (await configRes.json()) as {
    feature_flags?: { charting_viewer?: boolean };
  };
  test.skip(!config?.feature_flags?.charting_viewer, "charting viewer disabled");
  await primePageAuth(page, request);
  const patientId = await createPatient(request);

  await page.goto(`${baseUrl}/patients/${patientId}/charting`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/charting`));
  await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("R4 charting viewer")).toBeVisible();
  await page.waitForResponse(
    (response) =>
      response.url().includes(`/patients/${patientId}/charting/meta`) &&
      response.status() === 200,
    { timeout: 15_000 }
  );
  await page.waitForResponse(
    (response) =>
      response.url().includes(`/patients/${patientId}/charting/perio-probes`) &&
      response.status() === 200,
    { timeout: 15_000 }
  );
  await expect(
    page.locator(".badge", { hasText: "Perio probes:" }).first()
  ).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/Read-only view/i)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Patient not linked to R4 charting yet.")).toBeVisible();
});

test("charting viewer gating follows backend config", async ({ page, request }) => {
  const baseUrl = getBaseUrl();
  const configRes = await request.get(`${baseUrl}/api/config`);
  const config = (await configRes.json()) as {
    feature_flags?: { charting_viewer?: boolean };
  };
  const enabled = config?.feature_flags?.charting_viewer === true;

  await primePageAuth(page, request);
  const patientId = await createPatient(request);

  await page.goto(`${baseUrl}/patients/${patientId}`, {
    waitUntil: "domcontentloaded",
  });

  const chartingTab = page.getByTestId("patient-tab-charting");
  if (enabled) {
    await expect(chartingTab).toBeVisible();
  } else {
    await expect(chartingTab).toHaveCount(0);
    await page.goto(`${baseUrl}/patients/${patientId}/charting`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("charting-viewer")).toBeVisible();
    await expect(page.getByText("Charting viewer is disabled")).toBeVisible();
  }
});
