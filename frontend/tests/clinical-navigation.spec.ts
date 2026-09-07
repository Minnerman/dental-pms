import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { createPatient, createTreatmentPlanItem } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

type Mode = "current" | "planned" | "history";

async function fixture(page: Page, request: APIRequestContext, theme = "light") {
  const token = await primePageAuth(page, request);
  const id = await createPatient(request, { first_name: "Synthetic", last_name: `Clinical navigation ${Date.now()}` });
  await page.setViewportSize({ width: 1600, height: 1100 });
  await page.addInitScript((value) => localStorage.setItem("dental_pms_theme", value), theme);
  return { id, headers: { Authorization: `Bearer ${token}` } };
}

async function open(page: Page, id: string) {
  await page.goto(`${getBaseUrl()}/patients/${id}/clinical?clinicalView=current&source=synthetic-navigation`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-notes-panel")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-data-refresh")).toBeEnabled();
}

async function oneSelector(page: Page) {
  const clinical = page.getByTestId("patient-clinical-section");
  const selector = clinical.getByTestId("clinical-chart-toggle");
  const toolbar = clinical.getByTestId("clinical-navigation-toolbar");
  await expect(toolbar).toHaveCount(1);
  await expect(toolbar.getByTestId("clinical-chart-toggle")).toHaveCount(1);
  await expect(selector).toHaveCount(1);
  await expect(selector).toBeVisible();
  await expect(selector.getByRole("button")).toHaveCount(3);
  for (const mode of ["current", "planned", "history"]) await expect(selector.getByTestId(`clinical-chart-view-${mode}`)).toHaveCount(1);
  await expect(clinical.getByRole("button", { name: "Chart", exact: true })).toHaveCount(0);
  await expect(clinical.getByRole("button", { name: /^Treatment plan \(\d+\)$/ })).toHaveCount(0);
  await expect(clinical.getByRole("button", { name: /^Notes \(\d+\)$/ })).toHaveCount(0);
  await expect(clinical.getByTestId("clinical-data-refresh")).toHaveCount(1);
  await expect(clinical.getByTestId("clinical-chart-content").getByTestId("clinical-chart-toggle")).toHaveCount(0);
  const selectorBox = (await selector.boundingBox())!;
  const refreshBox = (await clinical.getByTestId("clinical-data-refresh").boundingBox())!;
  expect(Math.abs(selectorBox.y - refreshBox.y)).toBeLessThanOrEqual(12);
}

async function assertMode(page: Page, id: string, mode: Mode) {
  await expect(page.getByTestId(`clinical-chart-view-${mode}`)).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => {
    const url = new URL(page.url());
    return { path: url.pathname, mode: url.searchParams.get("clinicalView") ?? "current", source: url.searchParams.get("source") };
  }).toEqual({ path: `/patients/${id}/clinical`, mode, source: "synthetic-navigation" });
  if (mode === "planned") {
    await expect(page.getByTestId("treatment-planning-panel")).toBeVisible();
    await expect(page.getByTestId("planning-not-started")).toBeVisible();
  } else {
    await expect(page.getByTestId("clinical-chart")).toBeVisible();
    await expect(page.getByTestId("clinical-diagnosis-levels")).toHaveCount(mode === "current" ? 1 : 0);
  }
}

for (const theme of ["light", "dark"]) {
  test(`one clinical navigation row preserves view and URL across refresh in ${theme}`, async ({ page, request }) => {
    const { id } = await fixture(page, request, theme);
    const writes: string[] = [];
    page.on("request", (req) => { if (["POST", "PATCH", "PUT", "DELETE"].includes(req.method())) writes.push(new URL(req.url()).pathname); });
    await open(page, id); await oneSelector(page);
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    const previews = path.join(process.cwd(), ".run", "clinical-navigation-previews");
    await mkdir(previews, { recursive: true });
    for (const mode of ["planned", "history", "current"] as Mode[]) {
      const draft = `Synthetic unsaved ${theme} ${mode} navigation draft`;
      await page.getByTestId("clinical-notes-body").fill(draft);
      await page.getByTestId(`clinical-chart-view-${mode}`).click();
      await oneSelector(page); await assertMode(page, id, mode);
      await expect(page.getByTestId("clinical-notes-body")).toHaveValue(draft);
      const refreshed = page.waitForResponse((response) => response.request().method() === "GET" && new URL(response.url()).pathname === `/api/patients/${id}/clinical/summary`);
      await page.getByTestId("clinical-data-refresh").click();
      expect((await refreshed).ok()).toBeTruthy();
      await expect(page.getByTestId("clinical-data-refresh")).toBeEnabled();
      await assertMode(page, id, mode); await oneSelector(page);
      await expect(page.getByTestId("clinical-notes-body")).toHaveValue(draft);
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      await page.evaluate(() => new Promise<void>((resolve) => { scrollTo(0, 0); requestAnimationFrame(() => resolve()); }));
      await page.screenshot({ path: path.join(previews, `${theme}-${mode}.png`), fullPage: true });
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("clinical-chart-toggle")).toBeVisible({ timeout: 30_000 });
      await assertMode(page, id, mode); await oneSelector(page);
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    }
    expect(writes).toEqual([]);
  });
}

