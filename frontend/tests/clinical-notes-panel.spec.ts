import { expect, test, type Page, type APIRequestContext } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { createPatient } from "./helpers/api";
import { primePageAuth, getBaseUrl } from "./helpers/auth";
import type { JournalItem } from "../components/clinical/clinicalNotes";

const availability = { notes: "available", clinical: "available", medical: "available", correspondence: "available", imported: "available" };
const sample = (key: string, body: string, overrides: Partial<JournalItem> = {}): JournalItem => ({
  key, source_kind: "note", source_id: key.split(":").at(-1)!, category: "notes", title: "Clinical note", body,
  occurred_at: "2026-09-05T23:30:00Z", clinical_date: null, date_basis: "recorded_at", author: { name: "Sample Clinician", user_id: 1, source_user_code: null },
  tooth: null, surface: null, revision: 1, can_edit: false, history_url: null, link: null, provenance: "Native PMS", details: null, ...overrides,
});
async function fixture(page: Page, request: APIRequestContext) {
  const token = await primePageAuth(page, request);
  const id = await createPatient(request, { first_name: "Sample", last_name: `Notes sidebar ${Date.now()}` });
  await page.setViewportSize({ width: 1900, height: 1200 });
  return { id, headers: { Authorization: `Bearer ${token}` } };
}
async function open(page: Page, id: string) {
  await page.goto(`${getBaseUrl()}/patients/${id}/clinical?clinicalView=current`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("clinical-notes-panel")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-notes-panel").getByText("Loading clinical notes…", { exact: true })).toHaveCount(0, { timeout: 30_000 });
}
async function mockFeed(page: Page, id: string, items: JournalItem[]) {
  await page.route(`**/api/patients/${id}/clinical-journal?**`, (route) => route.fulfill({ json: { patient_id: Number(id), items, next_cursor: null, availability } }));
}

test("notes sidebar resizes, hides and returns without changing tooth geometry or losing draft", async ({ page, request }) => {
  const { id } = await fixture(page, request); await mockFeed(page, id, []); await open(page, id);
  const body = page.getByTestId("clinical-notes-body"); await body.fill("Synthetic unsaved sidebar draft");
  const svg = page.getByTestId("tooth-svg-UR5"); const before = (await svg.boundingBox())!;
  const originalGeometry = await svg.evaluate((element) => ({ viewBox: element.getAttribute("viewBox"), paths: [...element.querySelectorAll("path")].map((p) => p.getAttribute("d")) }));
  const handle = page.getByTestId("clinical-notes-resize"); await handle.scrollIntoViewIfNeeded();
  const initial = Number(await handle.getAttribute("aria-valuenow")); const box = (await handle.boundingBox())!;
  const header = (await page.getByTestId("patient-header-card").boundingBox())!;
  const dragY = Math.max(box.y + 120, header.y + header.height + 60);
  expect(await handle.evaluate((element, point) => element.contains(document.elementFromPoint(point.x, point.y)), { x: box.x + box.width / 2, y: dragY })).toBeTruthy();
  await page.mouse.move(box.x + box.width / 2, dragY); await page.mouse.down();
  await page.mouse.move(box.x - 80, dragY, { steps: 8 }); await page.mouse.up();
  await expect.poll(async () => Number(await handle.getAttribute("aria-valuenow"))).toBeGreaterThan(initial);
  await handle.focus(); await page.keyboard.press("Home"); await expect(handle).toHaveAttribute("aria-valuenow", "280");
  await page.keyboard.press("ArrowLeft"); await expect(handle).toHaveAttribute("aria-valuenow", "300");
  const after = (await svg.boundingBox())!;
  expect(after.width).toBeGreaterThanOrEqual(before.width);
  expect(after.height / after.width).toBeCloseTo(before.height / before.width, 2);
  expect(await svg.evaluate((element) => ({ viewBox: element.getAttribute("viewBox"), paths: [...element.querySelectorAll("path")].map((p) => p.getAttribute("d")) }))).toEqual(originalGeometry);
  await page.keyboard.press("End");
  expect((await page.locator(".patient-route-odontogram-canvas").boundingBox())!.width).toBeGreaterThanOrEqual(1096);
  const minimumCell = page.getByTestId("tooth-button-UR5");
  expect((await minimumCell.boundingBox())!.width).toBeGreaterThanOrEqual(64);
  const cellBorders = await minimumCell.evaluate((element) => parseFloat(getComputedStyle(element).borderLeftWidth) + parseFloat(getComputedStyle(element).borderRightWidth));
  expect((await svg.boundingBox())!.width).toBeGreaterThanOrEqual(64 - cellBorders);
  const scroll = page.locator(".patient-route-odontogram-scroll");
  expect(await scroll.evaluate((element) => getComputedStyle(element).overflowX)).toBe("auto");
  await page.getByTestId("clinical-notes-toggle").click(); await expect(page.getByTestId("clinical-notes-panel")).toBeHidden();
  const showNotes = page.getByRole("button", { name: "Show clinical notes", exact: true });
  await expect(showNotes).toBeFocused(); await showNotes.click();
  await expect(body).toHaveValue("Synthetic unsaved sidebar draft");
  const stored = await page.evaluate(() => Object.entries(localStorage).filter(([key]) => key !== "dental_pms_token"));
  expect(JSON.stringify(stored)).not.toContain("Synthetic unsaved");
  let release!: () => void; const hold = new Promise<void>((resolve) => { release = resolve; }); let writes = 0;
  await page.route(`**/api/patients/${id}/notes`, async (route) => { writes += 1; await hold; await route.fulfill({ status: 200, json: { id: 123 } }); });
  await page.getByTestId("clinical-notes-save").click();
  await expect(page.getByTestId("clinical-notes-toggle")).toBeDisabled(); await expect(body).toBeDisabled();
  await expect(page.getByTestId("clinical-notes-save")).toBeDisabled(); expect(writes).toBe(1);
  release(); await expect(page.getByTestId("clinical-notes-toggle")).toBeEnabled();
});

test("journal groups by London day and filters search/category/tooth with opaque pagination", async ({ page, request }) => {
  const { id } = await fixture(page, request); const seen: URLSearchParams[] = [];
  const initial = [sample("note:1", "Late evening synthetic note"), sample("r4:2", "<script>synthetic text only</script>", { source_kind: "r4_patient_note", occurred_at: null, author: { name: null, user_id: null, source_user_code: "UNKNOWN9" }, revision: null, provenance: { table: "SyntheticImportedNotes", key: "2" } })];
  await page.route(`**/api/patients/${id}/clinical-journal?**`, (route) => {
    const params = new URL(route.request().url()).searchParams; seen.push(params);
    const filtered = Boolean(params.get("q") || params.get("tooth") || params.get("category") !== "all");
    return route.fulfill({ json: { patient_id: Number(id), items: filtered ? [sample("note:3", "Matching synthetic note", { tooth: "UR5" })] : params.has("before") ? [sample("note:4", "Older synthetic note", { occurred_at: "2026-08-01T10:00:00Z" })] : initial, next_cursor: filtered || params.has("before") ? null : "opaque-next-page", availability } });
  });
  await open(page, id);
  await expect(page.getByTestId("clinical-notes-date-2026-09-06")).toContainText("Late evening synthetic note");
  await expect(page.getByTestId("clinical-notes-date-undated")).toContainText("Unmapped author code UNKNOWN9");
  await expect(page.getByText("<script>synthetic text only</script>", { exact: true })).toBeVisible();
  await expect(page.getByTestId("clinical-notes-entry-r4:2").getByRole("button", { name: "Edit note" })).toHaveCount(0);
  await page.getByTestId("clinical-notes-older").click(); await expect(page.getByText("Older synthetic note", { exact: true })).toBeVisible();
  expect(seen.some((params) => params.get("before") === "opaque-next-page")).toBeTruthy();
  await page.getByTestId("clinical-notes-search").fill("Matching"); await page.getByTestId("clinical-notes-category").selectOption("notes"); await page.getByTestId("clinical-notes-tooth-filter").selectOption("UR5");
  await expect.poll(() => seen.some((params) => params.get("q") === "Matching" && params.get("category") === "notes" && params.get("tooth") === "UR5")).toBeTruthy();
  await expect(page.getByText("Late evening synthetic note", { exact: true })).toHaveCount(0);
});

test("native notes save and amend with retained earlier text and no finance mutation", async ({ page, request }) => {
  const { id } = await fixture(page, request); await open(page, id);
  const mutations: string[] = []; page.on("request", (r) => { if (["POST", "PATCH", "DELETE"].includes(r.method())) mutations.push(new URL(r.url()).pathname); });
  const text = "Synthetic native clinical note before amendment";
  await page.getByTestId("clinical-notes-body").fill(text);
  const create = page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith(`/api/patients/${id}/notes`));
  await page.getByTestId("clinical-notes-save").click(); const created = await create; expect(created.ok()).toBeTruthy(); const note = await created.json();
  const entry = page.locator('[data-testid^="clinical-notes-entry-"]').filter({ has: page.getByText(text, { exact: true }) });
  await expect(entry).toBeVisible(); await entry.getByRole("button", { name: "Edit note" }).click();
  await page.getByTestId("clinical-notes-body").fill("Synthetic corrected clinical note");
  await page.getByLabel("Reason for amendment (optional)").fill("Synthetic correction");
  const amend = page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith(`/api/notes/${note.id}/amendments`));
  await page.getByTestId("clinical-notes-save").click(); expect((await amend).ok()).toBeTruthy();
  const updated = page.locator('[data-testid^="clinical-notes-entry-"]').filter({ has: page.getByText("Synthetic corrected clinical note", { exact: true }) });
  await expect(updated).toBeVisible(); await updated.getByRole("button", { name: "Earlier versions" }).click();
  await expect(page.getByTestId("clinical-notes-history")).toContainText(text);
  await expect(page.getByTestId("clinical-notes-history")).toContainText("Synthetic corrected clinical note");
  expect(mutations.some((url) => /ledger|invoice|procedure|treatment-plan/.test(url))).toBeFalsy();
});

