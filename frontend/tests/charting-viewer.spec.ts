import { test, expect } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

const chartingEnabled = process.env.NEXT_PUBLIC_FEATURE_CHARTING_VIEWER === "1";

test.skip(!chartingEnabled, "charting viewer disabled");

test("charting viewer renders read-only sections", async ({ page, request }) => {
  await primePageAuth(page, request);
  const patientId = await createPatient(request);
  const baseUrl = getBaseUrl();

  await page.goto(`${baseUrl}/patients/${patientId}/charting`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/charting`));
  await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("R4 charting viewer")).toBeVisible();
  await expect(page.getByText("Perio probes", { exact: true })).toBeVisible();
});
