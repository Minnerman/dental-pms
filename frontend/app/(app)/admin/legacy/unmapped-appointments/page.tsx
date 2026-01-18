"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import HeaderBar from "@/components/ui/HeaderBar";
import { apiFetch, clearToken } from "@/lib/auth";

type UnmappedAppointment = {
  id: number;
  legacy_source: string | null;
  legacy_id: string | null;
  legacy_patient_code: string | null;
  starts_at: string;
  ends_at: string;
  status: string;
  appointment_type: string | null;
  clinician: string | null;
  location: string | null;
  location_type: string;
  is_domiciliary: boolean;
  created_at: string;
  updated_at: string;
};

type UnmappedResponse = {
  items: UnmappedAppointment[];
  total: number;
  limit: number;
  offset: number;
};

function formatDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

function formatDateTime(value: string) {
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString("en-GB", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function UnmappedLegacyAppointmentsPage() {
  const router = useRouter();
  const [items, setItems] = useState<UnmappedAppointment[]>([]);
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [legacySource, setLegacySource] = useState("r4");
  const [fromDate, setFromDate] = useState(() => {
    const end = new Date();
    const start = new Date(end);
    start.setDate(start.getDate() - 29);
    return formatDate(start);
  });
  const [toDate, setToDate] = useState(() => formatDate(new Date()));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  const queryString = useMemo(() => {
    const params = new URLSearchParams({
      legacy_source: legacySource.trim(),
      limit: String(limit),
      offset: String(offset),
      sort: "starts_at",
      dir: "asc",
    });
    if (fromDate) params.set("from", fromDate);
    if (toDate) params.set("to", toDate);
    return params.toString();
  }, [legacySource, limit, offset, fromDate, toDate]);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/admin/legacy/unmapped-appointments?${queryString}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.status === 403) {
        setError("Only admins can access the legacy queue.");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load queue (HTTP ${res.status})`);
      }
      const data = (await res.json()) as UnmappedResponse;
      setItems(data.items);
      setTotal(data.total);
      setLimit(data.limit);
      setOffset(data.offset);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load queue");
    } finally {
      setLoading(false);
    }
  }, [queryString, router]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  useEffect(() => {
    setOffset(0);
  }, [legacySource, fromDate, toDate]);

  return (
    <div className="app-grid">
      <div className="card">
        <div className="stack">
          <HeaderBar
            title="Legacy unmapped appointments"
            subtitle="Appointments imported without a mapped patient record."
            actions={
              <div className="row" style={{ gap: 8 }}>
                <select
                  className="input"
                  value={legacySource}
                  onChange={(e) => setLegacySource(e.target.value)}
                >
                  <option value="r4">R4</option>
                  <option value="">All sources</option>
                </select>
                <input
                  className="input"
                  type="date"
                  value={fromDate}
                  onChange={(e) => setFromDate(e.target.value)}
                />
                <input
                  className="input"
                  type="date"
                  value={toDate}
                  onChange={(e) => setToDate(e.target.value)}
                />
              </div>
            }
          />

          {loading && <div className="badge">Loading queue…</div>}
          {error && <div className="notice">{error}</div>}

          {!loading && items.length === 0 ? (
            <div className="notice">No unmapped legacy appointments.</div>
          ) : (
            <table className="table table-compact table-hover">
              <thead>
                <tr>
                  <th>Starts</th>
                  <th>Legacy</th>
                  <th>Legacy patient</th>
                  <th>Type</th>
                  <th>Clinician</th>
                  <th>Location</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {items.map((appt) => (
                  <tr key={appt.id}>
                    <td>{formatDateTime(appt.starts_at)}</td>
                    <td>
                      <div>{appt.legacy_source || "unknown"}</div>
                      <div style={{ color: "var(--muted)", fontSize: 12 }}>
                        {appt.legacy_id || "unknown"}
                      </div>
                    </td>
                    <td>{appt.legacy_patient_code || "unknown"}</td>
                    <td>{appt.appointment_type || "—"}</td>
                    <td>{appt.clinician || "—"}</td>
                    <td>{appt.location || "—"}</td>
                    <td>{appt.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="row" style={{ justifyContent: "space-between" }}>
            <div style={{ color: "var(--muted)" }}>
              {total} total · showing {items.length}
            </div>
            <div className="row" style={{ gap: 8 }}>
              <button
                className="btn btn-secondary"
                type="button"
                onClick={() => setOffset((prev) => Math.max(prev - limit, 0))}
                disabled={!canPrev}
              >
                Prev
              </button>
              <button
                className="btn btn-secondary"
                type="button"
                onClick={() => setOffset((prev) => prev + limit)}
                disabled={!canNext}
              >
                Next
              </button>
              <select
                className="input"
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
              >
                {[25, 50, 100].map((value) => (
                  <option key={value} value={value}>
                    {value} per page
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
