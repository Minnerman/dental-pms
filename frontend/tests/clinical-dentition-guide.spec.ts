import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { JsxEmit, ModuleKind, transpileModule } from "typescript";

// These are pure component/helper checks: no browser, API, patient or R4 data.
// Compile real React output rather than Playwright's browser JSX descriptors.
const componentFile = resolve(__dirname, "../components/clinical/DentitionGuide.tsx");
const compiled = transpileModule(readFileSync(componentFile, "utf8"), {
  compilerOptions: { module: ModuleKind.CommonJS, jsx: JsxEmit.ReactJSX },
}).outputText;
const componentModule = { exports: {} as typeof import("../components/clinical/DentitionGuide") };
new Function("require", "module", "exports", compiled)(
  createRequire(componentFile), componentModule, componentModule.exports
);
const { default: DentitionGuide, dentitionSuggestion } = componentModule.exports;
const today = new Date("2026-09-05T12:00:00Z");
const quadrants = ["UR", "UL", "LR", "LL"];

test("a four-year-old age guide suggests twenty primary positions without recording any findings", () => {
  const before = today.toISOString();
  const guide = dentitionSuggestion("2022-09-01", today);
  expect(guide).toEqual({
    age: 4,
    stage: "Primary dentition",
    likely: quadrants.flatMap((quadrant) => [1, 2, 3, 4, 5].map((position) => `${quadrant}${position}`)),
    changing: [],
  });
  expect(today.toISOString()).toBe(before);
  expect(guide).not.toHaveProperty("condition");
  expect(guide).not.toHaveProperty("teeth");
  expect(guide).not.toHaveProperty("revision");
  expect(dentitionSuggestion("2022-09-01", today)).toEqual(guide);
});

test("an eight-year-old age guide distinguishes transition sites from likely primary teeth", () => {
  const guide = dentitionSuggestion("2018-09-01", today);
  expect(guide).toEqual({
    age: 8,
    stage: "Mixed dentition",
    likely: quadrants.flatMap((quadrant) => [3, 4, 5].map((position) => `${quadrant}${position}`)),
    changing: ["UR2", "UL2"],
  });
  expect(guide!.likely.some((tooth) => /[6-8]$/.test(tooth))).toBe(false);
  expect(guide!.changing.some((tooth) => /[6-8]$/.test(tooth))).toBe(false);
  // Sites absent from the guide are not inferred as missing or permanent.
  expect(guide).not.toHaveProperty("missing");
  expect(guide).not.toHaveProperty("permanent");
});

test("unknown invalid or future dates do not produce age-based dental claims", () => {
  for (const date of [undefined, null, "", "2018", "2018-2-01", "not-a-date", "2018-02-30", "2025-02-29", "2026-13-01", "2026-00-01", "2026-09-06"]) {
    expect(dentitionSuggestion(date, today), String(date)).toBeNull();
  }
  expect(dentitionSuggestion("2024-02-29", today)).toMatchObject({ age: 2, stage: "Developing primary dentition", likely: [], changing: [] });
});

test("age boundaries avoid extrapolating individual tooth findings for infants and adults", () => {
  expect(dentitionSuggestion("2024-09-01", today)).toMatchObject({ age: 2, stage: "Developing primary dentition", likely: [], changing: [] });
  expect(dentitionSuggestion("2023-09-05", today)).toMatchObject({ age: 3, stage: "Primary dentition" });
  expect(dentitionSuggestion("2020-09-05", today)).toMatchObject({ age: 6, stage: "Mixed dentition" });
  expect(dentitionSuggestion("2013-09-05", today)).toMatchObject({ age: 13, stage: "Permanent dentition", likely: [], changing: [] });
  expect(dentitionSuggestion("1986-09-01", today)).toMatchObject({ age: 40, stage: "Permanent dentition", likely: [], changing: [] });
});

test("recorded observations suppress the age guide instead of overriding the chart", () => {
  expect(renderToStaticMarkup(createElement(DentitionGuide, { dateOfBirth: "2022-09-01", hasFindings: true }))).toBe("");
  expect(renderToStaticMarkup(createElement(DentitionGuide, { dateOfBirth: null, hasFindings: true }))).toBe("");
});

test("an unconfirmed guide is labelled educational and offers no control that could save inferred findings", () => {
  const markup = renderToStaticMarkup(createElement(DentitionGuide, { dateOfBirth: null, hasFindings: false }));
  expect(markup).toContain("First chart · Unconfirmed age guide");
  expect(markup).toContain("A valid date of birth is needed");
  expect(markup).toContain("Confirm the teeth clinically before recording findings");
  expect(markup).toContain("No teeth are marked present, missing or unerupted from age");
  expect(markup).toContain("This guide is not saved as clinical data");
  expect(markup).not.toMatch(/<(?:button|form|input|select|textarea)\b/i);
  expect(markup).not.toContain("data-baseline-status");
  expect(markup).not.toContain("data-testid=\"tooth-");
});
