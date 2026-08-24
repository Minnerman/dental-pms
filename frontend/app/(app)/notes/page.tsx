"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import { NOTE_BODY_MAX_LENGTH, noteResponseError } from "@/lib/noteErrors";
import HeaderBar from "@/components/ui/HeaderBar";
import Panel from "@/components/ui/Panel";
import Table from "@/components/ui/Table";

type Actor = { id: number; email: string; role: string };

type Note = {
  id: number;
  patient_id: number;
  appointment_id?: number | null;
  body: string;
  note_type: "clinical" | "admin";
  created_at: string;
  updated_at: string;
  created_by: Actor;
  updated_by?: Actor | null;
  deleted_at?: string | null;
};

type Patient = {
  id: number;
  first_name: string;
  last_name: string;
  deleted_at?: string | null;
};

const noteDetailSaveLocks = new Set<number>();
const noteArchiveLocks = new Set<number>();

export default function NotesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedNoteId = useMemo(() => {
    const raw = searchParams?.get("note");
    if (!raw) return null;
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);
  const requestedIncludeDeleted = searchParams?.get("include_deleted") === "1";
  const [capabilities, setCapabilities] = useState<string[] | null>(null);
  const [capabilityError, setCapabilityError] = useState<string | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(requestedIncludeDeleted);
  const [query, setQuery] = useState("");
  const [selectedNoteId, setSelectedNoteId] = useState<number | null>(null);
  const [editBody, setEditBody] = useState("");
  const [editType, setEditType] = useState<Note["note_type"]>("clinical");
  const [savingEdit, setSavingEdit] = useState(false);
  const [archiveAction, setArchiveAction] = useState<{
    noteId: number;
    action: "archive" | "restore";
  } | null>(null);

  const canViewNotes = Boolean(capabilities?.includes("notes.view"));
  const canViewPatients = Boolean(capabilities?.includes("patients.view"));
  const canWriteNotes = Boolean(
    canViewNotes && capabilities?.includes("notes.write")
  );
  const capabilityState =
    capabilities === null
      ? "loading"
      : canViewNotes
        ? canWriteNotes
          ? "write"
          : "read-only"
        : "denied";

  const patientMap = useMemo(
    () => new Map(patients.map((patient) => [patient.id, patient])),
    [patients]
  );

  const filteredNotes = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return notes;
    return notes.filter((note) => {
      const patient = patientMap.get(note.patient_id);
      const patientName = patient
        ? `${patient.first_name} ${patient.last_name}`.toLowerCase()
        : "";
      return note.body.toLowerCase().includes(normalizedQuery) || patientName.includes(normalizedQuery);
    });
  }, [notes, patientMap, query]);

  const loadCapabilities = useCallback(async () => {
    setCapabilityError(null);
    try {
      const response = await apiFetch("/api/me/capabilities");
      if (response.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!response.ok) {
        throw new Error("Note permissions could not be verified.");
      }
      const data = (await response.json()) as unknown;
      if (!Array.isArray(data) || !data.every((item) => typeof item === "string")) {
        throw new Error("Note permissions could not be verified.");
      }
      setCapabilities(data);
    } catch (caught) {
      setCapabilities([]);
      setCapabilityError(
        caught instanceof Error ? caught.message : "Note permissions could not be verified."
      );
    }
  }, [router]);

  const loadNotes = useCallback(
    async (includeDeleted: boolean = showArchived) => {
      if (!canViewNotes) {
        setNotes([]);
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        if (includeDeleted) params.set("include_deleted", "1");
        const response = await apiFetch(`/api/notes?${params.toString()}`);
        if (response.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        if (!response.ok) {
          throw new Error(await noteResponseError(response, "Failed to load notes."));
        }
        const data = (await response.json()) as Note[];
        setNotes(data);
      } catch (caught) {
        setNotes([]);
        setError(caught instanceof Error ? caught.message : "Failed to load notes.");
      } finally {
        setLoading(false);
      }
    },
    [canViewNotes, router, showArchived]
  );

  const loadPatients = useCallback(async () => {
    if (!canViewNotes || !canViewPatients) {
      setPatients([]);
      return;
    }
    try {
      const response = await apiFetch("/api/patients?limit=200&include_deleted=1");
      if (response.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!response.ok) {
        setPatients([]);
        return;
      }
      setPatients((await response.json()) as Patient[]);
    } catch {
      setPatients([]);
    }
  }, [canViewNotes, canViewPatients, router]);

  useEffect(() => {
    void loadCapabilities();
  }, [loadCapabilities]);

  useEffect(() => {
    if (capabilities === null) return;
    if (!canViewNotes) {
      setLoading(false);
      setNotes([]);
      setPatients([]);
      return;
    }
    void loadNotes();
    void loadPatients();
  }, [capabilities, canViewNotes, loadNotes, loadPatients]);

  useEffect(() => {
    if (requestedNoteId) {
      const requested = notes.find((note) => note.id === requestedNoteId);
      if (requested) {
        if (selectedNoteId !== requestedNoteId) setSelectedNoteId(requestedNoteId);
        return;
      }
    }
    if (selectedNoteId && notes.some((note) => note.id === selectedNoteId)) return;
    setSelectedNoteId(notes[0]?.id ?? null);
  }, [notes, requestedNoteId, selectedNoteId]);

  useEffect(() => {
    if (!selectedNoteId) return;
    const selected = notes.find((note) => note.id === selectedNoteId);
    if (!selected) return;
    setEditBody(selected.body);
    setEditType(selected.note_type);
  }, [selectedNoteId, notes]);

  const selectedNote = selectedNoteId
    ? notes.find((note) => note.id === selectedNoteId) ?? null
    : null;
  const editIsValid =
    editBody.trim().length > 0 && editBody.trim().length <= NOTE_BODY_MAX_LENGTH;
  const editIsChanged = Boolean(
    selectedNote &&
      (editBody.trim() !== selectedNote.body || editType !== selectedNote.note_type)
  );

  async function toggleArchive(note: Note, button?: HTMLButtonElement | null) {
    if (!canWriteNotes) {
      setError("Notes are read-only.");
      return;
    }
    const action = note.deleted_at ? "restore" : "archive";
    if (
      !button ||
      savingEdit ||
      archiveAction?.noteId === note.id ||
      noteArchiveLocks.has(note.id) ||
      button.disabled
    ) {
      return;
    }
    if (!confirm(`${note.deleted_at ? "Restore" : "Archive"} this note?`)) return;
    noteArchiveLocks.add(note.id);
    button.disabled = true;
    setError(null);
    setNotice(null);
    setArchiveAction({ noteId: note.id, action });
    try {
      const response = await apiFetch(`/api/notes/${note.id}/${action}`, {
        method: "POST",
        headers: { "Request-Id": crypto.randomUUID() },
      });
      if (response.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!response.ok) {
        throw new Error(
          await noteResponseError(response, `Failed to ${action} note.`)
        );
      }
      setNotice(`Note ${note.deleted_at ? "restored" : "archived"}.`);
      await loadNotes();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `Failed to ${action} note.`);
    } finally {
      noteArchiveLocks.delete(note.id);
      setArchiveAction((current) => (current?.noteId === note.id ? null : current));
    }
  }

  async function saveNoteEdit(button?: HTMLButtonElement | null) {
    const noteId = selectedNoteId;
    if (!canWriteNotes) {
      setError("Notes are read-only.");
      return;
    }
    if (!editIsValid) {
      setError(`Enter a note between 1 and ${NOTE_BODY_MAX_LENGTH} characters.`);
      return;
    }
    if (!editIsChanged) return;
    if (
      !noteId ||
      !button ||
      savingEdit ||
      noteDetailSaveLocks.has(noteId) ||
      button.disabled
    ) {
      return;
    }
    noteDetailSaveLocks.add(noteId);
    button.disabled = true;
    setSavingEdit(true);
    setError(null);
    setNotice(null);
    try {
      const response = await apiFetch(`/api/notes/${noteId}`, {
        method: "PATCH",
        headers: { "Request-Id": crypto.randomUUID() },
        body: JSON.stringify({ body: editBody.trim(), note_type: editType }),
      });
      if (response.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!response.ok) {
        throw new Error(await noteResponseError(response, "Failed to update note."));
      }
      await loadNotes();
      setNotice("Note updated.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to update note.");
    } finally {
      noteDetailSaveLocks.delete(noteId);
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
                  disabled={!canViewNotes || loading}
                  onChange={(event) => {
                    setShowArchived(event.target.checked);
                  }}
                />
                Show archived
              </label>
              <button
                className="btn btn-secondary"
                onClick={() => void loadNotes()}
                disabled={!canViewNotes || loading}
              >
                Refresh
              </button>
            </>
          }
        />

        <div data-testid="notes-capability-state" data-state={capabilityState}>
          {capabilities === null ? (
            <div className="badge">Checking note permissions…</div>
          ) : !canViewNotes ? (
            <div className="notice">
              {capabilityError || "You do not have permission to view notes."}
            </div>
          ) : !canWriteNotes ? (
            <div className="notice">Notes are read-only.</div>
          ) : null}
        </div>

        {canViewNotes && (
          <>
            <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
              <input
                className="input"
                placeholder="Search note text or patient"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>

            {notice && <div className="notice">{notice}</div>}
            {error && <div className="notice">{error}</div>}

            <div
              data-testid="notes-worklist"
              style={{ display: "grid", gap: 16, gridTemplateColumns: "1fr 1.2fr" }}
            >
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
                      {filteredNotes.length === 0 ? (
                        <tr data-testid="notes-empty-state">
                          <td colSpan={4}>No notes available.</td>
                        </tr>
                      ) : (
                        filteredNotes.map((note) => {
                          const patient = patientMap.get(note.patient_id);
                          return (
                            <tr
                              key={note.id}
                              onClick={() => setSelectedNoteId(note.id)}
                              style={{ cursor: "pointer" }}
                            >
                              <td>
                                {note.body.length > 60 ? `${note.body.slice(0, 60)}…` : note.body}
                              </td>
                              <td>
                                {patient ? (
                                  <Link href={`/patients/${note.patient_id}`}>
                                    {patient.first_name} {patient.last_name}
                                  </Link>
                                ) : (
                                  <span>Patient unavailable</span>
                                )}
                              </td>
                              <td>{new Date(note.updated_at).toLocaleDateString()}</td>
                              <td>{note.deleted_at ? "Archived" : "Active"}</td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </Table>
                )}
              </div>
              <div className="card" style={{ margin: 0 }}>
                {selectedNote ? (
                  <div className="stack" data-testid="note-detail">
                    <div className="row">
                      <div>
                        <h3 style={{ marginTop: 0 }}>Note detail</h3>
                        <p style={{ color: "var(--muted)" }}>
                          {selectedNote.deleted_at
                            ? "Archived note (read-only)."
                            : canWriteNotes
                              ? "Edit note content and metadata."
                              : "Read-only note detail."}
                        </p>
                      </div>
                      <div style={{ display: "flex", gap: 8 }}>
                        <Link
                          className="btn btn-secondary"
                          href={`/notes/${selectedNote.id}/audit`}
                          data-testid="note-detail-audit"
                        >
                          View audit
                        </Link>
                        {canWriteNotes && (
                          <button
                            className="btn btn-secondary"
                            onClick={(event) => void toggleArchive(selectedNote, event.currentTarget)}
                            disabled={savingEdit || archiveAction?.noteId === selectedNote.id}
                            data-testid="note-detail-archive"
                          >
                            {archiveAction?.noteId === selectedNote.id
                              ? archiveAction.action === "restore"
                                ? "Restoring..."
                                : "Archiving..."
                              : selectedNote.deleted_at
                                ? "Restore"
                                : "Archive"}
                          </button>
                        )}
                      </div>
                    </div>
                    {selectedNote.deleted_at || !canWriteNotes ? (
                      <div className="stack" data-testid="note-detail-readonly">
                        <div>
                          <strong>Note type</strong>
                          <div>{selectedNote.note_type === "admin" ? "Admin" : "Clinical"}</div>
                        </div>
                        <div>
                          <strong>Note body</strong>
                          <p style={{ whiteSpace: "pre-wrap" }}>{selectedNote.body}</p>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="stack" style={{ gap: 8 }}>
                          <label className="label">Note type</label>
                          <select
                            className="input"
                            value={editType}
                            onChange={(event) =>
                              setEditType(event.target.value as Note["note_type"])
                            }
                            data-testid="note-detail-type"
                            disabled={savingEdit}
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
                            maxLength={NOTE_BODY_MAX_LENGTH}
                            onChange={(event) => setEditBody(event.target.value)}
                            data-testid="note-detail-body"
                            disabled={savingEdit}
                          />
                        </div>
                        <button
                          className="btn btn-primary"
                          onClick={(event) => void saveNoteEdit(event.currentTarget)}
                          disabled={savingEdit || !editIsValid || !editIsChanged}
                          data-testid="note-detail-save"
                        >
                          {savingEdit ? "Saving..." : "Save changes"}
                        </button>
                      </>
                    )}
                  </div>
                ) : loading ? (
                  <div className="badge">Loading note detail…</div>
                ) : (
                  <div className="notice">No note selected.</div>
                )}
              </div>
            </div>
          </>
        )}
      </Panel>
    </div>
  );
}
