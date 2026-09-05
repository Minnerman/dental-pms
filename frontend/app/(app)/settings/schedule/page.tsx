"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import type { PracticeSchedule, PracticeHour } from "@/lib/practiceSchedule";
import { applyDayChoice, cloneSchedule, dateLabel, DAY_LABELS, effectiveDay, halfDayBoundary, londonToday, monthDays, remainingSessions, shiftMonth, timeInput, validateSchedule, validateSessions, weeklySessions, type DayChoice, type Session } from "./scheduleEditor";
import styles from "./ScheduleSettings.module.css";

const EMPTY_SCHEDULE: PracticeSchedule = { hours: [], closures: [], overrides: [] };
const CHOICES: { value: DayChoice; label: string }[] = [
  { value: "weekly", label: "Use weekly hours" }, { value: "closed", label: "Full day closed" },
  { value: "morning", label: "Morning closed" }, { value: "afternoon", label: "Afternoon closed" },
  { value: "custom", label: "Custom hours" },
];

function SessionsEditor({ label, sessions, onChange, disabled }: { label: string; sessions: Session[]; onChange: (sessions: Session[]) => void; disabled: boolean }) {
  return <div className={styles.sessions}>
    {sessions.map((session, index) => <div className={styles.session} key={index}>
      <span className={styles.sessionLabel}>Session {index + 1}</span>
      <label><span className={styles.srOnly}>{label} session {index + 1} start</span><input type="time" step={timeInput(session.start_time).length > 5 ? 1 : 60} aria-label={`${label} session ${index + 1} start`} value={timeInput(session.start_time)} disabled={disabled} onChange={(event) => onChange(sessions.map((row, rowIndex) => rowIndex === index ? { ...row, start_time: event.target.value || null } : row))} /></label>
      <span aria-hidden="true">–</span>
      <label><span className={styles.srOnly}>{label} session {index + 1} end</span><input type="time" step={timeInput(session.end_time).length > 5 ? 1 : 60} aria-label={`${label} session ${index + 1} end`} value={timeInput(session.end_time)} disabled={disabled} onChange={(event) => onChange(sessions.map((row, rowIndex) => rowIndex === index ? { ...row, end_time: event.target.value || null } : row))} /></label>
      <button type="button" className={styles.remove} aria-label={`Remove ${label} session ${index + 1}`} disabled={disabled} onClick={() => onChange(sessions.filter((_, rowIndex) => rowIndex !== index))}>Remove</button>
    </div>)}
    {!sessions.length && <span className={styles.muted}>No opening sessions.</span>}
    <button type="button" className={styles.textButton} disabled={disabled} onClick={() => onChange([...sessions, { start_time: null, end_time: null }])}>＋ Add session<span className={styles.srOnly}> for {label}</span></button>
  </div>;
}

