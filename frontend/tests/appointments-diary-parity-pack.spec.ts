import fs from "node:fs/promises";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

import { getBaseUrl, primePageAuth } from "./helpers/auth";

type RepresentativeDateEntry = {
  day?: string;
  category?: string;
};

const stage157Dir = path.resolve(__dirname, "..", "..", ".run", "stage157");
const artifactDir = process.env.APPOINTMENTS_DIARY_SCREENSHOT_DIR
  ? path.resolve(process.env.APPOINTMENTS_DIARY_SCREENSHOT_DIR)
  : stage157Dir;
const representativeDatesPath = path.join(stage157Dir, "diary_representative_dates.json");
const fallbackDates = ["2026-01-15", "2026-01-10", "2026-01-11", "2026-01-19", "2026-02-04"];

async function readRepresentativeDates(): Promise<string[]> {
  try {
    const raw = await fs.readFile(representativeDatesPath, "utf-8");
    const parsed = JSON.parse(raw) as { selected_dates?: RepresentativeDateEntry[] };
    const seen = new Set<string>();
    const ordered: string[] = [];
    for (const item of parsed.selected_dates ?? []) {
      const day = item.day;
      if (!day || seen.has(day)) continue;
      seen.add(day);
      ordered.push(day);
      if (ordered.length >= 5) break;
    }
    if (ordered.length > 0) return ordered;
  } catch {
    // fall back to known-in-db dates when the representative manifest has not been generated yet
  }
  return fallbackDates;
}

async function waitForDiaryReady(page: Page) {
  await expect(page.getByTestId("appointments-page")).toBeVisible({ timeout: 20_000 });
  await expect(page).not.toHaveURL(/\/login|\/change-password/);
  await page.waitForTimeout(500);
}

async function switchCalendarView(page: Page, label: "Day" | "Week") {
  const explicit = page.getByTestId(`appointments-calendar-view-${label.toLowerCase()}`);
  if (await explicit.count()) {
    await expect(explicit).toBeVisible({ timeout: 10_000 });
    await explicit.click();
    return;
  }
  const button = page.locator(".rbc-toolbar button").filter({ hasText: new RegExp(`^${label}$`, "i") }).first();
  await expect(button).toBeVisible({ timeout: 10_000 });
  await button.click();
}

async function captureDayScreenshot(
  page: Page,
  options: { baseUrl: string; day: string }
) {
  const { baseUrl, day } = options;
  await page.goto(`${baseUrl}/appointments?date=${day}`, { waitUntil: "domcontentloaded" });
  await waitForDiaryReady(page);
  await page.getByTestId("appointments-view-calendar").click();
  await waitForDiaryReady(page);
  await page.getByLabel("Jump to").fill(day);
  await switchCalendarView(page, "Day");
  await waitForDiaryReady(page);
  await page.screenshot({
    path: path.join(artifactDir, `appointments_day_${day}.png`),
    fullPage: true,
  });
}

async function captureWeekScreenshot(
  page: Page,
  options: { baseUrl: string; anchorDate: string }
) {
  const { baseUrl, anchorDate } = options;
  await page.goto(`${baseUrl}/appointments?date=${anchorDate}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForDiaryReady(page);
  await page.getByTestId("appointments-view-calendar").click();
  await waitForDiaryReady(page);
  await page.getByLabel("Jump to").fill(anchorDate);
  await switchCalendarView(page, "Week");
  await waitForDiaryReady(page);
  await page.screenshot({
    path: path.join(artifactDir, `appointments_week_${anchorDate}.png`),
    fullPage: true,
  });
}

test("stage157 diary screenshot pack", async ({ page, request }) => {
  test.setTimeout(180_000);
  await fs.mkdir(artifactDir, { recursive: true });
  const days = await readRepresentativeDates();
  const baseUrl = getBaseUrl();

  await primePageAuth(page, request);
  for (const day of days) {
    await captureDayScreenshot(page, { baseUrl, day });
  }

  await captureWeekScreenshot(page, {
    baseUrl,
    anchorDate: days[0] ?? fallbackDates[0],
  });
});
