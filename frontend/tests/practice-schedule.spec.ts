import { expect, test } from "@playwright/test";

import {
  getWorkingSessionsForKey, isWithinPracticeHours, practiceDateParts,
  type PracticeHour, type PracticeOverride, type PracticeSchedule,
} from "../lib/practiceSchedule";

// Pure unit tests: no browser, API client, authentication or database fixtures.
const monday = "2026-09-07";
const open = (start = "09:00", end = "17:00", day = 0): PracticeHour => ({
  day_of_week: day, start_time: start, end_time: end, is_closed: false,
});
const schedule = (hours: PracticeHour[] = [open()]): PracticeSchedule => ({
  hours, closures: [], overrides: [],
});
const override = (start: string | null, end: string | null, closed = false): PracticeOverride => ({
  date: monday, start_time: start, end_time: end, is_closed: closed, reason: null,
});
const within = (from: string, to: string, value: PracticeSchedule | null) =>
  isWithinPracticeHours(new Date(from), new Date(to), value);

test("all seven weekday numbers map Monday through Sunday independently of the host timezone", () => {
  const value = schedule(Array.from({ length: 7 }, (_, day) => open(`${String(9 + day).padStart(2, "0")}:00`, `${10 + day}:00`, day)));
  for (let day = 0; day < 7; day += 1) {
    const key = `2026-09-${String(7 + day).padStart(2, "0")}`;
    expect(getWorkingSessionsForKey(key, value)).toEqual([{ start: (9 + day) * 60, end: (10 + day) * 60 }]);
  }
  expect(getWorkingSessionsForKey("2026-09-13", schedule())).toEqual([]);
});

test("split sessions sort chronologically, preserve lunch gaps and include exact session edges", () => {
  const value = schedule([open("14:00", "18:00"), open("09:00", "12:30")]);
  expect(getWorkingSessionsForKey(monday, value)).toEqual([{ start: 540, end: 750 }, { start: 840, end: 1080 }]);
  expect(within(`${monday}T09:00:00+01:00`, `${monday}T12:30:00+01:00`, value)).toBe(true);
  expect(within(`${monday}T14:00:00+01:00`, `${monday}T18:00:00+01:00`, value)).toBe(true);
  expect(within(`${monday}T12:00:00+01:00`, `${monday}T14:30:00+01:00`, value)).toBe(false);
  expect(within(`${monday}T12:30:00+01:00`, `${monday}T13:00:00+01:00`, value)).toBe(false);
  expect(within(`${monday}T08:59:59+01:00`, `${monday}T10:00:00+01:00`, value)).toBe(false);
  const precise = getWorkingSessionsForKey(monday, schedule([open("09:00:30.500000", "09:01:59.250000")]));
  expect(precise).toHaveLength(1);
  expect(precise[0].start).toBeCloseTo(540 + 30.5 / 60);
  expect(precise[0].end).toBeCloseTo(541 + 59.25 / 60);
});

test("adjacent sessions form continuous coverage without mutating the source schedule", () => {
  const value = schedule([open("14:00", "18:00"), open("09:00", "12:00"), open("12:00", "14:00")]);
  const before = JSON.stringify(value);
  expect(getWorkingSessionsForKey(monday, value)).toEqual([{ start: 540, end: 1080 }]);
  expect(within(`${monday}T09:00:00+01:00`, `${monday}T18:00:00+01:00`, value)).toBe(true);
  expect(JSON.stringify(value)).toBe(before);
});

test("whole-day range closures are inclusive at both ends", () => {
  const value = schedule(Array.from({ length: 7 }, (_, day) => open("09:00", "17:00", day)));
  value.closures = [{ start_date: monday, end_date: "2026-09-09", reason: "Synthetic leave" }];
  for (const key of [monday, "2026-09-08", "2026-09-09"]) {
    expect(getWorkingSessionsForKey(key, value)).toEqual([]);
  }
  expect(getWorkingSessionsForKey("2026-09-06", value)).toHaveLength(1);
  expect(getWorkingSessionsForKey("2026-09-10", value)).toHaveLength(1);
});

test("date-specific open sessions replace the whole weekly day and reopen a range closure", () => {
  const value = schedule([open("09:00", "12:30"), open("14:00", "18:00")]);
  value.closures = [{ start_date: monday, end_date: monday, reason: "Synthetic leave" }];
  value.overrides = [override("14:00", "18:00")];
  expect(getWorkingSessionsForKey(monday, value)).toEqual([{ start: 840, end: 1080 }]);
  expect(within(`${monday}T09:00:00+01:00`, `${monday}T10:00:00+01:00`, value)).toBe(false);
  value.overrides = [override("09:00", "12:30")];
  expect(getWorkingSessionsForKey(monday, value)).toEqual([{ start: 540, end: 750 }]);
  value.overrides = [override("15:00", "16:00"), override("10:00", "11:00")];
  expect(getWorkingSessionsForKey(monday, value)).toEqual([{ start: 600, end: 660 }, { start: 900, end: 960 }]);
});