export default function ScheduleSettingsPage() {
  const router = useRouter();
  const [draft, setDraft] = useState<PracticeSchedule>(EMPTY_SCHEDULE);
  const [saved, setSaved] = useState<PracticeSchedule>(EMPTY_SCHEDULE);
  const [canEdit, setCanEdit] = useState(false);
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState(londonToday);
  const [month, setMonth] = useState(() => londonToday().slice(0, 7));
  const [choice, setChoice] = useState<DayChoice>("weekly");
  const [daySessions, setDaySessions] = useState<Session[]>([]);
  const [reason, setReason] = useState("");
  const [boundary, setBoundary] = useState("12:00");
  const [dayDirty, setDayDirty] = useState(false);
  const [dayError, setDayError] = useState<string | null>(null);
  const disabled = !canEdit || saving;
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  const days = useMemo(() => monthDays(month), [month]);
  const weekly = useMemo(() => weeklySessions(draft, selectedDate), [draft, selectedDate]);

  const loadSchedule = useCallback(async () => {
    setLoading(true); setError(null); setReady(false); setCanEdit(false);
    try {
      const [meResponse, scheduleResponse] = await Promise.all([apiFetch("/api/me", { cache: "no-store" }), apiFetch("/api/settings/schedule", { cache: "no-store" })]);
      if (meResponse.status === 401 || scheduleResponse.status === 401) { clearToken(); router.replace("/login"); return; }
      if (!meResponse.ok || !scheduleResponse.ok) throw new Error("The practice schedule and your access could not be verified. Please retry.");
      const me = await meResponse.json() as { role?: string };
      const value = cloneSchedule(await scheduleResponse.json() as PracticeSchedule);
      setDraft(value); setSaved(value); setCanEdit(me.role === "superadmin"); setReady(true); setDayDirty(false);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "The practice schedule could not be loaded."); }
    finally { setLoading(false); }
  }, [router]);

  useEffect(() => { void loadSchedule(); }, [loadSchedule]);
  useEffect(() => {
    if (!ready || dayDirty) return;
    const day = effectiveDay(draft, selectedDate);
    setChoice(day.source === "weekly" ? "weekly" : day.sessions.length ? "custom" : "closed");
    setDaySessions(day.sessions.map((session) => ({ ...session })));
    setBoundary(halfDayBoundary(weeklySessions(draft, selectedDate)));
    setReason(draft.overrides.find((row) => row.date === selectedDate)?.reason ?? draft.closures.find((row) => row.start_date <= selectedDate && row.end_date >= selectedDate)?.reason ?? "");
    setDayError(null);
  }, [draft, selectedDate, ready, dayDirty]);

  function updateDraft(value: PracticeSchedule) { if (!disabled) { setDraft(value); setNotice(null); setError(null); } }
  function updateDay(day: number, sessions: Session[]) {
    const rows: PracticeHour[] = sessions.length
      ? sessions.map((session) => ({ ...session, day_of_week: day, is_closed: false }))
      : [{ day_of_week: day, start_time: null, end_time: null, is_closed: true }];
    updateDraft({ ...draft, hours: [...draft.hours.filter((row) => row.day_of_week !== day), ...rows] });
  }
  function selectDate(key: string) {
    if (dayDirty && !window.confirm("Discard the unapplied changes for this date? Changes already added to the schedule draft are kept.")) return;
    setDayDirty(false); setSelectedDate(key); setMonth(key.slice(0, 7)); setDayError(null);
  }
  function chooseDay(value: DayChoice) {
    setChoice(value); setDayDirty(true); setDayError(null);
    if (value === "morning" || value === "afternoon") setDaySessions(remainingSessions(weekly, value, boundary));
    else if (value === "custom") setDaySessions(daySessions.length ? daySessions : weekly.length ? weekly.map((row) => ({ ...row })) : [{ start_time: null, end_time: null }]);
  }
  function applyDate() {
    if (disabled) return;
    const validation = choice !== "weekly" && choice !== "closed" ? validateSessions(daySessions, "Selected date") : null;
    if (validation) { setDayError(validation); return; }
    updateDraft(applyDayChoice(draft, selectedDate, choice, daySessions, reason));
    setDayDirty(false); setDayError(null); setNotice("Date added to the draft. Press Save schedule to keep your changes.");
  }
  async function saveSchedule() {
    if (disabled) return;
    if (dayDirty) { setError("Apply the selected date to the draft, or discard its changes, before saving the schedule."); return; }
    const validation = validateSchedule(draft);
    if (validation) { setError(validation); return; }
    setSaving(true); setError(null); setNotice(null);
    try {
      const response = await apiFetch("/api/settings/schedule", { method: "PUT", body: JSON.stringify(draft) });
      if (response.status === 401) { clearToken(); router.replace("/login"); return; }
      if (response.status === 403) { setCanEdit(false); throw new Error("Only a superadmin can save the practice schedule."); }
      if (!response.ok) {
        const body = await response.json().catch(() => null) as { detail?: unknown } | null;
        throw new Error(typeof body?.detail === "string" ? body.detail : "The schedule could not be saved. Check the dates and opening sessions, then retry.");
      }
      const value = cloneSchedule(await response.json() as PracticeSchedule);
      setDraft(value); setSaved(value); setNotice("Schedule saved. Existing appointments have not been changed or cancelled.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "The schedule could not be saved."); }
    finally { setSaving(false); }
  }

  return <section className={styles.page} data-testid="schedule-settings" data-mode={canEdit ? "edit" : "read-only"}>
    <header className={styles.heading}><div><h1>Practice opening hours</h1><p>Weekly sessions and date exceptions, in UK local time.</p></div>{ready && canEdit && <button type="button" className="btn btn-primary" disabled={saving || (!dirty && !dayDirty)} onClick={() => void saveSchedule()}>{saving ? "Saving…" : "Save schedule"}</button>}</header>
    {error && <div className="notice" role="alert">{error}{!ready && !loading && <button type="button" className="btn btn-secondary" onClick={() => void loadSchedule()}>Retry</button>}</div>}
    {notice && <div className={styles.notice} role="status">{notice}</div>}
    {loading ? <p role="status">Loading practice schedule…</p> : ready && <>
      {!canEdit && <p className={styles.notice} data-testid="schedule-read-only">Read-only. Only a superadmin can change practice hours.</p>}
      <div className={styles.saveStatus} role="status">{dirty || dayDirty ? "Unsaved changes" : "Showing saved hours"}<span>Changing hours does not cancel existing appointments.</span></div>
      <section className={styles.panel} aria-labelledby="weekly-hours-title">
        <div className={styles.sectionHeading}><div><h2 id="weekly-hours-title">Normal opening hours</h2><p>Add separate morning and afternoon sessions where you have a lunch break. Saved sessions are not split automatically.</p></div></div>
        <div className={styles.weekly} data-testid="weekly-hours">
          {DAY_LABELS.map((label, day) => {
            const rows = draft.hours.filter((row) => row.day_of_week === day);
            const closed = !rows.length || rows.every((row) => row.is_closed);
            return <div className={styles.dayRow} key={day} data-testid={`weekly-day-${day}`}>
              <div className={styles.dayHeading}><strong>{label}</strong><label className={styles.closedToggle}><input type="checkbox" aria-label={`${label} closed`} checked={closed} disabled={disabled} onChange={(event) => {
                if (event.target.checked) updateDraft({ ...draft, hours: [...draft.hours.filter((row) => row.day_of_week !== day), { day_of_week: day, start_time: null, end_time: null, is_closed: true }] });
                else { const previous = saved.hours.filter((row) => row.day_of_week === day && !row.is_closed); updateDay(day, previous.length ? previous : [{ start_time: null, end_time: null }]); }
              }} />Closed</label></div>
              {closed ? <span className={styles.muted}>{rows.length ? "Closed all day" : "No saved hours; treated as closed"}</span> : <SessionsEditor label={label} sessions={rows.filter((row) => !row.is_closed)} disabled={disabled} onChange={(sessions) => updateDay(day, sessions)} />}
            </div>;
          })}
        </div>
      </section>

      <section className={styles.panel} aria-labelledby="calendar-closures-title">
        <div className={styles.sectionHeading}><div><h2 id="calendar-closures-title">Closures and special hours</h2><p>Select a date to close all or part of the day, or set different opening sessions.</p></div></div>
        <div className={styles.calendarLayout}>
          <div>
            <div className={styles.monthHeading}><button type="button" className="btn btn-secondary" aria-label="Previous closure month" onClick={() => setMonth(shiftMonth(month, -1))}>‹</button><h3>{dateLabel(`${month}-01`, { month: "long", year: "numeric" })}</h3><button type="button" className="btn btn-secondary" aria-label="Next closure month" onClick={() => setMonth(shiftMonth(month, 1))}>›</button></div>
            <div className={styles.calendar} role="group" aria-label="Closure month calendar" data-testid="closure-calendar">
              {DAY_LABELS.map((label) => <div className={styles.weekday} key={label} aria-label={label}>{label.slice(0, 3)}</div>)}
              {days.map((key) => { const day = effectiveDay(draft, key); return <button key={key} type="button" className={styles.calendarDay} data-testid={`closure-date-${key}`} data-outside={key.slice(0, 7) !== month} data-kind={day.source === "weekly" ? day.sessions.length ? "weekly" : "weekly-closed" : day.sessions.length ? "custom" : "closed"} aria-label={`${dateLabel(key)}, ${day.label}`} aria-pressed={selectedDate === key} onClick={() => selectDate(key)}><span>{Number(key.slice(8))}</span><small>{day.source === "weekly" ? day.sessions.length ? "Open" : "Closed" : day.sessions.length ? "Special" : "Closed"}</small></button>; })}
            </div>
            <div className={styles.legend} aria-label="Schedule calendar legend"><span data-kind="weekly">Weekly hours</span><span data-kind="weekly-closed">Weekly closed</span><span data-kind="closed">Date closed</span><span data-kind="custom">Special hours</span></div>
          </div>
          <div className={styles.dayEditor} data-testid="schedule-day-editor">
            <h3>{dateLabel(selectedDate, { weekday: "long", day: "numeric", month: "short", year: "numeric" })}</h3>
            <label className={styles.field}>Selected date<input type="date" value={selectedDate} aria-label="Selected closure date" onChange={(event) => { if (event.target.value) selectDate(event.target.value); }} /></label>
            <label className={styles.field}>Opening arrangement<select aria-label="Date opening arrangement" value={choice} disabled={disabled} onChange={(event) => chooseDay(event.target.value as DayChoice)}>{CHOICES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
            {choice === "weekly" && <p className={styles.muted}>{weekly.length ? weekly.map((row) => `${timeInput(row.start_time)}–${timeInput(row.end_time)}`).join(" · ") : "This weekday is normally closed."}{draft.closures.some((row) => row.start_date <= selectedDate && row.end_date >= selectedDate) && " Using weekly hours removes this date from the closure range; all other dates stay unchanged."}</p>}
            {(choice === "morning" || choice === "afternoon") && <div className={styles.halfDay}><label className={styles.field}>Half-day boundary<input type="time" step={boundary.length > 5 ? 1 : 60} aria-label="Half-day boundary" value={boundary} disabled={disabled} onChange={(event) => { setBoundary(event.target.value); setDaySessions(remainingSessions(weekly, choice, event.target.value)); setDayDirty(true); }} /></label><p>{weekly.length > 1 ? "Suggested from the weekly session split above." : "Default boundary is 12:00, not a saved practice setting."} Check and edit the remaining opening sessions below.</p></div>}
            {choice !== "weekly" && choice !== "closed" && <div><h4>Remaining opening sessions</h4><SessionsEditor label="Selected date" sessions={daySessions} disabled={disabled} onChange={(sessions) => { setDaySessions(sessions); setDayDirty(true); }} /></div>}
            {choice !== "weekly" && <label className={styles.field}>Reason (optional)<input aria-label="Date closure reason" value={reason} disabled={disabled} onChange={(event) => { setReason(event.target.value); setDayDirty(true); }} /></label>}
            {dayError && <p role="alert" className={styles.validation}>{dayError}</p>}
            {canEdit && <div className={styles.editorActions}><button type="button" className="btn btn-secondary" disabled={disabled || !dayDirty} onClick={applyDate}>Apply date to draft</button>{dayDirty && <button type="button" className={styles.textButton} disabled={disabled} onClick={() => { setDayDirty(false); setDayError(null); }}>Discard date changes</button>}</div>}
            <p className={styles.muted}>The calendar previews the draft. Only Save schedule writes your changes.</p>
          </div>
        </div>
      </section>

      <section className={styles.panel} aria-labelledby="closure-ranges-title"><div className={styles.sectionHeading}><div><h2 id="closure-ranges-title">Closure ranges</h2><p>Whole-day closures over one or more dates. Date-specific opening sessions take priority.</p></div>{canEdit && <button type="button" className="btn btn-secondary" disabled={disabled} onClick={() => updateDraft({ ...draft, closures: [...draft.closures, { start_date: selectedDate, end_date: selectedDate, reason: null }] })}>Add closure range</button>}</div>
        {!draft.closures.length && <p className={styles.muted}>No closure ranges set.</p>}
        <div className={styles.rangeList}>{draft.closures.map((row, index) => <div key={index} className={styles.rangeRow}>
          <label className={styles.field}>From<input type="date" aria-label={`Closure range ${index + 1} start`} value={row.start_date} disabled={disabled} onChange={(event) => updateDraft({ ...draft, closures: draft.closures.map((item, i) => i === index ? { ...item, start_date: event.target.value } : item) })} /></label>
          <label className={styles.field}>To<input type="date" aria-label={`Closure range ${index + 1} end`} value={row.end_date} disabled={disabled} onChange={(event) => updateDraft({ ...draft, closures: draft.closures.map((item, i) => i === index ? { ...item, end_date: event.target.value } : item) })} /></label>
          <label className={styles.field}>Reason<input aria-label={`Closure range ${index + 1} reason`} value={row.reason ?? ""} disabled={disabled} onChange={(event) => updateDraft({ ...draft, closures: draft.closures.map((item, i) => i === index ? { ...item, reason: event.target.value || null } : item) })} /></label>
          <button type="button" className={styles.remove} aria-label={`Remove closure range ${index + 1}`} disabled={disabled} onClick={() => updateDraft({ ...draft, closures: draft.closures.filter((_, i) => i !== index) })}>Remove</button>
        </div>)}</div>
      </section>

      <details className={styles.panel} data-testid="schedule-override-review"><summary>Review individual date entries ({draft.overrides.length})</summary><p className={styles.muted}>Every saved override is retained here, including multiple sessions for the same date. Removing an entry restores the next applicable date closure or weekly session.</p>
        {!draft.overrides.length && <p className={styles.muted}>No date overrides set.</p>}
        <div className={styles.rangeList}>{draft.overrides.map((row, index) => <div key={index} className={styles.overrideRow}>
          <label className={styles.field}>Date<input type="date" aria-label={`Override ${index + 1} date`} value={row.date} disabled={disabled} onChange={(event) => updateDraft({ ...draft, overrides: draft.overrides.map((item, i) => i === index ? { ...item, date: event.target.value } : item) })} /></label>
          <label className={styles.closedToggle}><input type="checkbox" aria-label={`Override ${index + 1} closed`} checked={row.is_closed} disabled={disabled} onChange={(event) => updateDraft({ ...draft, overrides: draft.overrides.map((item, i) => i === index ? { ...item, is_closed: event.target.checked, start_time: event.target.checked ? null : item.start_time, end_time: event.target.checked ? null : item.end_time } : item) })} />Closed</label>
          <label className={styles.field}>From<input type="time" step={timeInput(row.start_time).length > 5 ? 1 : 60} aria-label={`Override ${index + 1} start`} value={timeInput(row.start_time)} disabled={disabled || row.is_closed} onChange={(event) => updateDraft({ ...draft, overrides: draft.overrides.map((item, i) => i === index ? { ...item, start_time: event.target.value || null } : item) })} /></label>
          <label className={styles.field}>To<input type="time" step={timeInput(row.end_time).length > 5 ? 1 : 60} aria-label={`Override ${index + 1} end`} value={timeInput(row.end_time)} disabled={disabled || row.is_closed} onChange={(event) => updateDraft({ ...draft, overrides: draft.overrides.map((item, i) => i === index ? { ...item, end_time: event.target.value || null } : item) })} /></label>
          <label className={styles.field}>Reason<input aria-label={`Override ${index + 1} reason`} value={row.reason ?? ""} disabled={disabled} onChange={(event) => updateDraft({ ...draft, overrides: draft.overrides.map((item, i) => i === index ? { ...item, reason: event.target.value || null } : item) })} /></label>
          <button type="button" className={styles.remove} aria-label={`Remove override ${index + 1}`} disabled={disabled} onClick={() => updateDraft({ ...draft, overrides: draft.overrides.filter((_, i) => i !== index) })}>Remove</button>
        </div>)}</div>
      </details>
      {canEdit && <footer className={styles.saveFooter}><span>{dirty || dayDirty ? "Changes are not saved yet." : "All changes saved."}</span><button type="button" className="btn btn-primary" disabled={saving || (!dirty && !dayDirty)} onClick={() => void saveSchedule()}>{saving ? "Saving…" : "Save schedule"}</button></footer>}
    </>}
  </section>;
}