test("a sidebar tooth note creates its yellow marker and retains patient selection", async ({ page, request }) => {
  const { id } = await fixture(page, request); await open(page, id);
  await page.getByTestId("clinical-notes-tooth").selectOption("UR5"); await page.getByTestId("clinical-notes-body").fill("Synthetic UR5 sidebar finding");
  const response = page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith(`/api/patients/${id}/tooth-notes`));
  await page.getByTestId("clinical-notes-save").click(); const saved = await response; expect(saved.ok()).toBeTruthy(); expect(saved.request().postDataJSON()).toMatchObject({ tooth: "UR5", surface: null });
  await expect(page.getByTestId("tooth-note-flag-UR5")).toBeVisible();
  await page.getByTestId("clinical-notes-toggle").click(); await page.getByTestId("tooth-note-flag-UR5").click();
  await expect(page.getByTestId("clinical-notes-panel")).toBeVisible(); await expect(page.getByTestId("clinical-notes-tooth-filter")).toHaveValue("UR5");
  await expect(page.getByTestId("clinical-notes-panel").getByText("Synthetic UR5 sidebar finding", { exact: true })).toBeVisible();
});

test("failed save retry reuses request identity and stale amendments keep draft", async ({ page, request }) => {
  const { id } = await fixture(page, request);
  await mockFeed(page, id, [sample("note:888", "Synthetic stale note", { can_edit: true, source_id: "888", revision: 2, history_url: "/notes/888/revisions" })]); await open(page, id);
  const ids: (string | undefined)[] = []; let failed = true;
  await page.route(`**/api/patients/${id}/notes`, (route) => { ids.push(route.request().headers()["request-id"]); if (failed) { failed = false; return route.fulfill({ status: 500, json: { detail: "Synthetic server fault" } }); } return route.fulfill({ status: 200, json: { id: 999 } }); });
  await page.getByTestId("clinical-notes-body").fill("Synthetic uncertain save"); await page.getByTestId("clinical-notes-save").click();
  await expect(page.getByTestId("clinical-notes-save-error")).toContainText("could not be confirmed");
  await page.getByTestId("clinical-notes-save").click(); await expect(page.getByTestId("clinical-notes-body")).toHaveValue("");
  expect(ids).toHaveLength(2); expect(ids[0]).toBeTruthy(); expect(ids[1]).toBe(ids[0]);
  await page.getByTestId("clinical-notes-edit-note:888").click(); await page.getByTestId("clinical-notes-body").fill("Synthetic local amendment");
  await page.route("**/api/notes/888/amendments", (route) => route.fulfill({ status: 409, json: { detail: "Synthetic revision conflict" } }));
  await page.getByTestId("clinical-notes-save").click(); await expect(page.getByTestId("clinical-notes-save-error")).toContainText("changed");
  await expect(page.getByTestId("clinical-notes-body")).toHaveValue("Synthetic local amendment");
  await expect(page.getByTestId("clinical-notes-entry-note:888")).toContainText("Synthetic stale note");
  await page.route("**/api/notes/888/revisions**", (route) => {
    const older = new URL(route.request().url()).searchParams.get("before_revision") === "2";
    return route.fulfill({ json: { items: [{ revision: older ? 1 : 2, body: older ? "Synthetic earlier captured text" : "Synthetic latest text", recorded_at: "2026-09-06T10:00:00Z", recorded_by: { id: 1, name: "Sample Clinician" }, baseline: older, archived: older }], next_before_revision: older ? null : 2 } });
  });
  await page.getByTestId("clinical-notes-history-note:888").click();
  await page.getByTestId("clinical-notes-history-older").click();
  await expect(page.getByTestId("clinical-notes-history")).toContainText("Synthetic earlier captured text");
  await expect(page.getByTestId("clinical-notes-history")).toContainText("Baseline captured; earlier edits unavailable");
  await expect(page.getByTestId("clinical-notes-history")).toContainText("Archived");
  await expect(page.getByTestId("clinical-notes-history")).toContainText("Synthetic latest text");
});

