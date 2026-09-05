"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import { recallResponseError, sanitizeRecallFilename } from "@/lib/recallErrors";
import Table from "@/components/ui/Table";
import Icon from "@/components/ui/Icon";
import RecallLetterDialog from "./RecallLetterDialog";
import styles from "./Recalls.module.css";
import RecallSummary from "./RecallSummary";

type RecallStatus = "upcoming" | "due" | "overdue" | "completed" | "cancelled";
type RecallKind = "exam" | "hygiene" | "perio" | "implant" | "custom";
type RecallContactChannel = "letter" | "phone" | "email" | "sms" | "other";

type RecallRow = {
  id: number;
  patient_id: number;
  first_name: string;
  last_name: string;
  phone?: string | null;
  recall_kind: RecallKind;
  due_date: string;
  status: RecallStatus;
  notes?: string | null;
  completed_at?: string | null;
  last_contacted_at?: string | null;
  last_contact_channel?: RecallContactChannel | null;
  last_contact_note?: string | null;
  last_contact_other_detail?: string | null;
  last_contact_outcome?: string | null;
};

const statusLabels: Record<RecallStatus, string> = {
  upcoming: "Upcoming",
  due: "Due",
  overdue: "Overdue",
  completed: "Completed",
  cancelled: "Cancelled",
};

const kindLabels: Record<RecallKind, string> = {
  exam: "Exam",
  hygiene: "Hygiene",
  perio: "Perio",
  implant: "Implant",
  custom: "Custom",
};

