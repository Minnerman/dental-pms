export type PracticeHour = { day_of_week: number; start_time: string | null; end_time: string | null; is_closed: boolean };
export type PracticeClosure = { start_date: string; end_date: string; reason: string | null };
export type PracticeOverride = { date: string; start_time: string | null; end_time: string | null; is_closed: boolean; reason: string | null };
export type PracticeSchedule = { hours: PracticeHour[]; closures: PracticeClosure[]; overrides: PracticeOverride[] };
export type WorkingSession = { start: number; end: number };

const practiceClock = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });

export function practiceDateParts(value: Date) {
  const parts = Object.fromEntries(practiceClock.formatToParts(value).map((part) => [part.type, part.value]));
  return { key: `${parts.year}-${parts.month}-${parts.day}`, minutes: Number(parts.hour) * 60 + Number(parts.minute) + Number(parts.second) / 60 };
}

export function getWorkingSessionsForKey(key: string, schedule: PracticeSchedule): WorkingSession[] {
  const overrides = schedule.overrides.filter((item) => item.date === key);
  const weekday = (new Date(`${key}T12:00:00Z`).getUTCDay() + 6) % 7;
  const rows = overrides.length ? overrides : schedule.closures.some((item) => item.start_date <= key && key <= item.end_date) ? [] : schedule.hours.filter((item) => item.day_of_week === weekday);
  if (rows.some((item) => item.is_closed)) return [];
  const minutes = (value: string) => {
    const match = /^([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d(?:\.\d{1,6})?))?$/.exec(value);
    return match ? Number(match[1]) * 60 + Number(match[2]) + Number(match[3] ?? 0) / 60 : Number.NaN;
  };
  if (rows.some((item) => !item.start_time || !item.end_time)) return [];
  const sessions = rows.map((item) => ({ start: minutes(item.start_time!), end: minutes(item.end_time!) })).sort((a, b) => a.start - b.start);
  if (sessions.some((item, index) => !Number.isFinite(item.start) || !Number.isFinite(item.end) || item.start < 0 || item.end >= 1440 || item.end <= item.start || (index > 0 && item.start < sessions[index - 1].end))) return [];
  // Adjacent sessions cover a continuous period; a lunch gap never does.
  const merged: WorkingSession[] = [];
  for (const session of sessions) {
    const last = merged[merged.length - 1];
    if (last && session.start === last.end) last.end = session.end;
    else merged.push({ ...session });
  }
  return merged;
}

export function isWithinPracticeHours(start: Date, end: Date, schedule: PracticeSchedule | null): boolean | null {
  if (!schedule) return null;
  if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) || end <= start) return false;
  const from = practiceDateParts(start), to = practiceDateParts(end);
  if (from.key !== to.key) return false;
  return getWorkingSessionsForKey(from.key, schedule).some((session) => from.minutes >= session.start && to.minutes <= session.end);
}
