import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

async function fixture(page: Page, request: APIRequestContext, width = 1920) {
  await primePageAuth(page, request);
  const id = await createPatient(request, { first_name: "Synthetic", last_name: `Shell notes ${Date.now()}` });
  await page.setViewportSize({ width, height: width < 761 ? 844 : 1200 });
  await page.route(`**/api/patients/${id}/clinical-journal?**`, (route) => route.fulfill({ json: {
    patient_id: Number(id), next_cursor: null,
    availability: { notes: "available", clinical: "available", medical: "available", correspondence: "available", imported: "disabled" },
    items: [{ key: "note:synthetic", source_kind: "note", source_id: "synthetic", category: "notes", title: "Clinical note", body: "Synthetic recorded note for layout review only.", occurred_at: "2026-09-06T09:00:00Z", clinical_date: null, date_basis: "recorded_at", author: { name: "Sample clinician", user_id: 1, source_user_code: null }, tooth: null, surface: null, revision: 1, can_edit: false, history_url: null, link: null, provenance: "Synthetic fixture", details: null }],
  } }));
  return id;
}

async function openChart(page: Page, id: string) {
  await page.goto(`${getBaseUrl()}/patients/${id}/clinical?clinicalView=current`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("clinical-notes-body")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading/i);
}

async function expectPageFits(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
}

async function expectFullWorkspace(page: Page) {
  const sidebar = (await page.getByTestId("app-sidebar").boundingBox())!;
  const main = (await page.getByTestId("app-main").boundingBox())!;
  const workspace = (await page.getByTestId("clinical-notes-workspace").boundingBox())!;
  expect(sidebar.x).toBe(0);
  expect(main.x).toBeCloseTo(sidebar.x + sidebar.width, 0);
  expect(main.x + main.width).toBeGreaterThanOrEqual(page.viewportSize()!.width - 1);
  expect(workspace.x - (sidebar.x + sidebar.width)).toBeLessThanOrEqual(32);
  expect(page.viewportSize()!.width - (workspace.x + workspace.width)).toBeLessThanOrEqual(32);
  await expectPageFits(page);
}

