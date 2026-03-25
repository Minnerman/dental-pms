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

function normalizeText(value: string) {
  return value.replace(/\s+/g, " ").trim();
}

async function expectRowWithCells(root: Locator, cells: string[]) {
  const rows = root.locator("tbody tr");
  const rowCount = await rows.count();
  for (let idx = 0; idx < rowCount; idx += 1) {
    const text = normalizeText(await rows.nth(idx).innerText());
    if (cells.every((cell) => text.includes(cell))) {
      return;
    }
  }
  throw new Error(`Expected BPE furcation row not found for cells: ${cells.join(" | ")}`);
}

async function expectBlockWithText(root: Locator, cells: string[]) {
  const text = normalizeText(await root.innerText());
  if (!cells.every((cell) => text.includes(cell))) {
    throw new Error(`Expected text not found for cells: ${cells.join(" | ")}`);
  }
}

test("patient charting page renders seeded BPE entry and furcation data for a patient with charting history", async ({
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
  const bpePatient = seed.patients.find((patient) => patient.legacy_code === 1000035);
  expect(bpePatient).toBeTruthy();

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${bpePatient?.patient_id}/charting`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page).toHaveURL(new RegExp(`/patients/${bpePatient?.patient_id}/charting`));
  await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".badge", { hasText: "BPE entries: 1" }).first()).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.locator(".badge", { hasText: "BPE furcations: 3" }).first()).toBeVisible({
    timeout: 30_000,
  });

  const bpePanel = page
    .locator("section.panel")
    .filter({ has: page.locator(".panel-title", { hasText: "BPE entries" }) });
  await expect(bpePanel).toBeVisible({ timeout: 30_000 });
  await expect(bpePanel.getByText("Showing 1 records")).toBeVisible({ timeout: 30_000 });
  const bpeGroup = bpePanel.getByTestId("bpe-group").first();
  await expect(bpeGroup).toBeVisible({ timeout: 30_000 });
  await expect(bpeGroup.getByText("Exam date: 16/01/2024")).toBeVisible({ timeout: 30_000 });
  await expect(bpeGroup.getByText("Latest exam")).toBeVisible({ timeout: 30_000 });
  await expectBlockWithText(bpeGroup.getByTestId("bpe-grid").first(), [
    "UR",
    "2",
    "UA",
    "1",
    "UL",
    "0",
    "LL",
    "2",
    "LA",
    "1",
    "LR",
    "0",
  ]);

  const furcationPanel = page
    .locator("section.panel")
    .filter({ has: page.locator(".panel-title", { hasText: "BPE furcations" }) });
  await expect(furcationPanel).toBeVisible({ timeout: 30_000 });
  await expect(furcationPanel.getByText("Showing 3 records")).toBeVisible({ timeout: 30_000 });
  await expect(furcationPanel.getByText("Uses the same date filters as BPE entries.")).toBeVisible(
    { timeout: 30_000 }
  );
  await expect(furcationPanel.getByTestId("bpe-furcation-group").first()).toBeVisible({
    timeout: 30_000,
  });

  await expectRowWithCells(furcationPanel, ["16/01/2024", "16", "1", "1"]);
  await expectRowWithCells(furcationPanel, ["16/01/2024", "26", "2", "2"]);
  await expectRowWithCells(furcationPanel, ["16/01/2024", "36", "3", "3"]);
});
