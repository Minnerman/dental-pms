"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Calendar, dateFnsLocalizer } from "react-big-calendar";
import {
  addMinutes,
  differenceInCalendarDays,
  endOfWeek,
  format,
  getDay,
  parse,
  startOfWeek,
} from "date-fns";
import { enGB } from "date-fns/locale";
import HeaderBar from "@/components/ui/HeaderBar";
import { apiFetch, clearToken } from "@/lib/auth";

type AppointmentItem = {
  legacy_appointment_id: number;
  starts_at: string;
  ends_at?: string | null;
  duration_minutes?: number | null;
  status_normalised?: string | null;
  status_raw?: string | null;
  clinician_code?: number | null;
  clinician_name?: string | null;
  clinician_role?: string | null;
  clinician_is_current?: boolean | null;
  patient_id?: number | null;
  patient_display_name?: string | null;
  is_unlinked: boolean;
  title?: string | null;
  notes?: string | null;
};

type AppointmentResponse = {
  items: AppointmentItem[];
  total_count?: number | null;
};

type CalendarEvent = {
  id: string;
  title: string;
  start: Date;
  end: Date;
  resource: AppointmentItem;
};

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek,
  getDay,
  locales: { "en-GB": enGB },
});

const r4AppointmentsPath = "/api/appointments";
const r4AppointmentsProxyPath = r4AppointmentsPath.startsWith("/api/")
  ? `/api${r4AppointmentsPath}`
  : r4AppointmentsPath;

function buildDefaultRange() {
  const today = new Date();
  const start = startOfWeek(today, { weekStartsOn: 1 });
  const end = endOfWeek(today, { weekStartsOn: 1 });
  return {
    from: format(start, "yyyy-MM-dd"),
    to: format(end, "yyyy-MM-dd"),
  };
}

function parseDate(value: string) {
  const parsed = parse(value, "yyyy-MM-dd", new Date());
  return Number.isNaN(parsed.getTime()) ? new Date() : parsed;
}

function buildUnlinkedDetail(item: AppointmentItem) {
  const parts = [item.title, item.notes].filter(Boolean) as string[];
  return parts.join(" — ").trim();
}

function buildClinicianLabel(item: AppointmentItem) {
  if (!item.clinician_name && !item.clinician_role) return null;
  if (item.clinician_name && item.clinician_role) {
    return `${item.clinician_name} (${item.clinician_role})`;
  }
  return item.clinician_name ?? item.clinician_role ?? null;
}

