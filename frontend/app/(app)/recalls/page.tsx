"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import Table from "@/components/ui/Table";

type RecallStatus = "upcoming" | "due" | "overdue" | "completed" | "cancelled";
type RecallKind = "exam" | "hygiene" | "perio" | "implant" | "custom";

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
  const [actionId, setActionId] = useState<number | null>(null);
  const [downloadId, setDownloadId] = useState<number | null>(null);
  const [exporting, setExporting] = useState(false);
  const [downloadingZip, setDownloadingZip] = useState(false);

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
    return params;
  }, [endDate, startDate, statusFilter, typeFilter]);

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
      const params = buildQueryParams();
      const refresh = await apiFetch(`/api/recalls?${params.toString()}`);
      if (refresh.ok) {
        setRows((await refresh.json()) as RecallRow[]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update recall");
    } finally {
      setActionId(null);
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
          <div className="row recall-toolbar">
            <div className="badge">{rows.length} recalls</div>
            <button
              className="btn btn-secondary"
              type="button"
              onClick={() => {
                setStatusFilter(["due", "overdue"]);
                setTypeFilter("all");
                setStartDate("");
                setEndDate("");
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
