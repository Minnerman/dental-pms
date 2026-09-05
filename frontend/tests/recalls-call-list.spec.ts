import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

// Exercise the actual Chromium PDF viewer; Playwright's lightweight headless
// shell intentionally omits it. The unsupported-browser case is tested below.
test.use({ channel: "chromium" });

type RecallFixture = {
  id: number;
  patient_id: number;
  first_name: string;
  last_name: string;
  phone: string | null;
  recall_kind: string;
  due_date: string;
  status: string;
  notes: string | null;
  completed_at: null;
  last_contacted_at: string | null;
  last_contact_channel: string | null;
  last_contact_outcome: string | null;
  last_contact_note: string | null;
  contact_preference: null;
  do_not_contact: null;
  contact_preferences_availability: "unavailable";
};

const capabilities = ["recalls.view", "recalls.write", "recalls.export", "patients.view", "appointments.view", "appointments.write"];
const fixedDate = new Date("2032-01-15T12:00:00Z");
const fixtures: RecallFixture[] = [
  { id: 92001, patient_id: 91001, first_name: "Sample", last_name: "Patient One", phone: "07700 900101", recall_kind: "exam", due_date: "2032-01-12", status: "overdue", notes: "Routine review — synthetic example", completed_at: null, last_contacted_at: null, last_contact_channel: null, last_contact_outcome: null, last_contact_note: null, contact_preference: null, do_not_contact: null, contact_preferences_availability: "unavailable" },
  { id: 92002, patient_id: 91002, first_name: "Sample", last_name: "Patient Two", phone: "07700 900102", recall_kind: "hygiene", due_date: "2032-01-15", status: "due", notes: "Hygiene follow-up — synthetic example", completed_at: null, last_contacted_at: "2032-01-14T10:30:00Z", last_contact_channel: "phone", last_contact_outcome: "Requested a call tomorrow", last_contact_note: "Synthetic contact note", contact_preference: null, do_not_contact: null, contact_preferences_availability: "unavailable" },
  { id: 92003, patient_id: 91003, first_name: "Sample", last_name: "Patient Three", phone: null, recall_kind: "perio", due_date: "2032-01-16", status: "due", notes: null, completed_at: null, last_contacted_at: null, last_contact_channel: null, last_contact_outcome: null, last_contact_note: null, contact_preference: null, do_not_contact: null, contact_preferences_availability: "unavailable" },
  { id: 92004, patient_id: 91004, first_name: "Sample", last_name: "Patient Four", phone: "07700 900104", recall_kind: "implant", due_date: "2032-01-19", status: "upcoming", notes: "Annual review — synthetic example", completed_at: null, last_contacted_at: null, last_contact_channel: null, last_contact_outcome: null, last_contact_note: null, contact_preference: null, do_not_contact: null, contact_preferences_availability: "unavailable" },
];
const summary = {
  as_of_date: "2032-01-15", timezone: "Europe/London",
  periods: { week_start: "2032-01-12", week_end: "2032-01-18", month_start: "2032-01-01", month_end: "2032-01-31" },
  due_this_week: 18, overdue: 7, scheduled_this_month: 11,
  scheduled_availability: "available", conversion_rate: null,
  conversion_availability: "unavailable", conversion_reason: "conversion_not_recorded",
};

// A small valid PDF with synthetic text, suitable for the native preview and download.
function samplePdf() {
  const stream = "BT /F1 18 Tf 60 760 Td (Recall letter - synthetic preview) Tj 0 -40 Td /F1 12 Tf (Dear Sample Patient One,) Tj 0 -24 Td (Please contact the practice to arrange your routine review.) Tj ET";
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}\nendstream`,
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  for (const [index, object] of objects.entries()) {
    offsets.push(Buffer.byteLength(pdf));
    pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
  }
  const xref = Buffer.byteLength(pdf);
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  pdf += offsets.slice(1).map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`).join("");
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(pdf);
}

