import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { createElement, type ComponentProps } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { JsxEmit, ModuleKind, ScriptTarget, transpileModule } from "typescript";
import { getToothAnatomy, implantScrewAnatomy } from "../components/clinical/toothAnatomy";
import { crownKinds, type CrownObservation } from "../components/clinical/crownDiagnosis";

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
const materials = { metal: "#a7adb5", gold: "#e9c34e", porcelain: "#f0b5d0", porcelain_bonded: "#70483b", composite: "#85c7a0" } as const;
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

test("all crown materials keep the approved outline and clip every red issue to the crown", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    for (const [kind, color] of Object.entries(materials)) {
      await render(page, tooth, { ...currentProps(), crownCondition: { kind: kind as CrownObservation["kind"], issues: [...issues] } });
      const crown = page.getByTestId(`tooth-crown-${tooth}`);
      await expect(crown).toHaveAttribute("d", getToothAnatomy(tooth).crown);
      await expect(crown).toHaveAttribute("fill", color);
      if (kind === "porcelain_bonded") {
        await expect(page.locator(`[data-testid^="tooth-crown-groove-${tooth}-"]`).first()).toHaveAttribute("stroke", "#d8b3a2");
      }
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

test("retired standalone fractured observations remain readable without becoming an authorable choice", async ({ page }) => {
  expect(crownKinds.map((item) => item.value)).not.toContain("fractured");
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    await render(page, tooth, { crownCondition: { kind: "fractured", issues: [] } });
    await expect(page.getByTestId(`tooth-crown-${tooth}`)).toHaveCount(0);
    await expect(page.getByTestId(`clinical-crown-${tooth}`).locator("title")).toHaveText(/fractured, crown absent/);
    expect(await page.locator(`[data-testid^="tooth-root-${tooth}-"]`).count()).toBeGreaterThan(0);
  }
});

test("both denture materials are rootless replacements in every quadrant without changing recorded absence", async ({ page }) => {
  const legacy: ToothProps["restorations"] = [{ type: "root_canal" }, { type: "post" }, { type: "implant" }, { type: "denture" }, { type: "extraction" }];
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    for (const kind of ["denture_cocr", "denture_acrylic"] as const) {
      for (const status of [undefined, "missing", "unrecorded", "present", "implant"] as const) {
        await render(page, tooth, { ...currentProps(), baselineCondition: status ? { status } : undefined,
          missing: true, extracted: true, restorations: legacy, crownCondition: { kind, issues: [] } });
        const svg = page.getByTestId(`tooth-svg-${tooth}`);
        await expect(svg).toHaveAttribute("data-artificial-tooth", "denture");
        if (status) await expect(svg).toHaveAttribute("data-baseline-status", status);
        else await expect(svg).not.toHaveAttribute("data-baseline-status");
        await expect(svg).toHaveAttribute("aria-label", /artificial replacement tooth/);
        if (status !== "present") await expect(svg).not.toHaveAttribute("aria-label", /current condition present|healthy/);
        await expect(page.getByTestId(`clinical-crown-${tooth}`)).toHaveAttribute("role", "button");
        await expect(page.getByTestId(`clinical-denture-base-${tooth}`)).toHaveAttribute("fill", kind === "denture_cocr" ? "#9eabb9" : "#d995ac");
        await expect(page.getByTestId(`tooth-crown-${tooth}`)).toHaveAttribute("d", getToothAnatomy(tooth).crown);
        await expect(page.getByTestId(`tooth-crown-${tooth}`)).toHaveAttribute("fill", "#fff7df");
        await expect(page.getByTestId(`tooth-surface-map-${tooth}`)).toBeAttached();
        await expect(page.getByTestId(`clinical-root-${tooth}`)).toHaveCount(0);
        await expect(page.locator(`[data-testid^="tooth-root-${tooth}-"],[data-testid^="tooth-implant-"],[data-testid^="clinical-root-finding-${tooth}-"]`)).toHaveCount(0);
        for (const type of ["root_canal", "post", "implant", "denture", "extraction", "missing"]) {
          await expect(page.getByTestId(`tooth-restoration-${tooth}-${type}`)).toHaveCount(0);
          await expect(page.getByTestId(`tooth-anatomy-restoration-${tooth}-${type}`)).toHaveCount(0);
        }
        await expect(svg).toHaveAttribute("viewBox", "0 0 100 280");
      }
    }
  }
});

