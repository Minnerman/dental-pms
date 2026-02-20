"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Calendar,
  dateFnsLocalizer,
  type SlotInfo,
  type View,
} from "react-big-calendar";
import withDragAndDrop from "react-big-calendar/lib/addons/dragAndDrop";
import {
  addDays,
  endOfMonth,
  endOfWeek,
  format,
  parse,
  startOfMonth,
  startOfWeek,
  getDay,
} from "date-fns";
import { enGB } from "date-fns/locale";
import { apiFetch, clearToken } from "@/lib/auth";
import StatusIcon from "@/components/ui/StatusIcon";

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
  allergies?: string | null;
  medical_alerts?: string | null;
  alerts_financial?: string | null;
  alerts_access?: string | null;
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
  created_at: string;
  updated_by?: Actor | null;
  updated_at: string;
  deleted_at?: string | null;
  cancel_reason?: string | null;
  cancelled_at?: string | null;
  cancelled_by_user_id?: number | null;
};

type CalendarEvent = {
  id: string;
  title: string;
  start: Date;
  end: Date;
  resourceId?: string;
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
  allergies?: string | null;
  medical_alerts?: string | null;
  alerts_financial?: string | null;
  alerts_access?: string | null;
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
  alerts_financial?: string | null;
  alerts_access?: string | null;
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
type DiaryGrouping = "chair" | "clinician";

type DiaryLane = {
  key: string;
  label: string;
  count: number;
  grouping: DiaryGrouping;
  clinicianUserId?: number;
  clinicianLabel?: string;
  locationType?: AppointmentLocationType;
  location?: string | null;
  locationText?: string | null;
};

type CalendarRange = {
  start: string;
  end: string;
  view: View;
  anchor: string;
};

type ConflictWarning = {
  message: string;
  items: Array<{
    id?: number;
    start: Date;
    end: Date;
    patientName: string;
    locationLabel?: string;
  }>;
  extraCount: number;
  anchorDate?: Date;
};

type ConflictApiItem = {
  id?: number;
  starts_at: string;
  ends_at: string;
  patient_name?: string;
  location?: string | null;
  location_type?: AppointmentLocationType | null;
};

type ConflictApiResponse = {
  detail?: string;
  message?: string;
  conflicts?: ConflictApiItem[];
};

type AppointmentAuditEntry = {
  id: number;
  created_at: string;
  actor_email?: string | null;
  actor?: { email: string };
  action: string;
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

const daySheetStatusLabels: Record<AppointmentStatus, string> = {
  booked: "Booked",
  arrived: "Arrived",
  in_progress: "In Tx",
  completed: "Complete",
  cancelled: "Cancelled",
  no_show: "DNA",
};

const DIARY_TIME_STEP_MINUTES = 10;

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
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function toLocalDateTimeInput(date: Date) {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
}

function parseLocalDateTime(value: string) {
  const match =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(value.trim());
  if (!match) return null;
  const [, year, month, day, hour, minute, second] = match;
  const parsed = new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    Number(second || 0)
  );
  if (
    parsed.getFullYear() !== Number(year) ||
    parsed.getMonth() !== Number(month) - 1 ||
    parsed.getDate() !== Number(day) ||
    parsed.getHours() !== Number(hour) ||
    parsed.getMinutes() !== Number(minute) ||
    parsed.getSeconds() !== Number(second || 0)
  ) {
    return null;
  }
  return parsed;
}

function parseStartParam(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const hasTimezone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(trimmed);
  const parsed = hasTimezone ? new Date(trimmed) : parseLocalDateTime(trimmed);
  if (!parsed || Number.isNaN(parsed.getTime())) return null;
  return parsed;
}

function parseDateParam(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (!match) return null;
  const [, year, month, day] = match;
  const parsed = new Date(Number(year), Number(month) - 1, Number(day));
  if (
    parsed.getFullYear() !== Number(year) ||
    parsed.getMonth() !== Number(month) - 1 ||
    parsed.getDate() !== Number(day)
  ) {
    return null;
  }
  return parsed;
}

function getRangeForView(date: Date, view: View) {
  if (view === "week") {
    const start = startOfWeek(date, { locale: enGB });
    const end = endOfWeek(date, { locale: enGB });
    return { start, end };
  }
  if (view === "month") {
    return { start: startOfMonth(date), end: endOfMonth(date) };
  }
  return { start: date, end: date };
}

function overlaps(startA: Date, endA: Date, startB: Date, endB: Date) {
  return startA < endB && endA > startB;
}

function snapDateToIncrement(value: Date, incrementMinutes: number) {
  const incrementMs = incrementMinutes * 60_000;
  const snappedMs = Math.round(value.getTime() / incrementMs) * incrementMs;
  return new Date(snappedMs);
}

function snapRangeToIncrement(start: Date, end: Date, incrementMinutes: number) {
  const snappedStart = snapDateToIncrement(start, incrementMinutes);
  const snappedEndRaw = snapDateToIncrement(end, incrementMinutes);
  const minEnd = new Date(snappedStart.getTime() + incrementMinutes * 60_000);
  const snappedEnd = snappedEndRaw <= snappedStart ? minEnd : snappedEndRaw;
  return { start: snappedStart, end: snappedEnd };
}

function formatTimeRange(start: string, end: string) {
  const startDate = new Date(start);
  const endDate = new Date(end);
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return "—";
  const startLabel = startDate.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });
  const endLabel = endDate.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${startLabel}–${endLabel}`;
}

function formatConflictTime(start: Date, end: Date) {
  const startLabel = start.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });
  const endLabel = end.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${startLabel}–${endLabel}`;
}

function formatMetaTimestamp(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
}

function parseConflictResponse(raw: string): ConflictApiResponse | null {
  if (!raw) return null;
  try {
    const data = JSON.parse(raw) as ConflictApiResponse;
    if (!data || typeof data !== "object") return null;
    return data;
  } catch {
    return null;
  }
}

function toConflictItems(conflicts: ConflictApiItem[]) {
  return conflicts
    .map((conflict) => {
      const start = new Date(conflict.starts_at);
      const end = new Date(conflict.ends_at);
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null;
      const patientName = (conflict.patient_name || "Another patient").trim();
      const locationLabel =
        conflict.location_type === "visit"
          ? conflict.location || "Visit"
          : conflict.location || "Clinic";
      return {
        id: conflict.id,
        start,
        end,
        patientName,
        locationLabel,
      };
    })
    .filter(Boolean) as Array<{
    id?: number;
    start: Date;
    end: Date;
    patientName: string;
    locationLabel?: string;
  }>;
}