async function mockRecallPage(page: Page, request: APIRequestContext, options: { capabilities?: string[]; summary?: object } = {}) {
  await primePageAuth(page, request);
  await page.clock.setFixedTime(fixedDate);
  await page.route("**/api/me/capabilities", (route) => route.fulfill({ json: options.capabilities ?? capabilities }));
  const queries: URLSearchParams[] = [];
  await page.route(/\/api\/recalls(?:\?|$)/, (route) => {
    const query = new URL(route.request().url()).searchParams;
    queries.push(query);
    let rows = fixtures.filter((row) => {
      const statuses = query.get("status")?.split(",");
      return (!statuses || statuses.includes(row.status)) &&
        (!query.get("type") || row.recall_kind === query.get("type")) &&
        (!query.get("start") || row.due_date >= query.get("start")!) &&
        (!query.get("end") || row.due_date <= query.get("end")!) &&
        (query.get("contact_state") !== "never" || !row.last_contacted_at) &&
        (query.get("contact_state") !== "contacted" || Boolean(row.last_contacted_at));
    });
    const offset = Number(query.get("offset") ?? 0);
    rows = rows.slice(offset, offset + Number(query.get("limit") ?? 50));
    return route.fulfill({ json: rows });
  });
  await page.route("**/api/recalls/export_count?**", (route) => route.fulfill({ json: { count: 18 } }));
  await page.route("**/api/recalls/summary", (route) => route.fulfill({ json: options.summary ?? summary }));
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method()) && /\/api\/(?:recalls|patients)/.test(new URL(request.url()).pathname)) {
      mutations.push(`${request.method()} ${new URL(request.url()).pathname}`);
    }
  });
  return { queries, mutations };
}

async function openList(page: Page) {
  await page.goto(`${getBaseUrl()}/recalls`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Recall call list" })).toBeVisible();
  await expect(page.getByTestId("recalls-row")).toHaveCount(3);
}

async function noHorizontalOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
}

test("compact recall rows show factual phone and contact information without invented preferences", async ({ page, request }) => {
  const { mutations } = await mockRecallPage(page, request);
  await openList(page);
  const first = page.getByTestId("recalls-row").filter({ hasText: "PATIENT ONE" });
  await expect(first.getByTestId("recalls-patient-navigation")).toHaveAttribute("href", "/patients/91001?tab=recalls");
  await expect(first).toContainText("07700 900101");
  await expect(first).toContainText("Not contacted");
  await expect(first.getByRole("button", { name: "Recall letter", exact: true })).toBeVisible();
  await expect(first.getByRole("button", { name: "Log contact" })).toBeVisible();
  await expect(first.getByRole("button", { name: "Book appointment" })).toBeVisible();
  await expect(page.getByTestId("recalls-row").filter({ hasText: "PATIENT THREE" })).toContainText("No phone recorded");
  const contacted = page.getByTestId("recalls-row").filter({ hasText: "PATIENT TWO" });
  await contacted.getByTestId("recalls-last-contact").locator("summary").click();
  await expect(contacted).toContainText("Synthetic contact note");
  await expect(contacted).toContainText("Requested a call tomorrow");
  await expect(page.getByText(/preferred contact: phone|do not contact: no|priority: normal/i)).toHaveCount(0);
  expect(mutations).toEqual([]);
});

test("month presets use calendar boundaries including leap February and keep future recalls visible", async ({ page, request }) => {
  const { queries } = await mockRecallPage(page, request);
  await openList(page);
  const menu = page.getByTestId("recalls-month-menu");
  await menu.locator("summary").click();
  await menu.getByRole("button", { name: "Feb", exact: true }).click();
  await expect.poll(() => queries.at(-1)?.get("start")).toBe("2032-02-01");
  expect(queries.at(-1)?.get("end")).toBe("2032-02-29");
  expect(queries.at(-1)?.get("status")?.split(",").sort()).toEqual(["due", "overdue", "upcoming"]);
  await expect(menu).not.toHaveAttribute("open", "");
  await expect(menu.locator("summary")).toBeFocused();
  await menu.locator("summary").click();
  await menu.getByRole("button", { name: "Next year" }).click();
  await menu.getByRole("button", { name: "Feb", exact: true }).click();
  await expect.poll(() => queries.at(-1)?.get("end")).toBe("2033-02-28");
  await menu.locator("summary").click();
  await menu.getByRole("button", { name: "This month" }).click();
  await expect.poll(() => queries.at(-1)?.get("start")).toBe("2032-01-01");
  expect(queries.at(-1)?.get("end")).toBe("2032-01-31");
  await expect(page.getByTestId("recalls-row")).toHaveCount(4);
  await menu.locator("summary").click();
  await page.keyboard.press("Escape");
  await expect(menu.locator("summary")).toBeFocused();
  await menu.locator("summary").click();
  await menu.getByRole("button", { name: "All dates", exact: true }).click();
  await expect.poll(() => queries.at(-1)?.has("start")).toBe(false);
  expect(queries.at(-1)?.has("end")).toBe(false);
  await page.getByTestId("recalls-reset-filters").click();
  await expect(page.getByTestId("recalls-row")).toHaveCount(3);
  expect(queries.at(-1)?.get("status")).toBe("due,overdue");
});

