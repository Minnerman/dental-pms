import { expect, test } from "@playwright/test";

import { fdiToChartToothKey } from "../lib/charting/fdiToChartToothKey";

test("fdi mapping covers all permanent UR teeth", () => {
  for (let position = 1; position <= 8; position += 1) {
    const fdi = 10 + position;
    expect(fdiToChartToothKey(fdi)).toEqual({
      quadrant: "UR",
      position,
      key: `UR${position}`,
    });
  }
});

test("fdi mapping covers all permanent UL teeth", () => {
  for (let position = 1; position <= 8; position += 1) {
    const fdi = 20 + position;
    expect(fdiToChartToothKey(fdi)).toEqual({
      quadrant: "UL",
      position,
      key: `UL${position}`,
    });
  }
});

test("fdi mapping covers all permanent LL teeth", () => {
  for (let position = 1; position <= 8; position += 1) {
    const fdi = 30 + position;
    expect(fdiToChartToothKey(fdi)).toEqual({
      quadrant: "LL",
      position,
      key: `LL${position}`,
    });
  }
});

test("fdi mapping covers all permanent LR teeth", () => {
  for (let position = 1; position <= 8; position += 1) {
    const fdi = 40 + position;
    expect(fdiToChartToothKey(fdi)).toEqual({
      quadrant: "LR",
      position,
      key: `LR${position}`,
    });
  }
});

test("fdi mapping rejects non-permanent or invalid FDI values", () => {
  const invalid = [0, 7, 10, 19, 29, 39, 49, 51, 85, -11, 11.5];
  for (const fdi of invalid) {
    expect(fdiToChartToothKey(fdi)).toBeNull();
  }
});
