import type { PracticeSchedule, PracticeHour, PracticeOverride } from "@/lib/practiceSchedule";

export type Session = { start_time: string | null; end_time: string | null };
export type DayChoice = "weekly" | "closed" | "morning" | "afternoon" | "custom";
export const DAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export function londonToday() {
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  const part = (type: string) => parts.find((item) => item.type === type)?.value;
  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function shiftDate(key: string, days: number) {
  const date = new Date(`${key}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function shiftMonth(key: string, months: number) {
  const date = new Date(`${key}-01T12:00:00Z`);
  date.setUTCMonth(date.getUTCMonth() + months);
  return date.toISOString().slice(0, 7);
}

export function monthDays(month: string) {
  const first = `${month}-01`;
  const weekday = (new Date(`${first}T12:00:00Z`).getUTCDay() + 6) % 7;
  const start = shiftDate(first, -weekday);
  return Array.from({ length: 42 }, (_, index) => shiftDate(start, index));
}

export function dateLabel(key: string, options: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" }) {
  return new Intl.DateTimeFormat("en-GB", { ...options, timeZone: "UTC" }).format(new Date(`${key}T12:00:00Z`));
}

export function timeInput(value: string | null) {
  if (!value) return "";
  // Do not discard non-zero seconds from a previously saved time.
  return /:00(?:\.0+)?$/.test(value) && value.length > 5 ? value.slice(0, 5) : value;
}

function seconds(value: string | null) {
  if (!value || !/^\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(value)) return NaN;
  const [hour, minute, second = 0] = value.split(":").map(Number);
  return hour < 24 && minute < 60 && second < 60 ? hour * 3600 + minute * 60 + second : NaN;
}

export function cloneSchedule(value: PracticeSchedule): PracticeSchedule {
  return {
    hours: value.hours.map(({ day_of_week, start_time, end_time, is_closed }) => ({ day_of_week, start_time, end_time, is_closed })),
    closures: value.closures.map(({ start_date, end_date, reason }) => ({ start_date, end_date, reason })),
    overrides: value.overrides.map(({ date, start_time, end_time, is_closed, reason }) => ({ date, start_time, end_time, is_closed, reason })),
  };
}

export function weeklySessions(schedule: PracticeSchedule, key: string): Session[] {
  const weekday = (new Date(`${key}T12:00:00Z`).getUTCDay() + 6) % 7;
  const rows = schedule.hours.filter((row) => row.day_of_week === weekday);
  if (rows.some((row) => row.is_closed)) return [];
  return rows.filter((row) => row.start_time && row.end_time).map((row) => ({ start_time: row.start_time, end_time: row.end_time })).sort((a, b) => seconds(a.start_time) - seconds(b.start_time));
}

export function effectiveDay(schedule: PracticeSchedule, key: string) {
  const overrides = schedule.overrides.filter((row) => row.date === key);
  if (overrides.some((row) => row.is_closed)) return { source: "override" as const, sessions: [] as Session[], label: "Full day closed" };
  if (overrides.length) return { source: "override" as const, sessions: overrides.map((row) => ({ start_time: row.start_time, end_time: row.end_time })), label: "Custom hours" };
  if (schedule.closures.some((row) => row.start_date <= key && row.end_date >= key)) return { source: "closure" as const, sessions: [] as Session[], label: "Full day closed" };
  const sessions = weeklySessions(schedule, key);
  return { source: "weekly" as const, sessions, label: sessions.length ? "Weekly hours" : "Weekly closed" };
}

export function halfDayBoundary(sessions: Session[]) {
  return sessions.length > 1 ? timeInput(sessions[1].start_time) : "12:00";
}

export function remainingSessions(sessions: Session[], choice: "morning" | "afternoon", boundary: string): Session[] {
  const split = seconds(boundary);
  if (!Number.isFinite(split)) return [];
  return sessions.flatMap((session) => {
    const start = seconds(session.start_time);
    const end = seconds(session.end_time);
    if (!Number.isFinite(start) || !Number.isFinite(end)) return [];
    if (choice === "morning") return end > split ? [{ start_time: start < split ? boundary : session.start_time, end_time: session.end_time }] : [];
    return start < split ? [{ start_time: session.start_time, end_time: end > split ? boundary : session.end_time }] : [];
  });
}

export function withoutClosureDate(schedule: PracticeSchedule, key: string) {
  return schedule.closures.flatMap((row) => {
    if (key < row.start_date || key > row.end_date) return [row];
    return [
      ...(row.start_date < key ? [{ ...row, end_date: shiftDate(key, -1) }] : []),
      ...(row.end_date > key ? [{ ...row, start_date: shiftDate(key, 1) }] : []),
    ];
  });
}

export function applyDayChoice(schedule: PracticeSchedule, key: string, choice: DayChoice, sessions: Session[], reason: string): PracticeSchedule {
  const otherOverrides = schedule.overrides.filter((row) => row.date !== key);
  if (choice === "weekly") return { ...schedule, overrides: otherOverrides, closures: withoutClosureDate(schedule, key) };
  const rows: PracticeOverride[] = choice === "closed"
    ? [{ date: key, start_time: null, end_time: null, is_closed: true, reason: reason.trim() || null }]
    : sessions.map((session) => ({ ...session, date: key, is_closed: false, reason: reason.trim() || null }));
  return { ...schedule, overrides: [...otherOverrides, ...rows] };
}

export function validateSessions(rows: Session[], label: string): string | null {
  if (!rows.length) return `${label}: add at least one opening session or choose full day closed.`;
  const sorted = [...rows].sort((a, b) => seconds(a.start_time) - seconds(b.start_time));
  for (let index = 0; index < sorted.length; index += 1) {
    const row = sorted[index];
    const start = seconds(row.start_time);
    const end = seconds(row.end_time);
    if (!Number.isFinite(start) || !Number.isFinite(end)) return `${label}: each opening session needs a valid start and end time.`;
    if (end <= start) return `${label}: a session must end after it starts.`;
    if (index && start < seconds(sorted[index - 1].end_time)) return `${label}: opening sessions must not overlap.`;
  }
  return null;
}

export function validateSchedule(schedule: PracticeSchedule): string | null {
  if (!schedule.hours.length) return "Set weekly hours, or mark all seven days closed.";
  const validateGroup = (rows: (PracticeHour | PracticeOverride)[], label: string) => {
    if (rows.some((row) => row.is_closed)) return rows.length > 1 ? `${label}: a closed day cannot also contain another opening or closed entry.` : null;
    return validateSessions(rows, label);
  };
  for (const day of new Set(schedule.hours.map((row) => row.day_of_week))) {
    if (!Number.isInteger(day) || day < 0 || day > 6) return "Weekly hours contain an invalid day.";
    const error = validateGroup(schedule.hours.filter((row) => row.day_of_week === day), DAY_LABELS[day]);
    if (error) return error;
  }
  for (const row of schedule.closures) {
    if (!row.start_date || !row.end_date || row.end_date < row.start_date) return "Closure ranges need valid start and end dates, with the end on or after the start.";
  }
  for (const date of new Set(schedule.overrides.map((row) => row.date))) {
    if (!date) return "Each date override needs a date.";
    const error = validateGroup(schedule.overrides.filter((row) => row.date === date), date);
    if (error) return error;
  }
  return null;
}
