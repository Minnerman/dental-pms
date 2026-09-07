import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { createElement, type ComponentProps } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { JsxEmit, ModuleKind, ScriptTarget, transpileModule } from "typescript";
import { implantScrewAnatomy } from "../components/clinical/toothAnatomy";
import type { OdontogramPlannedOverlay } from "../components/clinical/OdontogramToothSvg";

// Actual renderer, synthetic props and a blank browser only: no clinical API.
const componentFile = resolve(__dirname, "../components/clinical/OdontogramToothSvg.tsx");
const componentModule = { exports: {} as typeof import("../components/clinical/OdontogramToothSvg") };
new Function("require", "module", "exports", transpileModule(readFileSync(componentFile, "utf8"), {
  compilerOptions: { module: ModuleKind.CommonJS, jsx: JsxEmit.ReactJSX, target: ScriptTarget.ES2017 },
}).outputText)(createRequire(componentFile), componentModule, componentModule.exports);
const { default: Tooth, getOdontogramToothType } = componentModule.exports;
type Props = ComponentProps<typeof Tooth>;
let sequence = 0;
const quadrants = ["UR", "UL", "LR", "LL"];
const noop = () => {};
function markup(tooth: string, props: Partial<Props>) {
  return renderToStaticMarkup(createElement(Tooth, { toothKey: tooth, toothType: getOdontogramToothType(tooth), ...props }),
    { identifierPrefix: `planning-${sequence++}-` });
}
const chartCss = readFileSync(resolve(__dirname, "../components/clinical/TreatmentPlanningChart.module.css"), "utf8");
const toothSizing = chartCss.match(/\.tooth > :global\(\.odontogram-tooth-svg\) \{([^}]+)\}/)![1];
const css = `body{margin:24px;font:14px system-ui;background:#faf8f4;color:#282624}.tooth{display:flow-root;width:100px}.tooth>.odontogram-tooth-svg{${toothSizing}}.clinical-root-halo,.clinical-crown-halo,.clinical-surface-halo{opacity:0}`;
async function render(page: Page, tooth: string, props: Partial<Props>) {
  await page.setContent(`<style>${css}</style><div class="tooth">${markup(tooth, props)}</div>`);
  return page.getByTestId(`tooth-svg-${tooth}`);
}
const overlay = (kind: OdontogramPlannedOverlay["kind"], props: Partial<OdontogramPlannedOverlay> = {}): OdontogramPlannedOverlay => ({
  id: kind, kind, label: `Synthetic ${kind.replaceAll("_", " ")}`, status: "planned", ...props,
});

