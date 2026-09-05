import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

type Condition = "present" | "missing" | "deciduous" | "implant" | "unerupted" | "impacted";
type Snapshot = {
  patient_id: number;
  teeth: Record<string, { condition: Condition | null; revision: number }>;
  note_teeth: string[];
};

function conditionsPath(patientId: string) {
  return `/api/patients/${patientId}/clinical/tooth-conditions`;
}

async function snapshot(request: APIRequestContext, patientId: string, token: string) {
  const response = await request.get(`${getBaseUrl()}${conditionsPath(patientId)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as Snapshot;
}

async function openChart(page: Page, patientId: string) {
  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical?clinicalView=current`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading/i);
}

async function openToothMenu(page: Page, tooth: string) {
  await page.getByTestId(`tooth-label-${tooth}`).click({ button: "right" });
  await expect(page.getByTestId("clinical-tooth-action-menu")).toBeVisible();
  await expect(page.getByTestId("clinical-tooth-action-menu")).toContainText(tooth);
}

async function selectCondition(page: Page, patientId: string, tooth: string, condition: Condition) {
  await openToothMenu(page, tooth);
  const saved = page.waitForResponse((response) =>
    response.request().method() === "POST" &&
    new URL(response.url()).pathname === conditionsPath(patientId)
  );
  await page.getByTestId(`clinical-baseline-condition-${condition}`).click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  expect(response.request().postDataJSON()).toMatchObject({ teeth: [tooth], condition });
  await expectConditionGlyph(page, tooth, condition);
}

async function expectConditionGlyph(page: Page, tooth: string, condition: Condition) {
  const svg = page.getByTestId(`tooth-svg-${tooth}`);
  await expect(svg).toHaveAttribute("data-baseline-status", condition === "deciduous" ? "present" : condition);
  await expect(svg).toHaveAttribute("data-dentition", condition === "deciduous" ? "deciduous" : "permanent");
  await expect(page.getByTestId(`tooth-label-${tooth}`)).toBeVisible();
  if (condition === "missing") {
    await expect(page.getByTestId(`tooth-anatomy-${tooth}`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-surface-map-${tooth}`)).toHaveCount(0);
    return;
  }
  await expect(page.getByTestId(`tooth-crown-${tooth}`)).toBeAttached();
  if (condition === "unerupted") {
    await expect(page.getByTestId(`tooth-baseline-gum-${tooth}`)).toBeAttached();
    await expect(page.locator(`[data-testid^="tooth-root-${tooth}-"]`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-surface-map-${tooth}`)).toHaveCount(0);
  } else if (condition === "implant") {
    await expect(page.getByTestId(`tooth-baseline-implant-${tooth}`)).toBeAttached();
    await expect(page.locator(`[data-testid^="tooth-root-${tooth}-"]`)).toHaveCount(0);
  } else if (condition === "impacted") {
    await expect(page.getByTestId(`tooth-crown-appearance-${tooth}`)).toHaveAttribute("data-impacted", "true");
    await expect(page.getByTestId(`tooth-crown-appearance-${tooth}`)).toHaveAttribute("transform", /rotate\(/);
  } else {
    await expect(page.getByTestId(`tooth-root-${tooth}-1`)).toBeAttached();
    await expect(page.getByTestId(`tooth-surface-map-${tooth}`)).toBeAttached();
  }
}

test("tooth-label menu records each current condition, persists after reload and never bills treatment", async ({ page, request }) => {
  const token = await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `Baseline conditions ${Date.now()}` });
  const headers = { Authorization: `Bearer ${token}` };
  const financeBefore = await request.get(`${getBaseUrl()}/api/patients/${patientId}/finance-summary`, { headers });
  expect(financeBefore.ok()).toBeTruthy();
  const originalFinance = await financeBefore.json();
  await openChart(page, patientId);
  await expect(page.getByTestId("tooth-label-UR5")).toHaveCSS("font-size", "18.7px");
  await expect(page.getByTestId("tooth-label-LL1")).toHaveCSS("font-size", "18.7px");
  await openToothMenu(page, "UR5");
  await expect(page.getByTestId("clinical-baseline-repeat")).toBeDisabled();
  await page.keyboard.press("Escape");

  for (const condition of ["missing", "deciduous", "implant", "unerupted", "impacted", "present"] as const) {
    await selectCondition(page, patientId, "UR5", condition);
    const stored = await snapshot(request, patientId, token);
    expect(stored.teeth.UR5.condition).toBe(condition);
    expect(stored.teeth.UR5.revision).toBeGreaterThan(0);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expectConditionGlyph(page, "UR5", condition);
  }

  const summaryResponse = await request.get(`${getBaseUrl()}/api/patients/${patientId}/clinical/summary`, { headers });
  expect(summaryResponse.ok()).toBeTruthy();
  expect(await summaryResponse.json()).toMatchObject({ recent_procedures: [], treatment_plan_items: [], recent_tooth_notes: [] });
  const financeAfter = await request.get(`${getBaseUrl()}/api/patients/${patientId}/finance-summary`, { headers });
  expect(financeAfter.ok()).toBeTruthy();
  expect(await financeAfter.json()).toEqual(originalFinance);
});