const statusOptions: { value: RecallStatus; label: string }[] = [
  { value: "due", label: "Due" },
  { value: "overdue", label: "Overdue" },
  { value: "upcoming", label: "Upcoming" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

const kindOptions: { value: RecallKind; label: string }[] = [
  { value: "exam", label: "Exam" },
  { value: "hygiene", label: "Hygiene" },
  { value: "perio", label: "Perio" },
  { value: "implant", label: "Implant" },
  { value: "custom", label: "Custom" },
];

const contactChannelOptions: { value: RecallContactChannel; label: string }[] = [
  { value: "letter", label: "Letter" },
  { value: "phone", label: "Phone" },
  { value: "email", label: "Email" },
  { value: "sms", label: "SMS" },
  { value: "other", label: "Other" },
];

const contactChannelLabels: Record<RecallContactChannel, string> = {
  letter: "Letter",
  phone: "Phone",
  email: "Email",
  sms: "SMS",
  other: "Other",
};

const recallsExportLocks = new Set<string>();
let recallsZipExportLocked = false;
const recallsZipExportListeners = new Set<() => void>();

function subscribeRecallsZipExportLock(listener: () => void) {
  recallsZipExportListeners.add(listener);
  return () => recallsZipExportListeners.delete(listener);
}

function getRecallsZipExportLockSnapshot() {
  return recallsZipExportLocked;
}

function setRecallsZipExportLocked(locked: boolean) {
  if (recallsZipExportLocked === locked) return;
  recallsZipExportLocked = locked;
  for (const listener of recallsZipExportListeners) {
    listener();
  }
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleDateString("en-GB");
}

function formatDateTime(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatDateInput(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

function addMonths(base: Date, months: number) {
  const year = base.getFullYear();
  const month = base.getMonth();
  const day = base.getDate();
  const next = new Date(year, month + months, 1);
  const lastDay = new Date(next.getFullYear(), next.getMonth() + 1, 0).getDate();
  next.setDate(Math.min(day, lastDay));
  return next;
}

export default function RecallsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<RecallRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [letterTarget, setLetterTarget] = useState<RecallRow | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const pageRef = useRef<HTMLDivElement>(null);
  const contactDialog = useRef<HTMLDialogElement>(null);
  const monthMenu = useRef<HTMLDetailsElement>(null);
  const [monthYear, setMonthYear] = useState(new Date().getFullYear());
  const [statusFilter, setStatusFilter] = useState<RecallStatus[]>([
    "due",
    "overdue",
  ]);
  const [typeFilter, setTypeFilter] = useState<RecallKind | "all">("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [contactState, setContactState] = useState<
    "all" | "never" | "contacted"
  >("all");
  const [lastContact, setLastContact] = useState<
    "all" | "7d" | "30d" | "older30d"
  >("all");
  const [contactMethod, setContactMethod] = useState<
    "all" | RecallContactChannel
  >("all");
  const [pageSize, setPageSize] = useState(50);
  const [offset, setOffset] = useState(0);
  const [actionId, setActionId] = useState<number | null>(null);
  const [downloadId, setDownloadId] = useState<number | null>(null);
  const [exporting, setExporting] = useState(false);
  const downloadingZip = useSyncExternalStore(
    subscribeRecallsZipExportLock,
    getRecallsZipExportLockSnapshot,
    getRecallsZipExportLockSnapshot
  );
  const [showContactModal, setShowContactModal] = useState(false);
  const [contactTarget, setContactTarget] = useState<RecallRow | null>(null);
  const [contactMethodInput, setContactMethodInput] =
    useState<RecallContactChannel>("phone");
  const [contactOtherDetail, setContactOtherDetail] = useState("");
  const [contactOutcome, setContactOutcome] = useState("");
  const [contactNote, setContactNote] = useState("");
  const [contactSaving, setContactSaving] = useState(false);
  const [contactError, setContactError] = useState<string | null>(null);
  const [exportCount, setExportCount] = useState<number | null>(null);
  const [exportCountLoading, setExportCountLoading] = useState(false);
  const [exportCountError, setExportCountError] = useState<string | null>(null);
  const [exportPageOnly, setExportPageOnly] = useState(false);
  const [suggestedFilenameCsv, setSuggestedFilenameCsv] = useState<string | null>(
    null
  );
  const [suggestedFilenameZip, setSuggestedFilenameZip] = useState<string | null>(
    null
  );
  const [capabilities, setCapabilities] = useState<string[] | null>(null);
  const [capabilityError, setCapabilityError] = useState<string | null>(null);
  const canViewRecalls = Boolean(capabilities?.includes("recalls.view"));
  const canWriteRecalls = Boolean(capabilities?.includes("recalls.write"));
  const canExportRecalls = Boolean(capabilities?.includes("recalls.export"));
  const canWriteAppointments = Boolean(
    capabilities?.includes("appointments.write")
  );
  const canViewPatients = Boolean(capabilities?.includes("patients.view"));

  useEffect(() => {
    const dialog = contactDialog.current;
    if (showContactModal && dialog && !dialog.open) dialog.showModal();
    if (!showContactModal && dialog?.open) dialog.close();
  }, [showContactModal]);

  useEffect(() => {
    function dismissMenus(event: PointerEvent | KeyboardEvent) {
      if (event instanceof KeyboardEvent && event.key !== "Escape") return;
      pageRef.current?.querySelectorAll<HTMLDetailsElement>("details[data-testid][open]").forEach((menu) => {
        // Filter/export panels stay open until explicitly closed; contextual
        // menus close on outside click or Escape without losing keyboard focus.
        if (["recalls-more-filters", "recalls-export-options", "recalls-more-actions", "recalls-month-menu", "recalls-status-menu"].includes(menu.dataset.testid || "")) {
          if (event instanceof PointerEvent && (menu.contains(event.target as Node) || ["recalls-more-filters", "recalls-export-options"].includes(menu.dataset.testid || ""))) return;
          if (event instanceof KeyboardEvent && menu.contains(document.activeElement)) menu.querySelector("summary")?.focus();
          menu.open = false;
        }
      });
    }
    document.addEventListener("pointerdown", dismissMenus);
    document.addEventListener("keydown", dismissMenus);
    return () => { document.removeEventListener("pointerdown", dismissMenus); document.removeEventListener("keydown", dismissMenus); };
  }, []);

  const selectedMonth = startDate && startDate.endsWith("-01") &&
    endDate === formatDateInput(new Date(Number(startDate.slice(0, 4)), Number(startDate.slice(5, 7)), 0))
      ? startDate.slice(0, 7) : "";
  const monthLabel = selectedMonth
    ? new Date(`${selectedMonth}-01T12:00:00`).toLocaleDateString("en-GB", { month: "long", year: "numeric" })
    : startDate || endDate ? "Custom date range" : "All dates";

  function selectMonth(year: number, month: number) {
    setStartDate(formatDateInput(new Date(year, month, 1)));
    setEndDate(formatDateInput(new Date(year, month + 1, 0)));
    setStatusFilter(["upcoming", "due", "overdue"]);
    if (monthMenu.current) {
      monthMenu.current.open = false;
      monthMenu.current.querySelector("summary")?.focus();
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function loadCapabilities() {
      setCapabilityError(null);
      try {
        const response = await apiFetch("/api/me/capabilities");
        if (response.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        if (!response.ok) throw new Error();
        const payload = (await response.json()) as string[];
        if (!cancelled) setCapabilities(payload);
      } catch {
        if (!cancelled) {
          setCapabilities([]);
          setCapabilityError(
            "Recall permissions could not be verified. Recall actions are blocked."
          );
        }
      }
    }
    void loadCapabilities();
    return () => {
      cancelled = true;
    };
  }, [router]);

  function handleBook(row: RecallRow) {
    if (!canWriteAppointments) return;
    const reason = `Recall: ${kindLabels[row.recall_kind]}`;
    const params = new URLSearchParams({
      book: "1",
      patientId: String(row.patient_id),
      reason,
      recallId: String(row.id),
    });
    router.push(`/appointments?${params.toString()}`);
  }

  const buildQueryParams = useCallback((options: { includePagination?: boolean } = {}) => {
    const { includePagination = true } = options;
    const params = new URLSearchParams();
    if (statusFilter.length > 0) {
      params.set("status", statusFilter.join(","));
    }
    if (typeFilter !== "all") {
      params.set("type", typeFilter);
    }
    if (startDate) {
      params.set("start", startDate);
    }
    if (endDate) {
      params.set("end", endDate);
    }
    if (contactState !== "all") {
      params.set("contact_state", contactState);
    }
    if (lastContact !== "all") {
      params.set("last_contact", lastContact);
    }
    if (contactMethod !== "all") {
      params.set("method", contactMethod);
    }
    if (includePagination) {
      params.set("limit", String(pageSize));
      params.set("offset", String(offset));
    }
    return params;
  }, [
    contactState,
    lastContact,
    contactMethod,
    endDate,
    offset,
    pageSize,
    startDate,
    statusFilter,
    typeFilter,
  ]);

  const exportCountLabel =
    exportCountLoading && exportCount === null
      ? "Calculating..."
      : exportCount !== null
        ? `${exportCount} recalls`
        : exportCountError
          ? "Count unavailable"
          : "—";
  const exportReady = !exportCountLoading && exportCountError === null;
  const fallbackFilenameCsv = buildExportFilename("csv");
  const fallbackFilenameZip = buildExportFilename("zip");
  const exportFilenameCsv = suggestedFilenameCsv ?? fallbackFilenameCsv;
  const exportFilenameZip = suggestedFilenameZip ?? fallbackFilenameZip;
  const errorText = error ?? "";
  const exportLimitMatch = errorText.match(/Too many recalls to export \((\d+)\)/);
  const exportLimitCount = exportLimitMatch ? Number(exportLimitMatch[1]) : exportCount;
  const showExportLimitHint = Boolean(exportLimitMatch);
  const showRecallsLoadHint =
    Boolean(errorText) &&
    (errorText.includes("Failed to load recalls") || errorText.includes("Internal server error"));

  function formatLastContact(row: RecallRow) {
    if (!row.last_contacted_at) return "—";
    const dateLabel = formatDate(row.last_contacted_at);
    if (row.last_contact_channel) {
      return `${contactChannelLabels[row.last_contact_channel]} · ${dateLabel}`;
    }
    return dateLabel;
  }

  function formatLastContactExtras(row: RecallRow) {
    const extras: string[] = [];
    const otherDetail = row.last_contact_other_detail?.trim();
    if (row.last_contact_channel === "other" && otherDetail) {
      extras.push(`Other: ${otherDetail}`);
    }
    const outcome = row.last_contact_outcome?.trim();
    if (outcome) {
      extras.push(`Outcome: ${outcome}`);
    }
    return extras;
  }

  function buildLastContactDetails(row: RecallRow) {
    if (!row.last_contacted_at) return [];
    const details = [
      `Date: ${formatDateTime(row.last_contacted_at)}`,
      `Method: ${row.last_contact_channel ? contactChannelLabels[row.last_contact_channel] : "—"}`,
    ];
    const otherDetail = row.last_contact_other_detail?.trim();
    if (row.last_contact_channel === "other" && otherDetail) {
      details.push(`Other detail: ${otherDetail}`);
    }
    const outcome = row.last_contact_outcome?.trim();
    if (outcome) {
      details.push(`Outcome: ${outcome}`);
    }
    const note = row.last_contact_note?.trim();
    if (note) {
      details.push(`Note: ${note}`);
    }
    return details;
  }

  function buildRecallFilename(row: RecallRow) {
    const rawName = `${row.last_name}_${row.first_name}`;
    const safeName = rawName.replace(/[^a-zA-Z0-9-_]+/g, "_");
    const date = row.due_date?.slice(0, 10) || new Date().toISOString().slice(0, 10);
    return `Recall_${safeName}_${date}.pdf`;
  }

  function sanitizeExportFilename(value: string, maxLength = 120) {
    return sanitizeRecallFilename(value, "recalls-export", maxLength);
  }

  function buildExportFilename(kind: "csv" | "zip") {
    const hasFilters = Boolean(
      startDate ||
        endDate ||
        statusFilter.length > 0 ||
        typeFilter !== "all" ||
        contactState !== "all" ||
        lastContact !== "all" ||
        contactMethod !== "all"
    );
    const suffixParts: string[] = [];
    if (hasFilters) {
      suffixParts.push("filtered");
    }
    if (exportPageOnly) {
      suffixParts.push("page");
    }
    const suffix = suffixParts.length > 0 ? `-${suffixParts.join("-")}` : "";
    const dateStamp = new Date().toISOString().slice(0, 10);
    if (kind === "zip") {
      return sanitizeExportFilename(`recall-letters-${dateStamp}${suffix}.zip`);
    }
    return sanitizeExportFilename(`recalls-${dateStamp}${suffix}.csv`);
  }

  function getFilenameFromDisposition(res: Response, fallback: string) {
    const header = res.headers.get("content-disposition");
    if (!header) return sanitizeRecallFilename(fallback, "recall-download");
    const match = /filename="?([^";]+)"?/i.exec(header);
    return sanitizeRecallFilename(match?.[1] || fallback, fallback);
  }

  async function downloadRecallLetter(
    row: RecallRow,
    button?: HTMLButtonElement | null
  ) {
    if (!canExportRecalls || !button || button.disabled) {
      return;
    }
    button.disabled = true;
    setDownloadId(row.id);
    setError(null);
    try {
      const res = await apiFetch(
        `/api/patients/${row.patient_id}/recalls/${row.id}/letter.pdf`
      );
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(
          await recallResponseError(res, "Failed to download recall letter.")
        );
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = getFilenameFromDisposition(res, buildRecallFilename(row));
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download recall letter");
    } finally {
      setDownloadId(null);
    }
  }

  async function exportCsv(button?: HTMLButtonElement | null) {
    if (
      !canExportRecalls ||
      !button ||
      exporting ||
      recallsExportLocks.has("csv") ||
      button.disabled
    ) {
      return;
    }
    recallsExportLocks.add("csv");
    button.disabled = true;
    setExporting(true);
    setError(null);
    setExportCountError(null);
    try {
      const params = buildQueryParams({ includePagination: exportPageOnly });
      if (exportPageOnly) {
        params.set("page_only", "true");
      }
      const res = await apiFetch(`/api/recalls/export.csv?${params.toString()}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(await recallResponseError(res, "Failed to export recalls CSV."));
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = getFilenameFromDisposition(
        res,
        exportFilenameCsv
      );
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to export CSV");
    } finally {
      recallsExportLocks.delete("csv");
      setExporting(false);
    }
  }

  async function downloadLettersZip(button?: HTMLButtonElement | null) {
    if (
      !canExportRecalls ||
      !button ||
      downloadingZip ||
      getRecallsZipExportLockSnapshot() ||
      button.disabled
    ) {
      return;
    }
    setRecallsZipExportLocked(true);
    button.disabled = true;
    setError(null);
    setExportCountError(null);
    try {
      const params = buildQueryParams({ includePagination: exportPageOnly });
      if (exportPageOnly) {
        params.set("page_only", "true");
      }
      const res = await apiFetch(`/api/recalls/letters.zip?${params.toString()}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(
          await recallResponseError(res, "Failed to download recall letters ZIP.")
        );
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = getFilenameFromDisposition(
        res,
        exportFilenameZip
      );
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download letters ZIP");
    } finally {
      setRecallsZipExportLocked(false);
    }
  }

  useEffect(() => {
    if (capabilities === null) return;
    if (!canViewRecalls) {
      setRows([]);
      setLoading(false);
      return;
    }
    let active = true;
    async function loadRecalls() {
      setLoading(true);
      setError(null);
      try {
        const params = buildQueryParams();
        const res = await apiFetch(`/api/recalls?${params.toString()}`);
        if (res.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        if (!res.ok) {
          throw new Error(await recallResponseError(res, "Failed to load recalls."));
        }
        const data = (await res.json()) as RecallRow[];
        if (active) {
          setRows(data);
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Failed to load recalls");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadRecalls();
    return () => {
      active = false;
    };
  }, [buildQueryParams, canViewRecalls, capabilities, router]);

  useEffect(() => {
    if (capabilities === null) return;
    if (!canViewRecalls || !canExportRecalls) {
      setExportCount(null);
      setExportCountLoading(false);
      setExportCountError(null);
      return;
    }
    let active = true;
    setSuggestedFilenameCsv(null);
    setSuggestedFilenameZip(null);
    setExportCountLoading(true);
    setExportCountError(null);
    const timer = setTimeout(() => {
      async function loadExportCount() {
        try {
          const params = buildQueryParams({ includePagination: exportPageOnly });
          if (exportPageOnly) {
            params.set("page_only", "true");
          }
          const res = await apiFetch(`/api/recalls/export_count?${params.toString()}`);
          if (res.status === 401) {
            clearToken();
            router.replace("/login");
            return;
          }
          if (!res.ok) {
            throw new Error(
              await recallResponseError(res, "Failed to load recall export count.")
            );
          }
          const data = (await res.json()) as {
            count: number;
            suggested_filename_csv?: string;
            suggested_filename_zip?: string;
          };
          if (active) {
            setExportCount(data.count);
            setSuggestedFilenameCsv(data.suggested_filename_csv ?? null);
            setSuggestedFilenameZip(data.suggested_filename_zip ?? null);
          }
        } catch (err) {
          if (active) {
            setExportCountError(
              err instanceof Error ? err.message : "Failed to load export count"
            );
          }
        } finally {
          if (active) {
            setExportCountLoading(false);
          }
        }
      }

      void loadExportCount();
    }, 200);

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [
    buildQueryParams,
    canExportRecalls,
    canViewRecalls,
    capabilities,
    exportPageOnly,
    refreshVersion,
    router,
  ]);

  useEffect(() => {
    setOffset(0);
  }, [
    statusFilter,
    typeFilter,
    startDate,
    endDate,
    contactState,
    lastContact,
    contactMethod,
    pageSize,
  ]);

  function toggleStatus(value: RecallStatus) {
    setStatusFilter((prev) => {
      if (prev.includes(value)) {
        return prev.filter((status) => status !== value);
      }
      return [...prev, value];
    });
  }

  async function updateRecall(
    row: RecallRow,
    payload: { status?: RecallStatus; due_date?: string; completed_at?: string | null },
    button?: HTMLButtonElement | null
  ) {
    if (!canWriteRecalls || actionId === row.id || button?.disabled) {
      return;
    }
    if (button) button.disabled = true;
    setActionId(row.id);
    setError(null);
    try {
      const res = await apiFetch(`/api/patients/${row.patient_id}/recalls/${row.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(await recallResponseError(res, "Failed to update recall."));
      }
      await refreshRecalls();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update recall");
    } finally {
      setActionId(null);
    }
  }

  async function refreshRecalls() {
    const params = buildQueryParams();
    const refresh = await apiFetch(`/api/recalls?${params.toString()}`);
    if (refresh.status === 401) {
      clearToken();
      router.replace("/login");
      return;
    }
    if (refresh.ok) {
      setRows((await refresh.json()) as RecallRow[]);
      setRefreshVersion((value) => value + 1);
    } else {
      throw new Error(await recallResponseError(refresh, "Failed to refresh recalls."));
    }
  }

  function handleComplete(row: RecallRow, button?: HTMLButtonElement | null) {
    void updateRecall(
      row,
      {
        status: "completed",
        completed_at: new Date().toISOString(),
      },
      button
    );
  }

  function handleSnooze(row: RecallRow, months: number) {
    const base = row.due_date ? new Date(row.due_date) : new Date();
    const next = addMonths(base, months);
    void updateRecall(row, {
      status: "upcoming",
      due_date: formatDateInput(next),
      completed_at: null,
    });
  }

  function resetFilters() {
    setStatusFilter(["due", "overdue"]);
    setTypeFilter("all");
    setStartDate("");
    setEndDate("");
    setContactState("all");
    setLastContact("all");
    setContactMethod("all");
  }

  function openContactModal(row: RecallRow) {
    if (!canWriteRecalls) return;
    setContactTarget(row);
    setContactMethodInput("phone");
    setContactOtherDetail("");
    setContactOutcome("");
    setContactNote("");
    setContactError(null);
    setShowContactModal(true);
  }

  async function saveContact(button?: HTMLButtonElement | null) {
    if (
      !canWriteRecalls ||
      !contactTarget ||
      !button ||
      contactSaving ||
      button.disabled ||
      otherDetailRequired
    ) {
      return;
    }
    button.disabled = true;
    setContactSaving(true);
    setContactError(null);
    try {
      const res = await apiFetch(`/api/recalls/${contactTarget.id}/contact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          method: contactMethodInput,
          other_detail: contactOtherDetail.trim() || null,
          outcome: contactOutcome.trim() || null,
          note: contactNote.trim() || null,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(await recallResponseError(res, "Failed to log recall contact."));
      }
      setShowContactModal(false);
      await refreshRecalls();
    } catch (err) {
      setContactError(err instanceof Error ? err.message : "Failed to log contact");
    } finally {
      setContactSaving(false);
    }
  }

  const otherDetailRequired =
    contactMethodInput === "other" && contactOtherDetail.trim().length === 0;

  if (capabilities === null) {
    return <div className="badge">Checking recall permissions…</div>;
  }

  if (!canViewRecalls) {
    return (
      <div className="stack" data-testid="recalls-page">
        <h2 style={{ marginTop: 0 }}>Recalls</h2>
        <div className="notice">
          {capabilityError || "You do not have permission to view recalls."}
        </div>
      </div>
    );
  }

  return (
    <div ref={pageRef} className={styles.page} data-testid="recalls-page">
      <header className={styles.heading}>
        <div><h1>Recall call list</h1><p>Patients to follow up, with everything you need close at hand.</p></div>
        {canExportRecalls && <div className={styles.headerActions}>
          <button className={styles.button} type="button"
            onClick={(event) => void exportCsv(event.currentTarget)}
            disabled={!exportReady || exporting || downloadingZip}
            data-testid="recalls-export-csv">
            <Icon name="reports" />{exporting ? "Exporting..." : exportCountLoading ? "Preparing..." : exportCountError ? "Export unavailable" : "Export CSV"}
          </button>
          <details className={styles.dropdown} data-testid="recalls-export-options">
            <summary className={styles.button} aria-label="Export and print options">•••</summary>
            <div className={styles.exportPanel}>
              <strong data-testid="recalls-export-summary">Export will include: {exportCountLabel}{exportPageOnly ? ` (this page: ${rows.length})` : ""}</strong>
              <p data-testid="recalls-export-hint">Exports include active filters and the page toggle.</p>
              <label className={styles.check}><input type="checkbox" checked={exportPageOnly}
                onChange={(event) => setExportPageOnly(event.target.checked)} data-testid="recalls-export-page-only" />Export this page only</label>
              <button className={styles.button} type="button"
                onClick={(event) => void downloadLettersZip(event.currentTarget)}
                disabled={!exportReady || downloadingZip || exporting} data-testid="recalls-export-zip">
                {downloadingZip ? "Preparing..." : "Download letters (ZIP)"}
              </button>
              <button className={styles.button} type="button" onClick={() => window.print()}>Print this call-list page</button>
              <small data-testid="recalls-export-filename-csv">CSV filename: {exportFilenameCsv}</small>
              <small data-testid="recalls-export-filename-zip">ZIP filename: {exportFilenameZip}</small>
              <small>Generating letters does not record them as sent. Large lists may take a moment.</small>
            </div>
          </details>
        </div>}
      </header>

      {!canWriteRecalls && <div className="notice" data-testid="recalls-read-only-notice">You can view recalls, but you cannot change them.</div>}
      {capabilityError && <div className="notice">{capabilityError}</div>}

      {/* Summary counts come from the whole native recall register, not this paginated list. */}
      <RecallSummary refreshKey={rows} />

      <section className={styles.filters} aria-label="Recall filters" data-testid="recalls-filters">
        <div className={styles.field}>
          <span className={styles.label}>Month</span>
          <details ref={monthMenu} className={styles.dropdown} data-testid="recalls-month-menu"
            onKeyDown={(event) => { if (event.key === "Escape" && monthMenu.current) { monthMenu.current.open = false; monthMenu.current.querySelector("summary")?.focus(); } }}>
            <summary className={styles.control}><Icon name="calendar" />{monthLabel}<span className={styles.chevron}>⌄</span></summary>
            <div className={styles.monthPanel}>
              <div className={styles.monthHeading}>
                <button className={styles.iconButton} aria-label="Previous year" onClick={() => setMonthYear((year) => Math.max(1900, year - 1))}>‹</button>
                <strong>{monthYear}</strong>
                <button className={styles.iconButton} aria-label="Next year" onClick={() => setMonthYear((year) => Math.min(9998, year + 1))}>›</button>
              </div>
              <div className={styles.monthGrid}>{Array.from({ length: 12 }, (_, month) => (
                <button key={month} type="button" aria-pressed={selectedMonth === `${monthYear}-${String(month + 1).padStart(2, "0")}`}
                  onClick={() => selectMonth(monthYear, month)}>
                  {new Date(2026, month, 1).toLocaleDateString("en-GB", { month: "short" })}
                </button>
              ))}</div>
              <div className={styles.monthHeading}>
                <button className={styles.textButton} onClick={() => { const today = new Date(); setMonthYear(today.getFullYear()); selectMonth(today.getFullYear(), today.getMonth()); }}>This month</button>
                <button className={styles.textButton} onClick={() => { setStartDate(""); setEndDate(""); if (monthMenu.current) { monthMenu.current.open = false; monthMenu.current.querySelector("summary")?.focus(); } }}>All dates</button>
              </div>
            </div>
          </details>
        </div>
        <label className={styles.field}><span className={styles.label}>Reason</span>
          <select className={styles.control} data-testid="recalls-filter-type" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as RecallKind | "all")}>
            <option value="all">Any reason</option>
            {kindOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
        <div className={styles.field}><span className={styles.label}>Status</span>
          <details className={styles.dropdown} data-testid="recalls-status-menu">
            <summary className={styles.control}>{statusFilter.length === 0 ? "Any status" : statusFilter.map((s) => statusLabels[s]).join(", ")}<span className={styles.chevron}>⌄</span></summary>
            <div className={styles.menuPanel}>
              {statusOptions.map((option) => <label className={styles.check} key={option.value}>
                <input type="checkbox" checked={statusFilter.includes(option.value)} onChange={() => toggleStatus(option.value)} />{option.label}
              </label>)}
              <button className={styles.textButton} onClick={() => setStatusFilter([])}>Any status</button>
            </div>
          </details>
        </div>
        <label className={styles.field}><span className={styles.label}>Contact state</span>
          <select className={styles.control} data-testid="recalls-filter-contact-state" value={contactState} onChange={(e) => setContactState(e.target.value as "all" | "never" | "contacted")}>
            <option value="all">Any contact state</option><option value="never">Never contacted</option><option value="contacted">Contacted</option>
          </select>
        </label>
        <details className={styles.moreFilters} data-testid="recalls-more-filters">
          <summary className={styles.button}><Icon name="settings" />More filters{startDate || endDate || lastContact !== "all" || contactMethod !== "all" ? " •" : ""}</summary>
          <div className={styles.filterPanel}>
            <label className={styles.field}><span className={styles.label}>Due from</span><input className={styles.control} type="date" data-testid="recalls-filter-start-date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></label>
            <label className={styles.field}><span className={styles.label}>Due to</span><input className={styles.control} type="date" data-testid="recalls-filter-end-date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></label>
            <label className={styles.field}><span className={styles.label}>Last contact</span>
              <select className={styles.control} data-testid="recalls-filter-last-contact" value={lastContact} onChange={(e) => setLastContact(e.target.value as "all" | "7d" | "30d" | "older30d")}>
                <option value="all">Any time</option><option value="7d">Last 7 days</option><option value="30d">Last 30 days</option><option value="older30d">Older than 30 days</option>
              </select>
            </label>
            <label className={styles.field}><span className={styles.label}>Method</span>
              <select className={styles.control} data-testid="recalls-filter-method" value={contactMethod} onChange={(e) => setContactMethod(e.target.value as "all" | RecallContactChannel)}>
                <option value="all">All methods</option>{contactChannelOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <p className={styles.filterHelp}>Dates and statuses apply together. Choose All dates to include earlier overdue recalls. Priority is not recorded in the PMS yet.</p>
          </div>
        </details>
        <button className={styles.textButton} type="button" onClick={resetFilters} data-testid="recalls-reset-filters">Reset filters</button>
      </section>

      <div className={styles.listCaption}>
        <span>{loading ? "Loading recalls…" : `${rows.length} recalls on this page`}{!loading && statusFilter.length === 0 ? " · all statuses" : ""}</span>
        <label className={styles.pageSize}>Per page
          <select value={String(pageSize)} onChange={(e) => setPageSize(Number(e.target.value))}>
            {[25, 50, 100, 200].map((size) => <option key={size} value={String(size)}>{size}</option>)}
          </select>
        </label>
      </div>
      {error && <div className="notice" role="alert">{error}
        {showExportLimitHint && <p>Try narrowing by contact state, last contact or method.{typeof exportLimitCount === "number" ? ` Current matches: ${exportLimitCount}.` : ""}</p>}
        {showRecallsLoadHint && <button className={styles.button} onClick={() => void refreshRecalls().then(() => setError(null)).catch(() => setError("Failed to load recalls. Please try again."))}>Refresh</button>}
      </div>}
      {loading ? <div className={styles.empty} role="status">Loading recalls…</div> : rows.length === 0 ? (
        <div className={styles.empty}><Icon name="history" size={28} /><strong>No recalls match your filters.</strong><button className={styles.textButton} onClick={resetFilters}>Clear filters</button></div>
      ) : (
        <Table className={styles.callList}>
          <caption className={styles.srOnly}>Recall patients and follow-up actions</caption>
          <thead className={styles.srOnly}><tr><th scope="col">Patient and recall</th><th scope="col">Actions</th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} data-testid="recalls-row">
                <td>
                  <div className={styles.patientLine}>
                    <span className={styles.avatar} aria-hidden="true">{row.first_name.slice(0, 1)}{row.last_name.slice(0, 1)}</span>
                    {canViewPatients ? <Link className={styles.patientName} href={`/patients/${row.patient_id}?tab=recalls`} data-testid="recalls-patient-navigation">{row.last_name.toUpperCase()}, {row.first_name}</Link> : <strong>{row.last_name.toUpperCase()}, {row.first_name}</strong>}
                    <span className={styles.kindBadge}>{kindLabels[row.recall_kind]}</span>
                    <span className={`${styles.statusBadge} ${row.status === "overdue" ? styles.overdue : row.status === "completed" ? styles.completed : ""}`}>{statusLabels[row.status]}</span>
                  </div>
                  <div className={styles.patientMeta}><span>Due {formatDate(row.due_date)}</span><span><Icon name="phone" size={13} />{row.phone || "No phone recorded"}</span></div>
                  {row.notes && <details className={styles.recallNote}><summary title={row.notes}>{row.notes}</summary><p>{row.notes}</p></details>}
                  <div data-testid="recalls-last-contact" className={styles.contactLine}>
                    {row.last_contacted_at ? (
                      <details><summary><Icon name="history" size={13} />Last contact: {formatLastContact(row)}</summary>
                        <div className={styles.contactDetails}>{buildLastContactDetails(row).map((detail, index) => <div key={index}>{detail}</div>)}</div>
                      </details>
                    ) : <span>Not contacted</span>}
                    {formatLastContactExtras(row).map((text, index) => <span key={index}>{text}</span>)}
                  </div>
                </td>
                <td className={styles.actions}>
                  <div className={styles.rowActions}>
                    {canExportRecalls && <button className={`${styles.button} ${styles.primary}`} type="button" data-testid={`recalls-letter-${row.id}`} onClick={() => setLetterTarget(row)}><Icon name="notes" />Recall letter</button>}
                    {canWriteRecalls && <button className={styles.button} type="button" onClick={() => openContactModal(row)} disabled={contactSaving && contactTarget?.id === row.id}><Icon name="phone" />Log contact</button>}
                    {canWriteAppointments && <button className={styles.iconButton} type="button" aria-label="Book appointment" title="Book appointment" data-testid="recalls-book-action" disabled={actionId === row.id} onClick={() => handleBook(row)}><Icon name="calendar" size={18} /></button>}
                    {(canWriteRecalls || canExportRecalls) && <details className={styles.dropdown} data-testid="recalls-more-actions">
                      <summary className={styles.iconButton} aria-label={`More recall actions for ${row.first_name} ${row.last_name}`}>•••</summary>
                      <div className={styles.actionPanel}>
                        {canExportRecalls && <button className={styles.menuButton} data-testid={`recalls-generate-letter-${row.id}`} disabled={downloadId === row.id} onClick={(event) => void downloadRecallLetter(row, event.currentTarget)}>{downloadId === row.id ? "Generating..." : "Generate letter"}</button>}
                        {canWriteRecalls && <div className={styles.mutationControls} data-testid="recalls-mutation-controls">
                          <button className={styles.menuButton} data-testid={`recalls-complete-${row.id}`} disabled={actionId === row.id || row.status === "completed" || row.status === "cancelled"}
                            onClick={(event) => handleComplete(row, event.currentTarget)}>{actionId === row.id ? "Updating..." : "Mark completed"}</button>
                          {[3, 6, 12].map((months) => <button className={styles.menuButton} key={months} disabled={actionId === row.id} onClick={() => handleSnooze(row, months)}>Snooze {months}m</button>)}
                        </div>}
                      </div>
                    </details>}
                    {!canWriteRecalls && !canWriteAppointments && !canExportRecalls && <span className={styles.muted}>View only</span>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <nav className={styles.pagination} aria-label="Recall pages" data-testid="recalls-pagination">
        <span>Showing {rows.length === 0 ? 0 : offset + 1}-{offset + rows.length}</span>
        <button className={styles.button} type="button" onClick={() => setOffset((prev) => Math.max(0, prev - pageSize))} disabled={offset === 0 || loading}>Prev</button>
        <button className={styles.button} type="button" onClick={() => setOffset((prev) => prev + pageSize)} disabled={rows.length < pageSize || loading}>Next</button>
      </nav>
      {letterTarget && canExportRecalls && <RecallLetterDialog patientId={letterTarget.patient_id} recallId={letterTarget.id} patientName={`${letterTarget.first_name} ${letterTarget.last_name}`} onClose={() => setLetterTarget(null)} />}
      {showContactModal && canWriteRecalls && (
        <dialog ref={contactDialog} className={styles.contactDialog} aria-labelledby="recall-contact-title" onCancel={(event) => { event.preventDefault(); if (!contactSaving) setShowContactModal(false); }}>
          <div className="stack">
            <div className="row">
              <div>
                <h3 id="recall-contact-title" style={{ marginTop: 0 }}>Log contact</h3>
                <p style={{ color: "var(--muted)" }}>
                  {contactTarget
                    ? `${contactTarget.last_name.toUpperCase()}, ${
                        contactTarget.first_name
                      } · Due ${formatDate(contactTarget.due_date)}`
                    : "Recall contact"}
                </p>
              </div>
              <button
                className="btn btn-secondary"
                type="button"
                disabled={contactSaving}
                onClick={() => setShowContactModal(false)}
              >
                Close
              </button>
            </div>
            {contactError && <div className="notice">{contactError}</div>}
            <div
              className={styles.contactFields}
            >
              <div className="stack" style={{ gap: 8 }}>
                <label className="label" htmlFor="recall-contact-method">Method</label>
                <select
                  className="input"
                  id="recall-contact-method"
                  value={contactMethodInput}
                  onChange={(e) =>
                    setContactMethodInput(e.target.value as RecallContactChannel)
                  }
                >
                  {contactChannelOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="stack" style={{ gap: 8 }}>
                <label className="label" htmlFor="recall-contact-outcome">Outcome</label>
                <input
                  className="input"
                  id="recall-contact-outcome"
                  value={contactOutcome}
                  onChange={(e) => setContactOutcome(e.target.value)}
                  placeholder="Optional outcome"
                  maxLength={250}
                />
              </div>
              {contactMethodInput === "other" && (
                <div className="stack" style={{ gap: 8, gridColumn: "1 / -1" }}>
                  <label className="label" htmlFor="recall-contact-other">Other detail</label>
                  <input
                    className="input"
                    id="recall-contact-other"
                    value={contactOtherDetail}
                    onChange={(e) => setContactOtherDetail(e.target.value)}
                    placeholder="e.g. WhatsApp"
                    maxLength={120}
                  />
                  <p style={{ color: "var(--muted)", margin: 0 }}>
                    Required when method is Other.
                  </p>
                </div>
              )}
              <div className="stack" style={{ gap: 8, gridColumn: "1 / -1" }}>
                <label className="label" htmlFor="recall-contact-note">Note</label>
                <textarea
                  className="input"
                  id="recall-contact-note"
                  rows={3}
                  value={contactNote}
                  onChange={(e) => setContactNote(e.target.value)}
                  placeholder="Optional note"
                  maxLength={2000}
                />
              </div>
            </div>
            <button
              className="btn btn-primary"
              type="button"
              data-testid="recalls-contact-save"
              onClick={(event) => void saveContact(event.currentTarget)}
              disabled={contactSaving || !contactTarget || otherDetailRequired}
            >
              {contactSaving ? "Saving..." : "Save log"}
            </button>
          </div>
        </dialog>
      )}
      <style jsx global>{`
        @media print {
          .app-top,
          .print-hidden,
          .recall-actions,
          .table-actions {
            display: none !important;
          }
          .app-shell {
            background: #fff;
          }
          .recall-table th,
          .recall-table td {
            padding: 4px 6px;
          }
          .badge {
            border: none;
            padding: 0;
          }
        }
      `}</style>
    </div>
  );
}
