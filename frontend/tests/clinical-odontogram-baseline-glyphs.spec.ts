import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { createElement, type ComponentProps } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { JsxEmit, ModuleKind, transpileModule } from "typescript";

import type { OdontogramBaselineCondition } from "../components/clinical/OdontogramToothSvg";

// Playwright's normal JSX transform produces its browser-mount descriptors,
// not React elements. Compile this local component with the existing TypeScript
// dependency so these component-only tests exercise genuine React server output.
const componentFile = resolve(__dirname, "../components/clinical/OdontogramToothSvg.tsx");
const compiledComponent = transpileModule(readFileSync(componentFile, "utf8"), {
  compilerOptions: { module: ModuleKind.CommonJS, jsx: JsxEmit.ReactJSX },
}).outputText;
const componentModule = { exports: {} as typeof import("../components/clinical/OdontogramToothSvg") };
new Function("require", "module", "exports", compiledComponent)(
  createRequire(componentFile), componentModule, componentModule.exports
);
const { default: OdontogramToothSvg, getOdontogramToothType } = componentModule.exports;

type ToothProps = ComponentProps<typeof OdontogramToothSvg>;
const quadrants = ["UR", "UL", "LR", "LL"] as const;
const historicalRestorations: ToothProps["restorations"] = [
  { type: "crown" },
  { type: "filling", surfaces: ["M"] },
  { type: "root_canal" },
  { type: "post" },
  { type: "implant" },
  { type: "extraction" },
];

function current(
  status: OdontogramBaselineCondition["status"],
  dentition: OdontogramBaselineCondition["dentition"] = "permanent"
): OdontogramBaselineCondition {
  return { status, dentition };
}

// Component-only regression coverage: no backend, patient records, or network
// fixtures. The production SVG implementation is rendered into a blank page.
async function renderTooth(page: Page, toothKey: string, props: Partial<ToothProps> = {}) {
  const markup = renderToStaticMarkup(createElement(OdontogramToothSvg, {
    toothKey,
    toothType: getOdontogramToothType(toothKey),
    ...props,
  }));
  await page.setContent(`<style>body { margin: 40px; } svg { width: 100px; height: 280px; }</style>${markup}`);
  return page.getByTestId(`tooth-svg-${toothKey}`);
}

function naturalRoots(page: Page, toothKey: string) {
  return page.locator(`[data-testid^="tooth-root-${toothKey}-"]`);
}

function historicalMarks(page: Page, toothKey: string) {
  return page.locator(`[data-testid^="tooth-restoration-${toothKey}-"], [data-testid^="tooth-anatomy-restoration-${toothKey}-"]`);
}

test("current missing removes anatomy and surfaces, preserving every quadrant's SVG slot", async ({ page }) => {
  for (const quadrant of quadrants) {
    const toothKey = `${quadrant}6`;
    const before = await (await renderTooth(page, toothKey)).boundingBox();
    const svg = await renderTooth(page, toothKey, {
      baselineCondition: { ...current("missing"), movement: "forward", rotation: "clockwise" },
      restorations: historicalRestorations,
      missing: true,
      extracted: true,
    });
    await expect(svg).toHaveAttribute("viewBox", "0 0 100 280");
    await expect(svg).toHaveAttribute("data-baseline-status", "missing");
    await expect(page.getByTestId(`tooth-anatomy-${toothKey}`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-surface-map-${toothKey}`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-crown-${toothKey}`)).toHaveCount(0);
    await expect(naturalRoots(page, toothKey)).toHaveCount(0);
    await expect(historicalMarks(page, toothKey)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-position-markers-${toothKey}`)).toHaveCount(0);
    const after = await svg.boundingBox();
    expect(after!.width).toBe(before!.width);
    expect(after!.height).toBe(before!.height);
  }
});

test("unerupted teeth show only the crown with a wavy gum line above it in every quadrant", async ({ page }) => {
  for (const quadrant of quadrants) {
    const toothKey = `${quadrant}6`;
    await renderTooth(page, toothKey, {
      baselineCondition: current("unerupted"),
      restorations: historicalRestorations,
      missing: true,
      extracted: true,
    });
    await expect(page.getByTestId(`tooth-anatomy-${toothKey}`)).toHaveAttribute("data-anatomy-parts", "crown gum");
    await expect(naturalRoots(page, toothKey)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-surface-map-${toothKey}`)).toHaveCount(0);
    await expect(historicalMarks(page, toothKey)).toHaveCount(0);
    const gum = page.getByTestId(`tooth-baseline-gum-${toothKey}`);
    await expect(gum).toHaveAttribute("d", /Q.*T/);
    const gumBox = await gum.boundingBox();
    const crownBox = await page.getByTestId(`tooth-crown-${toothKey}`).boundingBox();
    expect(gumBox!.y + gumBox!.height).toBeLessThan(crownBox!.y);
  }
});

