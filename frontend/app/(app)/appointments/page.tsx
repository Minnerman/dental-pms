"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Calendar,
  dateFnsLocalizer,
  type SlotInfo,
  type View,
} from "react-big-calendar";
import withDragAndDrop from "react-big-calendar/lib/addons/dragAndDrop";
import { format, parse, startOfWeek, getDay } from "date-fns";
import { enGB } from "date-fns/locale";
import { apiFetch, clearToken } from "@/lib/auth";

type Actor = { id: number; email: string; role: string };
type PatientCategory = "CLINIC_PRIVATE" | "DOMICILIARY_PRIVATE" | "DENPLAN";
type CareSetting = "CLINIC" | "HOME" | "CARE_HOME" | "HOSPITAL";
type AppointmentStatus =
  | "booked"
  | "arrived"
  | "in_progress"
  | "completed"
  | "cancelled"
  | "no_show";
type AppointmentLocationType = "clinic" | "visit";

type PatientSummary = {
  id: number;
  first_name: string;
  last_name: string;
  patient_category: PatientCategory;
  care_setting: CareSetting;
};

type Appointment = {
  id: number;
  patient: PatientSummary;
  patient_has_alerts: boolean;
  clinician_user_id?: number | null;
  appointment_type?: string | null;
  clinician?: string | null;
  location?: string | null;
  location_type: AppointmentLocationType;
  location_text?: string | null;
  is_domiciliary: boolean;
  visit_address?: string | null;
  starts_at: string;
  ends_at: string;
  status: AppointmentStatus;
  created_by: Actor;
  updated_by?: Actor | null;
  updated_at: string;
  deleted_at?: string | null;
};

type CalendarEvent = {
  id: string;
  title: string;
  start: Date;
  end: Date;
  resource: Appointment;
};

type Patient = {
  id: number;
  first_name: string;
  last_name: string;
  care_setting: CareSetting;
  visit_address_text?: string | null;
  phone?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  postcode?: string | null;
};
type PatientDetail = {
  id: number;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  phone?: string | null;
  email?: string | null;
  care_setting: CareSetting;
  visit_address_text?: string | null;
  access_notes?: string | null;
  primary_contact_name?: string | null;
  primary_contact_phone?: string | null;
  primary_contact_relationship?: string | null;
  allergies?: string | null;
  medical_alerts?: string | null;
  safeguarding_notes?: string | null;
};

type UserOption = {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
};

type AppointmentNote = {
  id: number;
  body: string;
  created_at: string;
  created_by: Actor;
};

type PracticeHour = {
  day_of_week: number;
  start_time: string | null;
  end_time: string | null;
  is_closed: boolean;
};

type PracticeClosure = {
  start_date: string;
  end_date: string;
  reason: string | null;
};

type PracticeOverride = {
  date: string;
  start_time: string | null;
  end_time: string | null;
  is_closed: boolean;
  reason: string | null;
};

type PracticeSchedule = {
  hours: PracticeHour[];
  closures: PracticeClosure[];
  overrides: PracticeOverride[];
};

type LocationFilter = "all" | "clinic" | "visit";

type CalendarRange = {
  start: string;
  end: string;
  view: View;
  anchor: string;
};

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek,
  getDay,
  locales: { "en-GB": enGB },
});

const DragAndDropCalendar = withDragAndDrop<CalendarEvent>(Calendar);

const statusLabels: Record<AppointmentStatus, string> = {
  booked: "Booked",
  arrived: "Arrived",
  in_progress: "In progress",
  completed: "Completed",
  cancelled: "Cancelled",
  no_show: "No show",
};

const statusThemeTokens: Record<
  AppointmentStatus,
  { bg: string; border: string; text: string }
> = {
  booked: {
    bg: "var(--cal-event-booked-bg)",
    border: "var(--cal-event-booked-border)",
    text: "var(--cal-event-booked-text)",
  },
  arrived: {
    bg: "var(--cal-event-arrived-bg)",
    border: "var(--cal-event-arrived-border)",
    text: "var(--cal-event-arrived-text)",
  },
  in_progress: {
    bg: "var(--cal-event-in-progress-bg)",
    border: "var(--cal-event-in-progress-border)",
    text: "var(--cal-event-in-progress-text)",
  },
  completed: {
    bg: "var(--cal-event-completed-bg)",
    border: "var(--cal-event-completed-border)",
    text: "var(--cal-event-completed-text)",
  },
  cancelled: {
    bg: "var(--cal-event-cancelled-bg)",
    border: "var(--cal-event-cancelled-border)",
    text: "var(--cal-event-cancelled-text)",
  },
  no_show: {
    bg: "var(--cal-event-no-show-bg)",
    border: "var(--cal-event-no-show-border)",
    text: "var(--cal-event-no-show-text)",
  },
};

