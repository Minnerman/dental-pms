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

  const metrics = await page.evaluate(() => {
    const rect = (selector: string) => document.querySelector(selector)?.getBoundingClientRect();
    const clinical = document.querySelector<HTMLElement>("[data-testid='patient-clinical-grid']");
    const chart = rect(".patient-route-chart-panel");
    const tools = rect(".patient-clinical-tools");
    return {
      shellHeaderHeight: rect(".app-top")?.height ?? 0,
      patientHeaderHeight: rect("[data-testid='patient-header-card']")?.height ?? 0,
      odontogramTop: chart?.top ?? Number.POSITIVE_INFINITY,
      chartWidth: chart?.width ?? 0,
      toolWidth: tools?.width ?? 0,
      clinicalColumnCount: clinical
        ? getComputedStyle(clinical).gridTemplateColumns.trim().split(/\s+/).length
        : 0,
      horizontalOverflow:
        document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });

  expect(metrics.shellHeaderHeight).toBeLessThanOrEqual(115);
  expect(metrics.patientHeaderHeight).toBeLessThanOrEqual(250);
  expect(metrics.odontogramTop).toBeLessThan(650);
  expect(metrics.clinicalColumnCount).toBe(2);
  expect(metrics.chartWidth).toBeGreaterThan(metrics.toolWidth * 2);
  expect(metrics.horizontalOverflow).toBe(0);
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
