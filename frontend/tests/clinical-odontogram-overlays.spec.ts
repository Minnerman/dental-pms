import { mkdirSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

test("clinical odontogram renders R4 overlays with filters and tooth drill-down", async ({
  page,
  request,
}) => {
  mkdirSync(".run/stage153c", { recursive: true });
  mkdirSync(".run/stage155a", { recursive: true });
  mkdirSync(".run/stage156b", { recursive: true });
  await primePageAuth(page, request);
  const patientId = await createPatient(request, {
    first_name: "Overlay",
    last_name: `Seed ${Date.now()}`,
  });
  let toothStateRequestSeen = false;

  await page.route(`**/api/patients/${patientId}/charting/treatment-plan-items*`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        patient_id: Number(patientId),
        legacy_patient_code: 1014496,
        total_items: 3,
        total_planned: 2,
        total_completed: 1,
        tooth_groups: [
          {
            tooth: 15,
            planned_count: 1,
            completed_count: 0,
            items: [
              {
                tp_number: 5001,
                tp_item: 1,
                tp_item_key: "5001-1",
                code_id: 3599,
                code_label: "Extraction",
                tooth: 15,
                surface: 1,
                tooth_level: false,
                completed: false,
                item_date: "2025-08-01T00:00:00+00:00",
                plan_creation_date: "2025-08-01T00:00:00+00:00",
              },
            ],
          },
          {
            tooth: 16,
            planned_count: 1,
            completed_count: 0,
            items: [
              {
                tp_number: 5001,
                tp_item: 2,
                tp_item_key: "5001-2",
                code_id: 3599,
                code_label: "Extraction",
                tooth: 16,
                surface: 77,
                tooth_level: false,
                completed: false,
                item_date: "2025-08-01T00:00:00+00:00",
                plan_creation_date: "2025-08-01T00:00:00+00:00",
              },
            ],
          },
        ],
        unassigned_items: [
          {
            tp_number: 5001,
            tp_item: 3,
            tp_item_key: "5001-3",
            code_id: 3600,
            code_label: "Emergency Appointment",
            tooth: 0,
            surface: 0,
            tooth_level: true,
            completed: true,
            item_date: "2025-08-01T00:00:00+00:00",
            plan_creation_date: "2025-08-01T00:00:00+00:00",
          },
        ],
      }),
    });
  });

  await page.route(`**/api/patients/${patientId}/charting/tooth-state*`, async (route) => {
    toothStateRequestSeen = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        patient_id: Number(patientId),
        legacy_patient_code: 1015073,
        teeth: {
          "15": {
            restorations: [
              {
                type: "filling",
                surfaces: ["M"],
                meta: { source: "mock" },
              },
            ],
            missing: false,
            extracted: false,
          },
          "16": {
            restorations: [
              {
                type: "crown",
                surfaces: [],
                meta: { source: "mock", code_label: "Mock Crown" },
              },
            ],
            missing: false,
            extracted: false,
          },
          "36": {
            restorations: [
              {
                type: "crown",
                surfaces: [],
                meta: { source: "mock", code_label: "White Crown", code_id: 3750 },
              },
            ],
            missing: false,
            extracted: false,
          },
          "24": {
            restorations: [
              {
                type: "root_canal",
                surfaces: [],
                meta: { source: "mock", code_label: "Root Canal Tx", completed: true },
              },
            ],
            missing: false,
            extracted: false,
          },
          "26": {
            restorations: [
              {
                type: "implant",
                surfaces: [],
                meta: { source: "mock", code_label: "Implant Fixture", completed: true },
              },
            ],
            missing: false,
            extracted: false,
          },
          "46": {
            restorations: [
              {
                type: "extraction",
                surfaces: [],
                meta: { source: "mock", code_label: "Planned Extraction", completed: false },
              },
            ],
            missing: false,
            extracted: false,
          },
        },
      }),
    });
  });

  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("odontogram-overlay-legend")).toBeVisible();
  await expect(page.getByTestId("tooth-overlay-planned-15")).toHaveText("P1");
  await expect(page.getByTestId("tooth-overlay-planned-16")).toHaveText("P1");
  expect(toothStateRequestSeen).toBeTruthy();
  await expect(page.getByTestId("tooth-restoration-UR5-filling-M")).toBeVisible();
  await expect(page.getByTestId("tooth-restoration-UR6-crown")).toBeVisible();
  await expect(page.getByTestId("tooth-restoration-UL4-root_canal")).toBeVisible();
  await expect(page.getByTestId("tooth-restoration-UL6-implant")).toBeVisible();
  await expect(page.getByTestId("tooth-restoration-LR6-extraction")).toBeVisible();
  await expect(page.getByTestId("tooth-restoration-LR6-extraction")).toHaveAttribute(
    "data-status",
    "planned"
  );
  await expect(page.getByTestId("tooth-restoration-LL6-crown")).toBeVisible();
  const crownTitle = await page
    .getByTestId("tooth-restoration-LL6-crown")
    .getAttribute("data-tooltip");
  expect(crownTitle ?? "").toContain("White Crown");
  expect(crownTitle ?? "").toContain("Type: crown");
  expect(crownTitle ?? "").toContain("Completed");
  await page.screenshot({
    path: ".run/stage155a/tooth_state_ui_1015073.png",
    fullPage: true,
  });
  await page.screenshot({
    path: ".run/stage156b/tooth_state_ui_types.png",
    fullPage: true,
  });
  await expect(page.getByTestId("tooth-surface-overlay-15-M")).toBeVisible();
  await expect(page.getByTestId("tooth-surface-overlay-15-M")).toHaveAttribute(
    "data-surface",
    "M"
  );
  await expect(page.getByTestId("overlay-unassigned-items")).toContainText(
    "Emergency Appointment"
  );
  const plannedMarkerTitle = await page.getByTestId("tooth-overlay-planned-15").getAttribute("title");
  expect(plannedMarkerTitle ?? "").toContain("Extraction");
  expect(plannedMarkerTitle ?? "").toContain("Planned");
  await page.screenshot({
    path: ".run/stage153c/overlay_ui_legend_tooltip.png",
    fullPage: true,
  });

  await page.getByTestId("tooth-button-UR5").click();
  await expect(page.getByTestId("overlay-panel")).toBeVisible();
  await expect(page.getByTestId("overlay-tooth-items")).toContainText("Extraction");
  await expect(page.getByTestId("overlay-tooth-items")).toContainText("Surface: M");
  await expect(page.getByTestId("overlay-tooth-items")).toContainText("Planned");
  await page.getByTestId("overlay-item").first().locator("summary").click();
  await expect(page.getByTestId("overlay-tooth-items")).toContainText("5001-1");

  await page.getByTestId("tooth-button-UR6").click();
  await expect(page.getByTestId("overlay-tooth-items")).toContainText("Surface: 77 (unmapped)");
  await expect(page.getByTestId("overlay-tooth-items")).toContainText(
    "Unmapped surface code; rendered as tooth-level fallback."
  );

  await page.getByTestId("clinical-overlay-filter-planned").click();
  await expect(page).toHaveURL(/overlay=planned/);
  await expect(page.getByTestId("overlay-unassigned-items")).toContainText(
    "No unassigned treatment plan items."
  );
  await expect(page.getByTestId("tooth-restoration-LL6-crown")).toBeVisible();
  await expect(page.getByTestId("tooth-overlay-planned-15")).toHaveText("P1");
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("clinical-overlay-filter-planned")).toHaveAttribute(
    "data-active",
    "true"
  );
  await expect(page).toHaveURL(/overlay=planned/);
  await expect(page.getByTestId("overlay-unassigned-items")).toContainText(
    "No unassigned treatment plan items."
  );
  await page.screenshot({
    path: ".run/stage153c/overlay_ui_filter_persist.png",
    fullPage: true,
  });

  await page.getByTestId("clinical-overlay-filter-completed").click();
  await expect(page).toHaveURL(/overlay=completed/);
  await expect(page.getByTestId("tooth-overlay-planned-15")).toHaveCount(0);
  await expect(page.getByTestId("tooth-overlay-planned-16")).toHaveCount(0);
  await expect(page.getByTestId("tooth-restoration-LL6-crown")).toBeVisible();
  await expect(page.getByTestId("overlay-unassigned-items")).toContainText(
    "Emergency Appointment"
  );
});