test("planned tooth, root and crown work preserves all captured finding paths and slot geometry", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    const base: Partial<Props> = {
      baselineCondition: { status: "present", movement: "forward", rotation: "clockwise" },
      hasToothNote: true,
      rootConditions: { "1": { condition: "filled_defective", apicectomy: true } },
      crownCondition: { kind: "gold", issues: ["defective"] },
      surfaceObservations: { M: { kind: "restored", material: "resin", condition: "sound", defects: [] } },
    };
    const before = await render(page, tooth, base);
    const bounds = await before.boundingBox();
    const captured = await before.locator(`[data-testid^="tooth-root-${tooth}-"], [data-testid="tooth-crown-${tooth}"], [data-testid="clinical-surface-fill-${tooth}-M"]`).evaluateAll((elements) => elements.map((el) => [el.getAttribute("d"), el.getAttribute("points"), el.getAttribute("fill")?.replace(/url\(#root-[^)]+\)/, "root-gradient")]));
    await render(page, tooth, { ...base, plannedOverlays: [overlay("extraction"), overlay("root_canal"), overlay("crown")] });
    expect(await page.getByTestId(`tooth-svg-${tooth}`).boundingBox()).toEqual(bounds);
    const after = await page.locator(`[data-testid^="tooth-root-${tooth}-"], [data-testid="tooth-crown-${tooth}"], [data-testid="clinical-surface-fill-${tooth}-M"]`).evaluateAll((elements) => elements.map((el) => [el.getAttribute("d"), el.getAttribute("points"), el.getAttribute("fill")?.replace(/url\(#root-[^)]+\)/, "root-gradient")]));
    expect(after).toEqual(captured);
    await expect(page.getByTestId(`clinical-root-finding-${tooth}-1`)).toBeAttached();
    await expect(page.getByTestId(`clinical-crown-issue-${tooth}-defective`)).toBeAttached();
    await expect(page.getByTestId(`tooth-note-flag-${tooth}`)).toBeAttached();
    await expect(page.getByTestId(`tooth-movement-${tooth}`)).toBeAttached();
    await expect(page.getByTestId(`tooth-planning-layer-${tooth}`)).toHaveAttribute("pointer-events", "none");
    await expect(page.getByTestId(`tooth-planning-overlay-${tooth}-extraction`)).toHaveAttribute("data-plan-status", "planned");
    await expect(page.getByTestId(`tooth-planning-count-${tooth}-planned`)).toContainText("P3");
  }
});

test("a planned implant remains an overlay on a missing position, without adding present anatomy or root controls", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}5`;
    await render(page, tooth, { baselineCondition: { status: "missing" }, rootConditions: {}, crownCondition: null,
      surfaceObservations: {}, onRootClick: noop, onCrownClick: noop, onDiagnosticSurfaceClick: noop,
      plannedOverlays: [overlay("implant")] });
    await expect(page.getByTestId(`tooth-svg-${tooth}`)).toHaveAttribute("data-baseline-status", "missing");
    await expect(page.getByTestId(`tooth-anatomy-${tooth}`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-baseline-implant-${tooth}`)).toHaveCount(0);
    await expect(page.getByTestId(`clinical-root-${tooth}`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-surface-map-${tooth}`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-planning-implant-${tooth}-implant`).locator("path").first()).toHaveAttribute("d", implantScrewAnatomy.body);
    await expect(page.getByTestId(`tooth-planning-overlay-${tooth}-implant`)).toHaveAttribute("aria-label", /Planned:.*Captured diagnosis unchanged/);
  }
});

test("planned surface outlines use the captured canonical M/D and upper P/lower L positions", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    const inner = quadrant.startsWith("U") ? "P" : "L";
    await render(page, tooth, { rootConditions: {}, surfaceObservations: {}, onDiagnosticSurfaceClick: noop,
      plannedOverlays: [overlay("filling", { surfaces: ["M", "O", "D", inner] })] });
    for (const surface of ["M", "O", "D", inner]) {
      const baseline = await page.getByTestId(`clinical-surface-${tooth}-${surface}`).locator("polygon").first().evaluate((element) => {
        const polygon = element as SVGPolygonElement;
        return Array.from(polygon.points).map((point) => { const p = new DOMPoint(point.x, point.y).matrixTransform(polygon.getScreenCTM()!); return [p.x, p.y]; });
      });
      const planned = await page.getByTestId(`tooth-planning-surface-${tooth}-filling-${surface}`).locator("polygon").first().evaluate((element) => {
        const polygon = element as SVGPolygonElement;
        return Array.from(polygon.points).map((point) => { const p = new DOMPoint(point.x, point.y).matrixTransform(polygon.getScreenCTM()!); return [p.x, p.y]; });
      });
      expect(planned).toEqual(baseline);
    }
    const m = await page.getByTestId(`tooth-planning-surface-${tooth}-filling-M`).boundingBox();
    const d = await page.getByTestId(`tooth-planning-surface-${tooth}-filling-D`).boundingBox();
    expect(quadrant.endsWith("R") ? m!.x > d!.x : m!.x < d!.x).toBeTruthy();
  }
});

test("planned and completed treatments stay distinguishable without completed labels on outstanding work", async ({ page }) => {
  await render(page, "UL6", { rootConditions: {}, surfaceObservations: {}, crownCondition: { kind: "porcelain", issues: [] },
    plannedOverlays: [overlay("crown"), overlay("root_canal", { status: "completed" }), overlay("other")] });
  await expect(page.getByTestId("tooth-planning-overlay-UL6-crown")).toHaveAttribute("aria-label", /^Planned:/);
  await expect(page.getByTestId("tooth-planning-overlay-UL6-root_canal")).toHaveAttribute("aria-label", /^Completed:/);
  await expect(page.getByTestId("tooth-planning-count-UL6-planned")).toContainText("P2");
  await expect(page.getByTestId("tooth-planning-count-UL6-completed")).toContainText("C");
  await expect(page.getByTestId("tooth-planning-crown-UL6-crown")).toHaveAttribute("d", await page.getByTestId("tooth-crown-UL6").getAttribute("d") as string);
  await expect(page.getByTestId("tooth-planning-overlay-UL6-other").locator("path,polygon,circle")).toHaveCount(0);
});

test("P and C badges are fifty percent larger, clear of each other and all anatomy markers at either arch", async ({ page }) => {
  for (const width of [58, 100]) {
    for (const quadrant of quadrants) {
      const tooth = `${quadrant}6`;
      const base: Partial<Props> = { baselineCondition: { movement: "forward", rotation: "clockwise" },
        hasToothNote: true, rootConditions: {}, crownCondition: null, surfaceObservations: {} };
      await render(page, tooth, base);
      await page.addStyleTag({ content: `.tooth{width:${width}px}` });
      const before = await page.getByTestId(`tooth-svg-${tooth}`).boundingBox();
      await render(page, tooth, { ...base, plannedOverlays: [overlay("other"), overlay("other", { id: "done", status: "completed" })] });
      await page.addStyleTag({ content: `.tooth{width:${width}px}` });
      expect(await page.getByTestId(`tooth-svg-${tooth}`).boundingBox()).toEqual(before);
      const planned = page.getByTestId(`tooth-planning-count-${tooth}-planned`);
      const completed = page.getByTestId(`tooth-planning-count-${tooth}-completed`);
      for (const badge of [planned, completed]) {
        await expect(badge.locator("rect")).toHaveAttribute("width", "45");
        await expect(badge.locator("rect")).toHaveAttribute("height", "24");
        await expect(badge.locator("text")).toHaveAttribute("font-size", "18");
        await expect(badge).toHaveAttribute("aria-label", /1 (planned|completed) treatment$/);
      }
      const p = (await planned.boundingBox())!;
      const c = (await completed.boundingBox())!;
      const scale = width / 100;
      expect(p.x + p.width + 2.1 * scale).toBeLessThan(c.x);
      const slot = (await page.locator(".tooth").boundingBox())!;
      expect(p.y - 1.05 * scale).toBeGreaterThanOrEqual(slot.y);
      expect(p.x - 1.05 * scale).toBeGreaterThanOrEqual(slot.x);
      expect(c.x + c.width + 1.05 * scale).toBeLessThanOrEqual(slot.x + slot.width);
      for (const marker of [`tooth-note-flag-${tooth}`, `tooth-position-markers-${tooth}`, `tooth-crown-${tooth}`, `tooth-surface-map-${tooth}`]) {
        const target = (await page.getByTestId(marker).boundingBox())!;
        expect(p.y + p.height + 1.05 * scale).toBeLessThan(target.y);
        expect(c.y + c.height + 1.05 * scale).toBeLessThan(target.y);
      }
    }
  }
});

test("planning glyph gallery preserves primary, upper and lower anatomy in light and dark themes", async ({ page }, testInfo) => {
  const kinds: OdontogramPlannedOverlay["kind"][] = ["extraction", "implant", "root_canal", "apicectomy", "post_core", "crown", "bridge", "denture", "filling", "inlay_onlay", "veneer", "sealant", "other"];
  const cards = kinds.map((kind, index) => {
    const tooth = `${quadrants[index % 4]}${index % 3 === 0 ? "4" : "6"}`;
    return `<article><div>${kind.replaceAll("_", " ")}</div><div class="tooth">${markup(tooth, {
      baselineCondition: kind === "implant" ? { status: "missing" } : index % 3 === 0 ? { dentition: "deciduous" } : undefined,
      rootConditions: {}, crownCondition: null, surfaceObservations: {},
      hasToothNote: true,
      plannedOverlays: [overlay(kind, { surfaces: ["filling", "inlay_onlay", "sealant"].includes(kind) ? ["M", "O", "D"] : [] }),
        overlay("other", { id: "completed", status: "completed" })],
    })}</div></article>`;
  }).join("");
  await page.setViewportSize({ width: 1480, height: 780 });
  for (const theme of ["light", "dark"]) {
    await page.setContent(`<style>${css}body{--planning-ink:${theme === "dark" ? "#c0adff" : "#493896"};--planning-halo:${theme === "dark" ? "#27212f" : "#faf8ff"};--planning-complete:${theme === "dark" ? "#adb4be" : "#626a74"};background:${theme === "dark" ? "#171614" : "#faf8f4"};color:${theme === "dark" ? "#faf8f4" : "#282624"}}main{display:grid;grid-template-columns:repeat(7,1fr);gap:12px}article{display:flex;align-items:center;flex-direction:column;border:1px solid #8885;border-radius:8px;padding:12px;gap:12px}</style><main>${cards}</main>`);
    await page.screenshot({ path: testInfo.outputPath(`planning-glyphs-${theme}.png`), fullPage: true });
    await expect(page.locator('[data-testid^="tooth-planning-overlay-"]')).toHaveCount(kinds.length * 2);
  }
});
