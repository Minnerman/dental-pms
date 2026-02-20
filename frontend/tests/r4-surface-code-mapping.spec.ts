import { expect, test } from "@playwright/test";

import { r4SurfaceCodeToSurfaceKey } from "../lib/charting/r4SurfaceCodeToSurfaceKey";

test("surface mapper handles discovered TP item values from artifacts", () => {
  // Current Stage 144/151 discovery evidence only contains surface "0".
  expect(r4SurfaceCodeToSurfaceKey(0)).toBeNull();
  expect(r4SurfaceCodeToSurfaceKey("0")).toBeNull();
});

test("surface mapper handles canonical letter keys", () => {
  expect(r4SurfaceCodeToSurfaceKey("M")).toBe("M");
  expect(r4SurfaceCodeToSurfaceKey("o")).toBe("O");
  expect(r4SurfaceCodeToSurfaceKey(" D ")).toBe("D");
  expect(r4SurfaceCodeToSurfaceKey("B")).toBe("B");
  expect(r4SurfaceCodeToSurfaceKey("L")).toBe("L");
  expect(r4SurfaceCodeToSurfaceKey("I")).toBe("I");
});

test("surface mapper provides conservative numeric mapping", () => {
  expect(r4SurfaceCodeToSurfaceKey(1)).toBe("M");
  expect(r4SurfaceCodeToSurfaceKey(2)).toBe("O");
  expect(r4SurfaceCodeToSurfaceKey(3)).toBe("D");
  expect(r4SurfaceCodeToSurfaceKey(4)).toBe("B");
  expect(r4SurfaceCodeToSurfaceKey(5)).toBe("L");
  expect(r4SurfaceCodeToSurfaceKey(6)).toBe("I");
});

test("surface mapper falls back for unknown values", () => {
  expect(r4SurfaceCodeToSurfaceKey(7)).toBeNull();
  expect(r4SurfaceCodeToSurfaceKey("99")).toBeNull();
  expect(r4SurfaceCodeToSurfaceKey("surface-x")).toBeNull();
  expect(r4SurfaceCodeToSurfaceKey(null)).toBeNull();
  expect(r4SurfaceCodeToSurfaceKey(undefined)).toBeNull();
});