test("denture and bridge observations leave passive History and unerupted anatomy unchanged", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    const restorations: ToothProps["restorations"] = [{ type: "denture" }, { type: "implant" }, { type: "root_canal" }, { type: "post" }, { type: "bridge" }];
    await render(page, tooth, { restorations });
    for (const type of ["denture", "implant", "root_canal", "post", "bridge"]) {
      await expect(page.getByTestId(`tooth-restoration-${tooth}-${type}`)).toBeAttached();
    }
    await expect(page.getByTestId(`tooth-svg-${tooth}`)).not.toHaveAttribute("data-artificial-tooth");
    for (const bridgeRole of ["abutment", "pontic", "wing"] as const) {
      await render(page, tooth, { ...currentProps(), baselineCondition: { status: "unerupted" }, bridgeRole,
        allowMissingCrownSelection: true, crownCondition: { kind: "denture_acrylic", issues: [] } });
      await expect(page.getByTestId(`tooth-baseline-gum-${tooth}`)).toBeAttached();
      await expect(page.getByTestId(`clinical-crown-${tooth}`)).not.toHaveAttribute("role");
      await expect(page.getByTestId(`clinical-denture-base-${tooth}`)).toHaveCount(0);
      await expect(page.getByTestId(`clinical-bridge-wing-${tooth}`)).toHaveCount(0);
      await expect(page.getByTestId(`clinical-crown-placeholder-${tooth}`)).toHaveCount(0);
      await expect(page.getByTestId(`tooth-svg-${tooth}`)).not.toHaveAttribute("data-bridge-role");
    }
  }
});

test("missing slots expose only an armed denture placeholder without creating a biological crown", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    for (const absence of [{ baselineCondition: { status: "missing" as const } }, { missing: true }, { extracted: true }]) {
      await render(page, tooth, { ...absence, crownCondition: null, onCrownClick: noAction });
      const slot = await page.getByTestId(`tooth-svg-${tooth}`).boundingBox();
      await expect(page.getByTestId(`clinical-crown-placeholder-${tooth}`)).toHaveCount(0);
      await render(page, tooth, { ...absence, crownCondition: null, onCrownClick: noAction, allowMissingCrownSelection: true });
      const target = page.getByTestId(`clinical-crown-${tooth}`);
      await expect(target).toHaveAttribute("data-crown-placeholder", "true");
      await expect(target).toHaveAttribute("role", "button");
      await expect(target).toHaveAttribute("tabindex", "0");
      await expect(target).toHaveAttribute("data-crown-recorded", "false");
      await expect(page.getByTestId(`clinical-crown-placeholder-${tooth}`)).toHaveAttribute("stroke-dasharray", "4 4");
      await expect(page.getByTestId(`tooth-crown-${tooth}`)).toHaveCount(0);
      await expect(page.getByTestId(`clinical-root-${tooth}`)).toHaveCount(0);
      await expect(page.getByTestId(`tooth-surface-map-${tooth}`)).toHaveCount(0);
      expect(await page.getByTestId(`tooth-svg-${tooth}`).boundingBox()).toEqual(slot);
      const hit = await page.getByTestId(`clinical-crown-hit-${tooth}`).evaluate((element) => {
        const point = new DOMPoint(50, 125).matrixTransform((element as SVGGraphicsElement).getScreenCTM()!);
        return document.elementFromPoint(point.x, point.y)?.getAttribute("data-testid");
      });
      expect(hit).toBe(`clinical-crown-hit-${tooth}`);
    }
    await render(page, tooth, { ...currentProps(), baselineCondition: { status: "present" }, allowMissingCrownSelection: true });
    await expect(page.getByTestId(`clinical-crown-placeholder-${tooth}`)).toHaveCount(0);
  }
});