test("repeat applies the last successful tooth condition but does not carry into another patient", async ({ page, request }) => {
  const token = await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `Baseline repeat ${Date.now()}` });
  await openChart(page, patientId);
  await selectCondition(page, patientId, "UR5", "implant");
  await openToothMenu(page, "LL6");
  const saved = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === conditionsPath(patientId));
  await page.getByTestId("clinical-baseline-repeat").click();
  expect((await saved).ok()).toBeTruthy();
  await expectConditionGlyph(page, "LL6", "implant");
  const stored = await snapshot(request, patientId, token);
  expect(stored.teeth.UR5.condition).toBe("implant");
  expect(stored.teeth.LL6.condition).toBe("implant");

  const nextPatient = await createPatient(request, { first_name: "Synthetic", last_name: `Repeat boundary ${Date.now()}` });
  await openChart(page, nextPatient);
  await openToothMenu(page, "UR5");
  await expect(page.getByTestId("clinical-baseline-repeat")).toBeDisabled();
  expect((await snapshot(request, nextPatient, token)).teeth).toEqual({});
});

test("all in arch missing requires confirmation and saves exactly the selected 16-tooth arch", async ({ page, request }) => {
  const token = await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `Arch baseline ${Date.now()}` });
  await openChart(page, patientId);
  const writes: Array<{ teeth: string[]; condition: string; expected_revisions: Record<string, number> }> = [];
  page.on("request", (outgoing) => {
    if (outgoing.method() === "POST" && new URL(outgoing.url()).pathname === conditionsPath(patientId)) writes.push(outgoing.postDataJSON());
  });
  await openToothMenu(page, "UR5");
  page.once("dialog", async (dialog) => {
    expect(dialog.type()).toBe("confirm");
    await dialog.dismiss();
  });
  await page.getByTestId("clinical-baseline-arch-missing").click();
  expect((await snapshot(request, patientId, token)).teeth).toEqual({});
  expect(writes).toEqual([]);

  await openToothMenu(page, "UR5");
  page.once("dialog", (dialog) => dialog.accept());
  const saved = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === conditionsPath(patientId));
  await page.getByTestId("clinical-baseline-arch-missing").click();
  expect((await saved).ok()).toBeTruthy();
  const upperTeeth = ["R", "L"].flatMap((side) => Array.from({ length: 8 }, (_, index) => `U${side}${index + 1}`)).sort();
  expect(writes).toHaveLength(1);
  expect([...writes[0].teeth].sort()).toEqual(upperTeeth);
  expect(writes[0].condition).toBe("missing");
  expect(Object.keys(writes[0].expected_revisions).sort()).toEqual(upperTeeth);
  const stored = await snapshot(request, patientId, token);
  expect(Object.keys(stored.teeth).sort()).toEqual(upperTeeth);
  for (const tooth of upperTeeth) await expectConditionGlyph(page, tooth, "missing");
  for (const side of ["R", "L"]) {
    for (let position = 1; position <= 8; position += 1) {
      await expect(page.getByTestId(`tooth-crown-L${side}${position}`)).toBeAttached();
    }
  }
  await page.reload({ waitUntil: "domcontentloaded" });
  await expectConditionGlyph(page, "UR8", "missing");
  await expectConditionGlyph(page, "UL8", "missing");
  await expect(page.getByTestId("tooth-crown-LL6")).toBeAttached();
});

