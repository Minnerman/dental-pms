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
  patient_has_alerts: boolean;
  clinician_user_id?: number | null;
  appointment_type?: string | null;
  clinician?: string | null;
  location?: string | null;
  is_domiciliary: boolean;
  visit_address?: string | null;
  starts_at: string;
  ends_at: string;
  status: string;
  created_by: Actor;
  updated_by?: Actor | null;
  updated_at: string;
  deleted_at?: string | null;
};

type Patient = { id: number; first_name: string; last_name: string };
type PatientDetail = {
  id: number;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  phone?: string | null;
  email?: string | null;
  allergies?: string | null;
  medical_alerts?: string | null;
  safeguarding_notes?: string | null;
};
type UserOption = { id: number; email: string; full_name: string; role: string; is_active: boolean };

type AppointmentNote = {
  id: number;
  body: string;
  created_at: string;
  created_by: Actor;
};

type DomiciliaryFilter = "all" | "clinic" | "domiciliary";

export default function AppointmentsPage() {
  const router = useRouter();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [users, setUsers] = useState<UserOption[]>([]);
  const [patientQuery, setPatientQuery] = useState("");
  const [rangeFrom, setRangeFrom] = useState("");
  const [rangeTo, setRangeTo] = useState("");
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [clinicianUserId, setClinicianUserId] = useState("");
  const [appointmentType, setAppointmentType] = useState("");
  const [location, setLocation] = useState("");
  const [isDomiciliary, setIsDomiciliary] = useState(false);
  const [visitAddress, setVisitAddress] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [showNewModal, setShowNewModal] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [domiciliaryFilter, setDomiciliaryFilter] = useState<DomiciliaryFilter>("all");
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
  const [detailDomiciliary, setDetailDomiciliary] = useState(false);
  const [detailVisitAddress, setDetailVisitAddress] = useState("");
  const [savingDetail, setSavingDetail] = useState(false);

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
      if (rangeFrom) params.set("from", new Date(rangeFrom).toISOString());
      if (rangeTo) params.set("to", new Date(rangeTo).toISOString());
      if (patientQuery.trim()) params.set("q", patientQuery.trim());
      if (domiciliaryFilter === "clinic") params.set("domiciliary", "false");
      if (domiciliaryFilter === "domiciliary") params.set("domiciliary", "true");
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

  useEffect(() => {
    void loadAppointments();
    void loadPatients();
    void loadUsers();
  }, []);

  useEffect(() => {
    void loadAppointments();
  }, [rangeFrom, rangeTo, domiciliaryFilter]);

  async function createAppointment(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedPatientId || !startsAt || !endsAt) return;
    if (isDomiciliary && !visitAddress.trim()) {
      setError("Visit address is required for domiciliary visits.");
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
          is_domiciliary: isDomiciliary,
          visit_address: isDomiciliary ? visitAddress.trim() : undefined,
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
      setIsDomiciliary(false);
      setVisitAddress("");
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
    if (detailDomiciliary && !detailVisitAddress.trim()) {
      setError("Visit address is required for domiciliary visits.");
      return;
    }
    setSavingDetail(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/appointments/${selectedAppointment.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          is_domiciliary: detailDomiciliary,
          visit_address: detailDomiciliary ? detailVisitAddress.trim() : null,
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
      setDetailDomiciliary(updated.is_domiciliary);
      setDetailVisitAddress(updated.visit_address || "");
      setNotice("Appointment updated.");
      await loadAppointments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update appointment");
    } finally {
      setSavingDetail(false);
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
            <button className="btn btn-primary" onClick={() => setShowNewModal(true)}>
              New appointment
            </button>
            <div style={{ display: "flex", gap: 6 }}>
              {([
                { id: "all", label: "All" },
                { id: "clinic", label: "Clinic" },
                { id: "domiciliary", label: "Domiciliary" },
              ] as const).map((item) => (
                <button
                  key={item.id}
                  className={
                    item.id === domiciliaryFilter ? "btn btn-primary" : "btn btn-secondary"
                  }
                  onClick={() => setDomiciliaryFilter(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
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
        {notice && <div className="notice">{notice}</div>}

        <div className="card" style={{ margin: 0 }}>
          <div className="stack" style={{ gap: 12 }}>
            <div style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr" }}>
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">From</label>
                <input
                  className="input"
                  type="date"
                  value={rangeFrom}
                  onChange={(e) => setRangeFrom(e.target.value)}
                />
              </div>
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">To</label>
                <input
                  className="input"
                  type="date"
                  value={rangeTo}
                  onChange={(e) => setRangeTo(e.target.value)}
                />
              </div>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Search patient</label>
              <input
                className="input"
                placeholder="Start typing a name"
                value={patientQuery}
                onChange={(e) => setPatientQuery(e.target.value)}
              />
            </div>
          </div>
        </div>

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
                  <th>Clinician</th>
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
                      {appt.is_domiciliary && (
                        <span className="badge" style={{ marginLeft: 8 }}>
                          Domiciliary
                        </span>
                      )}
                      {appt.patient_has_alerts && (
                        <span
                          className="badge"
                          style={{ marginLeft: 8, background: "#b07b24", color: "white" }}
                          title="Patient has alerts on file"
                        >
                          Alerts
                        </span>
                      )}
                    </td>
                    <td>{appt.clinician || "—"}</td>
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
                      <div className="table-actions">
                        <button
                          className="btn btn-secondary"
                          onClick={() => {
                            setSelectedAppointment(appt);
                            setDetailDomiciliary(appt.is_domiciliary);
                            setDetailVisitAddress(appt.visit_address || "");
                            void loadAppointmentNotes(appt.id);
                            void loadPatientDetail(appt.patient.id);
                          }}
                        >
                          Details
                        </button>
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
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

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
                <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={isDomiciliary}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      setIsDomiciliary(checked);
                      if (!checked) setVisitAddress("");
                    }}
                  />
                  Domiciliary (home visit)
                </label>
                {isDomiciliary && (
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Visit address</label>
                    <textarea
                      className="input"
                      rows={3}
                      value={visitAddress}
                      onChange={(e) => setVisitAddress(e.target.value)}
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
                  <strong>Status:</strong> {selectedAppointment.status}
                </div>
                <div>
                  <strong>Clinician:</strong> {selectedAppointment.clinician || "Unassigned"}
                </div>
                <div>
                  <strong>Type:</strong> {selectedAppointment.appointment_type || "—"}
                </div>
                <div>
                  <strong>Location:</strong> {selectedAppointment.location || "—"}
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

              <form onSubmit={saveAppointmentDetails} className="stack">
                <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={detailDomiciliary}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      setDetailDomiciliary(checked);
                      if (!checked) setDetailVisitAddress("");
                    }}
                  />
                  Domiciliary (home visit)
                </label>
                {detailDomiciliary && (
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Visit address</label>
                    <textarea
                      className="input"
                      rows={3}
                      value={detailVisitAddress}
                      onChange={(e) => setDetailVisitAddress(e.target.value)}
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