test("an explicit closed override takes precedence regardless of legacy row order", () => {
  for (const overrides of [
    [override(null, null, true), override("10:00", "16:00")],
    [override("10:00", "16:00"), override(null, null, true)],
  ]) {
    const value = schedule();
    value.overrides = overrides;
    expect(getWorkingSessionsForKey(monday, value)).toEqual([]);
  }
  const mixedWeekly = schedule([open(), { ...open(), start_time: null, end_time: null, is_closed: true }]);
  expect(getWorkingSessionsForKey(monday, mixedWeekly)).toEqual([]);
});

for (const [name, rows] of [
  ["missing endpoint", [override("09:00", null)]],
  ["reversed times", [override("17:00", "09:00")]],
  ["equal times", [override("09:00", "09:00")]],
  ["overlap", [override("09:00", "14:00"), override("12:00", "17:00")]],
  ["duplicate", [override("09:00", "17:00"), override("09:00", "17:00")]],
  ["nonnumeric time", [override("09:xx", "17:00")]],
  ["timezone-bearing time", [override("09:00:00Z", "17:00:00Z")]],
  ["minute overflow", [override("09:60", "17:00")]],
  ["second overflow", [override("09:00:60", "17:00")]],
] as Array<[string, PracticeOverride[]]>) {
  test(`malformed legacy ${name} never falls back to an open weekly day`, () => {
    const value = schedule();
    value.overrides = rows;
    expect(getWorkingSessionsForKey(monday, value)).toEqual([]);
    expect(within(`${monday}T10:00:00+01:00`, `${monday}T11:00:00+01:00`, value)).toBe(false);
  });
}

test("unknown schedule remains unknown rather than reporting open or closed", () => {
  expect(within(`${monday}T10:00:00+01:00`, `${monday}T11:00:00+01:00`, null)).toBeNull();
  expect(within(`${monday}T10:00:00+01:00`, `${monday}T11:00:00+01:00`, schedule([]))).toBe(false);
});

test("invalid, reversed and cross-practice-day appointment intervals are not inside hours", () => {
  const value = schedule(Array.from({ length: 7 }, (_, day) => open("00:00", "23:59:59", day)));
  expect(within("invalid", `${monday}T11:00:00+01:00`, value)).toBe(false);
  expect(within(`${monday}T11:00:00+01:00`, "invalid", value)).toBe(false);
  expect(within(`${monday}T11:00:00+01:00`, `${monday}T10:00:00+01:00`, value)).toBe(false);
  expect(within(`${monday}T11:00:00+01:00`, `${monday}T11:00:00+01:00`, value)).toBe(false);
  expect(within(`${monday}T22:30:00Z`, `${monday}T23:30:00Z`, value)).toBe(false);
});

test("London sessions use GMT in winter and BST in summer, not the process timezone", () => {
  const value = schedule(Array.from({ length: 7 }, (_, day) => open("09:00", "17:00", day)));
  expect(within("2026-01-05T09:00:00Z", "2026-01-05T17:00:00Z", value)).toBe(true);
  expect(within("2026-07-06T08:00:00Z", "2026-07-06T16:00:00Z", value)).toBe(true);
  expect(within("2026-07-06T16:00:00Z", "2026-07-06T17:00:00Z", value)).toBe(false);
  expect(practiceDateParts(new Date("2026-07-06T23:15:30Z"))).toEqual({ key: "2026-07-07", minutes: 15.5 });
  expect(practiceDateParts(new Date("2026-01-05T23:15:30Z"))).toEqual({ key: "2026-01-05", minutes: 1395.5 });
});

test("spring daylight-saving transition uses the correct London date and skips the missing hour", () => {
  expect(practiceDateParts(new Date("2026-03-29T00:59:00Z"))).toEqual({ key: "2026-03-29", minutes: 59 });
  expect(practiceDateParts(new Date("2026-03-29T01:00:00Z"))).toEqual({ key: "2026-03-29", minutes: 120 });
  expect(practiceDateParts(new Date("2026-03-29T23:00:00Z"))).toEqual({ key: "2026-03-30", minutes: 0 });
  const value = schedule([open("00:00", "02:00", 0)]);
  expect(within("2026-03-29T23:00:00Z", "2026-03-30T00:00:00Z", value)).toBe(true);
});

test("autumn daylight-saving transition handles the repeated hour and 25-hour date boundary", () => {
  expect(practiceDateParts(new Date("2026-10-24T23:00:00Z"))).toEqual({ key: "2026-10-25", minutes: 0 });
  expect(practiceDateParts(new Date("2026-10-25T00:30:00Z"))).toEqual({ key: "2026-10-25", minutes: 90 });
  expect(practiceDateParts(new Date("2026-10-25T01:30:00Z"))).toEqual({ key: "2026-10-25", minutes: 90 });
  expect(practiceDateParts(new Date("2026-10-25T23:59:00Z"))).toEqual({ key: "2026-10-25", minutes: 1439 });
  expect(practiceDateParts(new Date("2026-10-26T00:00:00Z"))).toEqual({ key: "2026-10-26", minutes: 0 });
  const value = schedule([open("00:00", "02:00", 0)]);
  expect(within("2026-10-26T00:00:00Z", "2026-10-26T01:00:00Z", value)).toBe(true);
});