test("a saved tooth note creates its sticky-note flag and appears in tooth details after reload", async ({ page, request }) => {
  const token = await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `Tooth note flag ${Date.now()}` });
  const note = `Synthetic baseline tooth observation ${Date.now()}`;
  // The practice uses an HTTP origin, where randomUUID may be unavailable.
  await page.addInitScript(() => {
    Object.defineProperty(window.crypto, "randomUUID", { configurable: true, value: undefined });
  });
  await openChart(page, patientId);
  await expect(page.getByTestId("tooth-note-flag-UR5")).toHaveCount(0);
  await openToothMenu(page, "UR5");
  await page.getByTestId("clinical-chart-menu-add-note").click();
  await expect(page.getByTestId("patient-chart-note-body")).toBeFocused();
  await page.getByTestId("patient-chart-note-body").fill(note);
  const saved = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === `/api/patients/${patientId}/tooth-notes`);
  await page.getByTestId("patient-chart-note-add").click();
  expect((await saved).ok()).toBeTruthy();
  await expect(page.getByTestId("tooth-note-flag-UR5")).toBeVisible();
  expect((await snapshot(request, patientId, token)).note_teeth).toContain("UR5");
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("tooth-note-flag-UR5")).toBeVisible();
  await openToothMenu(page, "UR5");
  await page.getByTestId("clinical-chart-menu-view-timeline").click();
  await expect(page.getByTestId("patient-tooth-history")).toBeVisible();
  await expect(page.getByTestId("patient-tooth-history")).toContainText(note);
});

test("read-only viewers can inspect tooth details but cannot record baseline conditions", async ({ page, request }) => {
  await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `Read only baseline ${Date.now()}` });
  await page.route("**/api/me/capabilities", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(["patients.view", "clinical.view"]) }));
  const writes: string[] = [];
  page.on("request", (outgoing) => {
    if (outgoing.method() === "POST" && new URL(outgoing.url()).pathname === conditionsPath(patientId)) writes.push(outgoing.method());
  });
  await openChart(page, patientId);
  await expect(page.getByTestId("patient-clinical-section")).toHaveAttribute("data-clinical-mode", "read-only");
  await openToothMenu(page, "UR5");
  for (const condition of ["present", "missing", "deciduous", "implant", "unerupted", "impacted"] as const) {
    await expect(page.getByTestId(`clinical-baseline-condition-${condition}`)).toBeDisabled();
  }
  await expect(page.getByTestId("clinical-baseline-repeat")).toBeDisabled();
  await expect(page.getByTestId("clinical-baseline-arch-missing")).toBeDisabled();
  await expect(page.getByTestId("clinical-chart-menu-view-timeline")).toBeEnabled();
  expect(writes).toEqual([]);
});

test("failed baseline saves do not draw the requested condition or expose a raw server response", async ({ page, request }) => {
  const token = await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `Baseline save failure ${Date.now()}` });
  await openChart(page, patientId);
  await page.route(`**${conditionsPath(patientId)}`, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    await route.fulfill({ status: 500, contentType: "text/html", body: "<html>private baseline infrastructure response</html>" });
  });
  await openToothMenu(page, "UR5");
  await page.getByTestId("clinical-baseline-condition-missing").click();
  await expect(page.getByTestId("clinical-baseline-error")).toBeVisible();
  await expect(page.getByTestId("clinical-baseline-error")).toContainText(/unable|failed|could not be confirmed/i);
  await expect(page.getByText(/private baseline infrastructure response/)).toHaveCount(0);
  await expect(page.getByTestId("tooth-crown-UR5")).toBeAttached();
  await expect(page.getByTestId("tooth-svg-UR5")).not.toHaveAttribute("data-baseline-status", "missing");
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/saved/i);
  expect((await snapshot(request, patientId, token)).teeth).toEqual({});
  await openToothMenu(page, "UR5");
  await expect(page.getByTestId("clinical-baseline-repeat")).toBeDisabled();
});

test("a stale revision is rejected and an explicit refresh loads the newer observation", async ({ page, request }) => {
  const token = await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `Baseline conflict ${Date.now()}` });
  await openChart(page, patientId);
  // Simulate another operator recording a current observation after this page loaded.
  const concurrentSave = await request.post(`${getBaseUrl()}${conditionsPath(patientId)}`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { teeth: ["UR5"], condition: "missing", expected_revisions: { UR5: 0 } },
  });
  expect(concurrentSave.ok()).toBeTruthy();
  await openToothMenu(page, "UR5");
  const conflict = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === conditionsPath(patientId));
  await page.getByTestId("clinical-baseline-condition-implant").click();
  expect((await conflict).status()).toBe(409);
  await expect(page.getByTestId("clinical-baseline-error")).toContainText(/changed|refresh/i);
  await expect(page.getByTestId("tooth-baseline-implant-UR5")).toHaveCount(0);
  expect((await snapshot(request, patientId, token)).teeth.UR5.condition).toBe("missing");
  await page.getByTestId("clinical-baseline-error").getByRole("button", { name: "Refresh conditions" }).click();
  await expectConditionGlyph(page, "UR5", "missing");
  await openToothMenu(page, "UR5");
  await expect(page.getByTestId("clinical-baseline-repeat")).toBeDisabled();
});
