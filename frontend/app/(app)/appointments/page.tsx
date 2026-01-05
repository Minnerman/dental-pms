"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";

type Actor = { id: number; email: string; role: string };
type PatientSummary = { id: number; first_name: string; last_name: string };

type Appointment = {
  id: number;
  patient: PatientSummary;
  starts_at: string;
  ends_at: string;
  status: string;
  created_by: Actor;
  updated_by?: Actor | null;
  updated_at: string;
  deleted_at?: string | null;
};

type Patient = { id: number; first_name: string; last_name: string };

export default function AppointmentsPage() {
  const router = useRouter();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [patientQuery, setPatientQuery] = useState("");
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filteredPatients = useMemo(() => {
    const q = patientQuery.toLowerCase().trim();
    if (!q) return patients;
    return patients.filter((p) =>
      `${p.first_name} ${p.last_name}`.toLowerCase().includes(q)
    );
  }, [patientQuery, patients]);

  async function loadAppointments(includeDeleted: boolean = showArchived) {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (includeDeleted) params.set("include_deleted", "1");
      const res = await apiFetch(`/api/appointments?${params.toString()}`);
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

  useEffect(() => {
    void loadAppointments();
    void loadPatients();
  }, []);

  async function createAppointment(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedPatientId || !startsAt || !endsAt) return;
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/api/appointments", {
        method: "POST",
        body: JSON.stringify({
          patient_id: Number(selectedPatientId),
          starts_at: new Date(startsAt).toISOString(),
          ends_at: new Date(endsAt).toISOString(),
          status: "booked",
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
      setStartsAt("");
      setEndsAt("");
      await loadAppointments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create appointment");
    } finally {
      setSaving(false);
    }
  }

  async function archiveAppointment(appointmentId: number) {
    if (!confirm("Archive this appointment?")) return;
    setError(null);
    try {
      const res = await apiFetch(`/api/appointments/${appointmentId}/archive`, {
        method: "POST",
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to archive appointment (HTTP ${res.status})`);
      }
      await loadAppointments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to archive appointment");
    }
  }

  async function restoreAppointment(appointmentId: number) {
    if (!confirm("Restore this appointment?")) return;
    setError(null);
    try {
      const res = await apiFetch(`/api/appointments/${appointmentId}/restore`, {
        method: "POST",
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to restore appointment (HTTP ${res.status})`);
      }
      await loadAppointments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to restore appointment");
    }
  }

  return (
    <div className="app-grid">
      <section className="card" style={{ display: "grid", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
          <div>
            <h2 style={{ marginTop: 0 }}>Appointments</h2>
            <p style={{ color: "var(--muted)", marginBottom: 0 }}>
              Schedule and track upcoming appointments.
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={showArchived}
                onChange={(e) => {
                  const next = e.target.checked;
                  setShowArchived(next);
                  void loadAppointments(next);
                }}
              />
              Show archived
            </label>
            <button className="btn btn-secondary" onClick={() => loadAppointments()}>
              Refresh
            </button>
          </div>
        </div>

        {error && <div className="notice">{error}</div>}

        <form onSubmit={createAppointment} className="card" style={{ margin: 0 }}>
          <div className="stack">
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
            <button className="btn btn-primary" disabled={saving}>
              {saving ? "Saving..." : "Create appointment"}
            </button>
          </div>
        </form>

        <div className="card" style={{ margin: 0 }}>
          {loading ? (
            <div className="badge">Loading appointments…</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Start</th>
                  <th>End</th>
                  <th>Patient</th>
                  <th>Status</th>
                  <th>Created by</th>
                  <th>Last edited by</th>
                  <th>Last edited</th>
                  <th>Audit</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {appointments.map((appt) => (
                  <tr key={appt.id}>
                    <td>{new Date(appt.starts_at).toLocaleString()}</td>
                    <td>{new Date(appt.ends_at).toLocaleString()}</td>
                    <td>
                      {appt.patient.first_name} {appt.patient.last_name}
                    </td>
                    <td>
                      {appt.status}
                      {appt.deleted_at && (
                        <span className="badge" style={{ marginLeft: 8 }}>
                          Archived
                        </span>
                      )}
                    </td>
                    <td>{appt.created_by.email}</td>
                    <td>{appt.updated_by?.email || appt.created_by.email}</td>
                    <td>{new Date(appt.updated_at).toLocaleString()}</td>
                    <td>
                      <Link className="btn btn-secondary" href={`/appointments/${appt.id}/audit`}>
                        View audit
                      </Link>
                    </td>
                    <td>
                      {appt.deleted_at ? (
                        <button
                          className="btn btn-secondary"
                          onClick={() => restoreAppointment(appt.id)}
                        >
                          Restore
                        </button>
                      ) : (
                        <button
                          className="btn btn-secondary"
                          onClick={() => archiveAppointment(appt.id)}
                        >
                          Archive
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}