test("Earlier treatment items remain reachable and the single view selector returns to the chart", async ({ page, request }) => {
  const { id } = await fixture(page, request);
  const description = `Synthetic earlier proposal ${id}`;
  await createTreatmentPlanItem(request, id, { tooth: "UL1", procedure_code: "NAV-OLD", description, fee_pence: 1500 });
  const writes: string[] = [];
  page.on("request", (req) => { if (["POST", "PATCH", "PUT", "DELETE"].includes(req.method())) writes.push(new URL(req.url()).pathname); });
  await open(page, id); await page.getByTestId("clinical-chart-view-planned").click();
  const earlier = page.getByTestId("planning-earlier-items");
  await earlier.locator("summary").click(); await expect(earlier).toContainText(description);
  await earlier.getByRole("button", { name: "Open earlier plan items", exact: true }).click();
  await expect(page.getByTestId("patient-treatment-plan-section")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Earlier treatment items", exact: true })).toBeVisible();
  await expect(page.getByTestId("patient-treatment-plan-section")).toContainText(description);
  await oneSelector(page);
  for (const mode of ["current", "planned", "history"]) await expect(page.getByTestId(`clinical-chart-view-${mode}`)).toHaveAttribute("aria-pressed", "false");
  await page.getByTestId("clinical-chart-view-current").click();
  await assertMode(page, id, "current"); await expect(page.getByTestId("patient-treatment-plan-section")).toHaveCount(0);
  await page.getByTestId("clinical-chart-view-planned").click(); await assertMode(page, id, "planned");
  await earlier.locator("summary").click(); await expect(earlier).toContainText(description);
  await expect(page.getByTestId("treatment-planning-chart")).toHaveCount(0);
  expect(writes).toEqual([]);
});

test("notes remain accessible through the sidebar and main Notes tab without duplicate clinical tabs", async ({ page, request }) => {
  const { id, headers } = await fixture(page, request);
  const body = `Synthetic saved navigation note ${id}`;
  const created = await request.post(`${getBaseUrl()}/api/patients/${id}/notes`, { headers: { ...headers, "Request-Id": `navigation-note-${id}` }, data: { body, note_type: "clinical" } });
  expect(created.ok()).toBeTruthy(); const note = await created.json();
  const writes: string[] = [];
  page.on("request", (req) => { if (["POST", "PATCH", "PUT", "DELETE"].includes(req.method())) writes.push(new URL(req.url()).pathname); });
  await open(page, id); await oneSelector(page);
  const sidebar = page.getByTestId("clinical-notes-panel");
  await expect(sidebar.getByText(body, { exact: true })).toBeVisible();
  const draft = "Synthetic draft survives hiding the notes sidebar";
  await page.getByTestId("clinical-notes-body").fill(draft);
  await page.getByTestId("clinical-notes-toggle").click(); await expect(sidebar).toBeHidden();
  await page.getByRole("button", { name: "Show clinical notes", exact: true }).click();
  await expect(page.getByTestId("clinical-notes-body")).toHaveValue(draft);
  await page.getByTestId("clinical-notes-body").fill("");
  await page.getByTestId("patient-tab-Notes").click();
  await expect(page.getByTestId("patient-tab-Notes")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("patient-notes-access")).toHaveAttribute("data-state", "write");
  await expect(page.getByTestId(`patient-note-open-${note.id}`)).toBeVisible();
  await expect(page.getByTestId("patient-notes-access").getByText(body, { exact: true })).toBeVisible();
  await expect(page.getByTestId("patient-note-type-select")).toBeEnabled();
  await page.getByTestId("patient-tab-Medical").click();
  await oneSelector(page); await expect(sidebar.getByText(body, { exact: true })).toBeVisible();
  expect(writes).toEqual([]);
});
