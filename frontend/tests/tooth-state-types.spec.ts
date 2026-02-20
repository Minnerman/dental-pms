import { expect, test } from "@playwright/test";

import {
  TOOTH_STATE_TYPE_LABELS,
  TOOTH_STATE_TYPES,
  isToothStateType,
} from "../lib/charting/toothStateTypes";

test("tooth-state type guard accepts all Stage 156A buckets", () => {
  for (const type of TOOTH_STATE_TYPES) {
    expect(isToothStateType(type)).toBeTruthy();
    expect(TOOTH_STATE_TYPE_LABELS[type].trim().length).toBeGreaterThan(0);
  }
});

test("tooth-state type guard rejects legacy or unknown values", () => {
  const invalidValues: unknown[] = ["rct", "", "ROOT_CANAL", "foo", null, undefined, 123];
  for (const value of invalidValues) {
    expect(isToothStateType(value)).toBeFalsy();
  }
});
