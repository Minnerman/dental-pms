import { expect, test } from "@playwright/test";

import { getOdontogramSurfaceAnchor } from "../components/clinical/OdontogramToothSvg";
import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

test("larger tooth silhouettes remain legible and reachable at desktop and narrow widths", async ({
  page, request,
}, testInfo) => {
  await primePageAuth(page, request);
  const patientId = await createPatient(request, {
    first_name: "Synthetic",
    last_name: "Tooth shapes",
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical`);
  const chart = page.getByTestId("clinical-chart");
  await expect(chart).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Loading clinical…")).toHaveCount(0);

  // The schematic incisors, canines, premolars and molars no longer share an oval crown.
  const crowns = await Promise.all(["UR1", "UR3", "UR4", "UR6"].map((tooth) =>
    page.getByTestId(`tooth-crown-${tooth}`).getAttribute("d")
  ));
  expect(new Set(crowns).size).toBe(4);
  expect(await page.getByTestId("tooth-crown-UR1").getAttribute("d")).not.toBe(
    await page.getByTestId("tooth-crown-LR1").getAttribute("d")
  );
  expect(await page.getByTestId("tooth-crown-UR1").getAttribute("d")).not.toBe(
    await page.getByTestId("tooth-crown-UR2").getAttribute("d")
  );
  // Each drawing has its own shading references; selection must not recolour another tooth.
  const illustrationIds = await chart.locator("defs > [id]").evaluateAll((elements) =>
    elements.map((element) => element.id)
  );
  // Three shading references per tooth are unchanged; Current now also has
  // independent root/crown definitions and five surface patterns per tooth,
  // all globally unique so one finding cannot recolour another tooth.
  await expect(chart.locator("defs > radialGradient, defs > linearGradient")).toHaveCount(96);
  await expect(chart.locator('defs > pattern[id^="root-defect-"]')).toHaveCount(32);
  await expect(chart.locator('defs > clipPath[id^="root-hit-"]')).toHaveCount(32);
  await expect(chart.locator('defs > clipPath[id^="root-clip-"]')).toHaveCount(52);
  await expect(chart.locator('defs > pattern[id^="crown-defect-"]')).toHaveCount(32);
  await expect(chart.locator('defs > clipPath[id^="crown-clip-"]')).toHaveCount(32);
  for (const pattern of ["early", "arrested", "established", "unspecified", "defective"]) {
    await expect(chart.locator(`defs > pattern[id^="surface-${pattern}-"]`)).toHaveCount(32);
  }
  expect(illustrationIds).toHaveLength(436);
  expect(new Set(illustrationIds).size).toBe(illustrationIds.length);
  expect(await page.getByTestId("tooth-anatomy-UL6").getAttribute("transform")).toContain("scale(-1 1)");
  expect(await page.getByTestId("tooth-anatomy-LL6").getAttribute("transform")).toContain("scale(-1 -1)");
  await expect(page.getByTestId("tooth-crown-groove-UR6-1")).toBeAttached();
  const upperCentral = await page.getByTestId("tooth-crown-UR1").boundingBox();
  const lowerCentral = await page.getByTestId("tooth-crown-LR1").boundingBox();
  expect(upperCentral!.width).toBeGreaterThan(lowerCentral!.width);

  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    const anatomy = page.getByTestId("tooth-anatomy-UR6");
    await anatomy.scrollIntoViewIfNeeded();
    const before = await anatomy.boundingBox();
    expect(before!.height).toBeGreaterThan(95);
    const surface = await page.getByTestId("tooth-surface-map-UR6").boundingBox();
    expect(before!.y + before!.height).toBeLessThan(surface!.y);
    await page.getByTestId("tooth-button-UR6").click({ position: { x: 20, y: 30 } });
    const after = await anatomy.boundingBox();
    expect(after!.width).toBeCloseTo(before!.width, 1);
    expect(after!.height).toBeCloseTo(before!.height, 1);
    await page.keyboard.press("Escape");
    for (const tooth of ["UR8", "UL8", "LR8", "LL8"]) {
      await page.getByTestId(`tooth-button-${tooth}`).click({ position: { x: 20, y: 30 } });
      await expect(page.getByTestId(`tooth-button-${tooth}`)).toHaveAttribute("data-selected", "true");
      await page.keyboard.press("Escape");
    }
    // Arches scroll inside their own region, not off the document edge.
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  }
  await page.setViewportSize({ width: 1440, height: 1500 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.mouse.move(0, 0);
  await chart.screenshot({ path: testInfo.outputPath("tooth-shapes-desktop.png") });
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await chart.screenshot({ path: testInfo.outputPath("tooth-shapes-dark.png") });
});

test("surface markers use the surface map coordinates, not the reflected root coordinates", () => {
  for (const toothType of ["incisor", "canine", "premolar", "molar"] as const) {
    for (const surface of ["M", "O", "I", "D", "B", "L"] as const) {
      const upper = Number.parseFloat(getOdontogramSurfaceAnchor(toothType, surface, true).top);
      const lower = Number.parseFloat(getOdontogramSurfaceAnchor(toothType, surface, false).top);
      expect(upper - lower).toBeCloseTo(180 / 280 * 100);
      expect(lower).toBeGreaterThan(0);
      expect(lower).toBeLessThan(100 / 280 * 100);
    }
  }
});