test("recall reason and contact filters return only matching rows and reset clearly", async ({ page, request }) => {
  const { queries } = await mockRecallPage(page, request);
  await openList(page);
  await page.getByTestId("recalls-filter-type").selectOption("hygiene");
  await expect(page.getByTestId("recalls-row")).toHaveCount(1);
  await expect(page.getByTestId("recalls-row")).toContainText("PATIENT TWO");
  await page.getByTestId("recalls-filter-contact-state").selectOption("never");
  await expect(page.getByText("No recalls match your filters.", { exact: true })).toBeVisible();
  await expect(page.getByTestId("recalls-pagination")).toContainText("Showing 0-0");
  expect(queries.at(-1)?.get("contact_state")).toBe("never");
  await page.getByTestId("recalls-reset-filters").click();
  await expect(page.getByTestId("recalls-row")).toHaveCount(3);
  await expect(page.getByTestId("recalls-filter-type")).toHaveValue("all");
  await expect(page.getByTestId("recalls-filter-contact-state")).toHaveValue("all");
});

test("recall letter preview loads once and download reuses the PDF without sending or logging contact", async ({ page, request }) => {
  const { mutations } = await mockRecallPage(page, request);
  let pdfReads = 0;
  let downloads = 0;
  page.on("download", () => { downloads += 1; });
  await page.route("**/api/patients/91001/recalls/92001/letter.pdf", (route) => {
    pdfReads += 1;
    return route.fulfill({ contentType: "application/pdf", headers: { "Content-Disposition": 'attachment; filename="synthetic-recall-preview.pdf"' }, body: samplePdf() });
  });
  await openList(page);
  const opener = page.getByTestId("recalls-letter-92001");
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "Recall letter", exact: true });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("Sample Patient One");
  await expect(page.getByTestId("recall-letter-preview")).toBeVisible();
  await expect(page.getByTestId("recall-letter-download")).toBeEnabled();
  expect(pdfReads).toBe(1);
  expect(downloads).toBe(0);
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByTestId("recall-letter-download").click()]);
  expect(download.suggestedFilename()).toBe("recall-91001-92001.pdf");
  expect(pdfReads).toBe(1);
  expect(mutations).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test("recall letter print is explicit and unavailable browser printing has a safe PDF fallback", async ({ page, request }) => {
  const { mutations } = await mockRecallPage(page, request);
  await page.route("**/api/patients/91001/recalls/92001/letter.pdf", (route) => route.fulfill({ contentType: "application/pdf", body: samplePdf() }));
  await openList(page);
  await page.getByTestId("recalls-letter-92001").click();
  await expect(page.getByTestId("recall-letter-print")).toBeEnabled();
  // Intercept only the browser print surface, not application state or requests.
  await page.getByTestId("recall-letter-preview").evaluate((frame) => {
    const state = window as Window & { syntheticPrintCalls?: number };
    state.syntheticPrintCalls = 0;
    Object.defineProperty(frame, "contentWindow", { configurable: true, value: { focus() {}, print() { state.syntheticPrintCalls! += 1; throw new Error("Synthetic unsupported browser print"); } } });
  });
  expect(await page.evaluate(() => (window as Window & { syntheticPrintCalls?: number }).syntheticPrintCalls)).toBe(0);
  await page.getByTestId("recall-letter-print").click();
  expect(await page.evaluate(() => (window as Window & { syntheticPrintCalls?: number }).syntheticPrintCalls)).toBe(1);
  await expect(page.getByTestId("recall-letter-open-pdf")).toBeVisible();
  await expect(page.getByTestId("recall-letter-open-pdf")).toHaveAttribute("target", "_blank");
  expect(mutations).toEqual([]);
});

