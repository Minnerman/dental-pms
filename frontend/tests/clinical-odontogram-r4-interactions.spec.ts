import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

test("odontogram keeps its size and separates anatomy from the surface map", async ({
  page,
  request,
}) => {
  await primePageAuth(page, request);
  const patientId = await createPatient(request, {
    first_name: "Anatomy",
    last_name: `Chart ${Date.now()}`,
  });

  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });

  const ur6Button = page.getByTestId("tooth-button-UR6");
  const ur6Svg = page.getByTestId("tooth-svg-UR6");
  const beforeSelection = await ur6Svg.boundingBox();
  expect(beforeSelection).not.toBeNull();

  await expect(page.getByTestId("tooth-anatomy-UR6")).toHaveAttribute(
    "data-anatomy-parts",
    "crown root"
  );
  await expect(page.getByTestId("tooth-crown-UR6")).toBeAttached();
  await expect(page.getByTestId("tooth-root-UR6-1")).toBeAttached();
  await expect(page.getByTestId("tooth-root-UR6-2")).toBeAttached();
  await expect(page.getByTestId("tooth-root-UR6-3")).toBeAttached();
  await expect(page.getByTestId("tooth-surface-map-UR6")).toBeAttached();

  const upperAnatomy = await page.getByTestId("tooth-anatomy-UR6").boundingBox();
  const upperSurfaceMap = await page.getByTestId("tooth-surface-map-UR6").boundingBox();
  const lowerAnatomy = await page.getByTestId("tooth-anatomy-LR6").boundingBox();
  const lowerSurfaceMap = await page.getByTestId("tooth-surface-map-LR6").boundingBox();
  expect(upperAnatomy).not.toBeNull();
  expect(upperSurfaceMap).not.toBeNull();
  expect(lowerAnatomy).not.toBeNull();
  expect(lowerSurfaceMap).not.toBeNull();
  expect((upperAnatomy?.y ?? 0) < (upperSurfaceMap?.y ?? 0)).toBeTruthy();
  expect((lowerSurfaceMap?.y ?? 0) < (lowerAnatomy?.y ?? 0)).toBeTruthy();

  await ur6Button.click();
  await expect(ur6Button).toHaveAttribute("data-selected", "true");
  const afterSelection = await ur6Svg.boundingBox();
  expect(afterSelection).not.toBeNull();
  expect(afterSelection?.width).toBeCloseTo(beforeSelection?.width ?? 0, 1);
  expect(afterSelection?.height).toBeCloseTo(beforeSelection?.height ?? 0, 1);
  expect((afterSelection?.height ?? 0) > (afterSelection?.width ?? 0)).toBeTruthy();

  await page.getByTestId("tooth-button-LL6").click();
  await expect(page.getByTestId("tooth-button-LL6")).toHaveAttribute("data-selected", "true");

  await expect(page.getByTestId("tooth-root-LR6-1")).toBeAttached();
  await expect(page.getByTestId("tooth-root-LR6-2")).toBeAttached();
  await expect(page.getByTestId("tooth-root-LR6-3")).toHaveCount(0);
  await expect(page.getByTestId("tooth-root-LR5-1")).toBeAttached();
  await expect(page.getByTestId("tooth-root-LR5-2")).toHaveCount(0);
});

test("planned chart whole-tooth and surface actions are available by click and right-click", async ({
  page,
  request,
}) => {
  await primePageAuth(page, request);
  const patientId = await createPatient(request, {
    first_name: "Context",
    last_name: `Menu ${Date.now()}`,
  });

  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical?clinicalView=planned`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });

  const ur5Button = page.getByTestId("tooth-button-UR5");
  await ur5Button.click({ button: "right", position: { x: 6, y: 6 } });
  const toothMenu = page.getByTestId("clinical-tooth-action-menu");
  await expect(toothMenu).toBeVisible();
  await expect(toothMenu).toContainText("UR5 · Whole tooth");
  await expect(page.getByTestId("clinical-chart-menu-add-note")).toBeVisible();
  await expect(page.getByTestId("clinical-chart-menu-add-procedure")).toBeVisible();
  await expect(page.getByTestId("clinical-chart-menu-add-plan")).toBeVisible();

  await page.getByTestId("clinical-chart-menu-add-note").click();
  await expect(page.getByTestId("patient-chart-note-body")).toBeFocused();

  const ur5M = page.getByTestId("tooth-surface-UR5-M");
  const ur5D = page.getByTestId("tooth-surface-UR5-D");
  await ur5M.click();
  await expect(ur5M).toHaveAttribute("data-selected", "true");
  await ur5D.click();
  await ur5D.click({ button: "right" });
  await expect(page.getByTestId("clinical-surface-action-menu")).toContainText(
    "UR5 · Surfaces MD"
  );
  await expect(ur5M).toHaveAttribute("data-selected", "true");
  await expect(ur5D).toHaveAttribute("data-selected", "true");
});
