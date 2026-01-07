"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";

type RecallStatus = "due" | "contacted" | "booked" | "not_required";

type RecallRow = {
  id: number;
  first_name: string;
  last_name: string;
  phone?: string | null;
  postcode?: string | null;
  recall_interval_months?: number | null;
  recall_due_date?: string | null;
  recall_status?: RecallStatus | null;
  recall_last_set_at?: string | null;
  balance_pence?: number | null;
};

const statusLabels: Record<RecallStatus, string> = {
  due: "Due",
  contacted: "Contacted",
  booked: "Booked",
  not_required: "Not required",
};

type RangeFilter = "overdue" | "30" | "60" | "90" | "all";

export default function RecallsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<RecallRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<RecallStatus | "all">("all");
  const [rangeFilter, setRangeFilter] = useState<RangeFilter>("overdue");

  function formatDate(value?: string | null) {
    if (!value) return "—";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "—";
    return parsed.toLocaleDateString("en-GB");
  }

  function formatCurrency(pence?: number | null) {
    if (pence === null || pence === undefined) return "—";
    return new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency: "GBP",
    }).format(pence / 100);
  }

  function buildRangeParams(filter: RangeFilter) {
    if (filter === "all") return {};
    const today = new Date();
    const end = new Date(today);
    if (filter === "overdue") {
      return { end: today.toISOString().slice(0, 10) };
    }
    const days = Number(filter);
    end.setDate(end.getDate() + days);
    return {
      start: today.toISOString().slice(0, 10),
      end: end.toISOString().slice(0, 10),
    };
  }

  async function loadRecalls() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      const range = buildRangeParams(rangeFilter);
      if (range.start) params.set("start", range.start);
      if (range.end) params.set("end", range.end);
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (query.trim()) params.set("q", query.trim());
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
      setRows(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load recalls");
    } finally {
      setLoading(false);
    }
  }

  async function updateRecallStatus(patientId: number, status: RecallStatus) {
    try {
      const res = await apiFetch(`/api/patients/${patientId}/recall`, {
        method: "POST",
        body: JSON.stringify({ status }),
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
      await loadRecalls();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update recall");
    }
  }

  useEffect(() => {
    void loadRecalls();
  }, [rangeFilter, statusFilter]);

  useEffect(() => {
    const handle = setTimeout(() => {
      void loadRecalls();
    }, 300);
    return () => clearTimeout(handle);
  }, [query]);

  return (
    <div className="app-grid">
      <div className="card">
        <div className="stack">
          <div className="row">
            <div>
              <h2 style={{ marginTop: 0 }}>Recalls</h2>
              <div style={{ color: "var(--muted)" }}>
                Worklist of patients due for recall.
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <select
                className="input"
                value={rangeFilter}
                onChange={(e) => setRangeFilter(e.target.value as RangeFilter)}
              >
                <option value="overdue">Overdue</option>
                <option value="30">Due in 30 days</option>
                <option value="60">Due in 60 days</option>
                <option value="90">Due in 90 days</option>
                <option value="all">All recalls</option>
              </select>
              <select
                className="input"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as RecallStatus | "all")}
              >
                <option value="all">All statuses</option>
                <option value="due">Due</option>
                <option value="contacted">Contacted</option>
                <option value="booked">Booked</option>
                <option value="not_required">Not required</option>
              </select>
              <button className="btn btn-secondary" onClick={() => void loadRecalls()}>
                Refresh
              </button>
            </div>
          </div>
          <div className="row" style={{ gap: 12 }}>
            <input
              className="input"
              placeholder="Search name, phone, postcode"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
            {loading && <span className="badge">Loading…</span>}
            {error && <span className="badge">{error}</span>}
          </div>
          {rows.length === 0 && !loading ? (
            <div className="notice">No recalls found.</div>
          ) : (
            <table className="table table-compact table-hover table-sticky">
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>Phone</th>
                  <th>Postcode</th>
                  <th>Recall due</th>
                  <th>Status</th>
                  <th>Last set</th>
                  <th>Balance</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      {row.last_name.toUpperCase()}, {row.first_name}
                    </td>
                    <td>{row.phone || "—"}</td>
                    <td>{row.postcode || "—"}</td>
                    <td>{formatDate(row.recall_due_date)}</td>
                    <td>
                      <span className="badge">
                        {statusLabels[row.recall_status || "due"]}
                      </span>
                    </td>
                    <td>{formatDate(row.recall_last_set_at)}</td>
                    <td>{formatCurrency(row.balance_pence)}</td>
                    <td>
                      <div className="table-actions">
                        <button
                          className="btn btn-secondary"
                          onClick={() => router.push(`/patients/${row.id}`)}
                        >
                          Open
                        </button>
                        <button
                          className="btn btn-secondary"
                          onClick={() => void updateRecallStatus(row.id, "contacted")}
                        >
                          Contacted
                        </button>
                        <button
                          className="btn btn-secondary"
                          onClick={() => void updateRecallStatus(row.id, "not_required")}
                        >
                          Not required
                        </button>
                        <button
                          className="btn btn-secondary"
                          onClick={() => router.push(`/patients/${row.id}?book=1`)}
                        >
                          Book recall
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
