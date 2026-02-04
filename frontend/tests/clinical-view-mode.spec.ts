import { expect, test } from "@playwright/test";

import {
  createClinicalProcedure,
  createPatient,
  createTreatmentPlanItem,
} from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

async function openClinical(page: any, request: any, patientId: string) {
  await primePageAuth(page, request);
  const baseUrl = getBaseUrl();
  await page.goto(`${baseUrl}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/clinical`));
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-chart-toggle")).toBeVisible();
}

test("clinical view mode persists across refresh and patient navigation", async ({
  page,
  request,
}) => {
  const patientA = await createPatient(request, {
    first_name: "Mode",
    last_name: `A ${Date.now()}`,
  });
  const patientB = await createPatient(request, {
    first_name: "Mode",
    last_name: `B ${Date.now()}`,
  });

  await openClinical(page, request, patientA);

  const viewHistory = page.getByTestId("clinical-chart-view-history");
  await viewHistory.click();
  await expect(viewHistory).toHaveAttribute("data-active", "true");
  await expect(page).toHaveURL(/clinicalView=history/);

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("clinical-chart-view-history")).toHaveAttribute(
    "data-active",
    "true"
  );

  await page.goto(`${getBaseUrl()}/patients/${patientB}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("clinical-chart-view-history")).toHaveAttribute(
    "data-active",
    "true"
  );
});

test("tooth badges remain stable across mode changes and refresh", async ({ page, request }) => {
  const patientId = await createPatient(request, {
    first_name: "Badge",
    last_name: `Stability ${Date.now()}`,
  });

  await createClinicalProcedure(request, patientId, { tooth: "UR1" });
  await createTreatmentPlanItem(request, patientId, {
    tooth: "UL1",
    procedure_code: "PLN1",
    description: "Planned UL1",
  });

  await openClinical(page, request, patientId);

  await expect(page.getByTestId("tooth-badge-UR1")).toContainText("H", { timeout: 30_000 });
  await expect(page.getByTestId("tooth-badge-UL1")).toContainText("P", { timeout: 30_000 });

  await page.getByTestId("clinical-chart-view-planned").click();
  await expect(page.getByTestId("clinical-chart-view-planned")).toHaveAttribute(
    "data-active",
    "true"
  );
  await expect(page).toHaveURL(/clinicalView=planned/);
  await expect(page.getByTestId("tooth-badge-UL1")).toContainText("P");
  await expect(page.getByTestId("tooth-badge-UR1")).toHaveCount(0);

  await page.getByTestId("clinical-chart-view-history").click();
  await expect(page.getByTestId("clinical-chart-view-history")).toHaveAttribute(
    "data-active",
    "true"
  );
  await expect(page).toHaveURL(/clinicalView=history/);
  await expect(page.getByTestId("tooth-badge-UR1")).toContainText("H");
  await expect(page.getByTestId("tooth-badge-UL1")).toHaveCount(0);

  await page.getByTestId("clinical-chart-view-current").click();
  await expect(page.getByTestId("clinical-chart-view-current")).toHaveAttribute(
    "data-active",
    "true"
  );
  await expect(page).not.toHaveURL(/clinicalView=/);

  const beforeRefreshUr1 = await page.getByTestId("tooth-badge-UR1").innerText();
  const beforeRefreshUl1 = await page.getByTestId("tooth-badge-UL1").innerText();

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("clinical-chart-view-current")).toHaveAttribute(
    "data-active",
    "true"
  );
  await expect(page.getByTestId("tooth-badge-UR1")).toHaveText(beforeRefreshUr1);
  await expect(page.getByTestId("tooth-badge-UL1")).toHaveText(beforeRefreshUl1);
});