test("current implants replace natural roots without inheriting historic root treatments or absence", async ({ page }) => {
  for (const quadrant of quadrants) {
    const toothKey = `${quadrant}6`;
    await renderTooth(page, toothKey, {
      baselineCondition: current("implant"),
      restorations: historicalRestorations,
      missing: true,
      extracted: true,
    });
    await expect(page.getByTestId(`tooth-anatomy-${toothKey}`)).toHaveAttribute("data-anatomy-parts", "crown implant");
    await expect(page.getByTestId(`tooth-baseline-implant-${toothKey}`)).toBeAttached();
    await expect(page.getByTestId(`tooth-implant-body-${toothKey}`)).toBeAttached();
    await expect(page.getByTestId(`tooth-implant-collar-${toothKey}`)).toBeAttached();
    await expect(page.locator(`[data-testid^="tooth-implant-thread-${toothKey}-"]`)).toHaveCount(7);
    await expect(page.getByTestId(`tooth-baseline-implant-${toothKey}`).locator("circle, rect")).toHaveCount(0);
    const apicalThread = await page.getByTestId(`tooth-implant-thread-${toothKey}-1`).boundingBox();
    const cervicalThread = await page.getByTestId(`tooth-implant-thread-${toothKey}-7`).boundingBox();
    expect(cervicalThread!.width).toBeGreaterThan(apicalThread!.width);
    expect(Math.sign(cervicalThread!.y - apicalThread!.y)).toBe(quadrant[0] === "U" ? 1 : -1);
    await expect(page.getByTestId(`tooth-crown-${toothKey}`)).toBeAttached();
    await expect(page.getByTestId(`tooth-surface-map-${toothKey}`)).toBeAttached();
    await expect(naturalRoots(page, toothKey)).toHaveCount(0);
    for (const treatment of ["root_canal", "post", "implant", "missing", "extraction", "extracted"]) {
      await expect(page.getByTestId(`tooth-restoration-${toothKey}-${treatment}`)).toHaveCount(0);
      await expect(page.getByTestId(`tooth-anatomy-restoration-${toothKey}-${treatment}`)).toHaveCount(0);
    }
    await expect(page.getByTestId(`tooth-baseline-implant-${toothKey}`).locator("title")).toHaveCount(0);
  }
});

