import { test, expect } from "@playwright/test";

import { createClinicalProcedure, createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

test("clinical chart toggle renders tooth badges", async ({ page, request }) => {
  await primePageAuth(page, request);
  const patientId = await createPatient(request);
  await createClinicalProcedure(request, patientId, { tooth: "11" });
  const baseUrl = getBaseUrl();

  await page.goto(`${baseUrl}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/clinical`));
  await expect(page).not.toHaveURL(/\/(login|change-password)/, { timeout: 15_000 });

  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-chart-toggle")).toBeVisible();

  const viewHistory = page.getByTestId("clinical-chart-view-history");
  await viewHistory.click();
  await expect(viewHistory).toHaveAttribute("data-active", "true");

  const badgeIds = await page
    .locator('[data-testid^="tooth-badge-"]')
    .evaluateAll((elements) => elements.map((el) => el.getAttribute("data-testid")));
  console.log("TOOTH_BADGE_IDS", badgeIds);

  const badges = page.getByTestId(/^tooth-badge-/);
  await expect(async () => {
    const count = await badges.count();
    expect(count).toBeGreaterThan(0);
  }).toPass({ timeout: 30_000 });
});