function toDateKey(value: Date) {
  return value.toLocaleDateString("en-CA");
}

function toLocalDateTimeInput(date: Date) {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
}

function timeToMinutes(value: string) {
  const [hours, minutes = "0"] = value.split(":");
  return Number(hours) * 60 + Number(minutes);
}

function dateWithMinutes(minutes: number) {
  const base = new Date();
  base.setHours(0, 0, 0, 0);
  const next = new Date(base);
  next.setMinutes(minutes);
  return next;
}

function normalizeRangeEnd(start: Date, end: Date) {
  const normalized = new Date(end);
  if (
    normalized.getHours() === 0 &&
    normalized.getMinutes() === 0 &&
    normalized.getSeconds() === 0 &&
    normalized.getMilliseconds() === 0 &&
    normalized > start
  ) {
    normalized.setDate(normalized.getDate() - 1);
  }
  return normalized;
}

function buildShortAddress(patient?: Patient) {
  if (!patient) return "";
  if (patient.visit_address_text) return patient.visit_address_text;
  return [patient.address_line1, patient.address_line2, patient.city, patient.postcode]
    .filter(Boolean)
    .join(", ");
}

function getScheduleDayIndex(date: Date) {
  return (date.getDay() + 6) % 7;
}

function isDateWithinRange(date: Date, start: string, end: string) {
  const key = toDateKey(date);
  return key >= start && key <= end;
}

function getWorkingWindowForDate(date: Date, schedule: PracticeSchedule | null) {
  if (!schedule) return null;
  const key = toDateKey(date);
  const override = schedule.overrides.find((item) => item.date === key);
  if (override) {
    if (override.is_closed) return null;
    if (override.start_time && override.end_time) {
      return {
        start: timeToMinutes(override.start_time),
        end: timeToMinutes(override.end_time),
      };
    }
  }
  const isClosed = schedule.closures.some((closure) =>
    isDateWithinRange(date, closure.start_date, closure.end_date)
  );
  if (isClosed) return null;
  const dayIndex = getScheduleDayIndex(date);
  const hour = schedule.hours.find((item) => item.day_of_week === dayIndex);
  if (!hour || hour.is_closed || !hour.start_time || !hour.end_time) return null;
  return {
    start: timeToMinutes(hour.start_time),
    end: timeToMinutes(hour.end_time),
  };
}

function isRangeWithinSchedule(
  start: Date,
  end: Date,
  schedule: PracticeSchedule | null
) {
  if (!schedule) return true;
  if (toDateKey(start) !== toDateKey(end)) return false;
  const window = getWorkingWindowForDate(start, schedule);
  if (!window) return false;
  const startMinutes = start.getHours() * 60 + start.getMinutes();
  const endMinutes = end.getHours() * 60 + end.getMinutes();
  return startMinutes >= window.start && endMinutes <= window.end;
}

