import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

test("one dotted midline separates both arches and follows their shared horizontal scroll", async ({
  page,
  request,
}) => {
  await primePageAuth(page, request);
  const patientId = await createPatient(request, {
    first_name: "Synthetic",
    last_name: "Chart midline",
  });
  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical`);
  const chart = page.getByTestId("clinical-chart");
  const midline = page.getByTestId("clinical-chart-midline");
  await expect(chart).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Loading clinical…")).toHaveCount(0);
  await expect(midline).toHaveCount(1);
  await expect(midline).toHaveAttribute("aria-hidden", "true");
  await expect(midline).toHaveCSS("pointer-events", "none");
  await expect(midline).toHaveCSS("border-left-style", "dotted");

  const readGeometry = () => page.evaluate(() => {
    const rect = (id: string) => {
      const element = document.querySelector(`[data-testid="${id}"]`)!;
      const box = element.getBoundingClientRect();
      return { left: box.left, right: box.right, top: box.top, bottom: box.bottom };
    };
    const line = rect("clinical-chart-midline");
    const upperRight = rect("tooth-button-UR1");
    const upperLeft = rect("tooth-button-UL1");
    const lowerRight = rect("tooth-button-LR1");
    const lowerLeft = rect("tooth-button-LL1");
    return {
      lineX: (line.left + line.right) / 2,
      upperCentre: (upperRight.right + upperLeft.left) / 2,
      lowerCentre: (lowerRight.right + lowerLeft.left) / 2,
      upperGap: upperLeft.left - upperRight.right,
      lowerGap: lowerLeft.left - lowerRight.right,
      fullHeight: line.top <= upperRight.top && line.bottom >= lowerLeft.bottom,
      documentFits: document.documentElement.scrollWidth <= window.innerWidth + 1,
    };
  });

  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await chart.evaluate((element) => { element.scrollLeft = 0; });
    const before = await readGeometry();
    expect(before.lineX).toBeCloseTo(before.upperCentre, 0);
    expect(before.lineX).toBeCloseTo(before.lowerCentre, 0);
    expect(before.upperGap).toBeGreaterThanOrEqual(24);
    expect(before.lowerGap).toBeGreaterThanOrEqual(24);
    expect(before.fullHeight).toBeTruthy();
    expect(before.documentFits).toBeTruthy();

    const distance = await chart.evaluate((element) => {
      element.scrollLeft = (element.scrollWidth - element.clientWidth) / 2;
      return element.scrollLeft;
    });
    const after = await readGeometry();
    expect(after.lineX).toBeCloseTo(before.lineX - distance, 0);
    expect(after.lineX).toBeCloseTo(after.upperCentre, 0);
    expect(after.lineX).toBeCloseTo(after.lowerCentre, 0);
    if (width < 1096) expect(distance).toBeGreaterThan(0);

    // The decorative separator must not alter nearby tooth selection or menus.
    for (const tooth of ["UR1", "UL1", "LR1", "LL1"]) {
      const button = page.getByTestId(`tooth-button-${tooth}`);
      await button.scrollIntoViewIfNeeded();
      const buttonBox = await button.boundingBox();
      const anatomyBox = await page.getByTestId(`tooth-anatomy-${tooth}`).boundingBox();
      expect(buttonBox).not.toBeNull();
      expect(anatomyBox).not.toBeNull();
      // Lower teeth have their surface map above the anatomy, so a fixed y
      // would exercise the surface menu instead of the whole-tooth menu.
      await button.click({
        button: "right",
        position: {
          x: anatomyBox!.x + anatomyBox!.width / 2 - buttonBox!.x,
          y: anatomyBox!.y + anatomyBox!.height / 2 - buttonBox!.y,
        },
      });
      await expect(button).toHaveAttribute("data-selected", "true");
      await expect(page.getByTestId("clinical-tooth-action-menu")).toContainText(`${tooth} · Whole tooth`);
      await page.keyboard.press("Escape");
    }
    expect((await readGeometry()).documentFits).toBeTruthy();
  }
});