test("recall overview uses full counts and explicitly labels permission and unrecorded metrics", async ({ page, request }) => {
  await mockRecallPage(page, request, { capabilities: ["recalls.view", "patients.view"], summary: { ...summary, scheduled_this_month: null, scheduled_availability: "forbidden" } });
  await openList(page);
  await expect(page.getByTestId("recalls-summary-due")).toHaveText("18");
  await expect(page.getByTestId("recalls-summary-overdue")).toHaveText("7");
  await expect(page.getByTestId("recalls-summary-scheduled")).toHaveText("—");
  await expect(page.getByTestId("recalls-summary")).toContainText("Permission required");
  await expect(page.getByTestId("recalls-summary-conversion")).toHaveText("—");
  await expect(page.getByTestId("recalls-summary")).toContainText("Not recorded yet");
  await expect(page.getByTestId("recalls-read-only-notice")).toBeVisible();
  await expect(page.getByRole("button", { name: "Recall letter", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Log contact" })).toHaveCount(0);
  await expect(page.getByTestId("recalls-book-action")).toHaveCount(0);
  await page.getByTestId("recalls-filter-type").selectOption("hygiene");
  await expect(page.getByTestId("recalls-row")).toHaveCount(1);
  await expect(page.getByTestId("recalls-summary-due")).toHaveText("18");
});

test("recall overview loading and failure never display fabricated zeroes or block the call list", async ({ page, request }) => {
  await mockRecallPage(page, request);
  await page.unroute("**/api/recalls/summary");
  let release!: () => void;
  const pending = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/recalls/summary", async (route) => {
    await pending;
    await route.fulfill({ status: 503, contentType: "text/html", body: "<p>private synthetic overview detail</p>" });
  });
  await openList(page);
  await expect(page.getByTestId("recalls-summary-due")).toHaveText("…");
  await expect(page.getByTestId("recalls-summary-overdue")).toHaveText("…");
  await expect(page.getByTestId("recalls-summary-scheduled")).toHaveText("…");
  release();
  await expect(page.getByTestId("recalls-summary")).toContainText("Overview unavailable. The call list still works.");
  await expect(page.getByTestId("recalls-summary-due")).toHaveText("—");
  await expect(page.getByText("private synthetic overview detail")).toHaveCount(0);
  await expect(page.getByTestId("recalls-row")).toHaveCount(3);
  await page.unroute("**/api/recalls/summary");
  await page.route("**/api/recalls/summary", (route) => route.fulfill({ json: summary }));
  await page.getByRole("button", { name: "Retry overview" }).click();
  await expect(page.getByTestId("recalls-summary-due")).toHaveText("18");
  await expect(page.getByTestId("recalls-summary-scheduled")).toHaveText("11");
});

test("recall letter preview rejects failed or non-PDF responses and retry is deliberate", async ({ page, request }) => {
  const { mutations } = await mockRecallPage(page, request);
  let pdfReads = 0;
  await page.route("**/api/patients/91001/recalls/92001/letter.pdf", (route) => {
    pdfReads += 1;
    return pdfReads === 1
      ? route.fulfill({ status: 500, contentType: "text/html", body: "<p>private synthetic backend detail</p>" })
      : route.fulfill({ contentType: "text/html", body: "<p>Not a PDF</p>" });
  });
  await openList(page);
  await page.getByTestId("recalls-letter-92001").click();
  await expect(page.getByTestId("recall-letter-error")).toBeVisible();
  await expect(page.getByText("private synthetic backend detail")).toHaveCount(0);
  await expect(page.getByTestId("recall-letter-preview")).toHaveCount(0);
  await expect(page.getByTestId("recall-letter-download")).toBeDisabled();
  await page.getByRole("button", { name: "Retry preview" }).click();
  await expect.poll(() => pdfReads).toBe(2);
  await expect(page.getByTestId("recall-letter-error")).toBeVisible();
  await expect(page.getByTestId("recall-letter-preview")).toHaveCount(0);
  await expect(page.getByTestId("recall-letter-print")).toBeDisabled();
  expect(mutations).toEqual([]);
});

test("synthetic recall call list and letter dialog fit light dark desktop and mobile", async ({ page, request }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockRecallPage(page, request);
  await page.addInitScript(() => localStorage.setItem("dental_pms_theme", "light"));
  await page.route("**/api/patients/91001/recalls/92001/letter.pdf", (route) => route.fulfill({ contentType: "application/pdf", body: samplePdf() }));
  await openList(page);
  await noHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath("recall-call-list-light.png"), fullPage: true });
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await page.screenshot({ path: testInfo.outputPath("recall-call-list-dark.png"), fullPage: true });
  await page.getByTestId("recalls-letter-92001").click();
  await expect(page.getByTestId("recall-letter-preview")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("recall-letter-dark.png"), fullPage: true });
  await page.getByRole("button", { name: "Close recall letter" }).click();
  await page.setViewportSize({ width: 960, height: 900 });
  await page.getByTestId("recalls-month-menu").locator("summary").click();
  await noHorizontalOverflow(page);
  await page.getByTestId("recalls-month-menu").locator("summary").click();
  await page.setViewportSize({ width: 390, height: 844 });
  await noHorizontalOverflow(page);
  await expect(page.getByTestId("recalls-row").first().getByRole("button", { name: "Recall letter", exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("recall-call-list-mobile.png"), fullPage: true });
  await page.getByTestId("recalls-month-menu").locator("summary").click();
  await noHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath("recall-month-mobile.png"), fullPage: true });
  await page.keyboard.press("Escape");
  await page.getByTestId("recalls-letter-92001").click();
  await expect(page.getByTestId("recall-letter-download")).toBeVisible();
  await noHorizontalOverflow(page);
  const dialog = await page.getByTestId("recall-letter-dialog").boundingBox();
  expect(dialog).not.toBeNull();
  expect(dialog!.width).toBeLessThanOrEqual(390);
  expect(dialog!.height).toBeLessThanOrEqual(844);
  await page.screenshot({ path: testInfo.outputPath("recall-letter-mobile.png"), fullPage: true });
});