test("template dropdown answers are explicit and insert an editable unsaved draft", async ({ page, request }) => {
  const { id } = await fixture(page, request); await mockFeed(page, id, []);
  await page.route("**/api/clinical-note-templates**", (route) => {
    if (route.request().method() !== "GET") return route.fulfill({ json: { ...route.request().postDataJSON(), id: 52, revision: route.request().method() === "POST" ? 1 : 2, is_active: true } });
    return route.fulfill({ json: [{ id: 51, title: "Synthetic examination", category: "clinical", body: "Finding: {{finding}}", codes: ["EXAM-LABEL"], fields: [{ key: "finding", label: "Finding", options: ["Synthetic finding A", "Synthetic finding B"], required: true }], revision: 3, is_active: true }] });
  });
  await open(page, id); let posts = 0; page.on("request", (r) => { if (r.method() === "POST") posts += 1; });
  await page.getByTestId("clinical-note-templates").locator("summary").first().click();
  await page.getByTestId("clinical-note-template-select").selectOption("51");
  await expect(page.getByTestId("clinical-note-template-answer-finding")).toHaveValue("");
  await page.getByTestId("clinical-note-template-use").click(); await expect(page.getByTestId("clinical-note-templates")).toContainText("Answer: Finding");
  await expect(page.getByTestId("clinical-notes-body")).toHaveValue("");
  await page.getByTestId("clinical-note-template-answer-finding").selectOption("Synthetic finding B"); await page.getByTestId("clinical-note-template-use").click();
  await expect(page.getByTestId("clinical-notes-body")).toHaveValue("Finding: Synthetic finding B");
  await page.getByTestId("clinical-notes-body").fill("Clinician-edited synthetic final text"); expect(posts).toBe(0);
  await page.route(`**/api/patients/${id}/notes`, (route) => route.fulfill({ status: 200, json: { id: 51 } }));
  const save = page.waitForRequest((r) => r.method() === "POST" && r.url().endsWith(`/api/patients/${id}/notes`));
  await page.getByTestId("clinical-notes-save").click(); expect((await save).postDataJSON()).toMatchObject({ body: "Clinician-edited synthetic final text", template_id: 51, template_revision: 3, codes: ["EXAM-LABEL"] });
  await expect(page.getByTestId("clinical-notes-body")).toHaveValue("");
  await page.getByTestId("clinical-note-template-new").click();
  const editor = page.getByTestId("clinical-note-template-editor");
  await editor.getByLabel("Name", { exact: true }).fill("Synthetic new template");
  await editor.getByLabel("Template text", { exact: true }).fill("Recorded choice: {{finding}}");
  await editor.getByRole("button", { name: "Add dropdown question" }).click();
  await editor.getByLabel("Question 1 key", { exact: true }).fill("finding");
  await editor.getByLabel("Question 1 label", { exact: true }).fill("Finding");
  await editor.getByLabel("Question 1 answers (one per line)", { exact: true }).fill("Option A\nOption B");
  const creation = page.waitForRequest((r) => r.method() === "POST" && r.url().endsWith("/api/clinical-note-templates"));
  await page.getByTestId("clinical-note-template-save").click();
  const payload = (await creation).postDataJSON();
  expect(Object.keys(payload).sort()).toEqual(["body", "category", "codes", "fields", "title"]);
  expect(payload.fields).toEqual([{ key: "finding", label: "Finding", options: ["Option A", "Option B"], required: true }]);
  await expect(page.getByTestId("clinical-note-template-select")).toHaveValue("52");
  await page.getByTestId("clinical-note-template-edit").click();
  await editor.getByRole("textbox", { name: "Template text", exact: true }).fill("Updated wording: {{finding}}");
  const update = page.waitForRequest((r) => r.method() === "PATCH" && r.url().endsWith("/api/clinical-note-templates/52"));
  await page.getByTestId("clinical-note-template-save").click();
  expect((await update).postDataJSON()).toMatchObject({ expected_revision: 1, body: "Updated wording: {{finding}}" });
});