test("impacted crowns incline toward the adjacent midline-side tooth without moving surface targets", async ({ page }) => {
  for (const quadrant of quadrants) {
    const toothKey = `${quadrant}6`;
    await renderTooth(page, toothKey);
    const before = await page.getByTestId(`tooth-surface-${toothKey}-M`).boundingBox();
    const beforeSurface = await page.getByTestId(`tooth-surface-${toothKey}-M`).getAttribute("points");
    await renderTooth(page, toothKey, {
      baselineCondition: current("impacted"),
      restorations: historicalRestorations,
      missing: true,
      extracted: true,
    });
    const crownAppearance = page.getByTestId(`tooth-crown-appearance-${toothKey}`);
    await expect(crownAppearance).toHaveAttribute("data-impacted", "true");
    // Evaluate the actual composed SVG transform, including quadrant mirroring.
    // The amount is deliberately not asserted: this is a status illustration,
    // not a measured or inferred clinical angulation.
    const direction = await crownAppearance.evaluate((element) => {
      const matrix = (element as SVGGraphicsElement).getCTM()!;
      const neck = new DOMPoint(50, 100).matrixTransform(matrix);
      const tip = new DOMPoint(50, 160).matrixTransform(matrix);
      return { x: tip.x - neck.x, y: tip.y - neck.y };
    });
    expect(Math.sign(direction.x)).toBe(quadrant[1] === "R" ? 1 : -1);
    expect(Math.sign(direction.y)).toBe(quadrant[0] === "U" ? 1 : -1);
    const after = await page.getByTestId(`tooth-surface-${toothKey}-M`).boundingBox();
    expect(after).toEqual(before);
    await expect(page.getByTestId(`tooth-surface-${toothKey}-M`)).toHaveAttribute("points", beforeSurface!);
    await expect(naturalRoots(page, toothKey)).toHaveCount(quadrant[0] === "U" ? 3 : 2);
    for (const treatment of ["root_canal", "post", "implant", "missing", "extraction", "extracted"]) {
      await expect(page.getByTestId(`tooth-restoration-${toothKey}-${treatment}`)).toHaveCount(0);
      await expect(page.getByTestId(`tooth-anatomy-restoration-${toothKey}-${treatment}`)).toHaveCount(0);
    }
  }
});

test("deciduous positions four and five use primary molars in all quadrants without permanent predecessors' marks", async ({ page }) => {
  for (const quadrant of quadrants) {
    for (const position of [4, 5]) {
      const toothKey = `${quadrant}${position}`;
      await renderTooth(page, toothKey);
      const permanentPath = await page.getByTestId(`tooth-crown-${toothKey}`).getAttribute("d");
      const permanentBox = await page.getByTestId(`tooth-crown-${toothKey}`).boundingBox();
      const svg = await renderTooth(page, toothKey, {
        baselineCondition: current("present", "deciduous"),
        restorations: historicalRestorations,
        missing: true,
        extracted: true,
      });
      await expect(svg).toHaveAttribute("data-dentition", "deciduous");
      await expect(svg).toHaveAttribute("aria-label", new RegExp(`${quadrant}${position === 4 ? "D" : "E"} molar, current condition deciduous`));
      await expect(svg).toHaveAttribute("aria-label", new RegExp(`chart position ${toothKey}`));
      await expect(naturalRoots(page, toothKey)).toHaveCount(quadrant[0] === "U" ? 3 : 2);
      await expect(page.getByTestId(`tooth-crown-${toothKey}`)).not.toHaveAttribute("d", permanentPath!);
      const primaryBox = await page.getByTestId(`tooth-crown-${toothKey}`).boundingBox();
      expect(primaryBox!.height).toBeLessThan(permanentBox!.height);
      await expect(historicalMarks(page, toothKey)).toHaveCount(0);
      await expect(page.getByTestId(`tooth-surface-map-${toothKey}`)).toBeAttached();
    }
  }
});

