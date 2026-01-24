import fs from "node:fs";
import path from "node:path";

import { test, expect, type Locator } from "@playwright/test";

import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

type ParityTarget = {
  legacyCode: number;
  entity: "perio-probes" | "bpe" | "bpe-furcations" | "notes" | "tooth-surfaces";
  label:
    | "Perio probes"
    | "BPE entries"
    | "BPE furcations"
    | "Patient notes"
    | "Tooth surfaces";
};

const chartingEnabled = process.env.NEXT_PUBLIC_FEATURE_CHARTING_VIEWER === "1";
const parityTargets: ParityTarget[] = [
  {
    legacyCode: 1000000,
    entity: "perio-probes",
    label: "Perio probes",
  },
  {
    legacyCode: 1011978,
    entity: "bpe",
    label: "BPE entries",
  },
  {
    legacyCode: 1012056,
    entity: "notes",
    label: "Patient notes",
  },
  {
    legacyCode: 1013684,
    entity: "bpe",
    label: "BPE entries",
  },
  {
    legacyCode: 1000035,
    entity: "bpe",
    label: "BPE entries",
  },
  {
    legacyCode: 1000035,
    entity: "bpe-furcations",
    label: "BPE furcations",
  },
  {
    legacyCode: 1000000,
    entity: "tooth-surfaces",
    label: "Tooth surfaces",
  },
];

test.skip(!chartingEnabled, "charting parity requires viewer enabled");

function parseBadgeCount(text: string) {
  const match = text.match(/:\s*(\d+)\s*$/);
  if (!match) return null;
  return Number(match[1]);
}

function formatUiDate(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleDateString("en-GB");
}

const perioSiteLabels: Record<number, string> = {
  1: "MB",
  2: "B",
  3: "DB",
  4: "ML",
  5: "L",
  6: "DL",
};

function formatPerioSite(value?: number | null) {
  if (value === null || value === undefined) return "—";
  const label = perioSiteLabels[value];
  return label ? `${label} (${value})` : String(value);
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
  throw new Error(`Expected row not found for cells: ${cells.join(" | ")}`);
}

async function expectBlockWithText(root: Locator, cells: string[]) {
  const text = normalizeText(await root.innerText());
  if (!cells.every((cell) => text.includes(cell))) {
    throw new Error(`Expected text not found for cells: ${cells.join(" | ")}`);
  }
}

function extractApiItems<T>(payload: unknown): { items: T[]; total: number } {
  if (Array.isArray(payload)) {
    return { items: payload as T[], total: payload.length };
  }
  const data = payload as {
    items?: T[];
    total?: number;
  };
  return {
    items: data?.items ?? [],
    total: typeof data?.total === "number" ? data.total : (data?.items ?? []).length,
  };
}

