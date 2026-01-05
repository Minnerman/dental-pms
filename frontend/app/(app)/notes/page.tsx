"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";

type Actor = { id: number; email: string; role: string };

type Note = {
  id: number;
  patient_id: number;
  body: string;
  note_type: string;
  created_at: string;
  updated_at: string;
  created_by: Actor;
  updated_by?: Actor | null;
  deleted_at?: string | null;
};

type Patient = { id: number; first_name: string; last_name: string; deleted_at?: string | null };

export default function NotesPage() {
  const router = useRouter();
  const [notes, setNotes] = useState<Note[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [query, setQuery] = useState("");

  const patientMap = useMemo(() => {
    return new Map(patients.map((p) => [p.id, p]));
  }, [patients]);

  const filteredNotes = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return notes;
    return notes.filter((note) => {
      const patient = patientMap.get(note.patient_id);
      const patientName = patient ? `${patient.first_name} ${patient.last_name}`.toLowerCase() : "";
      return (
        note.body.toLowerCase().includes(q) ||
        patientName.includes(q) ||
        `${note.patient_id}`.includes(q)
      );
    });
  }, [notes, patientMap, query]);

  async function loadNotes(includeDeleted: boolean = showArchived) {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (includeDeleted) params.set("include_deleted", "1");
      const res = await apiFetch(`/api/notes?${params.toString()}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load notes (HTTP ${res.status})`);
      }
      const data = (await res.json()) as Note[];
      setNotes(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load notes");
    } finally {
      setLoading(false);
    }
  }

  async function loadPatients() {
    try {
      const res = await apiFetch("/api/patients?limit=200&include_deleted=1");
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.ok) {
        const data = (await res.json()) as Patient[];
        setPatients(data);
      }
    } catch {
      setPatients([]);
    }
  }

  useEffect(() => {
    void loadNotes();
    void loadPatients();
  }, []);

  async function toggleArchive(note: Note) {
    const action = note.deleted_at ? "restore" : "archive";
    if (!confirm(`${note.deleted_at ? "Restore" : "Archive"} this note?`)) return;
    setError(null);
    setNotice(null);
    try {
      const res = await apiFetch(`/api/notes/${note.id}/${action}`, { method: "POST" });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to ${action} note (HTTP ${res.status})`);
      }
      setNotice(`Note ${note.deleted_at ? "restored" : "archived"}.`);
      await loadNotes();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} note`);
    }
  }

  return (
    <div className="app-grid">
      <section className="card" style={{ display: "grid", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
          <div>
            <h2 style={{ marginTop: 0 }}>Notes</h2>
            <p style={{ color: "var(--muted)", marginBottom: 0 }}>
              Review and manage clinical notes across patients.
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
                  void loadNotes(next);
                }}
              />
              Show archived
            </label>
            <button className="btn btn-secondary" onClick={() => loadNotes()}>
              Refresh
            </button>
          </div>
        </div>

        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <input
            className="input"
            placeholder="Search note text or patient"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        {notice && <div className="notice">{notice}</div>}
        {error && <div className="notice">{error}</div>}

        <div className="card" style={{ margin: 0 }}>
          {loading ? (
            <div className="badge">Loading notes…</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Note</th>
                  <th>Patient</th>
                  <th>Created</th>
                  <th>Updated</th>
                  <th>Status</th>
                  <th>Audit</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredNotes.map((note) => {
                  const patient = patientMap.get(note.patient_id);
                  return (
                    <tr key={note.id}>
                      <td>{note.body.length > 80 ? `${note.body.slice(0, 80)}…` : note.body}</td>
                      <td>
                        {patient ? (
                          <Link href={`/patients/${note.patient_id}`}>
                            {patient.first_name} {patient.last_name}
                          </Link>
                        ) : (
                          <span>Patient #{note.patient_id}</span>
                        )}
                      </td>
                      <td>
                        <div>{note.created_by.email}</div>
                        <div style={{ color: "var(--muted)", fontSize: 12 }}>
                          {new Date(note.created_at).toLocaleString()}
                        </div>
                      </td>
                      <td>
                        <div>{note.updated_by?.email || note.created_by.email}</div>
                        <div style={{ color: "var(--muted)", fontSize: 12 }}>
                          {new Date(note.updated_at).toLocaleString()}
                        </div>
                      </td>
                      <td>
                        {note.deleted_at ? (
                          <span className="badge">Archived</span>
                        ) : (
                          <span className="badge">Active</span>
                        )}
                      </td>
                      <td>
                        <Link className="btn btn-secondary" href={`/notes/${note.id}/audit`}>
                          View audit
                        </Link>
                      </td>
                      <td>
                        <button className="btn btn-secondary" onClick={() => toggleArchive(note)}>
                          {note.deleted_at ? "Restore" : "Archive"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}
