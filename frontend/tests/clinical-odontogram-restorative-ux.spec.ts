import fs from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

const artifactDir = process.env.RESTORATIVE_UX_ARTIFACT_DIR
  ? path.resolve(process.env.RESTORATIVE_UX_ARTIFACT_DIR)
  : path.resolve(__dirname, "..", "..", ".run", "stage163e");

test("restorative chart UX supports selection toggles, keyboard navigation, and undo/redo", async ({
  page,
  request,
}) => {
  fs.mkdirSync(artifactDir, { recursive: true });
  await primePageAuth(page, request);

  const patientId = await createPatient(request, {
    first_name: "Restorative",
    last_name: `UX ${Date.now()}`,
  });

  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/clinical`));
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-selection-toolbar")).toBeVisible();

  const toothUR5 = page.getByTestId("tooth-button-UR5");
  const toothUR4 = page.getByTestId("tooth-button-UR4");
  const ur5M = page.getByTestId("tooth-surface-UR5-M");
  const ur4D = page.getByTestId("tooth-surface-UR4-D");
  const selectionState = page.getByTestId("clinical-selection-state");

  await toothUR5.click();
  await expect(toothUR5).toHaveAttribute("data-selected", "true");

  await page.keyboard.press("m");
  await expect(ur5M).toHaveAttribute("data-selected", "true");
  await expect(selectionState).toContainText("Tooth UR5");
  await expect(selectionState).toContainText("Surface M");

  await page.keyboard.press("m");
  await expect(ur5M).toHaveAttribute("data-selected", "false");
  await expect(selectionState).toContainText("Surface None");

  await page.keyboard.press("ArrowRight");
  await expect(toothUR4).toHaveAttribute("data-selected", "true");
  await page.keyboard.press("d");
  await expect(ur4D).toHaveAttribute("data-selected", "true");

  const modKey = process.platform === "darwin" ? "Meta" : "Control";
  await page.keyboard.press(`${modKey}+z`);
  await expect(ur4D).toHaveAttribute("data-selected", "false");
  await expect(selectionState).toContainText("Tooth UR4");
  await expect(selectionState).toContainText("Surface None");

  await page.keyboard.press(`${modKey}+Shift+z`);
  await expect(ur4D).toHaveAttribute("data-selected", "true");
  await expect(selectionState).toContainText("Surface D");

  await page.screenshot({
    path: path.join(artifactDir, `odontogram_restorative_ux_${patientId}.png`),
    fullPage: true,
  });
});