async function seedCharting(request: Parameters<typeof ensureAuthReady>[0]) {
  const token = await ensureAuthReady(request);
  const backendBaseUrl =
    process.env.BACKEND_BASE_URL ?? `http://localhost:${process.env.BACKEND_PORT ?? "8100"}`;
  const seedRes = await request.post(`${backendBaseUrl}/test/seed/charting`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (seedRes.status() === 404) {
    throw new Error("Seed endpoint missing. Set ENABLE_TEST_ROUTES=1 for parity tests.");
  }
  expect(seedRes.ok()).toBeTruthy();
  const seedPayload = (await seedRes.json()) as {
    patients: Array<{ legacy_code: number; patient_id: number }>;
  };
  const patientMap = new Map<number, string>();
  for (const patient of seedPayload.patients ?? []) {
    patientMap.set(patient.legacy_code, String(patient.patient_id));
  }
  return { token, patientMap };
}

test("charting viewer parity matches API counts", async ({ page, request }) => {
  test.setTimeout(120_000);
  const baseUrl = getBaseUrl();
  const configRes = await request.get(`${baseUrl}/api/config`);
  const config = (await configRes.json()) as {
    feature_flags?: { charting_viewer?: boolean };
  };
  test.skip(!config?.feature_flags?.charting_viewer, "charting viewer disabled");
  const { token, patientMap } = await seedCharting(request);
  const report: Array<{
    legacy_code: number;
    patient_id: string;
    entity: string;
    api_count: number;
    ui_count: number;
    status: "pass" | "fail";
    row_checks?: Array<{ cells: string[]; status: "pass" | "fail" }>;
  }> = [];

  await primePageAuth(page, request);
  const exportPatientId = patientMap.get(1000000);
  if (exportPatientId) {
    await page.goto(`${baseUrl}/patients/${exportPatientId}/charting`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 30_000 });
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByTestId("charting-export-csv").click(),
    ]);
    expect(download.suggestedFilename()).toMatch(/charting_/i);
  }

  for (const target of parityTargets) {
    const patientId = patientMap.get(target.legacyCode);
    if (!patientId) {
      throw new Error(`Missing seeded patient for legacy code ${target.legacyCode}`);
    }
    const apiResponse = await request.get(
      `${baseUrl}/api/patients/${patientId}/charting/${target.entity}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!apiResponse.ok()) {
      const status = apiResponse.status();
      const body = await apiResponse.text();
      throw new Error(
        `Charting API ${target.entity} failed (${status}): ${body.slice(0, 1000)}`
      );
    }
    const apiPayload = await apiResponse.json();
    const { items: apiData, total: apiCount } = extractApiItems<any>(apiPayload);

    await page.goto(`${baseUrl}/patients/${patientId}/charting`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator(".badge", { hasText: "Perio probes:" }).first()
    ).toBeVisible({ timeout: 30_000 });

    const badge = page.locator(".badge", { hasText: `${target.label}:` }).first();
    await expect(badge).toBeVisible();
    const badgeText = await badge.textContent();
    const uiCount = badgeText ? parseBadgeCount(badgeText) : null;
    expect(uiCount).not.toBeNull();
    expect(uiCount).toBe(apiCount);

    const entryReport: {
      legacy_code: number;
      patient_id: string;
      entity: string;
      api_count: number;
      ui_count: number;
      status: "pass" | "fail";
      row_checks?: Array<{ cells: string[]; status: "pass" | "fail" }>;
    } = {
      legacy_code: target.legacyCode,
      patient_id: patientId,
      entity: target.label,
      api_count: apiCount,
      ui_count: uiCount as number,
      status: apiCount === uiCount ? "pass" : "fail",
    };

    if (target.legacyCode === 1000000 && target.entity === "perio-probes") {
      const samples = apiData.slice(0, 3);
      if (samples.length === 0) {
        throw new Error("No perio probe rows available for row-level parity checks.");
      }
      const panel = page
        .locator("section.panel")
        .filter({ has: page.locator(".panel-title", { hasText: "Perio probes" }) });
      await expect(panel.getByText("Exam date:").first()).toBeVisible();
      entryReport.row_checks = [];
      for (const row of samples) {
        const cells = [
          formatUiDate(row.recorded_at),
          String(row.tooth ?? "—"),
          formatPerioSite(row.probing_point),
          String(row.depth ?? "—"),
        ];
        await expectRowWithCells(panel, cells);
        entryReport.row_checks.push({ cells, status: "pass" });
      }
    }

    if (target.legacyCode === 1011978 && target.entity === "bpe") {
      const samples = apiData.slice(0, 3);
      if (samples.length === 0) {
        throw new Error("No BPE rows available for row-level parity checks.");
      }
      const panel = page
        .locator("section.panel")
        .filter({ has: page.locator(".panel-title", { hasText: "BPE entries" }) });
      await expect(panel.getByTestId("bpe-grid").first()).toBeVisible();
      entryReport.row_checks = [];
      for (const row of samples) {
        const cells = [
          String(row.sextant_1 ?? "—"),
          String(row.sextant_2 ?? "—"),
          String(row.sextant_3 ?? "—"),
          String(row.sextant_4 ?? "—"),
          String(row.sextant_5 ?? "—"),
          String(row.sextant_6 ?? "—"),
        ];
        const dateLabel = `Exam date: ${formatUiDate(row.recorded_at)}`;
        const group = panel.locator('[data-testid="bpe-group"]', { hasText: dateLabel });
        await expectBlockWithText(group.first(), cells);
        entryReport.row_checks.push({ cells, status: "pass" });
      }
    }

    if (target.legacyCode === 1000035 && target.entity === "bpe-furcations") {
      const samples = apiData.slice(0, 3);
      if (samples.length === 0) {
        throw new Error("No BPE furcation rows available for row-level parity checks.");
      }
      const panel = page
        .locator("section.panel")
        .filter({ has: page.locator(".panel-title", { hasText: "BPE furcations" }) });
      await expect(panel.getByText("Exam date:")).toBeVisible();
      entryReport.row_checks = [];
      for (const row of samples) {
        const cells = [
          formatUiDate(row.recorded_at),
          String(row.tooth ?? "—"),
          String(row.furcation ?? "—"),
          String(row.sextant ?? "—"),
        ];
        await expectRowWithCells(panel, cells);
        entryReport.row_checks.push({ cells, status: "pass" });
      }
    }

    if (target.legacyCode === 1000000 && target.entity === "tooth-surfaces") {
      const samples = apiData.slice(0, 2);
      if (samples.length === 0) {
        throw new Error("No tooth surface rows available for row-level parity checks.");
      }
      const panel = page
        .locator("section.panel")
        .filter({ has: page.locator(".panel-title", { hasText: "Tooth surfaces" }) });
      await expect(panel.locator("table").first()).toBeVisible();
      entryReport.row_checks = [];
      for (const row of samples) {
        const cells = [
          String(row.legacy_tooth_id ?? "—"),
          String(row.legacy_surface_no ?? "—"),
        ];
        await expectRowWithCells(panel, cells);
        entryReport.row_checks.push({ cells, status: "pass" });
      }
    }

    if (target.legacyCode === 1012056 && target.entity === "notes") {
      const samples = [...apiData]
        .filter((row: any) => row?.note_date && row?.note)
        .sort((a: any, b: any) => {
          const timeA = a.note_date ? new Date(a.note_date).getTime() : -Infinity;
          const timeB = b.note_date ? new Date(b.note_date).getTime() : -Infinity;
          return timeB - timeA;
        })
        .slice(0, 2);
      const panel = page
        .locator("section.panel")
        .filter({ has: page.locator(".panel-title", { hasText: "Patient notes" }) });
      await expect(panel.getByTestId("notes-list")).toBeVisible();
      entryReport.row_checks = [];
      for (const row of samples) {
        const noteSnippet = normalizeText(String(row.note)).slice(0, 30);
        const cells = [
          formatUiDate(row.note_date),
          String(row.category_number ?? "—"),
          noteSnippet,
        ];
        await expectRowWithCells(panel, cells);
        entryReport.row_checks.push({ cells, status: "pass" });
      }
    }

    report.push(entryReport);
  }

  const reportPath =
    process.env.UI_PARITY_OUT ?? "/tmp/stage142/ui_parity.json";
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log("UI_PARITY_REPORT", JSON.stringify(report));
});

test("charting filters reduce totals in UI", async ({ page, request }) => {
  test.setTimeout(120_000);
  const baseUrl = getBaseUrl();
  const configRes = await request.get(`${baseUrl}/api/config`);
  const config = (await configRes.json()) as {
    feature_flags?: { charting_viewer?: boolean };
  };
  test.skip(!config?.feature_flags?.charting_viewer, "charting viewer disabled");
  const { patientMap } = await seedCharting(request);
  const patientId = patientMap.get(1012056);
  if (!patientId) {
    throw new Error("Missing seeded patient 1012056 for charting filters test.");
  }

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/charting`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 30_000 });

  const notesBadge = page.locator(".badge", { hasText: "Patient notes:" }).first();
  await expect(notesBadge).toBeVisible();
  const beforeText = await notesBadge.textContent();
  const beforeCount = beforeText ? parseBadgeCount(beforeText) : null;
  expect(beforeCount).not.toBeNull();

  const notesInput = page.getByPlaceholder("Find text...");
  await notesInput.click();
  await notesInput.type("note");
  await notesInput.type(" 1");
  await expect(notesBadge).toHaveText(/Patient notes:\s*1/, { timeout: 30_000 });
  if (beforeCount !== null) {
    expect(beforeCount).toBeGreaterThan(1);
  }
});

