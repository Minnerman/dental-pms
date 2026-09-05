import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { createElement, type ComponentProps } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { JsxEmit, ModuleKind, ScriptTarget, transpileModule } from "typescript";
import { getToothAnatomy, implantScrewAnatomy } from "../components/clinical/toothAnatomy";
import type { CrownObservation } from "../components/clinical/crownDiagnosis";

// Real React SVG output in a blank browser: no patients, server or API fixtures.
const componentFile = resolve(__dirname, "../components/clinical/OdontogramToothSvg.tsx");
const componentModule = { exports: {} as typeof import("../components/clinical/OdontogramToothSvg") };
new Function("require", "module", "exports", transpileModule(readFileSync(componentFile, "utf8"), {
  compilerOptions: { module: ModuleKind.CommonJS, jsx: JsxEmit.ReactJSX, target: ScriptTarget.ES2017 },
}).outputText)(createRequire(componentFile), componentModule, componentModule.exports);
const { default: OdontogramToothSvg, getOdontogramToothType } = componentModule.exports;
type ToothProps = ComponentProps<typeof OdontogramToothSvg>;
const quadrants = ["UR", "UL", "LR", "LL"] as const;
const noAction = () => {};
let sequence = 0;
const materials = { metal: "#a7adb5", gold: "#e9c34e", porcelain: "#f0b5d0", composite: "#85c7a0" } as const;
const issues = ["decayed", "defective", "fractured", "poor_fitting"] as const;
function markup(toothKey: string, props: Partial<ToothProps> = {}) {
  return renderToStaticMarkup(createElement(OdontogramToothSvg, {
    toothKey, toothType: getOdontogramToothType(toothKey), ...props,
  }), { identifierPrefix: `crown-${sequence++}-` });
}
async function render(page: Page, tooth: string, props: Partial<ToothProps> = {}) {
  await page.setContent(`<style>body{margin:30px}svg{width:100px;height:280px}.clinical-crown-halo,.clinical-root-halo{opacity:0}</style>${markup(tooth, props)}`);
  return page.getByTestId(`tooth-svg-${tooth}`);
}
function currentProps(): Partial<ToothProps> {
  return { rootConditions: { "1": { condition: "filled_sound", apicectomy: true } }, onRootClick: noAction, onCrownClick: noAction, onCrownContextMenu: noAction };
}

test("fractured crown removes only the crown and retains a full-size accessible re-entry target", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    await render(page, tooth, { ...currentProps(), crownCondition: null });
    const slot = await page.getByTestId(`tooth-svg-${tooth}`).boundingBox();
    const targetBefore = await page.getByTestId(`clinical-crown-${tooth}`).boundingBox();
    const rootBefore = await page.getByTestId(`tooth-root-${tooth}-1`).getAttribute("d");
    await render(page, tooth, { ...currentProps(), crownCondition: { kind: "fractured", issues: [] }, crownSelected: true });
    const area = page.getByTestId(`clinical-crown-${tooth}`);
    await expect(area).toHaveAttribute("role", "button");
    await expect(area).toHaveAttribute("aria-label", `${tooth} crown area`);
    await expect(area).toHaveAttribute("tabindex", "0");
    await expect(area).toHaveAttribute("data-crown-kind", "fractured");
    await expect(area).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId(`tooth-crown-${tooth}`)).toHaveCount(0);
    await expect(page.locator(`[data-testid^="tooth-crown-groove-${tooth}-"]`)).toHaveCount(0);
    await expect(area.locator(".clinical-crown-selection")).toHaveCount(0);
    await expect(area.locator(".clinical-crown-halo")).toHaveAttribute("d", getToothAnatomy(tooth).crown);
    await expect(page.getByTestId(`tooth-root-${tooth}-1`)).toHaveAttribute("d", rootBefore!);
    await expect(page.getByTestId(`clinical-root-finding-${tooth}-1`)).toBeAttached();
    await expect(page.getByTestId(`clinical-root-apicectomy-${tooth}-1`)).toBeAttached();
    await expect(page.getByTestId(`tooth-surface-map-${tooth}`)).toBeAttached();
    expect(await area.boundingBox()).toEqual(targetBefore);
    expect(await page.getByTestId(`tooth-svg-${tooth}`).boundingBox()).toEqual(slot);
  }
});

