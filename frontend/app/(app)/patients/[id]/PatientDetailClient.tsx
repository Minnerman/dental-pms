"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Timeline from "@/components/timeline/Timeline";
import { apiFetch, clearToken } from "@/lib/auth";

type Actor = {
  id: number;
  email: string;
  role: string;
};

type Patient = {
  id: number;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  phone?: string | null;
  email?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  created_by: Actor;
  updated_by?: Actor | null;
  deleted_at?: string | null;
  deleted_by?: Actor | null;
};

type Note = {
  id: number;
  body: string;
  note_type: string;
  created_at: string;
  created_by: Actor;
  deleted_at?: string | null;
};

type TimelineItem = {
  entity_type: string;
  entity_id: string;
  action: string;
  occurred_at: string;
  actor_email?: string | null;
  actor_role?: string | null;
  summary: string;
  link?: string | null;
};

export default function PatientDetailClient({ id }: { id: string }) {
  const router = useRouter();
  const patientId = id;
  const [patient, setPatient] = useState<Patient | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [tab, setTab] = useState<"summary" | "notes">("summary");
  const [loading, setLoading] = useState(true);
  const [noteBody, setNoteBody] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [savingPatient, setSavingPatient] = useState(false);
  const [showArchivedNotes, setShowArchivedNotes] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);

  async function loadPatient() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/patients/${patientId}?include_deleted=1`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load patient (HTTP ${res.status})`);
      }
      const data = (await res.json()) as Patient;
      setPatient(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load patient");
    } finally {
      setLoading(false);
    }
  }

  async function loadNotes(includeDeleted: boolean = showArchivedNotes) {
    try {
      const params = new URLSearchParams();
      if (includeDeleted) params.set("include_deleted", "1");
      const res = await apiFetch(`/api/patients/${patientId}/notes?${params.toString()}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.ok) {
        const data = (await res.json()) as Note[];
        setNotes(data);
      }
    } catch {
      setNotes([]);
    }
  }

  async function loadTimeline() {
    try {
      const res = await apiFetch(`/api/patients/${patientId}/timeline`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.ok) {
        const data = (await res.json()) as TimelineItem[];
        setTimeline(data);
      }
    } catch {
      setTimeline([]);
    }
  }

  useEffect(() => {
    void loadPatient();
    void loadNotes();
    void loadTimeline();
  }, [patientId]);

  async function savePatient(e: React.FormEvent) {
    e.preventDefault();
    if (!patient) return;
    setSavingPatient(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/patients/${patient.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          first_name: patient.first_name,
          last_name: patient.last_name,
          email: patient.email,
          phone: patient.phone,
          date_of_birth: patient.date_of_birth,
          notes: patient.notes,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to update patient (HTTP ${res.status})`);
      }
      const data = (await res.json()) as Patient;
      setPatient(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update patient");
    } finally {
      setSavingPatient(false);
    }
  }

  async function addNote() {
    if (!noteBody.trim()) return;
    setSavingNote(true);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/notes`, {
        method: "POST",
        body: JSON.stringify({ body: noteBody, note_type: "clinical" }),
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
      await loadNotes();
      await loadTimeline();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add note");
    } finally {
      setSavingNote(false);
    }
  }

  async function archivePatient() {
    if (!confirm("Archive this patient?")) return;
    try {
      const res = await apiFetch(`/api/patients/${patientId}/archive`, { method: "POST" });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to archive patient (HTTP ${res.status})`);
      }
      void loadPatient();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to archive patient");
    }
  }

  async function restorePatient() {
    try {
      const res = await apiFetch(`/api/patients/${patientId}/restore`, { method: "POST" });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to restore patient (HTTP ${res.status})`);
      }
      void loadPatient();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to restore patient");
    }
  }

  return (
    <div className="app-grid">
      <div>
        <Link className="btn btn-secondary" href="/patients">
          ← Back to patients
        </Link>
      </div>

      {loading ? (
        <div className="badge">Loading patient…</div>
      ) : error ? (
        <div className="notice">{error}</div>
      ) : patient ? (
        <div className="stack">
          <div className="card">
            <div className="stack">
              <div>
                <h2 style={{ margin: 0 }}>
                  {patient.first_name} {patient.last_name}
                </h2>
                <div style={{ color: "var(--muted)" }}>
                  Patient #{patient.id} • Created by {patient.created_by.email}
                </div>
              </div>

              <div className="tabs">
                <button
                  className={`tab ${tab === "summary" ? "active" : ""}`}
                  onClick={() => setTab("summary")}
                >
                  Summary
                </button>
                <button
                  className={`tab ${tab === "notes" ? "active" : ""}`}
                  onClick={() => setTab("notes")}
                >
                  Notes ({notes.length})
                </button>
                <Link className="tab" href={`/patients/${patientId}/timeline`}>
                  Timeline
                </Link>
                <Link className="tab" href={`/patients/${patientId}/audit`}>
                  Audit
                </Link>
              </div>

              {tab === "summary" ? (
                <form onSubmit={savePatient} className="stack">
                  <div className="grid grid-2">
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">First name</label>
                      <input
                        className="input"
                        value={patient.first_name}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, first_name: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Last name</label>
                      <input
                        className="input"
                        value={patient.last_name}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, last_name: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="grid grid-2">
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Email</label>
                      <input
                        className="input"
                        value={patient.email ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, email: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Phone</label>
                      <input
                        className="input"
                        value={patient.phone ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, phone: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="grid grid-2">
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Date of birth</label>
                      <input
                        className="input"
                        value={patient.date_of_birth ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, date_of_birth: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Notes</label>
                    <textarea
                      className="input"
                      rows={4}
                      value={patient.notes ?? ""}
                      onChange={(e) =>
                        setPatient((prev) => (prev ? { ...prev, notes: e.target.value } : prev))
                      }
                    />
                  </div>

                  <div className="row">
                    <button className="btn btn-primary" disabled={savingPatient}>
                      {savingPatient ? "Saving..." : "Save changes"}
                    </button>
                    {patient.deleted_at ? (
                      <button className="btn btn-secondary" type="button" onClick={restorePatient}>
                        Restore patient
                      </button>
                    ) : (
                      <button className="btn btn-secondary" type="button" onClick={archivePatient}>
                        Archive patient
                      </button>
                    )}
                  </div>
                </form>
              ) : (
                <div className="stack">
                  <div className="row">
                    <button
                      className="btn btn-secondary"
                      type="button"
                      onClick={() => {
                        setShowArchivedNotes((prev) => !prev);
                        void loadNotes(!showArchivedNotes);
                      }}
                    >
                      {showArchivedNotes ? "Hide archived" : "Show archived"}
                    </button>
                  </div>

                  <div className="card">
                    <div className="stack">
                      <label className="label">Add a note</label>
                      <textarea
                        className="input"
                        rows={3}
                        value={noteBody}
                        onChange={(e) => setNoteBody(e.target.value)}
                        placeholder="Write a clinical or admin note..."
                      />
                      <button className="btn btn-primary" onClick={addNote} disabled={savingNote}>
                        {savingNote ? "Saving..." : "Add note"}
                      </button>
                    </div>
                  </div>

                  <div className="stack">
                    {notes.length === 0 ? (
                      <div className="notice">No notes yet.</div>
                    ) : (
                      notes.map((note) => (
                        <div className="card" key={note.id}>
                          <div className="row">
                            <div>
                              <strong>{note.note_type}</strong>
                              <div style={{ color: "var(--muted)" }}>
                                {new Date(note.created_at).toLocaleString()} • {note.created_by.email}
                              </div>
                            </div>
                            <Link className="btn btn-secondary" href={`/notes/${note.id}/audit`}>
                              View audit
                            </Link>
                          </div>
                          <p style={{ marginBottom: 0 }}>{note.body}</p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <Timeline items={timeline} title="Recent activity" />
          </div>
        </div>
      ) : (
        <div className="notice">Patient not found.</div>
      )}
    </div>
  );
}