test("charting notes preset export/import roundtrip", async ({ page, request }) => {
  test.setTimeout(120_000);
  const baseUrl = getBaseUrl();
  const configRes = await request.get(`${baseUrl}/api/config`);
  const config = (await configRes.json()) as {
    feature_flags?: { charting_viewer?: boolean };
  };
  test.skip(!config?.feature_flags?.charting_viewer, "charting viewer disabled");
  const { patientMap } = await seedCharting(request);
  const patientId = patientMap.get(1012056);
  if (!patientId) {
    throw new Error("Missing seeded patient 1012056 for preset test.");
  }

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/charting`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 30_000 });

  await page.evaluate(() => {
    // @ts-expect-error - attach test helper to window
    window.__copiedPreset = null;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      const original = navigator.clipboard.writeText.bind(navigator.clipboard);
      navigator.clipboard.writeText = async (value: string) => {
        // @ts-expect-error - attach test helper to window
        window.__copiedPreset = value;
        return original(value);
      };
    }
  });

  const notesPanel = page
    .locator("section.panel")
    .filter({ has: page.locator(".panel-title", { hasText: "Patient notes" }) });
  await expect(notesPanel).toBeVisible();
  const notesInput = notesPanel.getByPlaceholder("Find text...");
  await notesInput.fill("note 1");
  await notesPanel.getByRole("button", { name: "Copy preset JSON" }).click();

  const copied = await page.evaluate(() => {
    // @ts-expect-error - read test helper from window
    return window.__copiedPreset as string | null;
  });
  expect(copied).not.toBeNull();
  if (copied) {
    expect(copied).toContain("\"section\":\"notes\"");
    expect(copied).toContain("\"version\":1");
    expect(copied).toContain("\"q\":\"note 1\"");
  }

  await notesPanel.getByRole("button", { name: "Clear filters" }).click();
  await expect(notesInput).toHaveValue("");

  await page.evaluate((value) => {
    window.prompt = () => value;
  }, copied);
  await notesPanel.getByRole("button", { name: "Import preset JSON" }).click();
  await expect(notesInput).toHaveValue("note 1");
});

test("charting notes share link roundtrip (non-text filters)", async ({ page, request }) => {
  test.setTimeout(120_000);
  const baseUrl = getBaseUrl();
  const configRes = await request.get(`${baseUrl}/api/config`);
  const config = (await configRes.json()) as {
    feature_flags?: { charting_viewer?: boolean };
  };
  test.skip(!config?.feature_flags?.charting_viewer, "charting viewer disabled");
  const { patientMap } = await seedCharting(request);
  const patientId = patientMap.get(1012056);
  if (!patientId) {
    throw new Error("Missing seeded patient 1012056 for share link test.");
  }

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/charting`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 30_000 });

  await page.evaluate(() => {
    // @ts-expect-error - attach test helper to window
    window.__copiedChartingLink = null;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      const original = navigator.clipboard.writeText.bind(navigator.clipboard);
      navigator.clipboard.writeText = async (value: string) => {
        // @ts-expect-error - attach test helper to window
        window.__copiedChartingLink = value;
        return original(value);
      };
    }
  });

  const notesPanel = page
    .locator("section.panel")
    .filter({ has: page.locator(".panel-title", { hasText: "Patient notes" }) });
  await expect(notesPanel).toBeVisible();

  await notesPanel.getByLabel("From").fill("2024-07-02");
  await notesPanel.getByLabel("To").fill("2024-07-03");
  await notesPanel.getByLabel("Category").selectOption("1");
  await notesPanel.getByRole("button", { name: "Copy filter link" }).click();

  const copied = await page.evaluate(() => {
    // @ts-expect-error - read test helper from window
    return window.__copiedChartingLink as string | null;
  });
  expect(copied).not.toBeNull();
  if (!copied) {
    return;
  }
  expect(copied).toContain("charting_notes_from=2024-07-02");
  expect(copied).toContain("charting_notes_to=2024-07-03");
  expect(copied).toContain("charting_notes_category=1");
  expect(copied).not.toContain("charting_notes_q=");

  await page.goto(copied, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 30_000 });
  const notesPanelAfter = page
    .locator("section.panel")
    .filter({ has: page.locator(".panel-title", { hasText: "Patient notes" }) });
  await expect(notesPanelAfter).toBeVisible();
  await expect(notesPanelAfter.getByLabel("From")).toHaveValue("2024-07-02");
  await expect(notesPanelAfter.getByLabel("To")).toHaveValue("2024-07-03");
  await expect(notesPanelAfter.getByLabel("Category")).toHaveValue("1");
  await expect(notesPanelAfter.getByPlaceholder("Find text...")).toHaveValue("");
  await expect(
    notesPanelAfter.getByLabel("Include text search in link")
  ).not.toBeChecked();

  const notesBadge = page.locator(".badge", { hasText: "Patient notes:" }).first();
  await expect(notesBadge).toHaveText(/Patient notes:\s*2/, { timeout: 30_000 });
});

