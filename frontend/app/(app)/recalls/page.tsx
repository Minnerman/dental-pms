"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import Table from "@/components/ui/Table";

type RecallStatus = "upcoming" | "due" | "overdue" | "completed" | "cancelled";
type RecallKind = "exam" | "hygiene" | "perio" | "implant" | "custom";
type RecallContactChannel = "letter" | "phone" | "email" | "sms" | "other";

type RecallRow = {
  id: number;
  patient_id: number;
  first_name: string;
  last_name: string;
  recall_kind: RecallKind;
  due_date: string;
  status: RecallStatus;
  notes?: string | null;
  completed_at?: string | null;
  last_contacted_at?: string | null;
  last_contact_channel?: RecallContactChannel | null;
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

function formatDate(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleDateString("en-GB");
}

function formatDateInput(value: Date) {
  return value.toISOString().slice(0, 10);
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
  const [downloadingZip, setDownloadingZip] = useState(false);
  const [showContactModal, setShowContactModal] = useState(false);
  const [contactTarget, setContactTarget] = useState<RecallRow | null>(null);
  const [contactMethodInput, setContactMethodInput] =
    useState<RecallContactChannel>("phone");
  const [contactOutcome, setContactOutcome] = useState("");
  const [contactNote, setContactNote] = useState("");
  const [contactSaving, setContactSaving] = useState(false);
  const [contactError, setContactError] = useState<string | null>(null);

  function handleBook(row: RecallRow) {
    const reason = `Recall: ${kindLabels[row.recall_kind]}`;
    const params = new URLSearchParams({
      book: "1",
      patientId: String(row.patient_id),
      reason,
      recallId: String(row.id),
    });
    router.push(`/appointments?${params.toString()}`);
  }

  const buildQueryParams = useCallback(() => {
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
    params.set("limit", String(pageSize));
    params.set("offset", String(offset));
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

  function formatLastContact(row: RecallRow) {
    if (!row.last_contacted_at) return "—";
    const dateLabel = formatDate(row.last_contacted_at);
    if (row.last_contact_channel) {
      return `${contactChannelLabels[row.last_contact_channel]} · ${dateLabel}`;
    }
    return dateLabel;
  }

  function buildRecallFilename(row: RecallRow) {
    const rawName = `${row.last_name}_${row.first_name}`;
    const safeName = rawName.replace(/[^a-zA-Z0-9-_]+/g, "_");
    const date = row.due_date?.slice(0, 10) || new Date().toISOString().slice(0, 10);
    return `Recall_${safeName}_${date}.pdf`;
  }

  async function downloadRecallLetter(row: RecallRow) {
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
        const msg = await res.text();
        throw new Error(msg || `Failed to download letter (HTTP ${res.status})`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = buildRecallFilename(row);
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

  async function exportCsv() {
    setExporting(true);
    setError(null);
    try {
      const params = buildQueryParams();
      const res = await apiFetch(`/api/recalls/export.csv?${params.toString()}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to export CSV (HTTP ${res.status})`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `recalls-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to export CSV");
    } finally {
      setExporting(false);
    }
  }

  async function downloadLettersZip() {
    setDownloadingZip(true);
    setError(null);
    try {
      const params = buildQueryParams();
      const res = await apiFetch(`/api/recalls/letters.zip?${params.toString()}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to download ZIP (HTTP ${res.status})`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `recall-letters-${new Date().toISOString().slice(0, 10)}.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download letters ZIP");
    } finally {
      setDownloadingZip(false);
    }
  }

  useEffect(() => {
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
          const msg = await res.text();
          throw new Error(msg || `Failed to load recalls (HTTP ${res.status})`);
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
  }, [buildQueryParams, router]);

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
    payload: { status?: RecallStatus; due_date?: string; completed_at?: string | null }
  ) {
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
        const msg = await res.text();
        throw new Error(msg || `Failed to update recall (HTTP ${res.status})`);
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
    } else {
      const msg = await refresh.text();
      throw new Error(msg || `Failed to refresh recalls (HTTP ${refresh.status})`);
    }
  }

  function handleComplete(row: RecallRow) {
    void updateRecall(row, {
      status: "completed",
      completed_at: new Date().toISOString(),
    });
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

  function openContactModal(row: RecallRow) {
    setContactTarget(row);
    setContactMethodInput("phone");
    setContactOutcome("");
    setContactNote("");
    setContactError(null);
    setShowContactModal(true);
  }

  async function saveContact() {
    if (!contactTarget) return;
    setContactSaving(true);
    setContactError(null);
    try {
      const res = await apiFetch(`/api/recalls/${contactTarget.id}/contact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          method: contactMethodInput,
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
        const msg = await res.text();
        throw new Error(msg || `Failed to log contact (HTTP ${res.status})`);
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
    contactMethodInput === "other" && contactNote.trim().length === 0;

  return (
    <div className="stack">
      <div className="row" style={{ alignItems: "center" }}>
        <div>
          <h2 style={{ marginTop: 0 }}>Recalls</h2>
          <p style={{ color: "var(--muted)", margin: 0 }}>
            Due and overdue recalls with quick actions.
          </p>
        </div>
      </div>

      <div className="card print-hidden" style={{ margin: 0 }}>
        <div className="stack">
          <div className="grid grid-3">
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Status</label>
              <div className="stack" style={{ gap: 6 }}>
                {statusOptions.map((option) => (
                  <label
                    key={option.value}
                    style={{ display: "flex", gap: 8, alignItems: "center" }}
                  >
                    <input
                      type="checkbox"
                      checked={statusFilter.includes(option.value)}
                      onChange={() => toggleStatus(option.value)}
                    />
                    {option.label}
                  </label>
                ))}
              </div>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Recall type</label>
              <select
                className="input"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value as RecallKind | "all")}
              >
                <option value="all">All types</option>
                {kindOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Due date range</label>
              <div style={{ display: "grid", gap: 8 }}>
                <input
                  className="input"
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                />
                <input
                  className="input"
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                />
              </div>
            </div>
          </div>
          <div className="grid grid-3">
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Contact state</label>
              <select
                className="input"
                value={contactState}
                onChange={(e) =>
                  setContactState(e.target.value as "all" | "never" | "contacted")
                }
              >
                <option value="all">All</option>
                <option value="never">Never contacted</option>
                <option value="contacted">Contacted</option>
              </select>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Last contact</label>
              <select
                className="input"
                value={lastContact}
                onChange={(e) =>
                  setLastContact(
                    e.target.value as "all" | "7d" | "30d" | "older30d"
                  )
                }
              >
                <option value="all">All</option>
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
                <option value="older30d">Older than 30 days</option>
              </select>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Method</label>
              <select
                className="input"
                value={contactMethod}
                onChange={(e) =>
                  setContactMethod(e.target.value as "all" | RecallContactChannel)
                }
              >
                <option value="all">All methods</option>
                {contactChannelOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="row recall-toolbar">
            <div className="badge">{rows.length} recalls</div>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="label" style={{ margin: 0 }}>
                Per page
              </span>
              <select
                className="input"
                value={String(pageSize)}
                onChange={(e) => setPageSize(Number(e.target.value))}
              >
                {[25, 50, 100, 200].map((size) => (
                  <option key={size} value={String(size)}>
                    {size}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="btn btn-secondary"
              type="button"
              onClick={() => {
                setStatusFilter(["due", "overdue"]);
                setTypeFilter("all");
                setStartDate("");
                setEndDate("");
                setContactState("all");
                setLastContact("all");
                setContactMethod("all");
              }}
            >
              Reset filters
            </button>
            <button
              className="btn btn-secondary"
              type="button"
              onClick={() => void exportCsv()}
              disabled={exporting}
            >
              {exporting ? "Exporting..." : "Export CSV"}
            </button>
            <button
              className="btn btn-secondary"
              type="button"
              onClick={() => void downloadLettersZip()}
              disabled={downloadingZip}
            >
              {downloadingZip ? "Preparing..." : "Download letters (ZIP)"}
            </button>
            <button
              className="btn btn-secondary"
              type="button"
              onClick={() => window.print()}
            >
              Print
            </button>
          </div>
          <div className="row">
            <div className="badge">
              Showing {offset + 1}-{offset + rows.length}
            </div>
            <button
              className="btn btn-secondary"
              type="button"
              onClick={() => setOffset((prev) => Math.max(0, prev - pageSize))}
              disabled={offset === 0}
            >
              Prev
            </button>
            <button
              className="btn btn-secondary"
              type="button"
              onClick={() => setOffset((prev) => prev + pageSize)}
              disabled={rows.length < pageSize}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {error && <div className="notice">{error}</div>}
      {loading ? (
        <div className="badge">Loading recalls…</div>
      ) : rows.length === 0 ? (
        <div className="notice">No recalls found.</div>
      ) : (
        <>
          <Table className="recall-table">
            <thead>
              <tr>
                <th>Patient</th>
                <th>Type</th>
                <th>Due date</th>
                <th>Status</th>
                <th>Last contact</th>
                <th>Notes</th>
                <th className="recall-actions">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <Link href={`/patients/${row.patient_id}?tab=recalls`}>
                      {row.last_name.toUpperCase()}, {row.first_name}
                    </Link>
                  </td>
                  <td>{kindLabels[row.recall_kind]}</td>
                  <td>{formatDate(row.due_date)}</td>
                  <td>
                    <span className="badge">{statusLabels[row.status]}</span>
                  </td>
                  <td>{formatLastContact(row)}</td>
                  <td title={row.notes || ""}>
                    <span
                      style={{
                        display: "inline-block",
                        maxWidth: 220,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {row.notes || "—"}
                    </span>
                  </td>
                  <td className="recall-actions">
                    <div className="table-actions">
                      <button
                        className="btn btn-secondary"
                        type="button"
                        disabled={actionId === row.id}
                        onClick={() => handleBook(row)}
                      >
                        Book appointment
                      </button>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        disabled={downloadId === row.id}
                        onClick={() => void downloadRecallLetter(row)}
                      >
                        {downloadId === row.id ? "Generating..." : "Generate letter"}
                      </button>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        disabled={contactSaving && contactTarget?.id === row.id}
                        onClick={() => openContactModal(row)}
                      >
                        Log contact
                      </button>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        disabled={
                          actionId === row.id ||
                          row.status === "completed" ||
                          row.status === "cancelled"
                        }
                        onClick={() => handleComplete(row)}
                      >
                        {actionId === row.id ? "Updating..." : "Mark completed"}
                      </button>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        disabled={actionId === row.id}
                        onClick={() => handleSnooze(row, 3)}
                      >
                        Snooze 3m
                      </button>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        disabled={actionId === row.id}
                        onClick={() => handleSnooze(row, 6)}
                      >
                        Snooze 6m
                      </button>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        disabled={actionId === row.id}
                        onClick={() => handleSnooze(row, 12)}
                      >
                        Snooze 12m
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
          <div className="recall-cards print-hidden">
            {rows.map((row) => (
              <div className="card recall-card" key={row.id}>
                <div className="row">
                  <div>
                    <Link href={`/patients/${row.patient_id}?tab=recalls`}>
                      <strong>
                        {row.last_name.toUpperCase()}, {row.first_name}
                      </strong>
                    </Link>
                    <div style={{ color: "var(--muted)" }}>
                      {kindLabels[row.recall_kind]} · Due {formatDate(row.due_date)}
                    </div>
                  </div>
                  <span className="badge">{statusLabels[row.status]}</span>
                </div>
                <div style={{ color: "var(--muted)" }}>
                  Last contact {formatLastContact(row)}
                </div>
                <div>{row.notes || "No notes."}</div>
                <div className="row">
                  <button
                    className="btn btn-secondary"
                    type="button"
                    disabled={actionId === row.id}
                    onClick={() => handleBook(row)}
                  >
                    Book appointment
                  </button>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    disabled={downloadId === row.id}
                    onClick={() => void downloadRecallLetter(row)}
                  >
                    {downloadId === row.id ? "Generating..." : "Generate letter"}
                  </button>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    disabled={contactSaving && contactTarget?.id === row.id}
                    onClick={() => openContactModal(row)}
                  >
                    Log contact
                  </button>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    disabled={
                      actionId === row.id ||
                      row.status === "completed" ||
                      row.status === "cancelled"
                    }
                    onClick={() => handleComplete(row)}
                  >
                    {actionId === row.id ? "Updating..." : "Mark completed"}
                  </button>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    disabled={actionId === row.id}
                    onClick={() => handleSnooze(row, 3)}
                  >
                    Snooze 3m
                  </button>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    disabled={actionId === row.id}
                    onClick={() => handleSnooze(row, 6)}
                  >
                    Snooze 6m
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
      {showContactModal && (
        <div className="card" style={{ margin: 0 }}>
          <div className="stack">
            <div className="row">
              <div>
                <h3 style={{ marginTop: 0 }}>Log contact</h3>
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
                onClick={() => setShowContactModal(false)}
              >
                Close
              </button>
            </div>
            {contactError && <div className="notice">{contactError}</div>}
            <div
              style={{
                display: "grid",
                gap: 12,
                gridTemplateColumns: "1fr 1fr",
              }}
            >
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Method</label>
                <select
                  className="input"
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
                <label className="label">Outcome</label>
                <input
                  className="input"
                  value={contactOutcome}
                  onChange={(e) => setContactOutcome(e.target.value)}
                  placeholder="Optional outcome"
                />
              </div>
              <div className="stack" style={{ gap: 8, gridColumn: "1 / -1" }}>
                <label className="label">
                  {contactMethodInput === "other" ? "Other detail" : "Note"}
                </label>
                <textarea
                  className="input"
                  rows={3}
                  value={contactNote}
                  onChange={(e) => setContactNote(e.target.value)}
                  placeholder={
                    contactMethodInput === "other"
                      ? "e.g. WhatsApp"
                      : "Optional note"
                  }
                />
                {contactMethodInput === "other" && (
                  <p style={{ color: "var(--muted)", margin: 0 }}>
                    Required when method is Other.
                  </p>
                )}
              </div>
            </div>
            <button
              className="btn btn-primary"
              type="button"
              onClick={saveContact}
              disabled={contactSaving || !contactTarget || otherDetailRequired}
            >
              {contactSaving ? "Saving..." : "Save log"}
            </button>
          </div>
        </div>
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
