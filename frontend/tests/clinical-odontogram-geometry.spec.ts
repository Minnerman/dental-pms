import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

test("odontogram surface clicks build a multi-surface selection", async ({
  page,
  request,
}) => {
  await primePageAuth(page, request);
  const patientId = await createPatient(request, {
    first_name: "Geometry",
    last_name: `Surface ${Date.now()}`,
  });

  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical?clinicalView=planned`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/clinical`));
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });

  const ur5M = page.getByTestId("tooth-surface-UR5-M");
  const ur5D = page.getByTestId("tooth-surface-UR5-D");
  const ur6M = page.getByTestId("tooth-surface-UR6-M");

  await ur5M.click();
  await expect(ur5M).toHaveAttribute("data-selected", "true");
  await expect(ur5D).toHaveAttribute("data-selected", "false");
  await expect(ur6M).toHaveAttribute("data-selected", "false");

  await ur5D.click();
  await expect(ur5D).toHaveAttribute("data-selected", "true");
  await expect(ur5M).toHaveAttribute("data-selected", "true");
  await expect(page.getByTestId("clinical-selection-state")).toContainText("Surfaces MD");

  await ur6M.click();
  await expect(ur6M).toHaveAttribute("data-selected", "true");
  await expect(ur5D).toHaveAttribute("data-selected", "false");
  await expect(ur5M).toHaveAttribute("data-selected", "false");
});