test("charting notes share link includes text search when opted in", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const baseUrl = getBaseUrl();
  const configRes = await request.get(`${baseUrl}/api/config`);
  const config = (await configRes.json()) as {
    feature_flags?: { charting_viewer?: boolean };
  };
  test.skip(!config?.feature_flags?.charting_viewer, "charting viewer disabled");
  const { patientMap } = await seedCharting(request);
  const patientId = patientMap.get(1012056);
  if (!patientId) {
    throw new Error("Missing seeded patient 1012056 for share link opt-in test.");
  }

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/charting`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 30_000 });

  await page.evaluate(() => {
    // @ts-expect-error - attach test helper to window
    window.__copiedChartingLink = null;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      const original = navigator.clipboard.writeText.bind(navigator.clipboard);
      navigator.clipboard.writeText = async (value: string) => {
        // @ts-expect-error - attach test helper to window
        window.__copiedChartingLink = value;
        return original(value);
      };
    }
    window.confirm = () => true;
  });

  const notesPanel = page
    .locator("section.panel")
    .filter({ has: page.locator(".panel-title", { hasText: "Patient notes" }) });
  await expect(notesPanel).toBeVisible();
  await notesPanel.getByPlaceholder("Find text...").fill("note 1");
  await notesPanel.getByLabel("Include text search in link").check();
  await notesPanel.getByRole("button", { name: "Copy filter link" }).click();

  const copied = await page.evaluate(() => {
    // @ts-expect-error - read test helper from window
    return window.__copiedChartingLink as string | null;
  });
  expect(copied).not.toBeNull();
  if (copied) {
    const parsed = new URL(copied);
    expect(parsed.searchParams.get("charting_notes_q_inc")).toBe("1");
    expect(parsed.searchParams.get("charting_notes_q")).toBe("note 1");
  }
});
