import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

test("desktop clinical workspace keeps the patient context compact and prioritises the odontogram", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Desktop",
    last_name: `Density ${Date.now()}`,
  });

  await page.setViewportSize({ width: 1280, height: 720 });
  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByTestId("patient-clinical-grid")).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".patient-route-chart-panel")).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".patient-clinical-tools")).toHaveCount(0);

  const metrics = await page.evaluate(() => {
    const rect = (selector: string) => document.querySelector(selector)?.getBoundingClientRect();
    const clinical = document.querySelector<HTMLElement>("[data-testid='patient-clinical-grid']");
    const chart = rect(".patient-route-chart-panel");
    return {
      shellHeaderHeight: rect(".app-top")?.height ?? 0,
      patientHeaderHeight: rect("[data-testid='patient-header-card']")?.height ?? 0,
      odontogramTop: chart?.top ?? Number.POSITIVE_INFINITY,
      chartWidth: chart?.width ?? 0,
      clinicalColumnCount: clinical
        ? getComputedStyle(clinical).gridTemplateColumns.trim().split(/\s+/).length
        : 0,
      horizontalOverflow:
        document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });

  expect(metrics.shellHeaderHeight).toBeLessThanOrEqual(115);
  expect(metrics.patientHeaderHeight).toBeLessThanOrEqual(160);
  expect(metrics.odontogramTop).toBeLessThan(480);
  expect(metrics.clinicalColumnCount).toBe(1);
  expect(metrics.chartWidth).toBeGreaterThan(950);
  expect(metrics.horizontalOverflow).toBe(0);

  await page.getByTestId("tooth-button-UR8").click();
  const tools = page.locator(".patient-clinical-tools");
  await expect(tools).toBeVisible();
  await expect(tools.getByRole("button", { name: "Close tooth tools" })).toBeVisible();
  await expect(page.getByTestId("patient-clinical-grid")).toHaveAttribute(
    "data-has-tooth-selection",
    "true"
  );
  await page.getByTestId("tooth-button-LL6").click();
  await expect(page.getByTestId("clinical-selection-toolbar")).toContainText("Tooth LL6");
  await tools.getByRole("button", { name: "Close tooth tools" }).click();
  await expect(page.locator(".patient-clinical-tools")).toHaveCount(0);
});

test("mobile patient route contains wide controls inside their own scrolling surfaces", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Mobile",
    last_name: `Density ${Date.now()}`,
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  const routeShell = page.getByTestId("patient-route-shell");
  await expect(page.getByTestId("patient-clinical-grid")).toBeVisible({ timeout: 20_000 });

  await expect
    .poll(() => routeShell.evaluate((element) => element.scrollWidth - element.clientWidth))
    .toBe(0);
});
