import { expect, test, type Page } from "@playwright/test";

import { createAppointment, createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

async function waitForPatientPage(page: Page, patientId: string) {
  await expect(page.getByTestId("patient-tabs")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Loading patient…")).toHaveCount(0);
  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}`));
}

async function expectNoDocumentHorizontalOverflow(page: Page) {
  await expect
    .poll(
      async () =>
        page.evaluate(() => {
          const doc = document.documentElement;
          const body = document.body;
          return {
            docOverflow: doc.scrollWidth - doc.clientWidth,
            bodyOverflow: body.scrollWidth - body.clientWidth,
          };
        }),
      { timeout: 15_000 }
    )
    .toEqual({ docOverflow: 0, bodyOverflow: 0 });
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

  await expect(page.getByTestId("patient-header")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("patient-appointments")).toBeVisible({ timeout: 15_000 });
  await expectNoDocumentHorizontalOverflow(page);

  await page.getByText("Patient details", { exact: true }).click();
  await expect(page.getByTestId("patient-notes-field")).toBeVisible({ timeout: 15_000 });
  await expectNoDocumentHorizontalOverflow(page);

  await page.getByRole("button", { name: "Book appointment" }).click();
  await expect(page.getByTestId("patient-booking-submit")).toBeVisible({ timeout: 15_000 });
  await expectNoDocumentHorizontalOverflow(page);
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

  await expect(page.getByText("Odontogram", { exact: true })).toBeVisible({ timeout: 20_000 });
  await expectNoDocumentHorizontalOverflow(page);

  const chart = page.getByTestId("clinical-chart");
  await expect(chart).toBeVisible({ timeout: 15_000 });
  const chartOverflow = await chart.evaluate((element) => {
    const styles = window.getComputedStyle(element);
    return {
      overflowX: styles.overflowX,
      scrollWidth: element.scrollWidth,
      clientWidth: element.clientWidth,
    };
  });

  expect(["auto", "scroll"]).toContain(chartOverflow.overflowX);
  expect(chartOverflow.scrollWidth).toBeGreaterThanOrEqual(chartOverflow.clientWidth);
});