test("missing crown uses a tapered prepared stump with unchanged roots and crown selection area", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    await render(page, tooth, { ...currentProps(), crownCondition: null });
    const crownBefore = (await page.getByTestId(`tooth-crown-${tooth}`).boundingBox())!;
    const rootBefore = await page.getByTestId(`tooth-root-${tooth}-1`).boundingBox();
    const hitBefore = await page.getByTestId(`clinical-crown-hit-${tooth}`).boundingBox();
    await render(page, tooth, { ...currentProps(), crownCondition: { kind: "missing", issues: [] }, crownSelected: true });
    await expect(page.getByTestId(`tooth-crown-${tooth}`)).toHaveCount(0);
    const stump = page.getByTestId(`clinical-crown-stump-${tooth}`);
    await expect(stump.locator("path")).toHaveCount(2);
    const box = (await stump.boundingBox())!;
    expect(box.height).toBeLessThan(crownBefore.height);
    expect(box.width).toBeLessThan(crownBefore.width);
    expect(await page.getByTestId(`tooth-root-${tooth}-1`).boundingBox()).toEqual(rootBefore);
    expect(await page.getByTestId(`clinical-crown-hit-${tooth}`).boundingBox()).toEqual(hitBefore);
    await expect(page.getByTestId(`clinical-crown-${tooth}`).locator(".clinical-crown-selection")).toHaveCount(1);
  }
});

test("all four crown materials keep the approved outline and clip every red issue to the crown", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    for (const [kind, color] of Object.entries(materials)) {
      await render(page, tooth, { ...currentProps(), crownCondition: { kind: kind as CrownObservation["kind"], issues: [...issues] } });
      const crown = page.getByTestId(`tooth-crown-${tooth}`);
      await expect(crown).toHaveAttribute("d", getToothAnatomy(tooth).crown);
      await expect(crown).toHaveAttribute("fill", color);
      for (const issue of issues) {
        const marker = page.getByTestId(`clinical-crown-issue-${tooth}-${issue}`);
        await expect(marker).toBeAttached();
        const clip = await marker.evaluate((element) => {
          const group = element.closest("[clip-path]")!;
          const id = group.getAttribute("clip-path")!.slice(5, -1);
          return document.getElementById(id)!.querySelector("path")!.getAttribute("d");
        });
        expect(clip).toBe(getToothAnatomy(tooth).crown);
      }
      await expect(page.getByTestId(`clinical-crown-issue-${tooth}-defective`)).toHaveAttribute("fill", /url\(#crown-defect-/);
      await expect(page.getByTestId(`clinical-crown-issue-${tooth}-fractured`)).toHaveAttribute("stroke", "#b91c1c");
      await expect(page.getByTestId(`clinical-crown-issue-${tooth}-poor_fitting`).locator("path")).toHaveCount(2);
      await expect(page.getByTestId(`clinical-root-finding-${tooth}-1`)).toBeAttached();
    }
    await render(page, tooth, { crownCondition: { kind: "missing", issues: [...issues] } });
    await expect(page.locator('[data-testid^="clinical-crown-issue-"]')).toHaveCount(0);
  }
});

test("crown hits exclude roots and the surface diagram and survive removed or prepared states", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    for (const kind of [null, "fractured", "missing", "metal"] as const) {
      await render(page, tooth, { ...currentProps(), crownCondition: { kind, issues: [] } });
      const hits = await page.getByTestId(`clinical-crown-hit-${tooth}`).evaluate((element) => {
        const hit = element as SVGGraphicsElement;
        return [[50, 125], [40, 140], [50, 50], [50, 230]].map(([x, y]) => {
          const point = new DOMPoint(x, y).matrixTransform(hit.getScreenCTM()!);
          return document.elementFromPoint(point.x, point.y)?.getAttribute("data-testid");
        });
      });
      expect(hits.slice(0, 2)).toEqual([`clinical-crown-hit-${tooth}`, `clinical-crown-hit-${tooth}`]);
      expect(hits[2]).not.toBe(`clinical-crown-hit-${tooth}`);
      expect(hits[3]).not.toBe(`clinical-crown-hit-${tooth}`);
      await expect(page.locator('[data-testid^="clinical-crown-"][role="button"]')).toHaveCount(1);
    }
  }
});