test("an explicit present baseline overrides legacy absence while unspecified baseline preserves the legacy drawing", async ({ page }) => {
  for (const quadrant of quadrants) {
    const toothKey = `${quadrant}6`;
    const legacyProps = { missing: true, extracted: true, restorations: historicalRestorations };
    await renderTooth(page, toothKey, legacyProps);
    await expect(page.getByTestId(`tooth-restoration-${toothKey}-missing`)).toBeAttached();
    await expect(page.getByTestId(`tooth-restoration-${toothKey}-extraction`)).toBeAttached();
    await expect(page.getByTestId(`tooth-anatomy-restoration-${toothKey}-root_canal`)).toBeAttached();
    await expect(page.getByTestId(`tooth-anatomy-restoration-${toothKey}-implant`)).toBeAttached();
    await renderTooth(page, toothKey, { ...legacyProps, baselineCondition: current("present") });
    await expect(page.getByTestId(`tooth-restoration-${toothKey}-missing`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-restoration-${toothKey}-extraction`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-restoration-${toothKey}-implant`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-anatomy-restoration-${toothKey}-implant`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-crown-${toothKey}`)).toBeAttached();
    await expect(page.getByTestId(`tooth-surface-map-${toothKey}`)).toBeAttached();
    await expect(page.getByTestId(`tooth-anatomy-restoration-${toothKey}-crown`)).toBeAttached();
    await expect(naturalRoots(page, toothKey)).toHaveCount(quadrant[0] === "U" ? 3 : 2);
  }
});

test("movement markers point toward or away from the midline without moving teeth or surface hit targets", async ({ page }) => {
  for (const quadrant of quadrants) {
    const toothKey = `${quadrant}6`;
    const before = await (await renderTooth(page, toothKey)).boundingBox();
    const crownBefore = await page.getByTestId(`tooth-crown-${toothKey}`).boundingBox();
    const surfaceBefore = await page.getByTestId(`tooth-surface-${toothKey}-M`).boundingBox();
    for (const movement of ["forward", "backward"] as const) {
      const svg = await renderTooth(page, toothKey, {
        baselineCondition: { ...current("present"), movement },
      });
      const marker = page.getByTestId(`tooth-movement-${toothKey}`);
      const direction = await marker.evaluate((element) => {
        const matrix = (element as SVGGraphicsElement).getCTM()!;
        return new DOMPoint(13, 0).matrixTransform(matrix).x - new DOMPoint(-13, 0).matrixTransform(matrix).x;
      });
      expect(Math.sign(direction)).toBe((quadrant[1] === "R" ? 1 : -1) * (movement === "forward" ? 1 : -1));
      await expect(svg).toHaveAttribute("aria-label", new RegExp(`movement ${movement}`));
      await expect(marker).toHaveAttribute("data-direction", movement);
      expect(await svg.boundingBox()).toEqual(before);
      expect(await page.getByTestId(`tooth-crown-${toothKey}`).boundingBox()).toEqual(crownBefore);
      expect(await page.getByTestId(`tooth-surface-${toothKey}-M`).boundingBox()).toEqual(surfaceBefore);
      const markers = page.getByTestId(`tooth-position-markers-${toothKey}`);
      await expect(markers).toHaveAttribute("pointer-events", "none");
      await expect(markers).toHaveAttribute("data-marker-side", quadrant[0] === "U" ? "above" : "below");
      const markerBox = await markers.boundingBox();
      const anatomyBox = await page.getByTestId(`tooth-anatomy-${toothKey}`).boundingBox();
      if (quadrant[0] === "U") expect(markerBox!.y + markerBox!.height).toBeLessThan(anatomyBox!.y);
      else expect(markerBox!.y).toBeGreaterThan(anatomyBox!.y + anatomyBox!.height);
    }
  }
});

