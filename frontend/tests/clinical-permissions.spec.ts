import { expect, test, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";


async function mockCapabilities(page: Page, capabilities: string[]) {
  await page.route("**/api/me/capabilities", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(capabilities),
    });
  });
}


test("clinical viewers get a converged read-only chart and plan", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Clinical",
    last_name: `Read only ${Date.now()}`,
  });
  await primePageAuth(page, request);
  await mockCapabilities(page, ["patients.view", "clinical.view"]);
  const writeRequests: string[] = [];
  page.on("request", (request) => {
    if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method())) {
      writeRequests.push(request.method());
    }
  });

  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });

  const section = page.getByTestId("patient-clinical-section");
  await expect(section).toHaveAttribute("data-clinical-mode", "read-only", {
    timeout: 20_000,
  });
  await expect(page.getByTestId("patient-clinical-read-only")).toBeVisible();
  await expect(page.getByTestId("clinical-chart")).toBeVisible();
  await expect(page.locator('[data-testid^="patient-bpe-score-"]').first()).toBeDisabled();
  await expect(page.getByTestId("patient-bpe-save")).toBeDisabled();
  await page.getByTestId("tooth-button-UR8").click();
  await expect(page.getByTestId("patient-chart-note-body")).toBeDisabled();
  await expect(page.getByTestId("patient-chart-note-add")).toBeDisabled();
  // Current is diagnosis-only; historical treatment controls remain protected.
  await expect(page.getByTestId("patient-chart-procedure-code")).toHaveCount(0);
  await expect(page.getByTestId("patient-chart-procedure-add")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.getByTestId("clinical-chart-view-history").click();
  await page.getByTestId("tooth-button-UR8").click();
  await expect(page.getByTestId("patient-chart-procedure-code")).toBeDisabled();
  await expect(page.getByTestId("patient-chart-procedure-add")).toBeDisabled();

  await page.keyboard.press("Escape");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.getByRole("button", { name: /^Treatment plan/ }).click();
  await expect(page.getByTestId("treatment-planning-panel")).toBeVisible();
  await expect(page.getByTestId("planning-read-only")).toBeVisible();
  await expect(page.getByTestId("planning-start")).toBeDisabled();
  expect(writeRequests).toEqual([]);
});


test("clinical data is not requested when clinical.view is absent", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Clinical",
    last_name: `Denied ${Date.now()}`,
  });
  await primePageAuth(page, request);
  await mockCapabilities(page, ["patients.view"]);
  const clinicalDataRequests: string[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (
      path.includes("/clinical/summary") ||
      path.includes("/tooth-history") ||
      path.includes("/charting/treatment-plan-items") ||
      path.includes("/charting/tooth-state")
    ) {
      clinicalDataRequests.push(path);
    }
  });

  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });

  const section = page.getByTestId("patient-clinical-section");
  await expect(section).toHaveAttribute("data-clinical-mode", "denied", {
    timeout: 20_000,
  });
  await expect(page.getByTestId("patient-clinical-denied")).toHaveText(
    "You do not have permission to view clinical records."
  );
  await expect(page.getByTestId("clinical-chart")).toHaveCount(0);
  expect(clinicalDataRequests).toEqual([]);
});


test("clinical capability failures stay safe and block data loading", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Clinical",
    last_name: `Capability failure ${Date.now()}`,
  });
  await primePageAuth(page, request);
  let clinicalDataRequests = 0;
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path.includes("/clinical/summary") || path.includes("/tooth-history")) {
      clinicalDataRequests += 1;
    }
  });
  await page.route("**/api/me/capabilities", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "text/html",
      body: "<html>private backend response body</html>",
    });
  });

  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByTestId("patient-clinical-denied")).toHaveText(
    "Patient permissions could not be verified.",
    { timeout: 20_000 }
  );
  await expect(page.getByText(/private backend response body/)).toHaveCount(0);
  expect(clinicalDataRequests).toBe(0);
});


test("clinical mutation errors are safe and duplicate clicks stay locked", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Clinical",
    last_name: `Safe failure ${Date.now()}`,
  });
  await primePageAuth(page, request);
  await mockCapabilities(page, ["patients.view", "clinical.view", "clinical.write"]);
  let bpeWrites = 0;
  await page.route(`**/api/patients/${patientId}/clinical/bpe`, async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    bpeWrites += 1;
    await new Promise((resolve) => setTimeout(resolve, 300));
    await route.fulfill({
      status: 500,
      contentType: "text/html",
      body: "<html>private clinical infrastructure response</html>",
    });
  });

  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  const save = page.getByTestId("patient-bpe-save");
  await expect(save).toBeEnabled({ timeout: 20_000 });
  await save.click();
  await expect(save).toBeDisabled();
  await save.click({ force: true }).catch(() => undefined);

  await expect(page.getByText("Unable to save BPE (HTTP 500).", { exact: true })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText(/private clinical infrastructure response/)).toHaveCount(0);
  expect(bpeWrites).toBe(1);
});


test("successful tooth note refresh preserves tooth and surface selection", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Clinical",
    last_name: `Refresh ${Date.now()}`,
  });
  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("patient-clinical-section")).toHaveAttribute(
    "data-clinical-mode",
    "write",
    { timeout: 20_000 }
  );

  const tooth = page.getByTestId("tooth-button-UR8");
  const surface = page.getByTestId("tooth-surface-UR8-O");
  await surface.click();
  await expect(tooth).toHaveAttribute("data-selected", "true");
  await expect(surface).toHaveAttribute("data-selected", "true");

  const summaryResponse = page.waitForResponse((response) => {
    const path = new URL(response.url()).pathname;
    return response.request().method() === "GET" && path.endsWith("/clinical/summary");
  });
  const historyResponse = page.waitForResponse((response) => {
    const path = new URL(response.url()).pathname;
    return response.request().method() === "GET" && path.endsWith("/tooth-history");
  });
  const noteResponse = page.waitForResponse((response) => {
    const path = new URL(response.url()).pathname;
    return response.request().method() === "POST" && path.endsWith("/tooth-notes");
  });
  await page.getByTestId("patient-chart-note-body").fill("Synthetic refresh proof");
  await page.getByTestId("patient-chart-note-add").click();

  expect((await noteResponse).ok()).toBeTruthy();
  expect((await summaryResponse).ok()).toBeTruthy();
  expect((await historyResponse).ok()).toBeTruthy();
  await expect(tooth).toHaveAttribute("data-selected", "true");
  await expect(surface).toHaveAttribute("data-selected", "true");
  await expect(page.getByTestId("patient-tooth-history")).toContainText(
    "Synthetic refresh proof"
  );
});