test("read-only permissions and journal errors never imply empty recorded history", async ({ page, request }) => {
  const { id } = await fixture(page, request);
  await page.route("**/api/me/capabilities", (route) => route.fulfill({ json: ["patients.view", "clinical.view", "notes.view"] }));
  await mockFeed(page, id, [sample("note:1", "Synthetic read-only note", { can_edit: false })]); await open(page, id);
  await expect(page.getByTestId("clinical-notes-body")).toHaveCount(0); await expect(page.getByRole("button", { name: "Edit note", exact: true })).toHaveCount(0);
  await page.unroute(`**/api/patients/${id}/clinical-journal?**`); await page.route(`**/api/patients/${id}/clinical-journal?**`, (route) => route.fulfill({ status: 500, json: { detail: "Synthetic unavailable" } }));
  await page.getByTestId("clinical-notes-panel").getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByTestId("clinical-notes-error")).toBeVisible(); await expect(page.getByTestId("clinical-notes-empty")).toHaveCount(0);
  await expect(page.getByText("Synthetic read-only note", { exact: true })).toHaveCount(0);
});

test("a delayed journal response cannot replace a newer search result", async ({ page, request }) => {
  const { id } = await fixture(page, request);
  let release!: () => void; const hold = new Promise<void>((resolve) => { release = resolve; });
  await page.route(`**/api/patients/${id}/clinical-journal?**`, async (route) => {
    const query = new URL(route.request().url()).searchParams.get("q");
    if (query === "slow") await hold;
    await route.fulfill({ json: { patient_id: Number(id), items: query ? [sample(`note:${query}`, `Synthetic ${query} response`)] : [], next_cursor: null, availability } });
  });
  await open(page, id);
  const slow = page.waitForRequest((r) => r.url().includes("clinical-journal") && new URL(r.url()).searchParams.get("q") === "slow");
  await page.getByTestId("clinical-notes-search").fill("slow"); await slow;
  await page.getByTestId("clinical-notes-search").fill("fast");
  await expect(page.getByText("Synthetic fast response", { exact: true })).toBeVisible();
  const response = page.waitForResponse((r) => r.url().includes("clinical-journal") && new URL(r.url()).searchParams.get("q") === "slow");
  release(); await response;
  await expect(page.getByText("Synthetic fast response", { exact: true })).toBeVisible();
  await expect(page.getByText("Synthetic slow response", { exact: true })).toHaveCount(0);
});

