import { expect, test, type Locator } from "@playwright/test";

import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

const chartingEnabled = process.env.NEXT_PUBLIC_FEATURE_CHARTING_VIEWER === "1";

async function seedChartingDemo(request: Parameters<typeof ensureAuthReady>[0]) {
  const token = await ensureAuthReady(request);
  const backendBaseUrl =
    process.env.BACKEND_BASE_URL ?? `http://localhost:${process.env.BACKEND_PORT ?? "8100"}`;
  const response = await request.post(`${backendBaseUrl}/test/seed/charting`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as {
    patients: Array<{ legacy_code: number; patient_id: number }>;
  };
}

async function expectRowWithCells(root: Locator, cells: string[]) {
  const rows = root.locator("tbody tr");
  const rowCount = await rows.count();
  for (let idx = 0; idx < rowCount; idx += 1) {
    const text = (await rows.nth(idx).innerText()).replace(/\s+/g, " ").trim();
    if (cells.every((cell) => text.includes(cell))) {
      return;
    }
  }
  throw new Error(`Expected perio probe row not found for cells: ${cells.join(" | ")}`);
}

test("patient charting page renders seeded perio probe data for a patient with probe history", async ({
  page,
  request,
}) => {
  test.skip(!chartingEnabled, "charting viewer disabled");
  const baseUrl = getBaseUrl();
  const configRes = await request.get(`${baseUrl}/api/config`);
  const config = (await configRes.json()) as {
    feature_flags?: { charting_viewer?: boolean };
  };
  test.skip(!config?.feature_flags?.charting_viewer, "charting viewer disabled");

  const seed = await seedChartingDemo(request);
  const probePatient = seed.patients.find((patient) => patient.legacy_code === 1000000);
  expect(probePatient).toBeTruthy();

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${probePatient?.patient_id}/charting`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page).toHaveURL(new RegExp(`/patients/${probePatient?.patient_id}/charting`));
  await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 30_000 });

  const perioPanel = page
    .locator("section.panel")
    .filter({ has: page.locator(".panel-title", { hasText: "Perio probes" }) });
  await expect(perioPanel).toBeVisible({ timeout: 30_000 });
  await expect(perioPanel.getByText("Showing 12 of 12 total")).toBeVisible({ timeout: 30_000 });
  await expect(perioPanel.getByText("Last imported:", { exact: false })).toBeVisible({
    timeout: 30_000,
  });
  await expect(perioPanel.locator('[data-testid="perio-group"]').first()).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.locator(".badge", { hasText: "Perio probes: 12" }).first()).toBeVisible({
    timeout: 30_000,
  });

  await expectRowWithCells(perioPanel, ["01/01/2024", "11", "MB (1)", "4"]);
  await expectRowWithCells(perioPanel, ["12/01/2024", "12", "DL (6)", "3"]);
});