test("rotation direction is screen-relative in every quadrant and can coexist with movement", async ({ page }) => {
  for (const quadrant of quadrants) {
    const toothKey = `${quadrant}6`;
    for (const rotation of ["clockwise", "anticlockwise"] as const) {
      await renderTooth(page, toothKey, {
        baselineCondition: { ...current("present"), movement: "forward", rotation },
      });
      const marker = page.getByTestId(`tooth-rotation-${toothKey}`);
      await expect(marker).toHaveAttribute("data-direction", rotation);
      const directions = await marker.evaluate((element) => {
        const matrix = (element as SVGGraphicsElement).getCTM()!;
        const origin = new DOMPoint(0, 0).matrixTransform(matrix);
        const right = new DOMPoint(10, 0).matrixTransform(matrix);
        const below = new DOMPoint(0, 10).matrixTransform(matrix);
        return { x: right.x - origin.x, y: below.y - origin.y };
      });
      expect(Math.sign(directions.x)).toBe(rotation === "clockwise" ? 1 : -1);
      expect(Math.sign(directions.y)).toBe(1);
      const movementBox = await page.getByTestId(`tooth-movement-${toothKey}`).boundingBox();
      const rotationBox = await marker.boundingBox();
      expect(movementBox!.x + movementBox!.width).toBeLessThan(rotationBox!.x);
      await expect(page.getByTestId(`tooth-svg-${toothKey}`)).toHaveAttribute("aria-label", new RegExp(`rotation ${rotation}`));
    }
  }
});

test("movement-only records preserve legacy absence and restorations without implying present", async ({ page }) => {
  for (const quadrant of quadrants) {
    const toothKey = `${quadrant}6`;
    const legacy = { missing: true, extracted: true, restorations: historicalRestorations };
    const before = await (await renderTooth(page, toothKey, legacy)).boundingBox();
    const svg = await renderTooth(page, toothKey, {
      ...legacy,
      baselineCondition: { movement: "backward", rotation: "anticlockwise" },
    });
    await expect(svg).not.toHaveAttribute("data-baseline-status", /.+/);
    await expect(svg).not.toHaveAttribute("aria-label", /current condition/);
    await expect(page.getByTestId(`tooth-restoration-${toothKey}-missing`)).toBeAttached();
    await expect(page.getByTestId(`tooth-restoration-${toothKey}-extraction`)).toBeAttached();
    await expect(page.getByTestId(`tooth-anatomy-restoration-${toothKey}-root_canal`)).toBeAttached();
    await expect(page.getByTestId(`tooth-anatomy-restoration-${toothKey}-implant`)).toBeAttached();
    expect(await svg.boundingBox()).toEqual(before);
    await renderTooth(page, toothKey, { baselineCondition: { movement: null, rotation: null } });
    await expect(page.getByTestId(`tooth-position-markers-${toothKey}`)).toHaveCount(0);
  }
});

test("synthetic implant and position-marker gallery keeps every tooth slot the same size", async ({ page }, testInfo) => {
  const examples = quadrants.flatMap((quadrant) => [
    { toothKey: `${quadrant}6`, baselineCondition: current("implant") },
    { toothKey: `${quadrant}5`, baselineCondition: { ...current("present"), movement: "forward" as const, rotation: "clockwise" as const } },
  ]);
  const cards = examples.map(({ toothKey, baselineCondition }) =>
    `<section><strong>${toothKey}</strong>${renderToStaticMarkup(createElement(OdontogramToothSvg, {
      toothKey, toothType: getOdontogramToothType(toothKey), baselineCondition,
    }))}<span>${baselineCondition.status === "implant" ? "Existing implant" : "Forward · clockwise"}</span></section>`
  ).join("");
  await page.setViewportSize({ width: 1100, height: 830 });
  await page.setContent(`<style>body{margin:20px;background:#f7f7f5;color:#242320;font:14px Arial}.gallery{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.gallery section{display:grid;justify-items:center;gap:22px;background:white;padding:16px;border:1px solid #ddd;border-radius:10px}.gallery svg{width:86px;height:241px}.gallery span{font-size:12px}</style><div class="gallery">${cards}</div>`);
  const boxes = await page.locator(".odontogram-tooth-svg").evaluateAll((elements) => elements.map((element) => {
    const rect = element.getBoundingClientRect();
    return { width: rect.width, height: rect.height };
  }));
  expect(boxes).toHaveLength(8);
  for (const box of boxes) expect(box).toEqual(boxes[0]);
  await page.screenshot({ path: testInfo.outputPath("baseline-symbol-gallery.png"), fullPage: true });
});