test("real recall PDF preview and download preserve the recorded contact state", async ({ page, request }, testInfo) => {
  const token = await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `Recall Preview ${Date.now()}`, address_line1: "1 Example Road", city: "Example Town", postcode: "BN1 1AA" });
  const headers = { Authorization: `Bearer ${token}` };
  const created = await request.post(`${getBaseUrl()}/api/patients/${patientId}/recalls`, { headers, data: { kind: "exam", due_date: new Date().toISOString().slice(0, 10), status: "due", notes: "Synthetic no-send preview check" } });
  expect(created.ok()).toBeTruthy();
  const recall = await created.json() as { id: number };
  const readContact = async () => {
    const response = await request.get(`${getBaseUrl()}/api/recalls?status=due,overdue&limit=200`, { headers });
    expect(response.ok()).toBeTruthy();
    const rows = await response.json() as Array<Record<string, unknown>>;
    const row = rows.find((item) => item.id === recall.id);
    expect(row).toBeTruthy();
    return { at: row!.last_contacted_at ?? null, channel: row!.last_contact_channel ?? null, outcome: row!.last_contact_outcome ?? null, note: row!.last_contact_note ?? null, status: row!.status };
  };
  const before = await readContact();
  expect(before.at).toBeNull();
  await page.goto(`${getBaseUrl()}/recalls`, { waitUntil: "domcontentloaded" });
  await page.getByTestId(`recalls-letter-${recall.id}`).click();
  await expect(page.getByTestId("recall-letter-preview")).toBeVisible();
  await expect(page.getByTestId("recall-letter-download")).toBeEnabled();
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByTestId("recall-letter-download").click()]);
  expect(download.suggestedFilename()).toMatch(/\.pdf$/i);
  await download.saveAs(testInfo.outputPath("recall-letter-synthetic.pdf"));
  await page.getByRole("button", { name: "Close recall letter" }).click();
  expect(await readContact()).toEqual(before);
  await page.reload({ waitUntil: "domcontentloaded" });
  const row = page.getByTestId("recalls-row").filter({ has: page.getByTestId(`recalls-letter-${recall.id}`) });
  await expect(row).toContainText("Not contacted");
});

test("browsers without PDF viewing offer explicit download without automatic downloads", async ({ page, request }) => {
  await mockRecallPage(page, request);
  await page.addInitScript(() => Object.defineProperty(navigator, "pdfViewerEnabled", { get: () => false }));
  await page.route("**/api/patients/91001/recalls/92001/letter.pdf", (route) => route.fulfill({ contentType: "application/pdf", body: samplePdf() }));
  let downloads = 0;
  page.on("download", () => { downloads += 1; });
  await openList(page);
  await page.getByTestId("recalls-letter-92001").click();
  await expect(page.getByTestId("recall-letter-browser-fallback")).toBeVisible();
  await expect(page.getByTestId("recall-letter-preview")).toHaveCount(0);
  await expect(page.getByTestId("recall-letter-print")).toBeDisabled();
  await expect(page.getByTestId("recall-letter-download")).toBeEnabled();
  expect(downloads).toBe(0);
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByTestId("recall-letter-download").click()]);
  expect(download.suggestedFilename()).toBe("recall-91001-92001.pdf");
  expect(downloads).toBe(1);
});