function AppointmentEvent({ event }: { event: CalendarEvent }) {
  const item = event.resource;
  const clinician = buildClinicianLabel(item);
  const unlinkedDetail = item.is_unlinked ? buildUnlinkedDetail(item) : null;
  return (
    <div className="stack" style={{ gap: 2 }}>
      <div className="row" style={{ gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <strong>{item.patient_display_name ?? "Unlinked"}</strong>
        {item.is_unlinked && (
          <span className="badge" data-testid="r4-unlinked-badge">
            Unlinked
          </span>
        )}
      </div>
      {item.is_unlinked && unlinkedDetail && <div>{unlinkedDetail}</div>}
      {clinician && <div className="muted">{clinician}</div>}
    </div>
  );
}

export default function R4CalendarPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const defaults = useMemo(() => buildDefaultRange(), []);
  const [fromDate, setFromDate] = useState(defaults.from);
  const [toDate, setToDate] = useState(defaults.to);
  const [clinicianCode, setClinicianCode] = useState("");
  const [showHidden, setShowHidden] = useState(false);
  const [showUnlinked, setShowUnlinked] = useState(false);
  const [appointments, setAppointments] = useState<AppointmentItem[]>([]);
  const [totalCount, setTotalCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const nextFrom = searchParams.get("from") ?? defaults.from;
    const nextTo = searchParams.get("to") ?? defaults.to;
    const nextClinician = searchParams.get("clinician_code") ?? "";
    const nextShowHidden = searchParams.get("show_hidden") === "true";
    const nextShowUnlinked = searchParams.get("show_unlinked") === "true";
    if (nextFrom !== fromDate) setFromDate(nextFrom);
    if (nextTo !== toDate) setToDate(nextTo);
    if (nextClinician !== clinicianCode) setClinicianCode(nextClinician);
    if (nextShowHidden !== showHidden) setShowHidden(nextShowHidden);
    if (nextShowUnlinked !== showUnlinked) setShowUnlinked(nextShowUnlinked);
  }, [
    searchParams,
    defaults,
    fromDate,
    toDate,
    clinicianCode,
    showHidden,
    showUnlinked,
  ]);

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    params.set("from", fromDate);
    params.set("to", toDate);
    if (clinicianCode) params.set("clinician_code", clinicianCode);
    if (showHidden) params.set("show_hidden", "true");
    if (showUnlinked) params.set("show_unlinked", "true");
    return params.toString();
  }, [fromDate, toDate, clinicianCode, showHidden, showUnlinked]);

  useEffect(() => {
    const nextUrl = queryString ? `/r4-calendar?${queryString}` : "/r4-calendar";
    router.replace(nextUrl, { scroll: false });
  }, [queryString, router]);

  const loadAppointments = useCallback(async () => {
    if (!fromDate || !toDate) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        from: fromDate,
        to: toDate,
        include_total: "true",
      });
      if (clinicianCode) params.set("clinician_code", clinicianCode);
      if (showHidden) params.set("show_hidden", "true");
      if (showUnlinked) params.set("show_unlinked", "true");
      const res = await apiFetch(`${r4AppointmentsProxyPath}?${params.toString()}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load appointments (HTTP ${res.status})`);
      }
      const data = (await res.json()) as AppointmentResponse;
      setAppointments(data.items ?? []);
      setTotalCount(data.total_count ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load appointments");
    } finally {
      setLoading(false);
    }
  }, [fromDate, toDate, clinicianCode, showHidden, showUnlinked, router]);

  useEffect(() => {
    loadAppointments();
  }, [loadAppointments]);

  const clinicianOptions = useMemo(() => {
    const map = new Map<number, AppointmentItem>();
    appointments.forEach((item) => {
      if (!item.clinician_code) return;
      if (!map.has(item.clinician_code)) {
        map.set(item.clinician_code, item);
      }
    });
    return Array.from(map.values()).sort((a, b) => {
      const nameA = a.clinician_name ?? "";
      const nameB = b.clinician_name ?? "";
      return nameA.localeCompare(nameB);
    });
  }, [appointments]);

  const calendarEvents = useMemo<CalendarEvent[]>(() => {
    return appointments.map((item) => {
      const start = new Date(item.starts_at);
      let end = item.ends_at ? new Date(item.ends_at) : null;
      if (!end || Number.isNaN(end.getTime())) {
        const duration = item.duration_minutes ?? 30;
        end = addMinutes(start, duration);
      }
      const title = item.is_unlinked
        ? buildUnlinkedDetail(item) || "Unlinked"
        : item.patient_display_name ?? "Unlinked";
      return {
        id: String(item.legacy_appointment_id),
        title,
        start,
        end,
        resource: item,
      };
    });
  }, [appointments]);

  const fromParsed = parseDate(fromDate);
  const toParsed = parseDate(toDate);
  const agendaLength = Math.max(1, differenceInCalendarDays(toParsed, fromParsed) + 1);

  return (
    <div className="app-grid" data-testid="r4-calendar-page">
      <div className="card">
        <div className="stack">
          <HeaderBar
            title="R4 appointments (read-only)"
            subtitle="Review R4 diary data imported into Postgres."
          />
          <div className="notice" data-testid="r4-calendar-banner">
            Read-only: R4 remains the live diary
          </div>
          <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
            <label className="stack" style={{ gap: 6 }}>
              <span className="muted">From</span>
              <input
                className="input"
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                data-testid="r4-filter-from"
              />
            </label>
            <label className="stack" style={{ gap: 6 }}>
              <span className="muted">To</span>
              <input
                className="input"
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                data-testid="r4-filter-to"
              />
            </label>
            <label className="stack" style={{ gap: 6, minWidth: 220 }}>
              <span className="muted">Clinician</span>
              <select
                className="input"
                value={clinicianCode}
                onChange={(e) => setClinicianCode(e.target.value)}
                data-testid="r4-filter-clinician"
              >
                <option value="">All clinicians</option>
                {clinicianOptions.map((item) => (
                  <option key={item.clinician_code} value={item.clinician_code ?? ""}>
                    {item.clinician_name ?? "Unknown"}{" "}
                    {item.clinician_role ? `(${item.clinician_role})` : ""}
                  </option>
                ))}
              </select>
            </label>
            <label
              className="row"
              style={{ gap: 8, alignItems: "center" }}
              data-testid="r4-filter-show-hidden-toggle"
              onClick={() => setShowHidden((prev) => !prev)}
            >
              <input
                type="checkbox"
                checked={showHidden}
                onChange={(e) => setShowHidden(e.target.checked)}
                data-testid="r4-filter-show-hidden"
              />
              <span>Show hidden statuses</span>
            </label>
            <label className="row" style={{ gap: 8, alignItems: "center" }}>
              <input
                type="checkbox"
                checked={showUnlinked}
                onChange={(e) => setShowUnlinked(e.target.checked)}
                data-testid="r4-filter-show-unlinked"
              />
              <span>Show unlinked</span>
            </label>
            <button className="btn btn-secondary" onClick={loadAppointments} disabled={loading}>
              Refresh
            </button>
          </div>
          <div className="row" style={{ gap: 12, alignItems: "center" }}>
            {loading && <div className="badge">Loading appointments…</div>}
            {!loading && totalCount !== null && (
              <div className="badge">Total: {totalCount}</div>
            )}
          </div>
          {error && <div className="notice">{error}</div>}
          {!loading && appointments.length === 0 && !error && (
            <div className="notice">No appointments in this range.</div>
          )}
          <div style={{ height: 720 }}>
            <Calendar
              localizer={localizer}
              events={calendarEvents}
              defaultView="agenda"
              view="agenda"
              views={["agenda"]}
              date={fromParsed}
              length={agendaLength}
              startAccessor="start"
              endAccessor="end"
              components={{ event: AppointmentEvent }}
              toolbar={false}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