test("explicit bridge roles preserve supports and make only pontics rootless without inferring connectors", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    await render(page, tooth, { ...currentProps(), baselineCondition: { status: "missing" }, bridgeRole: "pontic",
      crownCondition: { kind: "porcelain_bonded", issues: [] } });
    await expect(page.getByTestId(`tooth-svg-${tooth}`)).toHaveAttribute("data-baseline-status", "missing");
    await expect(page.getByTestId(`tooth-svg-${tooth}`)).toHaveAttribute("data-artificial-tooth", "pontic");
    await expect(page.getByTestId(`clinical-root-${tooth}`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-crown-${tooth}`)).toHaveAttribute("fill", "#70483b");
    await expect(page.getByTestId(`clinical-crown-${tooth}`)).toHaveAttribute("data-bridge-role", "pontic");
    await expect(page.locator('[data-testid*="connector"]')).toHaveCount(0);
    for (const bridgeRole of ["abutment", "wing"] as const) {
      await render(page, tooth, { ...currentProps(), baselineCondition: { status: "present" }, bridgeRole, crownCondition: null });
      await expect(page.getByTestId(`clinical-root-${tooth}`)).toHaveAttribute("role", "button");
      await expect(page.getByTestId(`clinical-root-finding-${tooth}-1`)).toBeAttached();
      await expect(page.getByTestId(`tooth-crown-${tooth}`)).toHaveAttribute("d", getToothAnatomy(tooth).crown);
      await expect(page.getByTestId(`clinical-bridge-wing-${tooth}`)).toHaveCount(bridgeRole === "wing" ? 1 : 0);
    }
    await render(page, tooth, { ...currentProps(), baselineCondition: { status: "implant" }, bridgeRole: "abutment", crownCondition: null });
    await expect(page.getByTestId(`tooth-implant-body-${tooth}`)).toHaveAttribute("d", implantScrewAnatomy.body);
    await expect(page.getByTestId(`tooth-implant-collar-${tooth}`)).toHaveAttribute("d", implantScrewAnatomy.collar);
    await expect(page.getByTestId(`clinical-root-${tooth}`)).toHaveCount(0);
  }
});

test("bonded crowns, artificial replacements and bridge roles are legible in both gallery themes", async ({ page }, testInfo) => {
  const examples: Array<{ label: string; tooth: string; props: Partial<ToothProps> }> = [
    { label: "Bonded porcelain", tooth: "UR6", props: { crownCondition: { kind: "porcelain_bonded", issues: [] } } },
    { label: "Bonded · defective", tooth: "UL6", props: { crownCondition: { kind: "porcelain_bonded", issues: ["defective"] } } },
    { label: "Co-Cr denture", tooth: "UR6", props: { baselineCondition: { status: "missing" }, crownCondition: { kind: "denture_cocr", issues: [] } } },
    { label: "Acrylic denture", tooth: "UL6", props: { baselineCondition: { status: "missing" }, crownCondition: { kind: "denture_acrylic", issues: [] } } },
    { label: "Missing · denture tool armed", tooth: "UR6", props: { baselineCondition: { status: "missing" }, rootConditions: {}, allowMissingCrownSelection: true } },
    { label: "Co-Cr denture · lower", tooth: "LR6", props: { baselineCondition: { status: "missing" }, crownCondition: { kind: "denture_cocr", issues: [] } } },
    { label: "Acrylic denture · lower", tooth: "LL6", props: { baselineCondition: { status: "missing" }, crownCondition: { kind: "denture_acrylic", issues: [] } } },
    { label: "Bridge pontic", tooth: "LL6", props: { baselineCondition: { status: "missing" }, bridgeRole: "pontic", crownCondition: { kind: "porcelain_bonded", issues: [] } } },
    { label: "Bridge wing", tooth: "LR6", props: { bridgeRole: "wing", crownCondition: null } },
    { label: "Implant bridge abutment", tooth: "UL6", props: { baselineCondition: { status: "implant" }, bridgeRole: "abutment", crownCondition: { kind: "porcelain_bonded", issues: [] } } },
  ];
  await page.setViewportSize({ width: 1360, height: 920 });
  await page.setContent(`<style>body{margin:24px;background:#f7f7f5;color:#242320;font:14px Arial}.gallery{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}.tooth{background:white;border:1px solid #deded8;border-radius:10px;padding:12px;text-align:center}.tooth svg{width:96px;height:269px;margin:10px auto}.tooth strong{font-size:12px}.clinical-root-halo,.clinical-crown-halo{opacity:0}body.dark{background:#171614;color:#f5f4f1}.dark .tooth{background:#211f1c;border-color:#3b3832}</style><h1>Bonded crowns, dentures and bridge roles</h1><p>Synthetic illustrations; connectors are drawn only by the chart's explicitly recorded bridge groups.</p><div class="gallery">${examples.map(({ label, tooth, props }) => `<section class="tooth"><strong>${label}</strong>${markup(tooth, { ...currentProps(), ...props })}<span>${tooth}</span></section>`).join("")}</div>`);
  await page.screenshot({ path: testInfo.outputPath("crown-replacements-light.png"), fullPage: true });
  await page.evaluate(() => document.body.classList.add("dark"));
  await page.screenshot({ path: testInfo.outputPath("crown-replacements-dark.png"), fullPage: true });
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