export default function AppointmentsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [schedule, setSchedule] = useState<PracticeSchedule | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [users, setUsers] = useState<UserOption[]>([]);
  const [patientQuery, setPatientQuery] = useState("");
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [clinicianUserId, setClinicianUserId] = useState("");
  const [appointmentType, setAppointmentType] = useState("");
  const [location, setLocation] = useState("");
  const [locationType, setLocationType] = useState<AppointmentLocationType>("clinic");
  const [locationText, setLocationText] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [showNewModal, setShowNewModal] = useState(false);
  const [locationFilter, setLocationFilter] = useState<LocationFilter>("all");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [selectedAppointment, setSelectedAppointment] = useState<Appointment | null>(null);
  const [noteBody, setNoteBody] = useState("");
  const [notes, setNotes] = useState<AppointmentNote[]>([]);
  const [loadingNotes, setLoadingNotes] = useState(false);
  const [detailPatient, setDetailPatient] = useState<PatientDetail | null>(null);
  const [loadingPatientDetail, setLoadingPatientDetail] = useState(false);
  const [detailLocationType, setDetailLocationType] =
    useState<AppointmentLocationType>("clinic");
  const [detailLocationText, setDetailLocationText] = useState("");
  const [savingDetail, setSavingDetail] = useState(false);
  const [range, setRange] = useState<CalendarRange | null>(null);
  const [calendarView, setCalendarView] = useState<View>("week");
  const [currentDate, setCurrentDate] = useState(() => new Date());
  const [highlightedAppointmentId, setHighlightedAppointmentId] = useState<string | null>(
    null
  );

  const filteredPatients = useMemo(() => {
    const q = patientQuery.toLowerCase().trim();
    if (!q) return patients;
    return patients.filter((p) =>
      `${p.first_name} ${p.last_name}`.toLowerCase().includes(q)
    );
  }, [patientQuery, patients]);

  const calendarEvents = useMemo<CalendarEvent[]>(
    () =>
      appointments.map((appt) => ({
        id: String(appt.id),
        title: `${appt.patient.first_name} ${appt.patient.last_name}`,
        start: new Date(appt.starts_at),
        end: new Date(appt.ends_at),
        resource: appt,
      })),
    [appointments]
  );

  const patientLookup = useMemo(() => {
    return new Map(patients.map((patient) => [patient.id, patient]));
  }, [patients]);

  const { minTime, maxTime } = useMemo(() => {
    if (!schedule) return { minTime: undefined, maxTime: undefined };
    const hours = schedule.hours.filter(
      (hour) => !hour.is_closed && hour.start_time && hour.end_time
    );
    if (hours.length === 0) return { minTime: undefined, maxTime: undefined };
    const minMinutes = Math.min(...hours.map((hour) => timeToMinutes(hour.start_time!)));
    const maxMinutes = Math.max(...hours.map((hour) => timeToMinutes(hour.end_time!)));
    return {
      minTime: dateWithMinutes(minMinutes),
      maxTime: dateWithMinutes(maxMinutes),
    };
  }, [schedule]);

  function openAppointment(appt: Appointment) {
    setSelectedAppointment(appt);
    setDetailLocationType(appt.location_type);
    setDetailLocationText(appt.location_text || "");
    void loadAppointmentNotes(appt.id);
    void loadPatientDetail(appt.patient.id);
  }

  async function loadSchedule() {
    try {
      const res = await apiFetch("/api/settings/schedule");
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) throw new Error(`Failed to load schedule (HTTP ${res.status})`);
      const data = (await res.json()) as PracticeSchedule;
      setSchedule(data);
    } catch {
      setSchedule(null);
    }
  }

  async function loadAppointments() {
    if (!range) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("start", range.start);
      params.set("end", range.end);
      if (locationFilter !== "all") params.set("location", locationFilter);
      const res = await apiFetch(`/api/appointments/range?${params.toString()}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) throw new Error(`Failed to load appointments (HTTP ${res.status})`);
      const data = (await res.json()) as Appointment[];
      setAppointments(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load appointments");
    } finally {
      setLoading(false);
    }
  }

  async function loadPatients() {
    try {
      const res = await apiFetch("/api/patients?limit=200");
      if (res.ok) {
        const data = (await res.json()) as Patient[];
        setPatients(data);
      }
    } catch {
      setPatients([]);
    }
  }

  async function loadUsers() {
    try {
      const res = await apiFetch("/api/users");
      if (res.ok) {
        const data = (await res.json()) as UserOption[];
        setUsers(data.filter((u) => u.is_active));
      }
    } catch {
      setUsers([]);
    }
  }

  async function updateAppointmentStatus(appointmentId: number, status: AppointmentStatus) {
    setError(null);
    try {
      const res = await apiFetch(`/api/appointments/${appointmentId}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to update appointment (HTTP ${res.status})`);
      }
      const updated = (await res.json()) as Appointment;
      setAppointments((prev) => prev.map((appt) => (appt.id === updated.id ? updated : appt)));
      setNotice(`Status updated to ${statusLabels[status]}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update appointment");
    }
  }

  async function updateAppointmentTimes(
    appointmentId: number,
    startsAt: Date,
    endsAt: Date
  ) {
    const res = await apiFetch(`/api/appointments/${appointmentId}`, {
      method: "PATCH",
      body: JSON.stringify({
        starts_at: startsAt.toISOString(),
        ends_at: endsAt.toISOString(),
      }),
    });
    if (res.status === 401) {
      clearToken();
      router.replace("/login");
      return null;
    }
    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || `Failed to update appointment (HTTP ${res.status})`);
    }
    return (await res.json()) as Appointment;
  }

  async function createEstimateForAppointment(appt: Appointment) {
    setError(null);
    try {
      const res = await apiFetch(`/api/patients/${appt.patient.id}/estimates`, {
        method: "POST",
        body: JSON.stringify({ appointment_id: appt.id }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to create estimate (HTTP ${res.status})`);
      }
      const data = (await res.json()) as { id: number };
      setNotice(`Estimate created (EST-${data.id}).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create estimate");
    }
  }

  async function downloadRunSheet() {
    if (!range) return;
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("date", range.start);
      if (range.start !== range.end) params.set("end", range.end);
      params.set("location", "visit");
      const res = await apiFetch(`/api/appointments/run-sheet.pdf?${params.toString()}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to download run sheet (HTTP ${res.status})`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      const label =
        range.view === "week" || range.view === "agenda"
          ? `week-of-${range.start}`
          : range.start;
      link.href = url;
      link.download = `Run_Sheet_${label}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download run sheet");
    }
  }

  useEffect(() => {
    void loadSchedule();
    void loadPatients();
    void loadUsers();
  }, []);

  useEffect(() => {
    void loadAppointments();
  }, [range, locationFilter]);

  useEffect(() => {
    if (!selectedPatientId) return;
    const patient = patients.find((p) => String(p.id) === selectedPatientId);
    if (!patient) return;
    if (patient.care_setting !== "CLINIC") {
      setLocationType("visit");
      if (!locationText.trim()) {
        setLocationText(patient.visit_address_text || "");
      }
    } else {
      setLocationType("clinic");
      setLocationText("");
    }
  }, [selectedPatientId, patients, locationText]);

  async function createAppointment(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedPatientId || !startsAt || !endsAt) return;
    if (locationType === "visit" && !locationText.trim()) {
      setError("Visit address is required for domiciliary visits.");
      return;
    }
    if (!isRangeWithinSchedule(new Date(startsAt), new Date(endsAt), schedule)) {
      setError("Appointment time is outside of working hours.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/api/appointments", {
        method: "POST",
        body: JSON.stringify({
          patient_id: Number(selectedPatientId),
          clinician_user_id: clinicianUserId ? Number(clinicianUserId) : undefined,
          starts_at: new Date(startsAt).toISOString(),
          ends_at: new Date(endsAt).toISOString(),
          status: "booked",
          appointment_type: appointmentType.trim() || undefined,
          location: location.trim() || undefined,
          location_type: locationType,
          location_text: locationText.trim() || undefined,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to create appointment (HTTP ${res.status})`);
      }
      setSelectedPatientId("");
      setClinicianUserId("");
      setAppointmentType("");
      setLocation("");
      setLocationType("clinic");
      setLocationText("");
      setStartsAt("");
      setEndsAt("");
      setShowNewModal(false);
      setNotice("Appointment created.");
      await loadAppointments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create appointment");
    } finally {
      setSaving(false);
    }
  }

  async function loadAppointmentNotes(appointmentId: number) {
    setLoadingNotes(true);
    try {
      const res = await apiFetch(`/api/appointments/${appointmentId}/notes`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.ok) {
        const data = (await res.json()) as AppointmentNote[];
        setNotes(data);
      }
    } catch {
      setNotes([]);
    } finally {
      setLoadingNotes(false);
    }
  }

  async function loadPatientDetail(patientId: number) {
    setLoadingPatientDetail(true);
    try {
      const res = await apiFetch(`/api/patients/${patientId}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.ok) {
        const data = (await res.json()) as PatientDetail;
        setDetailPatient(data);
      } else {
        setDetailPatient(null);
      }
    } catch {
      setDetailPatient(null);
    } finally {
      setLoadingPatientDetail(false);
    }
  }

  async function addAppointmentNote(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedAppointment || !noteBody.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/api/notes", {
        method: "POST",
        body: JSON.stringify({
          patient_id: selectedAppointment.patient.id,
          appointment_id: selectedAppointment.id,
          body: noteBody.trim(),
          note_type: "clinical",
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to add note (HTTP ${res.status})`);
      }
      setNoteBody("");
      await loadAppointmentNotes(selectedAppointment.id);
      setNotice("Note added.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add note");
    } finally {
      setSaving(false);
    }
  }

  async function saveAppointmentDetails(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedAppointment) return;
    if (detailLocationType === "visit" && !detailLocationText.trim()) {
      setError("Visit address is required for domiciliary visits.");
      return;
    }
    setSavingDetail(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/appointments/${selectedAppointment.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          location_type: detailLocationType,
          location_text: detailLocationText.trim() || null,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to update appointment (HTTP ${res.status})`);
      }
      const updated = (await res.json()) as Appointment;
      setSelectedAppointment(updated);
      setDetailLocationType(updated.location_type);
      setDetailLocationText(updated.location_text || "");
      setNotice("Appointment updated.");
      await loadAppointments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update appointment");
    } finally {
      setSavingDetail(false);
    }
  }

  function updateRange(start: Date, end: Date, view: View, anchor: Date) {
    const normalizedEnd = normalizeRangeEnd(start, end);
    setRange({
      start: toDateKey(start),
      end: toDateKey(normalizedEnd),
      view,
      anchor: toDateKey(anchor),
    });
  }

  useEffect(() => {
    if (!searchParams) return;
    const targetDate = searchParams.get("date");
    const appointmentParam = searchParams.get("appointment");
    setHighlightedAppointmentId(appointmentParam);
    if (!targetDate) return;
    const parsed = new Date(`${targetDate}T00:00:00`);
    if (Number.isNaN(parsed.getTime())) return;
    setCalendarView("day");
    setCurrentDate(parsed);
    updateRange(parsed, parsed, "day", parsed);
  }, [searchParams]);

  function handleRangeChange(nextRange: Date[] | { start: Date; end: Date }, view?: View) {
    const nextView = view ?? calendarView;
    if (Array.isArray(nextRange)) {
      const start = nextRange[0];
      const end = nextRange[nextRange.length - 1];
      updateRange(start, end, nextView, currentDate);
      return;
    }
    updateRange(nextRange.start, nextRange.end, nextView, currentDate);
  }

  function handleSelectSlot(slotInfo: SlotInfo) {
    if (calendarView === "month" || calendarView === "agenda") {
      setError("Select a time slot in day/week view to create an appointment.");
      return;
    }
    if (!slotInfo.start || !slotInfo.end) return;
    if (!isRangeWithinSchedule(slotInfo.start, slotInfo.end, schedule)) {
      setError("Selected time is outside of working hours.");
      return;
    }
    setStartsAt(toLocalDateTimeInput(slotInfo.start));
    setEndsAt(toLocalDateTimeInput(slotInfo.end));
    setShowNewModal(true);
  }

  async function handleEventDrop({
    event,
    start,
    end,
  }: {
    event: CalendarEvent;
    start: Date;
    end: Date;
  }) {
    try {
      if (!isRangeWithinSchedule(start, end, schedule)) {
        setError("Reschedule is outside of working hours.");
        await loadAppointments();
        return;
      }
      const confirmed = window.confirm("Reschedule this appointment?");
      if (!confirmed) {
        await loadAppointments();
        return;
      }
      const updated = await updateAppointmentTimes(event.resource.id, start, end);
      if (updated) {
        setAppointments((prev) =>
          prev.map((item) => (item.id === updated.id ? updated : item))
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reschedule appointment");
      await loadAppointments();
    }
  }

  async function handleEventResize({
    event,
    start,
    end,
  }: {
    event: CalendarEvent;
    start: Date;
    end: Date;
  }) {
    try {
      if (!isRangeWithinSchedule(start, end, schedule)) {
        setError("Resize is outside of working hours.");
        await loadAppointments();
        return;
      }
      const confirmed = window.confirm("Update appointment duration?");
      if (!confirmed) {
        await loadAppointments();
        return;
      }
      const updated = await updateAppointmentTimes(event.resource.id, start, end);
      if (updated) {
        setAppointments((prev) =>
          prev.map((item) => (item.id === updated.id ? updated : item))
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resize appointment");
      await loadAppointments();
    }
  }

  function handleEventSelect(event: CalendarEvent) {
    openAppointment(event.resource);
  }

  function jumpToDate(value: string) {
    if (!value) return;
    setCurrentDate(new Date(`${value}T00:00:00`));
  }

  function handleNavigate(date: Date) {
    setCurrentDate(date);
    setRange((prev) => (prev ? { ...prev, anchor: toDateKey(date) } : prev));
  }

  function eventStyleGetter(event: CalendarEvent) {
    const theme = statusThemeTokens[event.resource.status];
    const isHighlighted =
      highlightedAppointmentId && String(event.resource.id) === highlightedAppointmentId;
    return {
      style: {
        backgroundColor: theme.bg,
        borderColor: theme.border,
        color: theme.text,
        borderStyle: "solid",
        borderWidth: isHighlighted ? 2 : 1,
        outline: isHighlighted ? "2px solid var(--accent)" : undefined,
        outlineOffset: isHighlighted ? 1 : undefined,
        boxShadow:
          event.resource.location_type === "visit"
            ? "0 0 0 2px rgba(255,255,255,0.5) inset"
            : undefined,
      },
    };
  }

  function dayPropGetter(date: Date) {
    if (!schedule) return {};
    const window = getWorkingWindowForDate(date, schedule);
    if (window) return {};
    return { style: { backgroundColor: "rgba(120, 120, 120, 0.12)" } };
  }

  function slotPropGetter(date: Date) {
    if (!schedule) return {};
    const window = getWorkingWindowForDate(date, schedule);
    if (!window) {
      return { style: { backgroundColor: "rgba(120, 120, 120, 0.12)" } };
    }
    const minutes = date.getHours() * 60 + date.getMinutes();
    if (minutes < window.start || minutes >= window.end) {
      return { style: { backgroundColor: "rgba(120, 120, 120, 0.12)" } };
    }
    return {};
  }

  function AppointmentEvent({ event }: { event: CalendarEvent }) {
    const appt = event.resource;
    const patientDetail = patientLookup.get(appt.patient.id);
    const phone = patientDetail?.phone || "";
    const address = buildShortAddress(patientDetail);
    const timeLabel = `${format(event.start, "HH:mm")}-${format(event.end, "HH:mm")}`;
    const secondaryParts = [
      appt.clinician ? `Clinician: ${appt.clinician}` : null,
      appt.location || appt.location_text ? `Location: ${appt.location || appt.location_text}` : null,
    ].filter(Boolean);
    return (
      <div style={{ display: "grid", gap: 4 }}>
        <div style={{ fontWeight: 600, lineHeight: 1.2 }}>
          {timeLabel} {event.title}
        </div>
        {calendarView === "day" && (phone || address) && (
          <div style={{ fontSize: 12, opacity: 0.9 }}>
            {[phone ? `Phone: ${phone}` : null, address ? `Address: ${address}` : null]
              .filter(Boolean)
              .join(" · ")}
          </div>
        )}
        {secondaryParts.length > 0 && (
          <div style={{ fontSize: 12, opacity: 0.9 }}>{secondaryParts.join(" · ")}</div>
        )}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <span
            className="badge"
            style={{
              color: "white",
              borderColor: "transparent",
              background: "rgba(255, 255, 255, 0.2)",
            }}
          >
            {statusLabels[appt.status]}
          </span>
          <span
            className="badge"
            style={{
              color: "white",
              borderColor: "transparent",
              background: "rgba(255, 255, 255, 0.2)",
            }}
          >
            {appt.location_type === "visit" ? "Visit" : "Clinic"}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="app-grid">
      <section className="card" style={{ display: "grid", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
          <div>
            <h2 style={{ marginTop: 0 }}>Appointments</h2>
            <p style={{ color: "var(--muted)", marginBottom: 0 }}>
              Plan your clinic and visit diary across day, week, and month views.
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button className="btn btn-primary" onClick={() => setShowNewModal(true)}>
              New appointment
            </button>
            <div style={{ display: "flex", gap: 6 }}>
              {([
                { id: "all", label: "All" },
                { id: "clinic", label: "Clinic" },
                { id: "visit", label: "Visits" },
              ] as const).map((item) => (
                <button
                  key={item.id}
                  className={
                    item.id === locationFilter ? "btn btn-primary" : "btn btn-secondary"
                  }
                  onClick={() => setLocationFilter(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
            {locationFilter === "visit" &&
              range &&
              ["day", "week", "agenda"].includes(range.view) && (
                <button className="btn btn-secondary" onClick={downloadRunSheet}>
                  Download run sheet
                </button>
              )}
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="label" style={{ margin: 0 }}>
                Jump to
              </span>
              <input
                className="input"
                type="date"
                value={range?.anchor ?? ""}
                onChange={(e) => jumpToDate(e.target.value)}
              />
            </label>
          </div>
        </div>

        {error && <div className="notice">{error}</div>}
        {notice && <div className="notice">{notice}</div>}

        <div className="card" style={{ margin: 0, padding: 16 }}>
          {loading && <div className="badge">Loading appointments…</div>}
          <DragAndDropCalendar
            localizer={localizer}
            events={calendarEvents}
            startAccessor="start"
            endAccessor="end"
            selectable
            resizable
            step={10}
            timeslots={1}
            onSelectSlot={handleSelectSlot}
            onSelectEvent={handleEventSelect}
            onEventDrop={handleEventDrop}
            onEventResize={handleEventResize}
            draggableAccessor={() => true}
            view={calendarView}
            date={currentDate}
            onView={setCalendarView}
            onNavigate={handleNavigate}
            onRangeChange={handleRangeChange}
            showNowIndicator
            min={minTime}
            max={maxTime}
            culture="en-GB"
            views={["day", "week", "month", "agenda"]}
            components={{ event: AppointmentEvent }}
            eventPropGetter={eventStyleGetter}
            dayPropGetter={dayPropGetter}
            slotPropGetter={slotPropGetter}
            style={{ height: "70vh" }}
          />
        </div>
        {!loading && appointments.length === 0 && (
          <div className="notice">No appointments in this range.</div>
        )}

        {showNewModal && (
          <div className="card" style={{ margin: 0 }}>
            <div className="stack">
              <div className="row">
                <div>
                  <h3 style={{ marginTop: 0 }}>New appointment</h3>
                  <p style={{ color: "var(--muted)" }}>
                    Choose a patient, date/time, and optional clinician details.
                  </p>
                </div>
                <button className="btn btn-secondary" onClick={() => setShowNewModal(false)}>
                  Close
                </button>
              </div>
              <form onSubmit={createAppointment} className="stack">
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">Search patient</label>
                  <input
                    className="input"
                    placeholder="Start typing a name"
                    value={patientQuery}
                    onChange={(e) => setPatientQuery(e.target.value)}
                  />
                </div>
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">Select patient</label>
                  <select
                    className="input"
                    value={selectedPatientId}
                    onChange={(e) => setSelectedPatientId(e.target.value)}
                  >
                    <option value="">Choose patient</option>
                    {filteredPatients.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.first_name} {p.last_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr" }}>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Start</label>
                    <input
                      className="input"
                      type="datetime-local"
                      value={startsAt}
                      onChange={(e) => setStartsAt(e.target.value)}
                    />
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">End</label>
                    <input
                      className="input"
                      type="datetime-local"
                      value={endsAt}
                      onChange={(e) => setEndsAt(e.target.value)}
                    />
                  </div>
                </div>
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">Clinician (optional)</label>
                  <select
                    className="input"
                    value={clinicianUserId}
                    onChange={(e) => setClinicianUserId(e.target.value)}
                  >
                    <option value="">Unassigned</option>
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.full_name || u.email} ({u.role})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">Appointment type</label>
                  <input
                    className="input"
                    value={appointmentType}
                    onChange={(e) => setAppointmentType(e.target.value)}
                    placeholder="Exam, cleaning, emergency"
                  />
                </div>
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">Location / room</label>
                  <input
                    className="input"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="Room 1"
                  />
                </div>
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">Location type</label>
                  <select
                    className="input"
                    value={locationType}
                    onChange={(e) => {
                      const next = e.target.value as AppointmentLocationType;
                      setLocationType(next);
                      if (next === "clinic") setLocationText("");
                    }}
                  >
                    <option value="clinic">Clinic</option>
                    <option value="visit">Visit</option>
                  </select>
                </div>
                {locationType === "visit" && (
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Visit address</label>
                    <textarea
                      className="input"
                      rows={3}
                      value={locationText}
                      onChange={(e) => setLocationText(e.target.value)}
                      placeholder="Full address for the home visit"
                    />
                  </div>
                )}
                <button className="btn btn-primary" disabled={saving}>
                  {saving ? "Saving..." : "Create appointment"}
                </button>
              </form>
            </div>
          </div>
        )}

        {selectedAppointment && (
          <div className="card" style={{ margin: 0 }}>
            <div className="stack">
              <div className="row">
                <div>
                  <h3 style={{ marginTop: 0 }}>Appointment details</h3>
                  <p style={{ color: "var(--muted)" }}>
                    {selectedAppointment.patient.first_name} {selectedAppointment.patient.last_name} ·{" "}
                    {new Date(selectedAppointment.starts_at).toLocaleString()}
                  </p>
                </div>
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    setSelectedAppointment(null);
                    setNotes([]);
                    setDetailPatient(null);
                  }}
                >
                  Close
                </button>
              </div>

              <div className="stack" style={{ gap: 6 }}>
                <div>
                  <strong>Status:</strong> {statusLabels[selectedAppointment.status]}
                </div>
                <div>
                  <strong>Clinician:</strong> {selectedAppointment.clinician || "Unassigned"}
                </div>
                <div>
                  <strong>Type:</strong> {selectedAppointment.appointment_type || "—"}
                </div>
                <div>
                  <strong>Location type:</strong> {selectedAppointment.location_type}
                </div>
                <div>
                  <strong>Location:</strong> {selectedAppointment.location_text || "—"}
                </div>
              </div>

              {loadingPatientDetail ? (
                <div className="badge">Loading patient alerts…</div>
              ) : detailPatient ? (
                <div className="card" style={{ margin: 0 }}>
                  <div className="stack" style={{ gap: 8 }}>
                    <div>
                      <strong>Patient alerts</strong>
                    </div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      {!detailPatient.allergies &&
                        !detailPatient.medical_alerts &&
                        !detailPatient.safeguarding_notes && <span className="badge">None</span>}
                      {detailPatient.allergies && (
                        <span className="badge" style={{ background: "#b13636", color: "white" }}>
                          Allergies
                        </span>
                      )}
                      {detailPatient.medical_alerts && (
                        <span className="badge" style={{ background: "#b07b24", color: "white" }}>
                          Medical alerts
                        </span>
                      )}
                      {detailPatient.safeguarding_notes && (
                        <span className="badge" style={{ background: "#b07b24", color: "white" }}>
                          Safeguarding
                        </span>
                      )}
                    </div>
                    {detailPatient.allergies && (
                      <div>
                        <div className="label">Allergies</div>
                        <div>{detailPatient.allergies}</div>
                      </div>
                    )}
                    {detailPatient.medical_alerts && (
                      <div>
                        <div className="label">Medical alerts</div>
                        <div>{detailPatient.medical_alerts}</div>
                      </div>
                    )}
                    {detailPatient.safeguarding_notes && (
                      <div>
                        <div className="label">Safeguarding</div>
                        <div>{detailPatient.safeguarding_notes}</div>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="notice">Unable to load patient alerts.</div>
              )}

              {detailPatient?.care_setting && detailPatient.care_setting !== "CLINIC" && (
                <div className="card" style={{ margin: 0 }}>
                  <div className="stack" style={{ gap: 8 }}>
                    <div>
                      <strong>Visit summary</strong>
                    </div>
                    <div>
                      <div className="label">Visit address</div>
                      <div>{detailPatient.visit_address_text || "—"}</div>
                    </div>
                    <div>
                      <div className="label">Access notes</div>
                      <div>{detailPatient.access_notes || "—"}</div>
                    </div>
                    <div>
                      <div className="label">Primary contact</div>
                      <div>
                        {detailPatient.primary_contact_name || "—"}{" "}
                        {detailPatient.primary_contact_relationship
                          ? `(${detailPatient.primary_contact_relationship})`
                          : ""}
                        {detailPatient.primary_contact_phone
                          ? ` · ${detailPatient.primary_contact_phone}`
                          : ""}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div className="stack" style={{ gap: 8 }}>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button
                    className="btn btn-secondary"
                    onClick={() => updateAppointmentStatus(selectedAppointment.id, "arrived")}
                  >
                    Arrived
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => updateAppointmentStatus(selectedAppointment.id, "in_progress")}
                  >
                    In progress
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => updateAppointmentStatus(selectedAppointment.id, "completed")}
                  >
                    Completed
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => updateAppointmentStatus(selectedAppointment.id, "cancelled")}
                  >
                    Cancel
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => updateAppointmentStatus(selectedAppointment.id, "no_show")}
                  >
                    No show
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => createEstimateForAppointment(selectedAppointment)}
                  >
                    Create estimate
                  </button>
                  <Link
                    className="btn btn-secondary"
                    href={`/patients/${selectedAppointment.patient.id}`}
                  >
                    Patient
                  </Link>
                </div>
              </div>

              <form onSubmit={saveAppointmentDetails} className="stack">
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">Location type</label>
                  <select
                    className="input"
                    value={detailLocationType}
                    onChange={(e) => {
                      const next = e.target.value as AppointmentLocationType;
                      setDetailLocationType(next);
                      if (next === "clinic") setDetailLocationText("");
                    }}
                  >
                    <option value="clinic">Clinic</option>
                    <option value="visit">Visit</option>
                  </select>
                </div>
                {detailLocationType === "visit" && (
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Visit address</label>
                    <textarea
                      className="input"
                      rows={3}
                      value={detailLocationText}
                      onChange={(e) => setDetailLocationText(e.target.value)}
                    />
                  </div>
                )}
                <button className="btn btn-secondary" disabled={savingDetail}>
                  {savingDetail ? "Saving..." : "Save details"}
                </button>
              </form>

              <form onSubmit={addAppointmentNote} className="stack">
                <label className="label">Quick note</label>
                <textarea
                  className="input"
                  rows={3}
                  value={noteBody}
                  onChange={(e) => setNoteBody(e.target.value)}
                  placeholder="Add a brief clinical note"
                />
                <button className="btn btn-primary" disabled={saving}>
                  {saving ? "Saving..." : "Add note"}
                </button>
              </form>

              {loadingNotes ? (
                <div className="badge">Loading notes…</div>
              ) : (
                <div className="stack">
                  {notes.length === 0 ? (
                    <div className="notice">No notes yet.</div>
                  ) : (
                    notes.map((note) => (
                      <div key={note.id} className="card" style={{ margin: 0 }}>
                        <div style={{ fontSize: 12, color: "var(--muted)" }}>
                          {note.created_by?.email || "—"} ·{" "}
                          {new Date(note.created_at).toLocaleString()}
                        </div>
                        <div style={{ marginTop: 6 }}>{note.body}</div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