test("crown reset differs from untouched Current and History while preserving root and surface history", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    const restorations: ToothProps["restorations"] = [{ type: "crown" }, { type: "root_canal" }, { type: "post" }, { type: "filling", surfaces: ["M"] }];
    for (const crownCondition of [undefined, null]) {
      await render(page, tooth, { restorations, crownCondition });
      await expect(page.getByTestId(`tooth-anatomy-restoration-${tooth}-crown`)).toBeAttached();
      await expect(page.getByTestId(`tooth-restoration-${tooth}-crown`)).toBeAttached();
      await expect(page.getByTestId(`clinical-crown-${tooth}`)).toHaveAttribute("data-crown-recorded", "false");
    }
    await render(page, tooth, { restorations, crownCondition: { kind: null, issues: [] } });
    await expect(page.getByTestId(`tooth-anatomy-restoration-${tooth}-crown`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-restoration-${tooth}-crown`)).toHaveCount(0);
    await expect(page.getByTestId(`clinical-crown-${tooth}`)).toHaveAttribute("data-crown-kind", "unspecified");
    await expect(page.getByTestId(`clinical-crown-${tooth}`).locator("title")).toHaveText(/reset, unspecified/);
    await expect(page.getByTestId(`tooth-anatomy-restoration-${tooth}-root_canal`)).toBeAttached();
    await expect(page.getByTestId(`tooth-anatomy-restoration-${tooth}-post`)).toBeAttached();
    await expect(page.getByTestId(`tooth-restoration-${tooth}-filling-M`)).toBeAttached();
  }
});

test("native implant crowns remain editable without changing the fixture, while whole-tooth absence dominates", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    for (const kind of ["porcelain", "missing", "fractured"] as const) {
      await render(page, tooth, { ...currentProps(), baselineCondition: { status: "implant" }, crownCondition: { kind, issues: [] } });
      await expect(page.getByTestId(`clinical-crown-${tooth}`)).toHaveAttribute("role", "button");
      await expect(page.getByTestId(`tooth-implant-body-${tooth}`)).toHaveAttribute("d", implantScrewAnatomy.body);
      await expect(page.getByTestId(`tooth-implant-collar-${tooth}`)).toHaveAttribute("d", implantScrewAnatomy.collar);
      expect(await page.locator(`[data-testid^="tooth-implant-thread-${tooth}-"]`).evaluateAll((elements) => elements.map((element) => element.getAttribute("d")))).toEqual(implantScrewAnatomy.threads);
      await expect(page.locator(`[data-testid^="tooth-root-${tooth}-"]`)).toHaveCount(0);
    }
    for (const status of ["missing", "unerupted"] as const) {
      await render(page, tooth, { ...currentProps(), baselineCondition: { status }, crownCondition: { kind: "metal", issues: ["defective"] } });
      await expect(page.locator('[data-testid^="clinical-crown-"][role="button"]')).toHaveCount(0);
      await expect(page.getByTestId(`clinical-crown-issue-${tooth}-defective`)).toHaveCount(0);
      await expect(page.getByTestId(`clinical-crown-hit-${tooth}`)).toHaveCount(0);
    }
    await render(page, tooth, { ...currentProps(), rootConditions: {}, missing: true, extracted: true, restorations: [{ type: "extraction" }], crownCondition: { kind: "gold", issues: [] } });
    await expect(page.getByTestId(`clinical-crown-${tooth}`)).toHaveAttribute("role", "button");
    await expect(page.getByTestId(`tooth-crown-${tooth}`)).toHaveAttribute("fill", materials.gold);
    await expect(page.getByTestId(`tooth-restoration-${tooth}-missing`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-restoration-${tooth}-extraction`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-svg-${tooth}`)).not.toHaveAttribute("aria-label", /current condition present|healthy/);
  }
});

test("synthetic crown gallery shows removed, prepared and material crowns with clipped issues", async ({ page }, testInfo) => {
  const examples: Array<{ label: string; tooth: string; crown: CrownObservation; implant?: boolean }> = [
    { label: "Fractured · crown absent", tooth: "UR6", crown: { kind: "fractured", issues: [] } },
    { label: "Missing · prepared stump", tooth: "UR6", crown: { kind: "missing", issues: [] } },
    { label: "Metal", tooth: "UR6", crown: { kind: "metal", issues: [] } },
    { label: "Gold · decayed", tooth: "UR6", crown: { kind: "gold", issues: ["decayed"] } },
    { label: "Porcelain · defective", tooth: "UR6", crown: { kind: "porcelain", issues: ["defective"] } },
    { label: "Composite · fractured", tooth: "LL6", crown: { kind: "composite", issues: ["fractured"] } },
    { label: "Metal · poor fitting", tooth: "LL6", crown: { kind: "metal", issues: ["poor_fitting"] } },
    { label: "Implant crown", tooth: "UL6", crown: { kind: "porcelain", issues: [] }, implant: true },
  ];
  await page.setViewportSize({ width: 1360, height: 650 });
  await page.setContent(`<style>body{margin:24px;background:#f7f7f5;color:#242320;font:14px Arial}.gallery{display:flex;gap:10px}.tooth{background:white;border:1px solid #deded8;border-radius:10px;padding:16px 9px;flex:1;text-align:center}.tooth svg{width:110px;height:308px;margin:12px auto}.tooth strong{font-size:12px}.clinical-root-halo,.clinical-crown-halo{opacity:0}body.dark{background:#171614;color:#f5f4f1}.dark .tooth{background:#211f1c;border-color:#3b3832}</style><h1>Crown-area observations · synthetic schematic review</h1><p>Crown changes preserve roots, root findings, implant fixtures and surface-map positions.</p><div class="gallery">${examples.map(({ label, tooth, crown, implant }) => `<section class="tooth"><strong>${label}</strong>${markup(tooth, { ...currentProps(), baselineCondition: { status: implant ? "implant" : "present" }, crownCondition: crown })}<span>${tooth}</span></section>`).join("")}</div>`);
  await page.screenshot({ path: testInfo.outputPath("crown-gallery-light.png"), fullPage: true });
  await page.evaluate(() => document.body.classList.add("dark"));
  await page.screenshot({ path: testInfo.outputPath("crown-gallery-dark.png"), fullPage: true });
});
