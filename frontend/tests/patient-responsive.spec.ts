import { expect, test, type Locator, type Page } from "@playwright/test";

import { createAppointment, createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

async function waitForPatientPage(page: Page, patientId: string) {
  await expect(page.getByTestId("patient-tabs")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Loading patient…")).toHaveCount(0);
  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}`));
}

async function expectNoHorizontalOverflow(locator: Locator) {
  await expect
    .poll(
      async () =>
        locator.evaluate((element) => element.scrollWidth - element.clientWidth),
      { timeout: 15_000 }
    )
    .toBe(0);
}

async function expectSingleColumnGrid(locator: Locator) {
  await expect
    .poll(
      async () =>
        locator.evaluate((element) => {
          const columns = getComputedStyle(element).gridTemplateColumns.trim();
          if (!columns || columns === "none") return 0;
          return columns.split(/\s+/).length;
        }),
      { timeout: 15_000 }
    )
    .toBe(1);
}

test("patient summary and detail views stay within viewport on narrow screens", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Responsive",
    last_name: `Patient ${Date.now()}`,
  });
  await createAppointment(request, patientId, {
    starts_at: "2026-04-15T10:00:00.000Z",
    ends_at: "2026-04-15T10:30:00.000Z",
    location_type: "clinic",
    location: "Room 4",
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientPage(page, patientId);

  const routeShell = page.getByTestId("patient-route-shell");
  const headerCard = page.getByTestId("patient-header-card");
  await expect(page.getByTestId("patient-header")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("patient-appointments")).toBeVisible({ timeout: 15_000 });
  await expect(routeShell).toBeVisible({ timeout: 15_000 });
  await expectSingleColumnGrid(page.getByTestId("patient-header"));
  await expectSingleColumnGrid(page.getByTestId("patient-appointment-card-grid").first());
  await expect
    .poll(
      async () => headerCard.evaluate((element) => getComputedStyle(element).position),
      { timeout: 15_000 }
    )
    .toBe("static");
  await expectNoHorizontalOverflow(routeShell);

  await page.getByText("Patient details", { exact: true }).click();
  await expect(page.getByTestId("patient-notes-field")).toBeVisible({ timeout: 15_000 });
  await expectNoHorizontalOverflow(routeShell);

  await page.getByRole("button", { name: "Book appointment" }).click();
  await expect(page.getByTestId("patient-booking-submit")).toBeVisible({ timeout: 15_000 });
  await expectSingleColumnGrid(page.getByTestId("patient-booking-grid"));
  await expectNoHorizontalOverflow(routeShell);
});

test("patient clinical route keeps page width stable and scrolls the chart inside its panel", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Responsive",
    last_name: `Clinical ${Date.now()}`,
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientPage(page, patientId);

  const routeShell = page.getByTestId("patient-route-shell");
  const clinicalGrid = page.getByTestId("patient-clinical-grid");
  await expect(page.getByText("Odontogram", { exact: true })).toBeVisible({ timeout: 20_000 });
  await expect(routeShell).toBeVisible({ timeout: 15_000 });
  await expect(clinicalGrid).toBeVisible({ timeout: 15_000 });
  await expectSingleColumnGrid(clinicalGrid);
  await expectNoHorizontalOverflow(routeShell);

  const chart = page.getByTestId("clinical-chart");
  await expect(chart).toBeVisible({ timeout: 15_000 });
  const chartOverflow = await chart.evaluate((element) => {
    const styles = window.getComputedStyle(element);
    const before = element.scrollLeft;
    element.scrollLeft = 120;
    return {
      overflowX: styles.overflowX,
      scrollLeft: element.scrollLeft,
      scrollWidth: element.scrollWidth,
      clientWidth: element.clientWidth,
      before,
    };
  });

  expect(["auto", "scroll"]).toContain(chartOverflow.overflowX);
  expect(chartOverflow.scrollWidth).toBeGreaterThan(chartOverflow.clientWidth);
  expect(chartOverflow.scrollLeft).toBeGreaterThan(chartOverflow.before);
  await expectNoHorizontalOverflow(routeShell);
});
