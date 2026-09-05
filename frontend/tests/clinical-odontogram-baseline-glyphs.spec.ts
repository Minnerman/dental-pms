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
      baselineCondition: current("missing"),
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
      await expect(svg).toHaveAttribute("aria-label", new RegExp(`${toothKey} molar, current condition deciduous`));
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
