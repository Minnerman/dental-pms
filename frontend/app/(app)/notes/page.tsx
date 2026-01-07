"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import HeaderBar from "@/components/ui/HeaderBar";
import Panel from "@/components/ui/Panel";
import Table from "@/components/ui/Table";

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
  const [selectedNoteId, setSelectedNoteId] = useState<number | null>(null);
  const [editBody, setEditBody] = useState("");
  const [editType, setEditType] = useState("clinical");
  const [savingEdit, setSavingEdit] = useState(false);

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

  useEffect(() => {
    if (!selectedNoteId && notes.length > 0) {
      setSelectedNoteId(notes[0].id);
    }
  }, [notes, selectedNoteId]);

  useEffect(() => {
    if (!selectedNoteId) return;
    const selected = notes.find((note) => note.id === selectedNoteId);
    if (!selected) return;
    setEditBody(selected.body);
    setEditType(selected.note_type);
  }, [selectedNoteId, notes]);

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

  async function saveNoteEdit() {
    if (!selectedNoteId) return;
    setSavingEdit(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/notes/${selectedNoteId}`, {
        method: "PATCH",
        body: JSON.stringify({
          body: editBody.trim(),
          note_type: editType,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to update note (HTTP ${res.status})`);
      }
      await loadNotes();
      setNotice("Note updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update note");
    } finally {
      setSavingEdit(false);
    }
  }

  return (
    <div className="app-grid">
      <Panel>
        <HeaderBar
          title="Notes"
          subtitle="Review and manage clinical notes across patients."
          actions={
            <>
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
            </>
          }
        />

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

        <div style={{ display: "grid", gap: 16, gridTemplateColumns: "1fr 1.2fr" }}>
          <div className="card" style={{ margin: 0 }}>
            {loading ? (
              <div className="badge">Loading notes…</div>
            ) : (
              <Table className="table-compact table-hover table-sticky">
                <thead>
                  <tr>
                    <th>Note</th>
                    <th>Patient</th>
                    <th>Updated</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredNotes.map((note) => {
                    const patient = patientMap.get(note.patient_id);
                    return (
                      <tr
                        key={note.id}
                        onClick={() => setSelectedNoteId(note.id)}
                        style={{ cursor: "pointer" }}
                      >
                        <td>{note.body.length > 60 ? `${note.body.slice(0, 60)}…` : note.body}</td>
                        <td>
                          {patient ? (
                            <Link href={`/patients/${note.patient_id}`}>
                              {patient.first_name} {patient.last_name}
                            </Link>
                          ) : (
                            <span>Patient #{note.patient_id}</span>
                          )}
                        </td>
                        <td>{new Date(note.updated_at).toLocaleDateString()}</td>
                        <td>{note.deleted_at ? "Archived" : "Active"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </Table>
            )}
          </div>
          <div className="card" style={{ margin: 0 }}>
            {selectedNoteId ? (
              <div className="stack">
                <div className="row">
                  <div>
                    <h3 style={{ marginTop: 0 }}>Note detail</h3>
                    <p style={{ color: "var(--muted)" }}>
                      Edit note content and metadata.
                    </p>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <Link
                      className="btn btn-secondary"
                      href={`/notes/${selectedNoteId}/audit`}
                    >
                      View audit
                    </Link>
                    <button
                      className="btn btn-secondary"
                      onClick={() => {
                        const note = notes.find((item) => item.id === selectedNoteId);
                        if (note) void toggleArchive(note);
                      }}
                    >
                      {notes.find((item) => item.id === selectedNoteId)?.deleted_at
                        ? "Restore"
                        : "Archive"}
                    </button>
                  </div>
                </div>
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">Note type</label>
                  <select
                    className="input"
                    value={editType}
                    onChange={(e) => setEditType(e.target.value)}
                  >
                    <option value="clinical">Clinical</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">Note body</label>
                  <textarea
                    className="input"
                    rows={8}
                    value={editBody}
                    onChange={(e) => setEditBody(e.target.value)}
                  />
                </div>
                <button className="btn btn-primary" onClick={saveNoteEdit} disabled={savingEdit}>
                  {savingEdit ? "Saving..." : "Save changes"}
                </button>
              </div>
            ) : (
              <div className="notice">Select a note to view details.</div>
            )}
          </div>
        </div>
      </Panel>
    </div>
  );
}