test("diagnosis entries show only their action-specific finding while original records stay accessible", async ({ page, request }) => {
  const { id } = await fixture(page, request);
  const original = '{"surface_observations":{"M":{"kind":"restored","material":null}}}';
  const fullRow = { condition: "present", dentition: "permanent", movement: "forward", rotation: null,
    root_observations: { "1": { condition: "filled_sound", apicectomy: false }, "2": { condition: null, apicectomy: true } },
    crown_observation: { kind: "gold", issues: [] },
    surface_observations: { M: { kind: "restored", material: null, condition: "sound", defects: [] } },
    bridge_role: "abutment", revision: 3, updated_by: "Synthetic hidden metadata" };
  const diagnosis = (key: string, action: string) => sample(`diagnosis:${key}`, original, { source_kind: "diagnosis", category: "diagnosis", title: `${key} observations recorded`, details: { action, changed_teeth: ["UR6"], observations: { UR6: fullRow, LL5: fullRow } } });
  const rawNotes = ['{"native":"literal note body"}', '{"tooth":"literal note body"}', '{"imported":"<b>unchanged raw text</b>"}'];
  await mockFeed(page, id, [diagnosis("surface", "clinical.surface_conditions.recorded"), diagnosis("root", "clinical.root_conditions.recorded"), diagnosis("crown", "clinical.crown_conditions.recorded"), diagnosis("tooth", "clinical.tooth_conditions.recorded"), diagnosis("bridge", "clinical.bridge.created"),
    diagnosis("unknown", "constructor"), sample("note:raw", rawNotes[0]), sample("tooth_note:raw", rawNotes[1], { source_kind: "tooth_note" }), sample("import:raw", rawNotes[2], { source_kind: "r4_patient_note" })]);
  await open(page, id);
  const surface = page.getByTestId("clinical-notes-diagnosis-body-diagnosis:surface");
  await expect(surface).toHaveText("UR6 · Surface M: kind: restored; material: not specified; condition: sound; defects: none recorded");
  const root = page.getByTestId("clinical-notes-diagnosis-body-diagnosis:root");
  await expect(root).toContainText("UR6 · Root 1: condition: filled sound; apicectomy: no");
  await expect(root).toContainText("UR6 · Root 2: condition: not specified; apicectomy: yes");
  await expect(page.getByTestId("clinical-notes-diagnosis-body-diagnosis:crown")).toHaveText("UR6 · Crown: kind: gold; issues: none recorded");
  await expect(page.getByTestId("clinical-notes-diagnosis-body-diagnosis:tooth")).toContainText("UR6 · rotation: not specified");
  await expect(page.getByTestId("clinical-notes-diagnosis-body-diagnosis:bridge")).toContainText("UR6 · bridge role: abutment");
  await expect(page.getByTestId("clinical-notes-diagnosis-body-diagnosis:unknown")).toHaveText("Recorded diagnosis — see Source details.");
  for (const level of ["surface", "root", "crown", "tooth", "bridge"]) {
    const entry = page.getByTestId(`clinical-notes-entry-diagnosis:${level}`);
    const visible = await entry.innerText();
    expect(visible).not.toContain("{"); expect(visible).not.toContain("LL5"); expect(visible).not.toContain("Synthetic hidden metadata");
    const main = page.getByTestId(`clinical-notes-diagnosis-body-diagnosis:${level}`);
    if (level !== "surface") await expect(main).not.toContainText("Surface M");
    if (level !== "root") await expect(main).not.toContainText("apicectomy");
  }
  const entry = page.getByTestId("clinical-notes-entry-diagnosis:surface");
  await entry.locator("summary", { hasText: "Source details" }).click();
  await expect(entry.getByText(original, { exact: true })).toBeVisible();
  await expect(entry.locator("details")).toContainText('"root_observations"');
  await entry.locator("summary", { hasText: "Source details" }).click();
  for (const [index, key] of ["note:raw", "tooth_note:raw", "import:raw"].entries()) {
    await expect(page.getByTestId(`clinical-notes-entry-${key}`).getByText(rawNotes[index], { exact: true })).toBeVisible();
  }
  const output = path.resolve(".run/clinical-notes-readable-previews"); await mkdir(output, { recursive: true });
  await page.getByTestId("clinical-notes-composer").locator("summary").first().click();
  for (const theme of ["light", "dark"]) {
    await page.evaluate((value) => { document.documentElement.dataset.theme = value; }, theme);
    await page.getByTestId("clinical-notes-panel").screenshot({ path: path.join(output, `diagnosis-readable-${theme}.png`) });
  }
});

