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

  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("clinical-chart-toggle")).toBeVisible();

  const viewHistory = page.getByTestId("clinical-chart-view-history");
  await viewHistory.click();
  await expect(viewHistory).toHaveAttribute("data-active", "true");

  await expect(page.getByTestId("tooth-badge-11")).toBeVisible({ timeout: 15_000 });
});