test("desktop practice navigation is vertical and uses the full workspace before and after collapse", async ({ page, request }) => {
  const id = await fixture(page, request); await openChart(page, id);
  const sidebar = page.getByTestId("app-sidebar");
  const navigation = page.getByRole("navigation", { name: "Main navigation" });
  await expect(sidebar).toHaveAttribute("data-collapsed", "false");
  await expect.poll(async () => (await sidebar.boundingBox())!.width).toBe(232);
  const patients = (await navigation.getByRole("link", { name: "Patients", exact: true }).boundingBox())!;
  const appointments = (await navigation.getByRole("link", { name: "Appointments", exact: true }).boundingBox())!;
  expect(appointments.y).toBeGreaterThan(patients.y); expect(appointments.x).toBeCloseTo(patients.x, 0);
  await expectFullWorkspace(page);
  await page.getByTestId("app-sidebar-toggle").click();
  await expect(sidebar).toHaveAttribute("data-collapsed", "true");
  await expect.poll(async () => (await sidebar.boundingBox())!.width).toBe(64);
  await expect(navigation.getByRole("link", { name: "Patients", exact: true })).toHaveAccessibleName("Patients");
  await expect(page.getByTestId("app-sidebar-resize")).toBeHidden();
  await expectFullWorkspace(page);
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(sidebar).toHaveAttribute("data-collapsed", "true");
  await navigation.getByRole("link", { name: "Patients", exact: true }).click();
  await expect(page).toHaveURL(/\/patients(?:[?#]|$)/);
  await expect(navigation.getByRole("link", { name: "Patients", exact: true })).toHaveAttribute("aria-current", "page");
  await expectPageFits(page);
});

test("navigation resize supports drag cancellation keyboard limits and persisted expanded width", async ({ page, request }) => {
  const id = await fixture(page, request); await openChart(page, id);
  const resize = page.getByTestId("app-sidebar-resize");
  await expect(resize).toHaveRole("separator"); await expect(resize).toHaveAccessibleName("Navigation width");
  await expect(resize).toHaveAttribute("aria-valuemin", "200"); await expect(resize).toHaveAttribute("aria-valuemax", "320");
  const box = (await resize.boundingBox())!; const point = { x: box.x + box.width / 2, y: Math.min(400, box.y + box.height / 2) };
  expect(await resize.evaluate((element, p) => element.contains(document.elementFromPoint(p.x, p.y)), point)).toBeTruthy();
  await page.mouse.move(point.x, point.y); await page.mouse.down(); await page.mouse.move(point.x + 55, point.y, { steps: 5 });
  await expect.poll(async () => Number(await resize.getAttribute("aria-valuenow"))).toBeGreaterThan(232);
  await page.keyboard.press("Escape"); await page.mouse.up();
  await expect(resize).toHaveAttribute("aria-valuenow", "232");
  await resize.focus(); await page.keyboard.press("Home"); await expect(resize).toHaveAttribute("aria-valuenow", "200");
  await page.keyboard.press("ArrowLeft"); await expect(resize).toHaveAttribute("aria-valuenow", "200");
  await page.keyboard.press("ArrowRight"); await expect(resize).toHaveAttribute("aria-valuenow", "210");
  await page.keyboard.press("Shift+ArrowRight"); await expect(resize).toHaveAttribute("aria-valuenow", "250");
  await page.keyboard.press("End"); await expect(resize).toHaveAttribute("aria-valuenow", "320");
  await page.keyboard.press("ArrowRight"); await expect(resize).toHaveAttribute("aria-valuenow", "320");
  await page.keyboard.press("ArrowLeft"); await expect(resize).toHaveAttribute("aria-valuenow", "310");
  await expect.poll(() => page.evaluate(() => localStorage.getItem("dental_pms_sidebar_width"))).toBe("310");
  await page.getByTestId("app-sidebar-toggle").click(); await page.getByTestId("app-sidebar-toggle").click();
  await expect(resize).toHaveAttribute("aria-valuenow", "310");
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(resize).toHaveAttribute("aria-valuenow", "310", { timeout: 30_000 });
  await expectFullWorkspace(page);
});

test("left and right sidebar changes retain the unsaved note and keep chart overflow inside its own canvas", async ({ page, request }) => {
  const id = await fixture(page, request); await openChart(page, id);
  const draft = "Synthetic unsaved draft remains attached to this patient while menus resize.";
  const body = page.getByTestId("clinical-notes-body"); await body.fill(draft);
  const mutations: string[] = []; page.on("request", (r) => { if (["POST", "PATCH", "PUT", "DELETE"].includes(r.method())) mutations.push(new URL(r.url()).pathname); });
  const svg = page.getByTestId("tooth-svg-UR5");
  const geometry = await svg.evaluate((element) => ({ viewBox: element.getAttribute("viewBox"), paths: [...element.querySelectorAll("path")].map((p) => p.getAttribute("d")) }));
  const left = page.getByTestId("app-sidebar-resize"); await left.focus(); await page.keyboard.press("End");
  const right = page.getByTestId("clinical-notes-resize"); await right.scrollIntoViewIfNeeded();
  const box = (await right.boundingBox())!, header = (await page.getByTestId("patient-header-card").boundingBox())!;
  const point = { x: box.x + box.width / 2, y: Math.max(box.y + 120, header.y + header.height + 60) };
  expect(await right.evaluate((element, p) => element.contains(document.elementFromPoint(p.x, p.y)), point)).toBeTruthy();
  const previous = Number(await right.getAttribute("aria-valuenow"));
  await page.mouse.move(point.x, point.y); await page.mouse.down(); await page.mouse.move(point.x - 60, point.y, { steps: 6 }); await page.mouse.up();
  await expect.poll(async () => Number(await right.getAttribute("aria-valuenow"))).toBeGreaterThan(previous);
  await expect(body).toHaveValue(draft);
  await page.getByTestId("app-sidebar-toggle").click(); await expect(body).toHaveValue(draft);
  await page.getByRole("button", { name: "Hide notes", exact: true }).click();
  await page.getByTestId("app-sidebar-toggle").click();
  await page.getByRole("button", { name: "Show clinical notes", exact: true }).click(); await expect(body).toHaveValue(draft);
  await page.setViewportSize({ width: 1280, height: 1000 });
  await right.focus(); await page.keyboard.press("End");
  await expect.poll(async () => (await page.getByTestId("clinical-chart-canvas").boundingBox())!.width).toBeGreaterThanOrEqual(1096);
  const scroller = page.locator(".patient-route-odontogram-scroll");
  await expect.poll(() => scroller.evaluate((element) => element.scrollWidth > element.clientWidth)).toBeTruthy();
  expect(await scroller.evaluate((element) => getComputedStyle(element).overflowX)).toBe("auto");
  await expectPageFits(page);
  expect(await svg.evaluate((element) => ({ viewBox: element.getAttribute("viewBox"), paths: [...element.querySelectorAll("path")].map((p) => p.getAttribute("d")) }))).toEqual(geometry);
  const cell = page.getByTestId("tooth-button-UR5"); expect((await cell.boundingBox())!.width).toBeGreaterThanOrEqual(64);
  await expect(body).toHaveValue(draft); expect(mutations).toEqual([]);
  expect(await page.evaluate(() => Object.entries(localStorage).filter(([key]) => key.includes("sidebar") || key.includes("clinical-notes-layout")).map(([, value]) => value).join(" "))).not.toContain(draft);
});

test("mobile practice drawer traps focus restores its opener and dismisses without disturbing a note draft", async ({ page, request }) => {
  const id = await fixture(page, request, 390); await openChart(page, id);
  const body = page.getByTestId("clinical-notes-body"); await body.fill("Synthetic mobile draft");
  const toggle = page.getByTestId("app-mobile-menu-toggle"), sidebar = page.getByTestId("app-sidebar");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByTestId("app-sidebar-resize")).toBeHidden(); await expect(page.getByTestId("clinical-notes-resize")).toBeHidden();
  await toggle.click(); await expect(sidebar).toHaveRole("dialog"); await expect(sidebar).toHaveAttribute("aria-modal", "true");
  await expect(page.getByTestId("app-main")).toHaveAttribute("inert", "");
  await expect(page.getByTestId("app-sidebar-toggle")).toBeFocused();
  const first = sidebar.getByRole("link", { name: "Dental PMS home", exact: true }), last = sidebar.getByRole("button", { name: "Sign out", exact: true });
  await first.focus(); await page.keyboard.press("Shift+Tab"); await expect(last).toBeFocused();
  await page.keyboard.press("Tab"); await expect(first).toBeFocused();
  await page.keyboard.press("Escape"); await expect(toggle).toHaveAttribute("aria-expanded", "false"); await expect(toggle).toBeFocused();
  await expect(page.getByTestId("app-main")).not.toHaveAttribute("inert", ""); await expect(body).toHaveValue("Synthetic mobile draft");
  await toggle.click(); const backdrop = page.getByTestId("app-sidebar-backdrop"), bounds = (await backdrop.boundingBox())!;
  await backdrop.click({ position: { x: bounds.width - 5, y: 300 } }); await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await toggle.click(); await sidebar.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Patients", exact: true }).click();
  await expect(page).toHaveURL(/\/patients(?:[?#]|$)/); await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expectPageFits(page);
});

test("wide light and dark previews and narrow layouts respect reduced motion without page overflow", async ({ page, request }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const id = await fixture(page, request); await openChart(page, id);
  for (const element of [page.getByTestId("app-sidebar"), page.getByTestId("app-main")]) {
    const durations = await element.evaluate((node) => getComputedStyle(node).transitionDuration.split(",").map(parseFloat));
    expect(durations.every((duration) => duration <= 0.001)).toBeTruthy();
  }
  const output = path.resolve(".run/clinical-shell-previews"); await mkdir(output, { recursive: true });
  for (const theme of ["light", "dark"]) {
    await page.evaluate((value) => { document.documentElement.dataset.theme = value; }, theme);
    await page.evaluate(() => window.scrollTo(0, 0)); await expectFullWorkspace(page);
    await page.screenshot({ path: path.join(output, `clinical-shell-${theme}-1920.png`), fullPage: true });
  }
  for (const width of [1280, 920, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 }); await expectPageFits(page);
    expect((await page.getByTestId("clinical-chart-canvas").boundingBox())!.width).toBeGreaterThanOrEqual(1096);
  }
  await page.getByTestId("app-mobile-menu-toggle").click();
  await page.screenshot({ path: path.join(output, "clinical-shell-mobile-navigation.png"), fullPage: false });
});

test("unconnected AI assistance explains setup without sending changing or saving note text", async ({ page, request }) => {
  const id = await fixture(page, request); await openChart(page, id);
  const draft = "Synthetic uncorrected note: the spelling is deliberate for this safety check.";
  const body = page.getByTestId("clinical-notes-body"), assistant = page.getByTestId("note-writing-assistant");
  await body.fill(draft);
  await expect(assistant).toHaveAccessibleName("AI writing assistance — not connected");
  await expect(assistant).toContainText("Not connected");
  await page.waitForLoadState("networkidle");
  const requests: string[] = []; const track = (r: { url: () => string }) => { requests.push(r.url()); }; page.on("request", track);
  await assistant.click();
  const explanation = page.getByTestId("note-writing-assistant-status");
  await expect(explanation).toContainText("AI writing correction is not connected yet.");
  await expect(explanation).toContainText("No note text has been sent.");
  await expect(explanation).toContainText("Saving a note will remain a separate step.");
  await expect(explanation.getByRole("button")).toHaveCount(0);
  await expect(body).toHaveValue(draft);
  await page.waitForTimeout(300);
  expect(requests).toEqual([]); page.off("request", track);
  const resize = page.getByTestId("clinical-notes-resize"); await resize.focus(); await page.keyboard.press("Home");
  const output = path.resolve(".run/clinical-shell-previews"); await mkdir(output, { recursive: true });
  for (const theme of ["light", "dark"]) {
    await page.evaluate((value) => { document.documentElement.dataset.theme = value; }, theme);
    const buttonBox = (await assistant.boundingBox())!, bodyBox = (await body.boundingBox())!;
    expect(buttonBox.x).toBeGreaterThanOrEqual(bodyBox.x);
    expect(buttonBox.x + buttonBox.width).toBeLessThanOrEqual(bodyBox.x + bodyBox.width + 1);
    expect(buttonBox.y).toBeLessThan(bodyBox.y);
    await assistant.locator("..").screenshot({ path: path.join(output, `note-writing-not-connected-${theme}.png`) });
  }
  await assistant.click(); await expect(explanation).toHaveCount(0); await expect(body).toHaveValue(draft);
  let release!: () => void; const hold = new Promise<void>((resolve) => { release = resolve; });
  await page.route(`**/api/patients/${id}/notes`, async (route) => { await hold; await route.fulfill({ status: 500, json: { detail: "Synthetic unconfirmed save" } }); });
  try {
    await page.getByTestId("clinical-notes-save").click(); await expect(body).toBeDisabled(); await expect(assistant).toBeDisabled();
  } finally { release(); }
  await expect(body).toBeEnabled(); await expect(body).toHaveValue(draft);
  await page.route("**/api/me/capabilities", (route) => route.fulfill({ json: ["patients.view", "clinical.view", "notes.view"] }));
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("clinical-notes-panel")).toBeVisible({ timeout: 30_000 });
  await expect(assistant).toHaveCount(0);
});