test("clinical notes visual preview remains clear in light dark and mobile layouts", async ({ page, request }) => {
  const { id } = await fixture(page, request);
  await mockFeed(page, id, [sample("note:1", "Synthetic examination note.\nThe clinician can review and amend this native record.", { can_edit: true, tooth: "UR5" }), sample("diagnosis:2", "UR5 · Crown · Porcelain · condition not specified", { source_kind: "diagnosis", category: "diagnosis", title: "Current diagnosis", tooth: "UR5", revision: null }), sample("document:3", "Synthetic follow-up letter prepared for review. Delivery not recorded.", { source_kind: "document", category: "correspondence", title: "Generated letter", revision: null }), sample("r4:4", "Synthetic imported historical note, preserved unchanged.", { source_kind: "r4_patient_note", title: "Imported note", occurred_at: "2025-01-03T10:00:00Z", revision: null })]);
  await open(page, id); const output = path.resolve(".run/clinical-notes-previews"); await mkdir(output, { recursive: true });
  for (const theme of ["light", "dark"]) {
    await page.evaluate((value) => { document.documentElement.dataset.theme = value; }, theme);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(output, `clinical-notes-${theme}.png`), fullPage: true });
    await page.getByTestId("clinical-notes-panel").screenshot({ path: path.join(output, `clinical-notes-panel-${theme}.png`) });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByTestId("clinical-notes-resize")).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  await page.getByTestId("clinical-notes-panel").screenshot({ path: path.join(output, "clinical-notes-mobile.png") });
});