function toAppointmentCode(raw: string | null | undefined) {
  if (!raw) return "GEN";
  const normalized = raw.toLowerCase();
  const mapping = [
    { match: ["exam", "examination"], code: "EX" },
    { match: ["emergency", "emg"], code: "EM" },
    { match: ["filling", "fill"], code: "FIL" },
    { match: ["root canal", "rct"], code: "RCT" },
    { match: ["extraction", "extract"], code: "EXT" },
    { match: ["hygiene", "scale", "polish"], code: "HY" },
    { match: ["implant consult", "implant"], code: "IC" },
    { match: ["ortho", "orthodontic"], code: "OR" },
    { match: ["denture impression", "denture"], code: "DI" },
    { match: ["fit", "fitting"], code: "FIT" },
    { match: ["review"], code: "RV" },
  ];
  const found = mapping.find((item) =>
    item.match.some((term) => normalized.includes(term))
  );
  return found ? found.code : raw.trim().slice(0, 3).toUpperCase();
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

function buildPatientAlertFlags(
  patient?: PatientSummary | Patient | null
): Array<{ key: string; label: string; short: string; value?: string | null }> {
  if (!patient) return [];
  const flags = [
    { key: "allergy", label: "Allergy", short: "A", value: patient.allergies },
    { key: "medical", label: "Medical", short: "M", value: patient.medical_alerts },
    { key: "financial", label: "Financial", short: "F", value: patient.alerts_financial },
    { key: "access", label: "Access", short: "AC", value: patient.alerts_access },
  ];
  return flags.filter((flag) => (flag.value || "").trim().length > 0);
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
  const patientSearchRef = useRef<HTMLInputElement | null>(null);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [schedule, setSchedule] = useState<PracticeSchedule | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [patientSearchResults, setPatientSearchResults] = useState<Patient[]>([]);
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
  const [durationMinutes, setDurationMinutes] = useState<number | null>(30);
  const bookIntent = searchParams?.get("book") === "1";
  const [showNewModal, setShowNewModal] = useState(bookIntent);
  const [locationFilter, setLocationFilter] = useState<LocationFilter>("all");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [conflictChecking, setConflictChecking] = useState(false);
  const conflictCheckKeyRef = useRef<string>("");
  const conflictCheckTimerRef = useRef<number | null>(null);
  const conflictRequestIdRef = useRef(0);
  const [recallContext, setRecallContext] = useState<{
    recallId: string;
    patientId: string;
  } | null>(null);
  const [showRecallPrompt, setShowRecallPrompt] = useState(false);
  const [recallPromptSaving, setRecallPromptSaving] = useState(false);
  const [recallAppointmentId, setRecallAppointmentId] = useState<number | null>(null);
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
  const [viewMode, setViewMode] = useState<"day_sheet" | "calendar">("day_sheet");
  const [diaryGrouping, setDiaryGrouping] = useState<DiaryGrouping>("chair");
  const [diaryChairFilter, setDiaryChairFilter] = useState("all");
  const [diaryClinicianFilter, setDiaryClinicianFilter] = useState("all");
  const [highlightedAppointmentId, setHighlightedAppointmentId] = useState<string | null>(
    null
  );
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    appointment: Appointment;
  } | null>(null);
  const [clipboard, setClipboard] = useState<{
    mode: "cut" | "copy";
    appointment: Appointment;
  } | null>(null);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelTarget, setCancelTarget] = useState<Appointment | null>(null);
  const [selectedAppointmentId, setSelectedAppointmentId] = useState<number | null>(
    null
  );
  const [bookingSubmitError, setBookingSubmitError] = useState<string | null>(null);
  const [lastSelectedSlot, setLastSelectedSlot] = useState<Date | null>(null);
  const [noteCache, setNoteCache] = useState<Record<number, string[]>>({});
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    content: string;
  } | null>(null);
  const [isEditingAppointment, setIsEditingAppointment] = useState(false);
  const [editStartsAt, setEditStartsAt] = useState("");
  const [editEndsAt, setEditEndsAt] = useState("");
  const [editDuration, setEditDuration] = useState("30");
  const [editAppointmentType, setEditAppointmentType] = useState("");
  const [editClinicianUserId, setEditClinicianUserId] = useState("");
  const [editLocation, setEditLocation] = useState("");
  const [editLocationType, setEditLocationType] =
    useState<AppointmentLocationType>("clinic");
  const [editLocationText, setEditLocationText] = useState("");
  const [editStatus, setEditStatus] = useState<AppointmentStatus>("booked");
  const [editCancelReason, setEditCancelReason] = useState("");
  const [editNoteBody, setEditNoteBody] = useState("");
  const [conflictWarning, setConflictWarning] = useState<ConflictWarning | null>(null);
  const [editConflictWarning, setEditConflictWarning] =
    useState<ConflictWarning | null>(null);
  const [rescheduleSavingId, setRescheduleSavingId] = useState<number | null>(null);
  const [auditOpen, setAuditOpen] = useState(false);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [auditEntries, setAuditEntries] = useState<AppointmentAuditEntry[]>([]);
  // Keyboard bindings are intentionally constrained for predictable diary shortcuts.
  useEffect(() => {
    function isEditableTarget(target: EventTarget | null) {
      if (!(target instanceof HTMLElement)) return false;
      const tag = target.tagName;
      return (
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        tag === "SELECT" ||
        target.isContentEditable
      );
    }

    function focusGlobalSearch() {
      const input = document.querySelector(
        'input[placeholder="Search patients..."]'
      ) as HTMLInputElement | null;
      if (input) {
        input.focus();
        input.select();
        return true;
      }
      return false;
    }

    function handleShortcut(event: KeyboardEvent) {
      if (event.defaultPrevented) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === "escape" && showNewModal) {
        event.preventDefault();
        setShowNewModal(false);
        return;
      }
      if (isEditableTarget(event.target)) return;
      if (key === "n") {
        event.preventDefault();
        setShowNewModal(true);
        return;
      }
      if (key === "/") {
        event.preventDefault();
        if (showNewModal && patientSearchRef.current) {
          patientSearchRef.current.focus();
          patientSearchRef.current.select();
          return;
        }
        focusGlobalSearch();
        return;
      }
    }

    window.addEventListener("keydown", handleShortcut);
    return () => {
      window.removeEventListener("keydown", handleShortcut);
    };
  }, [showNewModal]);

  useEffect(() => {
    if (!showNewModal) return;
    const focusTimer = window.setTimeout(() => {
      if (patientSearchRef.current) {
        patientSearchRef.current.focus();
        patientSearchRef.current.select();
      }
    }, 0);
    return () => window.clearTimeout(focusTimer);
  }, [showNewModal]);
  const didAutoOpen = useRef(false);
  const didApplyDate = useRef<string | null>(null);
  const [modalClinicianUserId, setModalClinicianUserId] = useState<string | null>(null);
  const [modalLocationType, setModalLocationType] =
    useState<AppointmentLocationType | null>(null);
  const [modalLocationText, setModalLocationText] = useState<string | null>(null);
  const [modalLocation, setModalLocation] = useState<string | null>(null);

  const activeClinicianUserId = showNewModal
    ? modalClinicianUserId ?? clinicianUserId
    : clinicianUserId;
  const activeLocationType = showNewModal
    ? modalLocationType ?? locationType
    : locationType;
  const activeLocationText = showNewModal
    ? modalLocationText ?? locationText
    : locationText;
  const activeLocation = showNewModal ? modalLocation ?? location : location;
  const loadAppointmentsRequestId = useRef(0);
  const loadPatientsRequestId = useRef(0);

  const filteredPatients = useMemo(() => {
    const merged = new Map<number, Patient>();
    for (const patient of patients) merged.set(patient.id, patient);
    for (const patient of patientSearchResults) merged.set(patient.id, patient);
    const mergedPatients = Array.from(merged.values());
    const q = patientQuery.toLowerCase().trim();
    if (!q) return mergedPatients;
    return mergedPatients.filter((p) =>
      `${p.first_name} ${p.last_name}`.toLowerCase().includes(q)
    );
  }, [patientQuery, patients, patientSearchResults]);

  const patientLookup = useMemo(() => {
    return new Map(patients.map((patient) => [patient.id, patient]));
  }, [patients]);

  const clinicianLookup = useMemo(() => {
    return new Map(
      users.map((user) => [
        user.id,
        user.full_name || user.email || `Clinician ${user.id}`,
      ])
    );
  }, [users]);

  const getClinicianLabel = useCallback(
    (clinicianId: number | null | undefined) => {
      if (!clinicianId) return "";
      return clinicianLookup.get(clinicianId) || `Clinician ${clinicianId}`;
    },
    [clinicianLookup]
  );

  const getChairLane = useCallback((appt: Appointment) => {
    const room = (appt.location || "").trim();
    if (room) {
      return {
        key: `chair:clinic:${room.toLowerCase()}`,
        label: room,
        locationType: "clinic" as AppointmentLocationType,
        location: room,
        locationText: null,
      };
    }
    const locationText = (appt.location_text || "").trim();
    if (appt.location_type === "visit") {
      if (locationText) {
        return {
          key: `chair:visit:${locationText.toLowerCase()}`,
          label: locationText,
          locationType: "visit" as AppointmentLocationType,
          location: null,
          locationText,
        };
      }
      return {
        key: "chair:visit:unassigned",
        label: "Visit",
        locationType: "visit" as AppointmentLocationType,
        location: null,
        locationText: "Visit",
      };
    }
    return {
      key: "chair:clinic:unassigned",
      label: "Unassigned",
      locationType: "clinic" as AppointmentLocationType,
      location: null,
      locationText: null,
    };
  }, []);

  const getChairLabel = useCallback((appt: Appointment) => {
    return getChairLane(appt).label;
  }, [getChairLane]);

  const getClinicianLane = useCallback(
    (appt: Appointment) => {
      if (appt.clinician_user_id) {
        const label = getClinicianLabel(appt.clinician_user_id);
        return {
          key: `clinician:user:${appt.clinician_user_id}`,
          label,
          clinicianUserId: appt.clinician_user_id,
          clinicianLabel: label,
        };
      }
      const raw = (appt.clinician || "").trim();
      if (raw) {
        return {
          key: `clinician:text:${raw.toLowerCase()}`,
          label: raw,
          clinicianUserId: undefined,
          clinicianLabel: raw,
        };
      }
      return {
        key: "clinician:unassigned",
        label: "Unassigned",
        clinicianUserId: undefined,
        clinicianLabel: undefined,
      };
    },
    [getClinicianLabel]
  );

  const getClinicianFilterKey = useCallback(
    (appt: Appointment) => {
      if (appt.clinician_user_id) {
        return `user:${appt.clinician_user_id}`;
      }
      const raw = (appt.clinician || "").trim();
      if (raw) return `text:${raw.toLowerCase()}`;
      return "unassigned";
    },
    []
  );

  const getClinicianDisplayLabel = useCallback(
    (appt: Appointment) => {
      return getClinicianLane(appt).label;
    },
    [getClinicianLane]
  );

  const diaryChairOptions = useMemo(() => {
    const labels = Array.from(new Set(appointments.map((appt) => getChairLabel(appt))));
    return labels.sort((a, b) => a.localeCompare(b));
  }, [appointments, getChairLabel]);

  const diaryClinicianOptions = useMemo(() => {
    const entries = new Map<string, string>();
    for (const appt of appointments) {
      const key = getClinicianFilterKey(appt);
      if (!entries.has(key)) {
        entries.set(key, getClinicianDisplayLabel(appt));
      }
    }
    return Array.from(entries.entries())
      .map(([key, label]) => ({ key, label }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [appointments, getClinicianDisplayLabel, getClinicianFilterKey]);

  useEffect(() => {
    if (diaryGrouping === "chair") {
      if (diaryChairFilter !== "all" && !diaryChairOptions.includes(diaryChairFilter)) {
        setDiaryChairFilter("all");
      }
      return;
    }
    if (
      diaryClinicianFilter !== "all" &&
      !diaryClinicianOptions.some((item) => item.key === diaryClinicianFilter)
    ) {
      setDiaryClinicianFilter("all");
    }
  }, [
    diaryGrouping,
    diaryChairFilter,
    diaryChairOptions,
    diaryClinicianFilter,
    diaryClinicianOptions,
  ]);

  const diaryFilteredAppointments = useMemo(() => {
    return appointments.filter((appt) => {
      if (diaryGrouping === "chair") {
        if (diaryChairFilter !== "all" && getChairLabel(appt) !== diaryChairFilter) {
          return false;
        }
      } else if (diaryClinicianFilter !== "all") {
        if (getClinicianFilterKey(appt) !== diaryClinicianFilter) {
          return false;
        }
      }
      return true;
    });
  }, [
    appointments,
    diaryGrouping,
    diaryChairFilter,
    diaryClinicianFilter,
    getChairLabel,
    getClinicianFilterKey,
  ]);

  const diaryLanes = useMemo<DiaryLane[]>(() => {
    const lanes = new Map<string, DiaryLane>();
    for (const appt of diaryFilteredAppointments) {
      if (diaryGrouping === "chair") {
        const chairLane = getChairLane(appt);
        const existing = lanes.get(chairLane.key);
        if (existing) {
          existing.count += 1;
        } else {
          lanes.set(chairLane.key, {
            key: chairLane.key,
            label: chairLane.label,
            count: 1,
            grouping: "chair",
            locationType: chairLane.locationType,
            location: chairLane.location,
            locationText: chairLane.locationText,
          });
        }
      } else {
        const clinicianLane = getClinicianLane(appt);
        const existing = lanes.get(clinicianLane.key);
        if (existing) {
          existing.count += 1;
        } else {
          lanes.set(clinicianLane.key, {
            key: clinicianLane.key,
            label: clinicianLane.label,
            count: 1,
            grouping: "clinician",
            clinicianUserId: clinicianLane.clinicianUserId,
            clinicianLabel: clinicianLane.clinicianLabel,
          });
        }
      }
    }
    const rows = Array.from(lanes.values()).sort((a, b) =>
      a.label.localeCompare(b.label)
    );
    if (rows.length > 0) return rows;
    if (diaryGrouping === "chair") {
      return [
        {
          key: "chair:clinic:unassigned",
          label: "Unassigned",
          count: 0,
          grouping: "chair",
          locationType: "clinic",
          location: null,
          locationText: null,
        },
      ];
    }
    return [
      {
        key: "clinician:unassigned",
        label: "Unassigned",
        count: 0,
        grouping: "clinician",
      },
    ];
  }, [diaryFilteredAppointments, diaryGrouping, getChairLane, getClinicianLane]);

  const diaryColumns = diaryLanes;

  const diaryLaneByKey = useMemo(() => {
    return new Map(diaryLanes.map((lane) => [lane.key, lane]));
  }, [diaryLanes]);

  const calendarResources = useMemo(
    () => diaryLanes.map((lane) => ({ id: lane.key, title: lane.label })),
    [diaryLanes]
  );

  const calendarEvents = useMemo<CalendarEvent[]>(
    () =>
      diaryFilteredAppointments.map((appt) => ({
        id: String(appt.id),
        title: `${appt.patient.first_name} ${appt.patient.last_name}`,
        start: new Date(appt.starts_at),
        end: new Date(appt.ends_at),
        resourceId:
          diaryGrouping === "chair"
            ? getChairLane(appt).key
            : getClinicianLane(appt).key,
        resource: appt,
      })),
    [diaryFilteredAppointments, diaryGrouping, getChairLane, getClinicianLane]
  );

  const selectedCalendarEvent = useMemo<CalendarEvent | undefined>(() => {
    if (selectedAppointmentId === null) return undefined;
    return calendarEvents.find(
      (event) => event.resource.id === selectedAppointmentId
    );
  }, [calendarEvents, selectedAppointmentId]);

  const sortedCalendarAppointmentIds = useMemo(() => {
    return [...diaryFilteredAppointments]
      .sort((a, b) => {
        const startDiff =
          new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime();
        if (startDiff !== 0) return startDiff;
        const endDiff = new Date(a.ends_at).getTime() - new Date(b.ends_at).getTime();
        if (endDiff !== 0) return endDiff;
        return a.id - b.id;
      })
      .map((item) => item.id);
  }, [diaryFilteredAppointments]);

  const isRescheduleLocked = rescheduleSavingId !== null;

  const highlightScrollTime = useMemo(() => {
    if (!highlightedAppointmentId) return undefined;
    const appt = diaryFilteredAppointments.find(
      (item) => String(item.id) === String(highlightedAppointmentId)
    );
    return appt ? new Date(appt.starts_at) : undefined;
  }, [diaryFilteredAppointments, highlightedAppointmentId]);

  const daySheetAppointments = useMemo(() => {
    const key = toDateKey(currentDate);
    return appointments
      .filter((appt) => toDateKey(new Date(appt.starts_at)) === key)
      .sort(
        (a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()
      );
  }, [appointments, currentDate]);

  const getLaneKeyForAppointment = useCallback(
    (appt: Appointment) =>
      diaryGrouping === "chair"
        ? getChairLane(appt).key
        : getClinicianLane(appt).key,
    [diaryGrouping, getChairLane, getClinicianLane]
  );

  const hasLaneOverlap = useCallback(
    ({
      appointmentId,
      laneKey,
      start,
      end,
    }: {
      appointmentId: number;
      laneKey: string;
      start: Date;
      end: Date;
    }) => {
      return appointments.some((item) => {
        if (item.id === appointmentId) return false;
        if (item.status === "cancelled" || item.status === "no_show") return false;
        if (getLaneKeyForAppointment(item) !== laneKey) return false;
        return overlaps(
          start,
          end,
          new Date(item.starts_at),
          new Date(item.ends_at)
        );
      });
    },
    [appointments, getLaneKeyForAppointment]
  );

  const resolveLanePatch = useCallback(
    (laneKey: string) => {
      const lane = diaryLaneByKey.get(laneKey);
      if (!lane) {
        return {
          error: "Unable to resolve the destination lane.",
          lanePatch: null,
        };
      }
      if (diaryGrouping === "chair") {
        if (lane.key.endsWith(":unassigned")) {
          return {
            error:
              "Move to the unassigned lane is not supported from drag/drop. Use the detail panel.",
            lanePatch: null,
          };
        }
        if (lane.locationType === "visit") {
          const visitLabel = (lane.locationText || lane.label || "").trim() || "Visit";
          return {
            error: null,
            lanePatch: {
              locationType: "visit" as AppointmentLocationType,
              location: null,
              locationText: visitLabel,
              isDomiciliary: true,
              visitAddress: visitLabel,
            },
          };
        }
        const locationLabel = (lane.location || lane.label || "").trim();
        if (!locationLabel) {
          return {
            error: "Destination chair is missing a location label.",
            lanePatch: null,
          };
        }
        return {
          error: null,
          lanePatch: {
            locationType: "clinic" as AppointmentLocationType,
            location: locationLabel,
            locationText: null,
            isDomiciliary: false,
            visitAddress: null,
          },
        };
      }
      if (!lane.clinicianUserId) {
        return {
          error:
            "Move to free-text or unassigned clinician lanes is not supported from drag/drop.",
          lanePatch: null,
        };
      }
      return {
        error: null,
        lanePatch: {
          clinicianUserId: lane.clinicianUserId,
          clinicianLabel: lane.clinicianLabel || lane.label,
        },
      };
    },
    [diaryGrouping, diaryLaneByKey]
  );

  const applyLanePatch = useCallback(
    (
      appt: Appointment,
      lanePatch:
        | {
            clinicianUserId?: number;
            clinicianLabel?: string | null;
            locationType?: AppointmentLocationType;
            location?: string | null;
            locationText?: string | null;
            isDomiciliary?: boolean;
            visitAddress?: string | null;
          }
        | null
        | undefined
    ) => {
      if (!lanePatch) return appt;
      const next = { ...appt };
      if (lanePatch.clinicianUserId) {
        next.clinician_user_id = lanePatch.clinicianUserId;
      }
      if (lanePatch.clinicianLabel) {
        next.clinician = lanePatch.clinicianLabel;
      }
      if (lanePatch.locationType) {
        next.location_type = lanePatch.locationType;
      }
      if ("location" in lanePatch) {
        next.location = lanePatch.location ?? null;
      }
      if ("locationText" in lanePatch) {
        next.location_text = lanePatch.locationText ?? null;
      }
      if (lanePatch.isDomiciliary !== undefined) {
        next.is_domiciliary = lanePatch.isDomiciliary;
      }
      if ("visitAddress" in lanePatch) {
        next.visit_address = lanePatch.visitAddress ?? null;
      }
      return next;
    },
    []
  );

  function selectRelativeAppointment(direction: 1 | -1) {
    if (sortedCalendarAppointmentIds.length === 0) return;
    if (selectedAppointmentId === null) {
      setSelectedAppointmentId(
        direction > 0
          ? sortedCalendarAppointmentIds[0]
          : sortedCalendarAppointmentIds[sortedCalendarAppointmentIds.length - 1]
      );
      return;
    }
    const index = sortedCalendarAppointmentIds.indexOf(selectedAppointmentId);
    if (index === -1) {
      setSelectedAppointmentId(sortedCalendarAppointmentIds[0]);
      return;
    }
    const nextIndex = Math.min(
      sortedCalendarAppointmentIds.length - 1,
      Math.max(0, index + direction)
    );
    setSelectedAppointmentId(sortedCalendarAppointmentIds[nextIndex]);
  }

  const buildConflictWarning = useCallback(
    (
      conflicts: Array<{
        id?: number;
        start: Date;
        end: Date;
        patientName: string;
        locationLabel?: string;
      }>,
      clinicianId: number | null | undefined
    ): ConflictWarning | null => {
      if (conflicts.length === 0) return null;
      const label = getClinicianLabel(clinicianId);
      const message = `Warning: overlaps with ${conflicts.length} existing appointment${
        conflicts.length === 1 ? "" : "s"
      }${label ? ` for ${label}` : ""}.`;
      const items = conflicts.slice(0, 5);
      const extraCount = Math.max(0, conflicts.length - items.length);
      return { message, items, extraCount, anchorDate: conflicts[0]?.start };
    },
    [getClinicianLabel]
  );

  const findConflicts = useCallback(
    ({
      clinicianId,
      start,
      end,
      excludeId,
    }: {
      clinicianId: number | null;
      start: Date;
      end: Date;
      excludeId?: number;
    }) => {
      if (!clinicianId) return [];
      return appointments
        .filter((appt) => appt.clinician_user_id === clinicianId)
        .filter(
          (appt) => appt.status !== "cancelled" && appt.status !== "no_show"
        )
        .filter((appt) => (excludeId ? appt.id !== excludeId : true))
        .map((appt) => {
          const startDate = new Date(appt.starts_at);
          const endDate = new Date(appt.ends_at);
          const locationLabel =
            appt.location_type === "visit"
              ? appt.location_text || "Visit"
              : appt.location || "Clinic";
          return {
            id: appt.id,
            start: startDate,
            end: endDate,
            patientName: `${appt.patient.first_name} ${appt.patient.last_name}`.trim(),
            locationLabel,
          };
        })
        .filter(
          (appt) =>
            !Number.isNaN(appt.start.getTime()) &&
            !Number.isNaN(appt.end.getTime()) &&
            overlaps(start, end, appt.start, appt.end)
        )
        .sort((a, b) => a.start.getTime() - b.start.getTime());
    },
    [appointments]
  );

  useEffect(() => {
    const stored = localStorage.getItem("dental_pms_appointments_view");
    if (stored === "calendar" || stored === "day_sheet") {
      setViewMode(stored);
    } else {
      setViewMode("day_sheet");
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("dental_pms_appointments_view", viewMode);
  }, [viewMode]);

  useEffect(() => {
    if (didAutoOpen.current) return;
    if (!searchParams || searchParams.get("book") !== "1") return;
    didAutoOpen.current = true;
    const startParam = searchParams.get("start");
    if (startParam) {
      const parsedStart = parseStartParam(startParam);
      if (parsedStart) {
        setStartsAt(toLocalDateTimeInput(parsedStart));
        const durationParam = searchParams.get("duration");
        const durationMinutes = durationParam ? Number(durationParam) : Number.NaN;
        if (Number.isFinite(durationMinutes) && durationMinutes > 0) {
          const cappedMinutes = Math.min(durationMinutes, 24 * 60);
          const endDate = new Date(parsedStart);
          endDate.setMinutes(endDate.getMinutes() + cappedMinutes);
          setEndsAt(toLocalDateTimeInput(endDate));
          if ([10, 15, 20, 30, 45, 60, 90].includes(cappedMinutes)) {
            setDurationMinutes(cappedMinutes);
          } else {
            setDurationMinutes(null);
          }
        }
      }
    }
    const patientIdParam = searchParams.get("patientId");
    if (patientIdParam && /^\d+$/.test(patientIdParam)) {
      setSelectedPatientId(patientIdParam);
    }
    const reasonParam = searchParams.get("reason");
    if (reasonParam) {
      setAppointmentType(reasonParam);
    }
    const recallIdParam = searchParams.get("recallId");
    if (patientIdParam && recallIdParam && /^\d+$/.test(recallIdParam)) {
      setRecallContext({ recallId: recallIdParam, patientId: patientIdParam });
    } else {
      setRecallContext(null);
    }
    const clinicianIdParam = searchParams.get("clinicianId");
    if (clinicianIdParam && /^\d+$/.test(clinicianIdParam)) {
      setClinicianUserId(clinicianIdParam);
      setModalClinicianUserId(clinicianIdParam);
    }
    setShowNewModal(true);
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.delete("book");
    nextParams.delete("reason");
    nextParams.delete("recallId");
    const nextQuery = nextParams.toString();
    router.replace(nextQuery ? `/appointments?${nextQuery}` : "/appointments", {
      scroll: false,
    });
  }, [router, searchParams]);

  useEffect(() => {
    if (!showNewModal) {
      if (conflictCheckTimerRef.current) {
        window.clearTimeout(conflictCheckTimerRef.current);
        conflictCheckTimerRef.current = null;
      }
      conflictRequestIdRef.current += 1;
      setConflictWarning(null);
      setConflictChecking(false);
      return;
    }
    if (!startsAt || !endsAt || !activeClinicianUserId) {
      if (conflictCheckTimerRef.current) {
        window.clearTimeout(conflictCheckTimerRef.current);
        conflictCheckTimerRef.current = null;
      }
      conflictRequestIdRef.current += 1;
      setConflictWarning(null);
      setConflictChecking(false);
      return;
    }
    const startDate = new Date(startsAt);
    const endDate = new Date(endsAt);
    if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
      if (conflictCheckTimerRef.current) {
        window.clearTimeout(conflictCheckTimerRef.current);
        conflictCheckTimerRef.current = null;
      }
      conflictRequestIdRef.current += 1;
      setConflictWarning(null);
      setConflictChecking(false);
      return;
    }
    if (endDate <= startDate) {
      if (conflictCheckTimerRef.current) {
        window.clearTimeout(conflictCheckTimerRef.current);
        conflictCheckTimerRef.current = null;
      }
      conflictRequestIdRef.current += 1;
      setConflictWarning(null);
      setConflictChecking(false);
      return;
    }
    const clinicianId = Number(activeClinicianUserId);
    if (!Number.isFinite(clinicianId)) {
      if (conflictCheckTimerRef.current) {
        window.clearTimeout(conflictCheckTimerRef.current);
        conflictCheckTimerRef.current = null;
      }
      conflictRequestIdRef.current += 1;
      setConflictWarning(null);
      setConflictChecking(false);
      return;
    }
    const conflictKey = [
      startsAt,
      endsAt,
      activeClinicianUserId,
      activeLocationType,
      activeLocation,
    ].join("|");
    conflictCheckKeyRef.current = conflictKey;
    conflictRequestIdRef.current += 1;
    const requestId = conflictRequestIdRef.current;
    setConflictChecking(true);
    if (conflictCheckTimerRef.current) {
      window.clearTimeout(conflictCheckTimerRef.current);
    }
    conflictCheckTimerRef.current = window.setTimeout(() => {
      const conflicts = findConflicts({ clinicianId, start: startDate, end: endDate });
      if (conflictRequestIdRef.current !== requestId) return;
      if (conflictCheckKeyRef.current !== conflictKey) return;
      setConflictWarning(buildConflictWarning(conflicts, clinicianId));
      setConflictChecking(false);
    }, 300);
    return () => {
      if (conflictCheckTimerRef.current) {
        window.clearTimeout(conflictCheckTimerRef.current);
        conflictCheckTimerRef.current = null;
      }
    };
  }, [
    appointments,
    startsAt,
    endsAt,
    activeClinicianUserId,
    activeLocationType,
    activeLocation,
    showNewModal,
    buildConflictWarning,
    findConflicts,
  ]);

  useEffect(() => {
    if (!isEditingAppointment || !selectedAppointment) {
      setEditConflictWarning(null);
      return;
    }
    if (!editStartsAt || !editEndsAt) {
      setEditConflictWarning(null);
      return;
    }
    const startDate = new Date(editStartsAt);
    const endDate = new Date(editEndsAt);
    if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
      setEditConflictWarning(null);
      return;
    }
    if (endDate <= startDate) {
      setEditConflictWarning(null);
      return;
    }
    const clinicianId = editClinicianUserId
      ? Number(editClinicianUserId)
      : selectedAppointment.clinician_user_id;
    if (!clinicianId || !Number.isFinite(clinicianId)) {
      setEditConflictWarning(null);
      return;
    }
    const conflicts = findConflicts({
      clinicianId,
      start: startDate,
      end: endDate,
      excludeId: selectedAppointment.id,
    });
    setEditConflictWarning(buildConflictWarning(conflicts, clinicianId));
  }, [
    buildConflictWarning,
    editClinicianUserId,
    editEndsAt,
    editStartsAt,
    findConflicts,
    isEditingAppointment,
    selectedAppointment,
  ]);

  useEffect(() => {
    if (!showNewModal) {
      setModalClinicianUserId(null);
      setModalLocationType(null);
      setModalLocationText(null);
      setModalLocation(null);
      setBookingSubmitError(null);
      return;
    }
    setModalClinicianUserId(clinicianUserId);
    setModalLocationType(locationType);
    setModalLocationText(locationText);
    setModalLocation(location);
    setBookingSubmitError(null);
  }, [showNewModal, clinicianUserId, locationType, locationText, location]);

  useEffect(() => {
    if (!conflictWarning && bookingSubmitError?.toLowerCase().includes("conflict")) {
      setBookingSubmitError(null);
    }
  }, [conflictWarning, bookingSubmitError]);

  useEffect(() => {
    if (durationMinutes === null || !startsAt) return;
    const startDate = new Date(startsAt);
    if (Number.isNaN(startDate.getTime())) return;
    const nextEnd = new Date(startDate);
    nextEnd.setMinutes(nextEnd.getMinutes() + durationMinutes);
    const nextValue = toLocalDateTimeInput(nextEnd);
    if (nextValue !== endsAt) {
      setEndsAt(nextValue);
    }
  }, [durationMinutes, startsAt, endsAt]);

  const bookingFieldErrors = useMemo(() => {
    const errors: { patient?: string; time?: string; visit?: string } = {};
    if (!selectedPatientId) {
      errors.patient = "Select a patient before booking.";
    }
    if (!startsAt || !endsAt) {
      errors.time = "Select a start and end time.";
    } else {
      const startDate = new Date(startsAt);
      const endDate = new Date(endsAt);
      if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
        errors.time = "Select a valid start and end time.";
      } else if (endDate <= startDate) {
        errors.time = "End time must be after the start time.";
      } else if (schedule && !isRangeWithinSchedule(startDate, endDate, schedule)) {
        errors.time = "Appointment time is outside of working hours.";
      }
    }
    if (activeLocationType === "visit" && !activeLocationText.trim()) {
      errors.visit = "Visit address is required for domiciliary visits.";
    }
    return errors;
  }, [selectedPatientId, startsAt, endsAt, activeLocationType, activeLocationText, schedule]);

  const bookingValidationError =
    bookingFieldErrors.patient || bookingFieldErrors.time || bookingFieldErrors.visit || null;
  const bookingConflictError = conflictWarning
    ? "Conflicts detected. Choose a different time."
    : null;
  const activeConflictWarning = showNewModal
    ? conflictWarning
    : isEditingAppointment
      ? editConflictWarning
      : conflictWarning;

  useEffect(() => {
    if (!highlightedAppointmentId) return;
    const timeout = window.setTimeout(() => {
      setHighlightedAppointmentId(null);
    }, 3000);
    return () => window.clearTimeout(timeout);
  }, [highlightedAppointmentId]);

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

  function openAppointment(appt: Appointment, mode: "view" | "edit" = "view") {
    setSelectedAppointment(appt);
    setSelectedAppointmentId(appt.id);
    setIsEditingAppointment(mode === "edit");
    setAuditOpen(false);
    setAuditEntries([]);
    setAuditError(null);
    setAuditLoading(false);
    setDetailLocationType(appt.location_type);
    setDetailLocationText(appt.location_text || "");
    void loadAppointmentNotes(appt.id);
    void loadPatientDetail(appt.patient.id);
    setEditStartsAt(toLocalDateTimeInput(new Date(appt.starts_at)));
    setEditEndsAt(toLocalDateTimeInput(new Date(appt.ends_at)));
    const diffMinutes = Math.round(
      (new Date(appt.ends_at).getTime() - new Date(appt.starts_at).getTime()) / 60000
    );
    const roundedDuration = Math.max(10, Math.round(diffMinutes / 10) * 10);
    setEditDuration(String(roundedDuration));
    setEditAppointmentType(appt.appointment_type || "");
    setEditClinicianUserId(appt.clinician_user_id ? String(appt.clinician_user_id) : "");
    setEditLocation(appt.location || "");
    setEditLocationType(appt.location_type);
    setEditLocationText(appt.location_text || "");
    setEditStatus(appt.status);
    setEditCancelReason(appt.cancel_reason || "");
    setEditNoteBody("");
  }

  const loadSchedule = useCallback(async () => {
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
  }, [router]);

  async function ensureNotesLoaded(appointmentId: number) {
    if (noteCache[appointmentId]) return;
    try {
      const res = await apiFetch(`/api/appointments/${appointmentId}/notes`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        setNoteCache((prev) => ({ ...prev, [appointmentId]: [] }));
        return;
      }
      const data = (await res.json()) as AppointmentNote[];
      const bodies = data.map((note) => note.body).filter(Boolean);
      setNoteCache((prev) => ({ ...prev, [appointmentId]: bodies }));
    } catch {
      setNoteCache((prev) => ({ ...prev, [appointmentId]: [] }));
    }
  }

  function buildTooltipContent(appt: Appointment) {
    const notes = noteCache[appt.id] || [];
    const lines: string[] = [];
    if (notes.length > 0) {
      lines.push("Notes:");
      notes.slice(0, 2).forEach((note) => lines.push(`- ${note}`));
    }
    if (appt.cancel_reason) {
      lines.push(`Cancel reason: ${appt.cancel_reason}`);
    }
    return lines.join("\n");
  }

  function showTooltip(event: { clientX: number; clientY: number }, appt: Appointment) {
    const content = buildTooltipContent(appt);
    if (!content) return;
    const maxWidth = 320;
    const padding = 12;
    const x = Math.min(event.clientX + padding, window.innerWidth - maxWidth - padding);
    const y = Math.min(event.clientY + padding, window.innerHeight - 160);
    setTooltip({ x, y, content });
  }

  const loadAppointments = useCallback(async () => {
    if (!range) return;
    const requestId = ++loadAppointmentsRequestId.current;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      const endDate = parseDateParam(range.end);
      const endExclusive = endDate ? addDays(endDate, 1) : null;
      params.set("start", range.start);
      params.set("end", endExclusive ? toDateKey(endExclusive) : range.end);
      if (locationFilter !== "all") params.set("location", locationFilter);
      const res = await apiFetch(`/api/appointments/range?${params.toString()}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) throw new Error(`Failed to load appointments (HTTP ${res.status})`);
      const data = (await res.json()) as Appointment[];
      if (requestId !== loadAppointmentsRequestId.current) return;
      setAppointments(data);
    } catch (err) {
      if (requestId !== loadAppointmentsRequestId.current) return;
      setError(err instanceof Error ? err.message : "Failed to load appointments");
    } finally {
      if (requestId !== loadAppointmentsRequestId.current) return;
      setLoading(false);
    }
  }, [locationFilter, range, router]);

  const loadPatients = useCallback(async (query?: string) => {
    const requestId = ++loadPatientsRequestId.current;
    try {
      const params = new URLSearchParams({ limit: "200" });
      const trimmed = query?.trim() ?? "";
      if (trimmed) params.set("q", trimmed);
      const res = await apiFetch(`/api/patients?${params.toString()}`);
      if (res.ok) {
        const data = (await res.json()) as Patient[];
        if (requestId !== loadPatientsRequestId.current) return;
        if (trimmed) {
          setPatientSearchResults(data);
        } else {
          setPatients(data);
        }
      }
    } catch {
      if (requestId !== loadPatientsRequestId.current) return;
      if (query?.trim()) {
        setPatientSearchResults([]);
      } else {
        setPatients([]);
      }
    }
  }, []);

  useEffect(() => {
    const query = patientQuery.trim();
    if (!query) {
      setPatientSearchResults([]);
      return;
    }
    const timer = window.setTimeout(() => {
      void loadPatients(query);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [loadPatients, patientQuery]);

  const loadUsers = useCallback(async () => {
    try {
      const res = await apiFetch("/api/users");
      if (res.ok) {
        const data = (await res.json()) as UserOption[];
        setUsers(data.filter((u) => u.is_active));
      }
    } catch {
      setUsers([]);
    }
  }, []);

  async function updateAppointmentStatus(
    appointmentId: number,
    status: AppointmentStatus,
    cancelReasonText?: string
  ) {
    setError(null);
    try {
      const res = await apiFetch(`/api/appointments/${appointmentId}`, {
        method: "PATCH",
        body: JSON.stringify({
          status,
          cancel_reason: cancelReasonText?.trim() || undefined,
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
      setAppointments((prev) => prev.map((appt) => (appt.id === updated.id ? updated : appt)));
      setNotice(`Status updated to ${statusLabels[status]}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update appointment");
    }
  }

  const updateAppointmentTimes = useCallback(
    async (
      appointmentId: number,
      startsAt: Date,
      endsAt: Date,
      lanePatch?: {
        clinicianUserId?: number;
        clinicianLabel?: string | null;
        locationType?: AppointmentLocationType;
        location?: string | null;
        locationText?: string | null;
        isDomiciliary?: boolean;
        visitAddress?: string | null;
      }
    ) => {
      const payload: Record<string, unknown> = {
        starts_at: startsAt.toISOString(),
        ends_at: endsAt.toISOString(),
      };
      if (lanePatch) {
        if ("clinicianUserId" in lanePatch && lanePatch.clinicianUserId) {
          payload.clinician_user_id = lanePatch.clinicianUserId;
        }
        if ("clinicianLabel" in lanePatch && lanePatch.clinicianLabel) {
          payload.clinician = lanePatch.clinicianLabel;
        }
        if ("locationType" in lanePatch && lanePatch.locationType) {
          payload.location_type = lanePatch.locationType;
        }
        if ("location" in lanePatch && lanePatch.location !== undefined) {
          payload.location = lanePatch.location;
        }
        if ("locationText" in lanePatch && lanePatch.locationText) {
          payload.location_text = lanePatch.locationText;
        }
        if ("isDomiciliary" in lanePatch && lanePatch.isDomiciliary !== undefined) {
          payload.is_domiciliary = lanePatch.isDomiciliary;
        }
        if ("visitAddress" in lanePatch && lanePatch.visitAddress) {
          payload.visit_address = lanePatch.visitAddress;
        }
      }
      const res = await apiFetch(`/api/appointments/${appointmentId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return null;
      }
      if (!res.ok) {
        const raw = await res.text();
        const conflictData = parseConflictResponse(raw);
        if (res.status === 409 && conflictData?.conflicts?.length) {
          const items = toConflictItems(conflictData.conflicts);
          setConflictWarning(buildConflictWarning(items, null));
          throw new Error(
            conflictData.detail || conflictData.message || "Conflicts detected."
          );
        }
        throw new Error(raw || `Failed to update appointment (HTTP ${res.status})`);
      }
      return (await res.json()) as Appointment;
    },
    [buildConflictWarning, router]
  );

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
  }, [loadSchedule, loadPatients, loadUsers]);

  useEffect(() => {
    if (!contextMenu) return;
    const handleClose = () => setContextMenu(null);
    window.addEventListener("click", handleClose);
    return () => window.removeEventListener("click", handleClose);
  }, [contextMenu]);

  useEffect(() => {
    void loadAppointments();
  }, [loadAppointments]);

  useEffect(() => {
    if (!selectedPatientId) return;
    const patient = patients.find((p) => String(p.id) === selectedPatientId);
    if (!patient) return;
    if (patient.care_setting !== "CLINIC") {
      const nextText = locationText.trim()
        ? locationText
        : patient.visit_address_text || "";
      setLocationType("visit");
      setLocationText(nextText);
      if (showNewModal) {
        setModalLocationType("visit");
        setModalLocationText(nextText);
      }
    } else {
      setLocationType("clinic");
      setLocationText("");
      if (showNewModal) {
        setModalLocationType("clinic");
        setModalLocationText("");
      }
    }
  }, [selectedPatientId, patients, locationText, showNewModal]);

  async function createAppointment(e: React.FormEvent) {
    e.preventDefault();
    if (bookingValidationError) return;
    const startDate = new Date(startsAt);
    const endDate = new Date(endsAt);
    const clinicianId = activeClinicianUserId ? Number(activeClinicianUserId) : null;
    if (clinicianId) {
      const conflicts = findConflicts({
        clinicianId,
        start: startDate,
        end: endDate,
      });
      const warning = buildConflictWarning(conflicts, clinicianId);
      setConflictWarning(warning);
      if (warning) {
        setBookingSubmitError("Conflicts detected. Choose a different time.");
        return;
      }
    }
    setSaving(true);
    setError(null);
    setBookingSubmitError(null);
    try {
      const res = await apiFetch("/api/appointments", {
        method: "POST",
        body: JSON.stringify({
          patient_id: Number(selectedPatientId),
          clinician_user_id: activeClinicianUserId
            ? Number(activeClinicianUserId)
            : undefined,
          starts_at: startDate.toISOString(),
          ends_at: endDate.toISOString(),
          status: "booked",
          appointment_type: appointmentType.trim() || undefined,
          location:
            activeLocationType === "clinic" ? activeLocation.trim() || undefined : undefined,
          location_type: activeLocationType,
          location_text: activeLocationText.trim() || undefined,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const raw = await res.text();
        let message = `Failed to create appointment (HTTP ${res.status})`;
        if (raw) {
          const conflictData = parseConflictResponse(raw);
          if (res.status === 409 && conflictData?.conflicts?.length && clinicianId) {
            const items = toConflictItems(conflictData.conflicts);
            setConflictWarning(buildConflictWarning(items, clinicianId));
            setBookingSubmitError(
              conflictData.detail || conflictData.message || "Conflicts detected."
            );
            return;
          }
          try {
            const data = JSON.parse(raw) as { detail?: string; message?: string };
            message = data.detail || data.message || message;
          } catch {
            message = raw;
          }
        }
        throw new Error(message);
      }
      const created = (await res.json()) as Appointment;
      setSelectedPatientId("");
      setClinicianUserId("");
      setAppointmentType("");
      setLocation("");
      setLocationType("clinic");
      setLocationText("");
      setStartsAt("");
      setEndsAt("");
      setDurationMinutes(30);
      setShowNewModal(false);
      setNotice("Appointment created.");
      if (recallContext) {
        setRecallAppointmentId(created?.id ?? null);
        setShowRecallPrompt(true);
      }
      if (created?.id) {
        setAppointments((prev) => [created, ...prev.filter((appt) => appt.id !== created.id)]);
        setHighlightedAppointmentId(String(created.id));
      }
      await loadAppointments();
    } catch (err) {
      setBookingSubmitError(
        err instanceof Error ? err.message : "Failed to create appointment"
      );
    } finally {
      setSaving(false);
    }
  }

  async function confirmRecallCompletion() {
    if (!recallContext) return;
    setRecallPromptSaving(true);
    setError(null);
    try {
      const res = await apiFetch(
        `/api/patients/${recallContext.patientId}/recalls/${recallContext.recallId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            status: "completed",
            completed_at: new Date().toISOString(),
            outcome: "attended",
            linked_appointment_id: recallAppointmentId ?? undefined,
          }),
        }
      );
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to update recall (HTTP ${res.status})`);
      }
      setShowRecallPrompt(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update recall");
    } finally {
      setRecallPromptSaving(false);
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

  async function loadAppointmentAudit(appointmentId: number) {
    setAuditLoading(true);
    setAuditError(null);
    try {
      const res = await apiFetch(`/api/audit/appointments/${appointmentId}?limit=10`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to load audit history (HTTP ${res.status})`);
      }
      const data = (await res.json()) as AppointmentAuditEntry[];
      setAuditEntries(data);
    } catch (err) {
      setAuditError(
        err instanceof Error ? err.message : "Failed to load audit history"
      );
    } finally {
      setAuditLoading(false);
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

  function handleEditStartChange(value: string) {
    setEditStartsAt(value);
    const start = new Date(value);
    if (Number.isNaN(start.getTime())) return;
    const duration = Number(editDuration || "30");
    const nextEnd = new Date(start);
    nextEnd.setMinutes(nextEnd.getMinutes() + duration);
    setEditEndsAt(toLocalDateTimeInput(nextEnd));
  }

  function handleEditEndChange(value: string) {
    setEditEndsAt(value);
    const start = new Date(editStartsAt);
    const end = new Date(value);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return;
    const diffMinutes = Math.max(
      10,
      Math.round((end.getTime() - start.getTime()) / 60000)
    );
    setEditDuration(String(Math.round(diffMinutes / 10) * 10));
  }

  function handleEditDurationChange(value: string) {
    setEditDuration(value);
    const start = new Date(editStartsAt);
    if (Number.isNaN(start.getTime())) return;
    const duration = Number(value || "30");
    const nextEnd = new Date(start);
    nextEnd.setMinutes(nextEnd.getMinutes() + duration);
    setEditEndsAt(toLocalDateTimeInput(nextEnd));
  }

  async function saveAppointmentEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedAppointment) return;
    const start = new Date(editStartsAt);
    const end = new Date(editEndsAt);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      setError("Start and end times are required.");
      return;
    }
    if (editConflictWarning) {
      setError("Conflicts detected. Choose a different time.");
      return;
    }
    if ((editStatus === "cancelled" || editStatus === "no_show") && !editCancelReason.trim()) {
      setError("Cancel reason is required for cancelled/no-show.");
      return;
    }
    setSavingDetail(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/appointments/${selectedAppointment.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          starts_at: start.toISOString(),
          ends_at: end.toISOString(),
          appointment_type: editAppointmentType.trim() || null,
          clinician_user_id: editClinicianUserId ? Number(editClinicianUserId) : null,
          location: editLocation.trim() || null,
          location_type: editLocationType,
          location_text: editLocationType === "visit" ? editLocationText.trim() || null : null,
          status: editStatus,
          cancel_reason:
            editStatus === "cancelled" || editStatus === "no_show"
              ? editCancelReason.trim()
              : null,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        const conflictData = parseConflictResponse(msg);
        if (res.status === 409 && conflictData?.conflicts?.length) {
          const clinicianId = editClinicianUserId
            ? Number(editClinicianUserId)
            : selectedAppointment.clinician_user_id;
          if (clinicianId) {
            const items = toConflictItems(conflictData.conflicts);
            setEditConflictWarning(buildConflictWarning(items, clinicianId));
          }
          setError(
            conflictData.detail || conflictData.message || "Conflicts detected."
          );
          return;
        }
        throw new Error(msg || `Failed to update appointment (HTTP ${res.status})`);
      }
      const updated = (await res.json()) as Appointment;
      if (editNoteBody.trim()) {
        await apiFetch("/api/notes", {
          method: "POST",
          body: JSON.stringify({
            patient_id: updated.patient.id,
            appointment_id: updated.id,
            body: editNoteBody.trim(),
            note_type: "clinical",
          }),
        });
        setEditNoteBody("");
      }
      setSelectedAppointment(updated);
      setAppointments((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setIsEditingAppointment(false);
      setNotice("Appointment updated.");
      await loadAppointments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update appointment");
      await loadAppointments();
    } finally {
      setSavingDetail(false);
    }
  }

  const pasteAppointment = useCallback(
    async (targetStart: Date) => {
      if (!clipboard) return;
      const appt = clipboard.appointment;
      const originalStart = new Date(appt.starts_at);
      const originalEnd = new Date(appt.ends_at);
      const durationMs = originalEnd.getTime() - originalStart.getTime();
      const targetEnd = new Date(targetStart.getTime() + durationMs);
      if (!isRangeWithinSchedule(targetStart, targetEnd, schedule)) {
        setError("Paste time is outside of working hours.");
        return;
      }
      const actionLabel = clipboard.mode === "cut" ? "Move" : "Copy";
      if (!window.confirm(`${actionLabel} this appointment to the selected slot?`)) {
        return;
      }
      try {
        if (clipboard.mode === "cut") {
          const updated = await updateAppointmentTimes(appt.id, targetStart, targetEnd);
          if (updated) {
            setAppointments((prev) =>
              prev.map((item) => (item.id === updated.id ? updated : item))
            );
          }
        } else {
          const res = await apiFetch("/api/appointments", {
            method: "POST",
            body: JSON.stringify({
              patient_id: appt.patient.id,
              clinician_user_id: appt.clinician_user_id ?? undefined,
              starts_at: targetStart.toISOString(),
              ends_at: targetEnd.toISOString(),
              status: "booked",
              appointment_type: appt.appointment_type ?? undefined,
              clinician: appt.clinician ?? undefined,
              location: appt.location ?? undefined,
              location_type: appt.location_type,
              location_text: appt.location_text ?? undefined,
              is_domiciliary: appt.is_domiciliary,
              visit_address: appt.visit_address ?? undefined,
            }),
          });
          if (res.status === 401) {
            clearToken();
            router.replace("/login");
            return;
          }
          if (!res.ok) {
            const msg = await res.text();
            throw new Error(msg || `Failed to copy appointment (HTTP ${res.status})`);
          }
        }
        setNotice(`${actionLabel}d appointment.`);
        setClipboard(null);
        await loadAppointments();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to paste appointment");
        await loadAppointments();
      }
    },
    [clipboard, loadAppointments, router, schedule, updateAppointmentTimes]
  );

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLTextAreaElement ||
        event.target instanceof HTMLSelectElement
      ) {
        return;
      }
      if (event.key === "Escape") {
        let handled = false;
        if (contextMenu) {
          setContextMenu(null);
          handled = true;
        }
        if (selectedAppointmentId !== null) {
          setSelectedAppointmentId(null);
          handled = true;
        }
        if (handled) {
          event.preventDefault();
          return;
        }
      }
      if (event.key === "Enter" && selectedAppointmentId !== null) {
        const appt = appointments.find((item) => item.id === selectedAppointmentId);
        if (appt) {
          event.preventDefault();
          openAppointment(appt);
          return;
        }
      }
      if (
        viewMode === "calendar" &&
        (event.key === "ArrowUp" || event.key === "ArrowLeft")
      ) {
        event.preventDefault();
        selectRelativeAppointment(-1);
        return;
      }
      if (
        viewMode === "calendar" &&
        (event.key === "ArrowDown" || event.key === "ArrowRight")
      ) {
        event.preventDefault();
        selectRelativeAppointment(1);
        return;
      }
      if (event.key === "PageUp" || event.key.toLowerCase() === "[") {
        event.preventDefault();
        const prev = new Date(currentDate);
        prev.setDate(prev.getDate() - 1);
        handleNavigate(prev);
        if (viewMode === "calendar") {
          const { start, end } = getRangeForView(prev, calendarView);
          updateRange(start, end, calendarView, prev);
        } else {
          updateRange(prev, prev, "day", prev);
        }
        return;
      }
      if (event.key === "PageDown" || event.key.toLowerCase() === "]") {
        event.preventDefault();
        const next = new Date(currentDate);
        next.setDate(next.getDate() + 1);
        handleNavigate(next);
        if (viewMode === "calendar") {
          const { start, end } = getRangeForView(next, calendarView);
          updateRange(start, end, calendarView, next);
        } else {
          updateRange(next, next, "day", next);
        }
        return;
      }
      if (event.key.toLowerCase() === "t") {
        event.preventDefault();
        const today = new Date();
        handleNavigate(today);
        if (viewMode === "calendar") {
          const { start, end } = getRangeForView(today, calendarView);
          updateRange(start, end, calendarView, today);
        } else {
          updateRange(today, today, "day", today);
        }
        return;
      }
      if (event.key === "Delete" && selectedAppointmentId) {
        const appt = appointments.find((item) => item.id === selectedAppointmentId);
        if (appt) {
          setCancelTarget(appt);
          setCancelReason("");
          setShowCancelModal(true);
        }
        return;
      }
      const isCmd = event.metaKey || event.ctrlKey;
      if (!isCmd) return;
      if (event.key.toLowerCase() === "c" && selectedAppointmentId) {
        const appt = appointments.find((item) => item.id === selectedAppointmentId);
        if (appt) {
          setClipboard({ mode: "copy", appointment: appt });
          setNotice("Copied appointment. Select a slot to paste.");
        }
        return;
      }
      if (event.key.toLowerCase() === "x" && selectedAppointmentId) {
        const appt = appointments.find((item) => item.id === selectedAppointmentId);
        if (appt) {
          setClipboard({ mode: "cut", appointment: appt });
          setNotice("Cut appointment. Select a slot to paste.");
        }
        return;
      }
      if (event.key.toLowerCase() === "v" && clipboard) {
        if (lastSelectedSlot) {
          void pasteAppointment(lastSelectedSlot);
        } else {
          setError("Select a slot before pasting.");
        }
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    appointments,
    calendarView,
    clipboard,
    contextMenu,
    currentDate,
    lastSelectedSlot,
    pasteAppointment,
    selectedAppointmentId,
    viewMode,
  ]);

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
    const appointmentParam = searchParams.get("appointment");
    setHighlightedAppointmentId(appointmentParam);
    const targetDate = searchParams.get("date");
    if (!targetDate) return;
    const parsed = parseDateParam(targetDate);
    if (!parsed) return;
    const viewParam = searchParams.get("view");
    const allowedViews = ["day", "week", "month"];
    const nextView =
      viewParam && allowedViews.includes(viewParam)
        ? (viewParam as View)
        : calendarView;
    const applyKey = `${targetDate}|${viewParam ?? ""}`;
    if (didApplyDate.current === applyKey) return;
    didApplyDate.current = applyKey;
    const storedViewMode = localStorage.getItem("dental_pms_appointments_view");
    const resolvedViewMode =
      storedViewMode === "calendar" || storedViewMode === "day_sheet"
        ? storedViewMode
        : viewMode;
    if (viewParam && allowedViews.includes(viewParam) && resolvedViewMode === "calendar") {
      setCalendarView(nextView);
    }
    setCurrentDate(parsed);
    if (resolvedViewMode === "calendar") {
      const { start, end } = getRangeForView(parsed, nextView);
      updateRange(start, end, nextView, parsed);
    } else {
      updateRange(parsed, parsed, "day", parsed);
    }
  }, [searchParams, calendarView, viewMode]);

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
    setLastSelectedSlot(slotInfo.start);
    if (clipboard) {
      void pasteAppointment(slotInfo.start);
      return;
    }
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
    resourceId,
  }: {
    event: CalendarEvent;
    start: Date;
    end: Date;
    resourceId?: string | number | null;
  }) {
    if (isRescheduleLocked) return;
    const snappedRange = snapRangeToIncrement(start, end, DIARY_TIME_STEP_MINUTES);
    const targetStart = snappedRange.start;
    const targetEnd = snappedRange.end;
    const sourceLaneKey = getLaneKeyForAppointment(event.resource);
    const requestedLaneKey =
      resourceId === null || resourceId === undefined
        ? sourceLaneKey
        : String(resourceId);
    let targetLaneKey = requestedLaneKey;
    if (targetLaneKey === sourceLaneKey) {
      const overlappingLanes = new Set(
        appointments
          .filter((item) => item.id !== event.resource.id)
          .filter((item) =>
            overlaps(
              targetStart,
              targetEnd,
              new Date(item.starts_at),
              new Date(item.ends_at)
            )
          )
          .map((item) => getLaneKeyForAppointment(item))
      );
      if (overlappingLanes.size === 1) {
        targetLaneKey = Array.from(overlappingLanes)[0];
      }
    }
    const laneChanged = targetLaneKey !== sourceLaneKey;
    const laneResolution = laneChanged
      ? resolveLanePatch(targetLaneKey)
      : { error: null, lanePatch: null };

    try {
      if (laneResolution.error) {
        setError(laneResolution.error);
        await loadAppointments();
        return;
      }
      if (!isRangeWithinSchedule(targetStart, targetEnd, schedule)) {
        setError("Reschedule is outside of working hours.");
        await loadAppointments();
        return;
      }
      if (
        hasLaneOverlap({
          appointmentId: event.resource.id,
          laneKey: targetLaneKey,
          start: targetStart,
          end: targetEnd,
        })
      ) {
        setError("Conflict: another appointment already occupies this lane and time.");
        await loadAppointments();
        return;
      }

      const targetClinicianId =
        laneResolution.lanePatch?.clinicianUserId ?? event.resource.clinician_user_id;
      if (targetClinicianId) {
        const conflicts = findConflicts({
          clinicianId: targetClinicianId,
          start: targetStart,
          end: targetEnd,
          excludeId: event.resource.id,
        });
        setConflictWarning(buildConflictWarning(conflicts, targetClinicianId));
      } else {
        setConflictWarning(null);
      }

      setRescheduleSavingId(event.resource.id);
      setAppointments((prev) =>
        prev.map((item) =>
          item.id === event.resource.id
            ? applyLanePatch(
                {
                  ...item,
                  starts_at: targetStart.toISOString(),
                  ends_at: targetEnd.toISOString(),
                },
                laneResolution.lanePatch
              )
            : item
        )
      );
      const updated = await updateAppointmentTimes(
        event.resource.id,
        targetStart,
        targetEnd,
        laneResolution.lanePatch ?? undefined
      );
      if (updated) {
        setAppointments((prev) =>
          prev.map((item) => (item.id === updated.id ? updated : item))
        );
        setSelectedAppointmentId(updated.id);
        setNotice("Appointment moved.");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to reschedule appointment";
      if (message.toLowerCase().includes("overlap")) {
        setError("Conflict: clinician already has an appointment at this time.");
      } else {
        setError(message);
      }
      await loadAppointments();
    } finally {
      setRescheduleSavingId(null);
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
    if (isRescheduleLocked) return;
    const snappedRange = snapRangeToIncrement(start, end, DIARY_TIME_STEP_MINUTES);
    const targetStart = snappedRange.start;
    const targetEnd = snappedRange.end;
    const laneKey = getLaneKeyForAppointment(event.resource);

    try {
      if (!isRangeWithinSchedule(targetStart, targetEnd, schedule)) {
        setError("Resize is outside of working hours.");
        await loadAppointments();
        return;
      }
      if (
        hasLaneOverlap({
          appointmentId: event.resource.id,
          laneKey,
          start: targetStart,
          end: targetEnd,
        })
      ) {
        setError("Conflict: another appointment already occupies this lane and time.");
        await loadAppointments();
        return;
      }
      if (event.resource.clinician_user_id) {
        const conflicts = findConflicts({
          clinicianId: event.resource.clinician_user_id,
          start: targetStart,
          end: targetEnd,
          excludeId: event.resource.id,
        });
        setConflictWarning(
          buildConflictWarning(conflicts, event.resource.clinician_user_id)
        );
      } else {
        setConflictWarning(null);
      }
      setRescheduleSavingId(event.resource.id);
      setAppointments((prev) =>
        prev.map((item) =>
          item.id === event.resource.id
            ? {
                ...item,
                starts_at: targetStart.toISOString(),
                ends_at: targetEnd.toISOString(),
              }
            : item
        )
      );
      const updated = await updateAppointmentTimes(event.resource.id, targetStart, targetEnd);
      if (updated) {
        setAppointments((prev) =>
          prev.map((item) => (item.id === updated.id ? updated : item))
        );
        setSelectedAppointmentId(updated.id);
        setNotice("Appointment duration updated.");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to resize appointment";
      if (message.toLowerCase().includes("overlap")) {
        setError("Conflict: clinician already has an appointment at this time.");
      } else {
        setError(message);
      }
      await loadAppointments();
    } finally {
      setRescheduleSavingId(null);
    }
  }

  function handleEventSelect(event: CalendarEvent) {
    setSelectedAppointmentId(event.resource.id);
  }

  function handleEventDoubleClick(event: CalendarEvent) {
    openAppointment(event.resource);
  }

  function jumpToDate(value: string) {
    if (!value) return;
    setCurrentDate(new Date(`${value}T00:00:00`));
  }

  function viewConflictsAt(date: Date) {
    setCurrentDate(date);
    setCalendarView("day");
    setViewMode("calendar");
    updateRange(date, date, "day", date);
  }

  function handleNavigate(date: Date) {
    setCurrentDate(date);
    setRange((prev) => (prev ? { ...prev, anchor: toDateKey(date) } : prev));
  }

  const isDiaryShellView =
    viewMode === "calendar" && (calendarView === "day" || calendarView === "week");

  function CalendarToolbar(toolbar: {
    date: Date;
    label: string;
    view: View;
    onNavigate: (action: "PREV" | "NEXT" | "TODAY" | "DATE", date?: Date) => void;
    onView: (view: View) => void;
  }) {
    const availableViews: Array<{ value: View; label: string }> = [
      { value: "day", label: "Day" },
      { value: "week", label: "Week" },
      { value: "month", label: "Month" },
      { value: "agenda", label: "Agenda" },
    ];
    return (
      <div className="rbc-toolbar appointments-r4-toolbar" data-testid="appointments-calendar-toolbar">
        <span className="rbc-btn-group">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => toolbar.onNavigate("PREV")}
            data-testid="appointments-calendar-prev"
          >
            Prev
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => toolbar.onNavigate("TODAY")}
            data-testid="appointments-calendar-today"
          >
            Today
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => toolbar.onNavigate("NEXT")}
            data-testid="appointments-calendar-next"
          >
            Next
          </button>
        </span>
        <span className="rbc-toolbar-label" data-testid="appointments-calendar-label">
          {toolbar.label}
        </span>
        <span className="rbc-btn-group">
          {availableViews.map((item) => (
            <button
              key={item.value}
              type="button"
              className={toolbar.view === item.value ? "btn btn-primary" : "btn btn-secondary"}
              onClick={() => toolbar.onView(item.value)}
              data-testid={`appointments-calendar-view-${item.value}`}
            >
              {item.label}
            </button>
          ))}
        </span>
      </div>
    );
  }

  function eventStyleGetter(
    event: CalendarEvent,
    _start: Date,
    _end: Date,
    isCalendarSelected?: boolean
  ) {
    const theme = statusThemeTokens[event.resource.status];
    const isSelected =
      Boolean(isCalendarSelected) || selectedAppointmentId === event.resource.id;
    const isHighlighted =
      highlightedAppointmentId && String(event.resource.id) === highlightedAppointmentId;
    return {
      style: {
        backgroundColor: theme.bg,
        borderColor: theme.border,
        color: theme.text,
        borderStyle: "solid",
        borderWidth: isHighlighted || isSelected ? 2 : 1,
        outline: isHighlighted || isSelected ? "2px solid var(--accent)" : undefined,
        outlineOffset: isHighlighted || isSelected ? 1 : undefined,
        boxShadow:
          event.resource.location_type === "visit"
            ? "0 0 0 2px rgba(255,255,255,0.5) inset"
            : undefined,
        opacity: rescheduleSavingId === event.resource.id ? 0.65 : 1,
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

  function AppointmentEvent({
    event,
    selected,
  }: {
    event: CalendarEvent;
    selected?: boolean;
  }) {
    const appt = event.resource;
    const isSelected = Boolean(selected) || selectedAppointmentId === appt.id;
    const patientDetail = patientLookup.get(appt.patient.id);
    const phone = patientDetail?.phone || "";
    const address = buildShortAddress(patientDetail);
    const timeLabel = `${format(event.start, "HH:mm")}–${format(event.end, "HH:mm")}`;
    const appointmentCode = toAppointmentCode(appt.appointment_type);
    const locationLabel =
      appt.location_type === "visit"
        ? appt.location_text || "Visit"
        : appt.location || "Clinic";
    const patientLabel = `${appt.patient.last_name.toUpperCase()}, ${appt.patient.first_name}`;
    const detailParts = [
      calendarView === "day" && phone ? `P: ${phone}` : null,
      calendarView === "day" && address ? address : null,
      locationLabel ? `@ ${locationLabel}` : null,
    ].filter(Boolean);
    return (
      <div
        className={`appointments-r4-event${isSelected ? " appointments-r4-event--selected" : ""}`}
        data-testid={`appointment-event-${appt.id}`}
        data-appointment-id={appt.id}
        data-selected={isSelected ? "true" : "false"}
        onClick={() => setSelectedAppointmentId(appt.id)}
        onDoubleClick={() => openAppointment(appt)}
        onContextMenu={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setSelectedAppointmentId(appt.id);
          setContextMenu({ x: event.clientX, y: event.clientY, appointment: appt });
        }}
      >
        <div className="appointments-r4-event-title">
          <span className="appointments-r4-event-time">{timeLabel}</span>
          <span>{patientLabel}</span>
        </div>
        <div className="appointments-r4-event-meta">
          <span className="appointments-r4-event-code">{appointmentCode}</span>
          <span className="r4-status-pill" data-status={appt.status}>
            {daySheetStatusLabels[appt.status]}
          </span>
          {rescheduleSavingId === appt.id && <span className="badge">Saving...</span>}
        </div>
        {detailParts.length > 0 && (
          <div className="appointments-r4-event-detail">{detailParts.join(" · ")}</div>
        )}
      </div>
    );
  }

  const requiredMark = (
    <span style={{ color: "var(--danger)", marginLeft: 4 }} aria-hidden="true">
      *
    </span>
  );

  return (
    <div
      className="app-grid"
      data-book-intent={bookIntent ? "1" : "0"}
      data-testid="appointments-page"
    >
      <section className="card" style={{ display: "grid", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
          <div>
            <h2 style={{ marginTop: 0 }}>Appointments</h2>
            <p style={{ color: "var(--muted)", marginBottom: 0 }}>
              Plan your clinic and visit diary across day, week, and month views.
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button
              className="btn btn-primary"
              onClick={() => setShowNewModal(true)}
              data-testid="new-appointment"
            >
              New appointment
            </button>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                className={viewMode === "day_sheet" ? "btn btn-primary" : "btn btn-secondary"}
                onClick={() => setViewMode("day_sheet")}
                data-testid="appointments-view-day-sheet"
              >
                Day sheet
              </button>
              <button
                className={viewMode === "calendar" ? "btn btn-primary" : "btn btn-secondary"}
                onClick={() => setViewMode("calendar")}
                data-testid="appointments-view-calendar"
              >
                Calendar
              </button>
            </div>
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
        {showRecallPrompt && recallContext && (
          <div className="card" style={{ margin: 0 }}>
            <div className="stack">
              <div className="row">
                <div>
                  <strong>Mark recall completed?</strong>
                  <div style={{ color: "var(--muted)" }}>
                    Close the recall linked to this booking.
                  </div>
                </div>
              </div>
              <div className="row">
                <button
                  className="btn btn-primary"
                  type="button"
                  onClick={confirmRecallCompletion}
                  disabled={recallPromptSaving}
                >
                  {recallPromptSaving ? "Saving..." : "Mark completed"}
                </button>
                <button
                  className="btn btn-secondary"
                  type="button"
                  onClick={() => setShowRecallPrompt(false)}
                  disabled={recallPromptSaving}
                >
                  Not now
                </button>
              </div>
            </div>
          </div>
        )}
        {activeConflictWarning && (
          <div
            className="notice"
            style={{
              background: "rgba(245, 158, 11, 0.12)",
              borderColor: "rgba(245, 158, 11, 0.4)",
            }}
            data-testid="booking-conflicts"
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                justifyContent: "space-between",
              }}
            >
              <span>{activeConflictWarning.message}</span>
              <button
                className="btn btn-secondary"
                type="button"
                onClick={() => {
                  if (activeConflictWarning.anchorDate) {
                    viewConflictsAt(activeConflictWarning.anchorDate);
                    router.replace(
                      `/appointments?date=${toDateKey(activeConflictWarning.anchorDate)}`,
                      { scroll: false }
                    );
                  }
                }}
                data-testid="booking-conflict-view-day"
              >
                View day
              </button>
            </div>
            {activeConflictWarning.items.length > 0 && (
              <div style={{ marginTop: 6, display: "grid", gap: 4 }}>
                {activeConflictWarning.items.map((item) => (
                  <div
                    key={`${item.patientName}-${item.start.toISOString()}`}
                    style={{ display: "flex", gap: 8, flexWrap: "wrap" }}
                    data-testid="booking-conflict-row"
                  >
                    <span>{formatConflictTime(item.start, item.end)}</span>
                    <span>{item.patientName}</span>
                    {item.locationLabel && (
                      <span style={{ color: "var(--muted)" }}>{item.locationLabel}</span>
                    )}
                  </div>
                ))}
                {activeConflictWarning.extraCount > 0 && (
                  <span style={{ color: "var(--muted)" }}>
                    + {activeConflictWarning.extraCount} more
                  </span>
                )}
              </div>
            )}
            <div style={{ marginTop: 6, color: "var(--muted)" }}>
              Conflicts are checked within the loaded calendar range.
            </div>
          </div>
        )}

        {viewMode === "calendar" ? (
          <div
            className="card appointments-r4-shell"
            style={{ margin: 0, padding: 16 }}
            data-testid="appointments-diary-shell"
          >
            {isDiaryShellView && (
              <div className="appointments-r4-shell-header">
                <label className="appointments-r4-filter">
                  <span className="label" style={{ margin: 0 }}>
                    Group by
                  </span>
                  <select
                    className="input"
                    value={diaryGrouping}
                    onChange={(event) => setDiaryGrouping(event.target.value as DiaryGrouping)}
                    data-testid="appointments-diary-grouping"
                  >
                    <option value="chair">Chair</option>
                    <option value="clinician">Clinician</option>
                  </select>
                </label>
                {diaryGrouping === "chair" ? (
                  <label className="appointments-r4-filter">
                    <span className="label" style={{ margin: 0 }}>
                      Chair
                    </span>
                    <select
                      className="input"
                      value={diaryChairFilter}
                      onChange={(event) => setDiaryChairFilter(event.target.value)}
                      data-testid="appointments-diary-chair-filter"
                    >
                      <option value="all">All chairs</option>
                      {diaryChairOptions.map((label) => (
                        <option key={label} value={label}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <label className="appointments-r4-filter">
                    <span className="label" style={{ margin: 0 }}>
                      Clinician
                    </span>
                    <select
                      className="input"
                      value={diaryClinicianFilter}
                      onChange={(event) => setDiaryClinicianFilter(event.target.value)}
                      data-testid="appointments-diary-clinician-filter"
                    >
                      <option value="all">All clinicians</option>
                      {diaryClinicianOptions.map((item) => (
                        <option key={item.key} value={item.key}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <div className="appointments-r4-shell-note">
                  Time scale: {DIARY_TIME_STEP_MINUTES}-minute increments
                </div>
              </div>
            )}
            {isDiaryShellView && (
              <div
                className="appointments-r4-columns"
                data-testid="appointments-diary-columns"
                data-grouping={diaryGrouping}
              >
                {diaryColumns.map((column, index) => (
                  <div
                    key={column.key}
                    className="appointments-r4-column"
                    data-testid={`appointments-diary-column-${index}`}
                    data-column-key={column.key}
                    data-column-label={column.label}
                  >
                    <span className="appointments-r4-column-label">{column.label}</span>
                    <span className="badge">{column.count}</span>
                  </div>
                ))}
              </div>
            )}
            {loading && <div className="badge">Loading appointments…</div>}
            <DragAndDropCalendar
              localizer={localizer}
              events={calendarEvents}
              startAccessor="start"
              endAccessor="end"
              selectable
              resizable
              step={DIARY_TIME_STEP_MINUTES}
              timeslots={1}
              resources={calendarResources}
              resourceIdAccessor="id"
              resourceTitleAccessor="title"
              onSelectSlot={handleSelectSlot}
              onSelectEvent={handleEventSelect}
              onDoubleClickEvent={handleEventDoubleClick}
              onEventDrop={handleEventDrop}
              onEventResize={handleEventResize}
              draggableAccessor={() => !isRescheduleLocked}
              resizableAccessor={() => !isRescheduleLocked}
              selected={selectedCalendarEvent}
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
              components={{ event: AppointmentEvent, toolbar: CalendarToolbar }}
              eventPropGetter={eventStyleGetter}
              dayPropGetter={dayPropGetter}
              slotPropGetter={slotPropGetter}
              scrollToTime={highlightScrollTime}
              className="appointments-r4-calendar"
              style={{ height: "70vh" }}
            />
          </div>
        ) : (
          <div className="card" style={{ margin: 0, padding: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <div className="label">Day sheet</div>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    const prev = new Date(currentDate);
                    prev.setDate(prev.getDate() - 1);
                    handleNavigate(prev);
                    updateRange(prev, prev, "day", prev);
                  }}
                >
                  ← Prev
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    const next = new Date(currentDate);
                    next.setDate(next.getDate() + 1);
                    handleNavigate(next);
                    updateRange(next, next, "day", next);
                  }}
                >
                  Next →
                </button>
              </div>
            </div>
            {loading ? (
              <div className="badge">Loading appointments…</div>
            ) : daySheetAppointments.length === 0 ? (
              <div className="notice">No appointments for this day.</div>
            ) : (
              <table className="table table-compact table-hover table-sticky day-sheet-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Patient</th>
                    <th>Code</th>
                    <th>Phone</th>
                    <th>Address</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {daySheetAppointments.map((appt) => {
                    const patient = patientLookup.get(appt.patient.id);
                    const address = buildShortAddress(patient);
                    const isCancelled =
                      appt.status === "cancelled" || appt.status === "no_show";
                    const hasNotes =
                      Boolean(appt.cancel_reason) || (noteCache[appt.id]?.length ?? 0) > 0;
                    const isHighlighted =
                      highlightedAppointmentId && String(appt.id) === highlightedAppointmentId;
                    const isSelected = selectedAppointmentId === appt.id;
                    const alertFlags = buildPatientAlertFlags(patient ?? appt.patient);
                    return (
                      <tr
                        key={appt.id}
                        className={`${isCancelled ? "row-muted" : ""}${isHighlighted || isSelected ? " row-highlight" : ""}`}
                        onClick={() => setSelectedAppointmentId(appt.id)}
                        onDoubleClick={() => openAppointment(appt, "edit")}
                        onContextMenu={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          setSelectedAppointmentId(appt.id);
                          setContextMenu({
                            x: event.clientX,
                            y: event.clientY,
                            appointment: appt,
                          });
                        }}
                        onMouseEnter={(event) => {
                          void ensureNotesLoaded(appt.id);
                          if (hasNotes) showTooltip(event, appt);
                        }}
                        onMouseLeave={() => setTooltip(null)}
                      >
                        <td className="day-sheet-time">{formatTimeRange(appt.starts_at, appt.ends_at)}</td>
                        <td className="day-sheet-patient">
                          {appt.patient.last_name.toUpperCase()}, {appt.patient.first_name}
                          {alertFlags.length > 0 && (
                            <span className="day-sheet-flags">
                              {alertFlags.map((flag) => (
                                <span
                                  key={flag.key}
                                  className="patient-flag"
                                  data-flag={flag.key}
                                  title={`${flag.label}: ${flag.value}`}
                                >
                                  {flag.short}
                                </span>
                              ))}
                            </span>
                          )}
                          {hasNotes && (
                            <span
                              className="day-sheet-note-icon"
                              onMouseEnter={(event) => showTooltip(event, appt)}
                              onMouseLeave={() => setTooltip(null)}
                            >
                              🛈
                            </span>
                          )}
                        </td>
                        <td>{toAppointmentCode(appt.appointment_type)}</td>
                        <td>{patient?.phone || "—"}</td>
                        <td>{address || "—"}</td>
                        <td>
                          <div className="day-sheet-status">
                            <StatusIcon status={appt.status} />
                            <span
                              className="r4-status-pill"
                              data-status={appt.status}
                            >
                              {daySheetStatusLabels[appt.status]}
                            </span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}
        {contextMenu && (
          <div
            className="card"
            style={{
              position: "fixed",
              top: contextMenu.y,
              left: contextMenu.x,
              zIndex: 50,
              padding: 8,
              display: "grid",
              gap: 6,
              minWidth: 180,
            }}
            data-testid="appointments-context-menu"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              className="btn btn-secondary"
              data-testid="appointments-context-open"
              onClick={() => {
                openAppointment(contextMenu.appointment);
                setContextMenu(null);
              }}
            >
              Open
            </button>
            <button
              className="btn btn-secondary"
              data-testid="appointments-context-move"
              onClick={() => {
                setClipboard({ mode: "cut", appointment: contextMenu.appointment });
                setNotice("Move mode enabled. Select a slot to paste.");
                setContextMenu(null);
              }}
            >
              Move
            </button>
            <button
              className="btn btn-secondary"
              data-testid="appointments-context-notes"
              onClick={() => {
                openAppointment(contextMenu.appointment, "edit");
                setNotice("Appointment detail opened for notes/editing.");
                setContextMenu(null);
              }}
            >
              Notes
            </button>
            <button
              className="btn btn-secondary"
              data-testid="appointments-context-cancel"
              onClick={() => {
                setCancelTarget(contextMenu.appointment);
                setCancelReason("");
                setShowCancelModal(true);
                setContextMenu(null);
              }}
            >
              Cancel…
            </button>
            <button
              className="btn btn-secondary"
              data-testid="appointments-context-no-show"
              onClick={() => {
                void updateAppointmentStatus(contextMenu.appointment.id, "no_show");
                setContextMenu(null);
              }}
            >
              Did not attend
            </button>
            <button
              className="btn btn-secondary"
              data-testid="appointments-context-copy"
              onClick={() => {
                setClipboard({ mode: "copy", appointment: contextMenu.appointment });
                setNotice("Copied appointment. Select a slot to paste.");
                setContextMenu(null);
              }}
            >
              Copy
            </button>
          </div>
        )}
        {tooltip && (
          <div
            className="day-sheet-tooltip"
            style={{ top: tooltip.y, left: tooltip.x }}
            onMouseLeave={() => setTooltip(null)}
          >
            {tooltip.content}
          </div>
        )}
        {!loading &&
          ((viewMode === "calendar" && calendarEvents.length === 0) ||
            (viewMode !== "calendar" && appointments.length === 0)) && (
          <div className="notice">No appointments in this range.</div>
        )}

        {showNewModal && (
          <div className="card" style={{ margin: 0 }} data-testid="booking-modal">
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
                {(bookingSubmitError || bookingValidationError || bookingConflictError) && (
                  <div className="notice" data-testid="booking-error">
                    {bookingSubmitError || bookingValidationError || bookingConflictError}
                  </div>
                )}
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">Search patient</label>
                  <input
                    className="input"
                    placeholder="Start typing a name"
                    value={patientQuery}
                    onChange={(e) => setPatientQuery(e.target.value)}
                    data-testid="booking-patient-search"
                    ref={patientSearchRef}
                  />
                </div>
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">
                    Select patient
                    {requiredMark}
                  </label>
                  <select
                    className="input"
                    value={selectedPatientId}
                    onChange={(e) => setSelectedPatientId(e.target.value)}
                    data-testid="booking-patient-select"
                  >
                    <option value="">Choose patient</option>
                    {filteredPatients.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.first_name} {p.last_name}
                      </option>
                    ))}
                  </select>
                  {bookingFieldErrors.patient && (
                    <div
                      style={{ color: "var(--danger)", fontSize: 12 }}
                      data-testid="booking-error-patient"
                    >
                      {bookingFieldErrors.patient}
                    </div>
                  )}
                </div>
                <div style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr" }}>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">
                      Start
                      {requiredMark}
                    </label>
                    <input
                      className="input"
                      type="datetime-local"
                      value={startsAt}
                      onChange={(e) => setStartsAt(e.target.value)}
                      data-testid="booking-start"
                    />
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">
                      End
                      {requiredMark}
                    </label>
                    <input
                      className="input"
                      type="datetime-local"
                      value={endsAt}
                      onChange={(e) => {
                        const nextValue = e.target.value;
                        setEndsAt(nextValue);
                        if (!startsAt) return;
                        const startDate = new Date(startsAt);
                        const endDate = new Date(nextValue);
                        if (
                          Number.isNaN(startDate.getTime()) ||
                          Number.isNaN(endDate.getTime()) ||
                          endDate <= startDate
                        ) {
                          setDurationMinutes(null);
                          return;
                        }
                        const diffMinutes = Math.round(
                          (endDate.getTime() - startDate.getTime()) / 60000
                        );
                        if ([10, 15, 20, 30, 45, 60, 90].includes(diffMinutes)) {
                          setDurationMinutes(diffMinutes);
                        } else {
                          setDurationMinutes(null);
                        }
                      }}
                      data-testid="booking-end"
                    />
                  </div>
                </div>
                {bookingFieldErrors.time && (
                  <div
                    style={{ color: "var(--danger)", fontSize: 12 }}
                    data-testid="booking-error-time"
                  >
                    {bookingFieldErrors.time}
                  </div>
                )}
                {startsAt && endsAt && (
                  <div
                    style={{ color: "var(--muted)", fontSize: 12 }}
                    data-testid="booking-preselected-slot"
                  >
                    Slot prefilled — edit times if needed.
                  </div>
                )}
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">Duration</label>
                  <select
                    className="input"
                    value={durationMinutes === null ? "" : String(durationMinutes)}
                    onChange={(e) => {
                      const value = e.target.value;
                      if (!value) {
                        setDurationMinutes(null);
                        return;
                      }
                      const parsed = Number(value);
                      if (Number.isFinite(parsed) && parsed > 0) {
                        setDurationMinutes(parsed);
                      }
                    }}
                  >
                    <option value="">Custom</option>
                    {[10, 15, 20, 30, 45, 60, 90].map((minutes) => (
                      <option key={minutes} value={minutes}>
                        {minutes} min
                      </option>
                    ))}
                  </select>
                </div>
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">Clinician (optional)</label>
                  <select
                    className="input"
                    value={activeClinicianUserId}
                    onChange={(e) => {
                      const next = e.target.value;
                      setClinicianUserId(next);
                      if (showNewModal) setModalClinicianUserId(next);
                    }}
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
                    data-testid="booking-location-room"
                    value={activeLocation}
                    onChange={(e) => {
                      const next = e.target.value;
                      setLocation(next);
                      if (showNewModal) setModalLocation(next);
                    }}
                    placeholder={
                      activeLocationType === "visit"
                        ? "Not used for visit appointments"
                        : "Room 1"
                    }
                    disabled={activeLocationType === "visit"}
                  />
                </div>
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">
                    Location type
                    {requiredMark}
                  </label>
                  <select
                    className="input"
                    data-testid="booking-location-type"
                    value={activeLocationType}
                    onChange={(e) => {
                      const next = e.target.value as AppointmentLocationType;
                      setLocationType(next);
                      if (showNewModal) setModalLocationType(next);
                      if (next === "clinic") {
                        setLocationText("");
                        if (showNewModal) setModalLocationText("");
                      }
                    }}
                  >
                    <option value="clinic">Clinic</option>
                    <option value="visit">Visit</option>
                  </select>
                </div>
                {activeLocationType === "visit" && (
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">
                      Visit address
                      {requiredMark}
                    </label>
                    <textarea
                      className="input"
                      data-testid="booking-visit-address"
                      rows={3}
                      value={activeLocationText}
                      onChange={(e) => {
                        const next = e.target.value;
                        setLocationText(next);
                        if (showNewModal) setModalLocationText(next);
                      }}
                      placeholder="Full address for the home visit"
                    />
                    {bookingFieldErrors.visit && (
                      <div
                        style={{ color: "var(--danger)", fontSize: 12 }}
                        data-testid="booking-error-visit"
                      >
                        {bookingFieldErrors.visit}
                      </div>
                    )}
                  </div>
                )}
                {conflictChecking && (
                  <div className="notice" data-testid="booking-conflicts-loading">
                    Checking conflicts…
                  </div>
                )}
                <button
                  className="btn btn-primary"
                  data-testid="booking-submit"
                  disabled={
                    saving ||
                    conflictChecking ||
                    Boolean(bookingValidationError) ||
                    Boolean(bookingConflictError)
                  }
                >
                  {saving ? "Saving..." : "Create appointment"}
                </button>
              </form>
            </div>
          </div>
        )}

        {selectedAppointment && (
          <div className="card" style={{ margin: 0 }} data-testid="appointment-detail-panel">
            <div className="stack">
              <div className="row">
                <div>
                  <h3 style={{ marginTop: 0 }}>Appointment details</h3>
                  <p style={{ color: "var(--muted)" }}>
                    {selectedAppointment.patient.first_name} {selectedAppointment.patient.last_name} ·{" "}
                    {new Date(selectedAppointment.starts_at).toLocaleString()}
                  </p>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    className="btn btn-secondary"
                    onClick={() => setIsEditingAppointment((prev) => !prev)}
                  >
                    {isEditingAppointment ? "View" : "Edit"}
                  </button>
                  <button
                    className="btn btn-secondary"
                    data-testid="appointment-detail-close"
                    onClick={() => {
                      setSelectedAppointment(null);
                      setNotes([]);
                      setDetailPatient(null);
                      setIsEditingAppointment(false);
                    }}
                  >
                    Close
                  </button>
                </div>
              </div>

              {isEditingAppointment ? (
                <form onSubmit={saveAppointmentEdit} className="stack">
                  <div style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr" }}>
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Start</label>
                      <input
                        className="input"
                        type="datetime-local"
                        value={editStartsAt}
                        onChange={(event) => handleEditStartChange(event.target.value)}
                        step={600}
                        required
                      />
                    </div>
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">End</label>
                      <input
                        className="input"
                        type="datetime-local"
                        value={editEndsAt}
                        onChange={(event) => handleEditEndChange(event.target.value)}
                        step={600}
                        required
                      />
                    </div>
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Duration</label>
                    <select
                      className="input"
                      value={editDuration}
                      onChange={(event) => handleEditDurationChange(event.target.value)}
                    >
                      {[10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120].map(
                        (minutes) => (
                          <option key={minutes} value={String(minutes)}>
                            {minutes} minutes
                          </option>
                        )
                      )}
                    </select>
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Appointment type</label>
                    <input
                      className="input"
                      data-testid="edit-appointment-type"
                      value={editAppointmentType}
                      onChange={(event) => setEditAppointmentType(event.target.value)}
                    />
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Clinician</label>
                    <select
                      className="input"
                      value={editClinicianUserId}
                      onChange={(event) => setEditClinicianUserId(event.target.value)}
                    >
                      <option value="">Unassigned</option>
                      {users.map((user) => (
                        <option key={user.id} value={user.id}>
                          {user.full_name || user.email} ({user.role})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Location / room</label>
                    <input
                      className="input"
                      value={editLocation}
                      onChange={(event) => setEditLocation(event.target.value)}
                    />
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Location type</label>
                    <select
                      className="input"
                      value={editLocationType}
                      onChange={(event) => {
                        const next = event.target.value as AppointmentLocationType;
                        setEditLocationType(next);
                        if (next === "clinic") setEditLocationText("");
                      }}
                    >
                      <option value="clinic">Clinic</option>
                      <option value="visit">Visit</option>
                    </select>
                  </div>
                  {editLocationType === "visit" && (
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Visit address</label>
                      <textarea
                        className="input"
                        rows={3}
                        value={editLocationText}
                        onChange={(event) => setEditLocationText(event.target.value)}
                      />
                    </div>
                  )}
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Status</label>
                    <select
                      className="input"
                      value={editStatus}
                      onChange={(event) =>
                        setEditStatus(event.target.value as AppointmentStatus)
                      }
                    >
                      <option value="booked">Booked</option>
                      <option value="arrived">Arrived</option>
                      <option value="in_progress">In progress</option>
                      <option value="completed">Completed</option>
                      <option value="cancelled">Cancelled</option>
                      <option value="no_show">No show</option>
                    </select>
                  </div>
                  {(editStatus === "cancelled" || editStatus === "no_show") && (
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Cancel reason</label>
                      <textarea
                        className="input"
                        rows={3}
                        value={editCancelReason}
                        onChange={(event) => setEditCancelReason(event.target.value)}
                      />
                    </div>
                  )}
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Add note</label>
                    <textarea
                      className="input"
                      rows={3}
                      value={editNoteBody}
                      onChange={(event) => setEditNoteBody(event.target.value)}
                      placeholder="Add a note for this appointment"
                    />
                  </div>
                  <div className="row">
                    <button
                      className="btn btn-primary"
                      disabled={savingDetail || Boolean(editConflictWarning)}
                    >
                      {savingDetail ? "Saving..." : "Save changes"}
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setIsEditingAppointment(false)}
                    >
                      Cancel edit
                    </button>
                  </div>
                </form>
              ) : (
                <>
                  <div className="stack" style={{ gap: 6 }}>
                    <div>
                      <strong>Status:</strong> {statusLabels[selectedAppointment.status]}
                    </div>
                    <div>
                      <strong>Clinician:</strong>{" "}
                      {selectedAppointment.clinician || "Unassigned"}
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
                    <div
                      data-testid="appointment-created-meta"
                      data-iso={selectedAppointment.created_at}
                    >
                      <strong>Created by:</strong>{" "}
                      {selectedAppointment.created_by?.email || "—"} ·{" "}
                      {formatMetaTimestamp(selectedAppointment.created_at)}
                    </div>
                    <div
                      data-testid="appointment-updated-meta"
                      data-iso={selectedAppointment.updated_at}
                    >
                      <strong>Last updated by:</strong>{" "}
                      {selectedAppointment.updated_by?.email ||
                        selectedAppointment.created_by?.email ||
                        "—"}{" "}
                      · {formatMetaTimestamp(selectedAppointment.updated_at)}
                    </div>
                  </div>

                  <div className="card" style={{ margin: 0 }}>
                    <div className="stack" style={{ gap: 8 }}>
                      <div className="row">
                        <strong>History</strong>
                        <button
                          className="btn btn-secondary"
                          type="button"
                          onClick={() => {
                            const next = !auditOpen;
                            setAuditOpen(next);
                            if (next && selectedAppointment) {
                              void loadAppointmentAudit(selectedAppointment.id);
                            }
                          }}
                          data-testid="appointment-history-toggle"
                        >
                          {auditOpen ? "Hide" : "View"}
                        </button>
                      </div>
                      {auditOpen && (
                        <>
                          {auditLoading && (
                            <div className="badge" data-testid="appointment-history-loading">
                              Loading history…
                            </div>
                          )}
                          {auditError && <div className="notice">{auditError}</div>}
                          {!auditLoading && !auditError && auditEntries.length === 0 && (
                            <div className="notice">No recent history.</div>
                          )}
                          {!auditLoading && auditEntries.length > 0 && (
                            <div className="stack" style={{ gap: 6 }}>
                              {auditEntries.map((entry) => (
                                <div
                                  key={entry.id}
                                  style={{ display: "flex", flexWrap: "wrap", gap: 8 }}
                                  data-testid="appointment-history-row"
                                >
                                  <span>{formatMetaTimestamp(entry.created_at)}</span>
                                  <span>{entry.action.replace("appointment.", "")}</span>
                                  <span style={{ color: "var(--muted)" }}>
                                    {entry.actor_email ||
                                      entry.actor?.email ||
                                      "Unknown user"}
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </>
                      )}
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
                            !detailPatient.safeguarding_notes && (
                              <span className="badge">None</span>
                            )}
                          {detailPatient.allergies && (
                            <span
                              className="badge"
                              style={{ background: "#b13636", color: "white" }}
                            >
                              Allergies
                            </span>
                          )}
                          {detailPatient.medical_alerts && (
                            <span
                              className="badge"
                              style={{ background: "#b07b24", color: "white" }}
                            >
                              Medical alerts
                            </span>
                          )}
                          {detailPatient.safeguarding_notes && (
                            <span
                              className="badge"
                              style={{ background: "#b07b24", color: "white" }}
                            >
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
                        onClick={() =>
                          updateAppointmentStatus(selectedAppointment.id, "in_progress")
                        }
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
                </>
              )}
            </div>
          </div>
        )}
        {showCancelModal && cancelTarget && (
          <div className="card" style={{ margin: 0 }}>
            <div className="stack">
              <div className="row">
                <div>
                  <h3 style={{ marginTop: 0 }}>Cancel appointment</h3>
                  <p style={{ color: "var(--muted)" }}>
                    {cancelTarget.patient.first_name} {cancelTarget.patient.last_name} ·{" "}
                    {new Date(cancelTarget.starts_at).toLocaleString()}
                  </p>
                </div>
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    setShowCancelModal(false);
                    setCancelTarget(null);
                    setCancelReason("");
                  }}
                >
                  Close
                </button>
              </div>
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  if (!cancelReason.trim()) {
                    setError("Cancellation reason is required.");
                    return;
                  }
                  void updateAppointmentStatus(
                    cancelTarget.id,
                    "cancelled",
                    cancelReason
                  );
                  setShowCancelModal(false);
                  setCancelTarget(null);
                  setCancelReason("");
                }}
                className="stack"
              >
                <label className="label">Reason</label>
                <textarea
                  className="input"
                  rows={3}
                  value={cancelReason}
                  onChange={(event) => setCancelReason(event.target.value)}
                  placeholder="Patient cancelled, clinician unavailable, etc."
                />
                <button className="btn btn-primary">Confirm cancel</button>
              </form>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
