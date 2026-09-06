"use client";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import { noteResponseError } from "@/lib/noteErrors";
import ClinicalNoteTemplates, { noteCategories, type TemplateInsert } from "./ClinicalNoteTemplates";
import NoteWritingAssistant from "./NoteWritingAssistant";
import { groupJournal, journalCategories, journalDayLabel, journalLabels, journalDetailLines, journalDiagnosisLines, noteRequestHeaders, noteTeeth, safeJournalLink, JOURNAL_NOTE_MAX_LENGTH, type JournalCategory, type JournalItem, type JournalResponse } from "./clinicalNotes";
import styles from "./ClinicalNotesPanel.module.css";

type Props = {
  patientId: string; capabilities: string[]; selectedTooth: string | null; refreshKey: number | string;
  focusRequest?: { tooth: string; nonce: number }; readOnly?: boolean;
  onSaved: () => void | Promise<void>; onSavingChange?: (saving: boolean) => void; onClose?: () => void;
};
type Draft = { body: string; tooth: string; category: string; clinical_date: string; reason: string; editing: JournalItem | null; template_id?: number; template_revision?: number; codes: string[] };
const emptyDraft = (): Draft => ({ body: "", tooth: "", category: "clinical", clinical_date: "", reason: "", editing: null, codes: [] });
type Revision = { revision: number; body: string; clinical_date: string | null; category: string | null; recorded_at: string; recorded_by: { id: number; name: string | null } | null; reason: string | null; baseline: boolean; archived?: boolean; deleted_at?: string | null };
const sourceNames: Record<string, string> = { note: "Patient note", tooth_note: "Tooth note", diagnosis: "Diagnosis", procedure: "Completed treatment", treatment_plan: "Treatment plan", medical_update: "Medical update", bpe: "BPE", document: "Generated document", recall_communication: "Manual contact log" };

export default function ClinicalNotesPanel({ patientId, capabilities, selectedTooth, refreshKey, focusRequest, readOnly = false, onSaved, onSavingChange, onClose }: Props) {
  const router = useRouter();
  const panel = useRef<HTMLElement>(null);
  const bodyInput = useRef<HTMLTextAreaElement>(null);
  const noteBodyId = useId();
  const [category, setCategory] = useState<JournalCategory>("all");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [toothFilter, setToothFilter] = useState("");
  const [feed, setFeed] = useState<{ target: string; data: JournalResponse } | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [feedError, setFeedError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const draft = drafts[patientId] ?? emptyDraft();
  const [saving, setSaving] = useState(false);
  const [templateSaving, setTemplateSaving] = useState(false);
  const [uncertainReviewed, setUncertainReviewed] = useState(false);
  const [saveError, setSaveError] = useState<{ patientId: string; message: string } | null>(null);
  const [notice, setNotice] = useState<{ patientId: string; message: string } | null>(null);
  const [history, setHistory] = useState<{ patientId: string; key: string; loading: boolean; items: Revision[]; error?: string; url?: string; nextBefore?: number | null; loadingOlder?: boolean } | null>(null);
  const mutationLock = useRef(false);
  const attempts = useRef<Record<string, { fingerprint: string; headers: Record<string, string>; uncertain: boolean }>>({});
  const sequence = useRef(0);
  const historySequence = useRef(0);
  const currentPatient = useRef(patientId);
  currentPatient.current = patientId;
  const canReadNotes = capabilities.includes("notes.view");
  const canReadClinical = capabilities.includes("clinical.view");
  const canWriteNotes = !readOnly && canReadNotes && capabilities.includes("notes.write");
  const canWriteClinical = !readOnly && canReadClinical && capabilities.includes("clinical.write");
  const canRead = capabilities.includes("patients.view") && (canReadNotes || canReadClinical || capabilities.includes("documents.download"));
  const permissionSignature = [...capabilities].sort().join(",");
  const target = `${patientId}:${category}:${debouncedQuery}:${toothFilter}:${permissionSignature}`;
  const currentTarget = useRef(target); currentTarget.current = target;
  const data = feed?.target === target ? feed.data : null;
  const unauthorized = useCallback(() => { clearToken(); router.replace("/login"); }, [router]);
  const templateBusy = useCallback((busy: boolean) => { setTemplateSaving(busy); onSavingChange?.(busy); }, [onSavingChange]);
  const changeDraft = useCallback((patch: Partial<Draft>) => {
    setDrafts((old) => ({ ...old, [patientId]: { ...(old[patientId] ?? emptyDraft()), ...patch } }));
    setSaveError(null); setNotice(null);
  }, [patientId]);

  useEffect(() => { const timer = setTimeout(() => setDebouncedQuery(query.trim()), 250); return () => clearTimeout(timer); }, [query]);
  useEffect(() => { setQuery(""); setDebouncedQuery(""); setCategory("all"); setToothFilter(""); setHistory(null); setUncertainReviewed(false); historySequence.current += 1; }, [patientId]);
  useEffect(() => { setHistory(null); setUncertainReviewed(false); historySequence.current += 1; }, [permissionSignature]);
  useEffect(() => {
    if (!focusRequest) return;
    setToothFilter(focusRequest.tooth); setCategory("all"); setQuery(""); setDebouncedQuery("");
    setDrafts((old) => { const existing = old[patientId] ?? emptyDraft(); return existing.body || existing.editing ? old : { ...old, [patientId]: { ...existing, tooth: focusRequest.tooth } }; });
    panel.current?.focus({ preventScroll: true });
  }, [focusRequest, patientId]);

  const load = useCallback(async (before?: string) => {
    if (!canRead) { setFeed(null); return false; }
    const request = ++sequence.current;
    const requestTarget = target;
    const isCurrent = () => request === sequence.current && currentTarget.current === requestTarget;
    if (before) setLoadingOlder(true); else setLoading(true);
    setFeedError(null);
    const params = new URLSearchParams({ limit: "50", category });
    if (debouncedQuery) params.set("q", debouncedQuery);
    if (toothFilter) params.set("tooth", toothFilter);
    if (before) params.set("before", before);
    try {
      const response = await apiFetch(`/api/patients/${patientId}/clinical-journal?${params}`);
      if (!isCurrent()) return;
      if (response.status === 401) { unauthorized(); return; }
      if (!response.ok) throw new Error(response.status === 403 ? "You do not have permission to view these records." : "Clinical notes could not be loaded. Please retry.");
      const next = await response.json() as JournalResponse;
      if (!isCurrent()) return;
      if (String(next.patient_id) !== patientId) throw new Error("Clinical notes could not be verified for this patient.");
      setFeed((old) => ({ target: requestTarget, data: { ...next, items: before && old?.target === requestTarget ? [...new Map([...old.data.items, ...next.items].map((item) => [item.key, item])).values()] : next.items } }));
      return true;
    } catch (caught) { if (isCurrent()) { if (!before) setFeed(null); setFeedError(caught instanceof Error ? caught.message : "Clinical notes could not be loaded."); } }
    finally { if (isCurrent()) { setLoading(false); setLoadingOlder(false); } }
  }, [canRead, target, category, debouncedQuery, toothFilter, patientId, unauthorized]);
  useEffect(() => { void load(); return () => { sequence.current += 1; }; }, [load, refreshKey]);
  useEffect(() => () => { sequence.current += 1; historySequence.current += 1; }, []);

  async function save() {
    const editing = draft.editing;
    const toothNote = editing ? editing.source_kind === "tooth_note" : Boolean(draft.tooth);
    if (mutationLock.current || saving || templateSaving || !(toothNote ? canWriteClinical : canWriteNotes)) return;
    if (!draft.body.trim() || draft.body.trim().length > JOURNAL_NOTE_MAX_LENGTH) { setSaveError({ patientId, message: `Enter a note between 1 and ${JOURNAL_NOTE_MAX_LENGTH} characters.` }); return; }
    if (editing && (!editing.can_edit || editing.revision === null || !["note", "tooth_note"].includes(editing.source_kind))) return;
    const savedPatient = patientId;
    let url: string;
    let method = "POST";
    let payload: Record<string, unknown>;
    if (editing) {
      url = toothNote ? `/api/patients/${patientId}/tooth-notes/${editing.source_id}` : `/api/notes/${editing.source_id}/amendments`;
      if (toothNote) method = "PATCH";
      payload = { expected_revision: editing.revision, [toothNote ? "note" : "body"]: draft.body.trim(), ...(draft.reason.trim() ? { reason: draft.reason.trim() } : {}) };
    } else {
      url = `/api/patients/${patientId}/${toothNote ? "tooth-notes" : "notes"}`;
      payload = { [toothNote ? "note" : "body"]: draft.body.trim(), ...(toothNote ? { tooth: draft.tooth, surface: null } : { note_type: draft.category === "admin" ? "admin" : "clinical" }), category: draft.category,
        ...(draft.clinical_date ? { clinical_date: draft.clinical_date } : {}), template_id: draft.template_id ?? null, template_revision: draft.template_revision ?? null, codes: draft.codes.map((code) => code.trim()).filter(Boolean) };
    }
    const fingerprint = JSON.stringify({ url, method, payload });
    const priorAttempt = attempts.current[patientId];
    if (priorAttempt?.uncertain && priorAttempt.fingerprint !== fingerprint) {
      setSaveError({ patientId, message: "An earlier save was not confirmed. Check the latest history before saving a changed draft." }); return;
    }
    const attempt = priorAttempt?.fingerprint === fingerprint ? priorAttempt : { fingerprint, headers: noteRequestHeaders(), uncertain: false };
    attempts.current[patientId] = attempt;
    mutationLock.current = true; setSaving(true); onSavingChange?.(true); setSaveError(null); setNotice(null);
    try {
      attempt.uncertain = true;
      const response = await apiFetch(url, { method, headers: attempt.headers, body: JSON.stringify(payload) });
      if (response.status === 401) { unauthorized(); return; }
      if (!response.ok) {
        if (response.status < 500) delete attempts.current[savedPatient];
        throw new Error(await noteResponseError(response, "Save could not be confirmed. Keep your draft and check the history before trying again."));
      }
      delete attempts.current[savedPatient]; setUncertainReviewed(false);
      setDrafts((old) => ({ ...old, [savedPatient]: emptyDraft() }));
      if (currentPatient.current === savedPatient) {
        setNotice({ patientId, message: editing ? "Note amended; earlier versions are retained." : "Note saved." }); setHistory(null); await load();
        if (currentPatient.current === savedPatient) await onSaved();
      }
    } catch (caught) { setSaveError({ patientId: savedPatient, message: caught instanceof Error ? caught.message : "Save could not be confirmed." }); }
    finally { mutationLock.current = false; setSaving(false); onSavingChange?.(false); }
  }
  async function showHistory(item: JournalItem) {
    if (history?.key === item.key) { historySequence.current += 1; setHistory(null); return; }
    const link = safeJournalLink(item.history_url);
    if (!link) return;
    const request = ++historySequence.current; const owner = patientId;
    setHistory({ patientId, key: item.key, loading: true, items: [] });
    try {
      const response = await apiFetch(link);
      if (request !== historySequence.current || owner !== currentPatient.current) return;
      if (response.status === 401) { unauthorized(); return; }
      if (!response.ok) throw new Error("Earlier versions could not be loaded.");
      const result = await response.json() as { items: Revision[]; next_before_revision?: number | null };
      if (request === historySequence.current && owner === currentPatient.current) setHistory({ patientId, key: item.key, loading: false, items: result.items, url: link, nextBefore: result.next_before_revision });
    } catch { if (request === historySequence.current && owner === currentPatient.current) setHistory({ patientId, key: item.key, loading: false, items: [], error: "Earlier versions could not be loaded." }); }
  }
  async function olderHistory() {
    if (!history?.url || history.nextBefore == null || history.loadingOlder) return;
    const previous = history; const historyUrl = history.url; const request = ++historySequence.current;
    setHistory({ ...previous, loadingOlder: true, error: undefined });
    try {
      const response = await apiFetch(`${historyUrl}${historyUrl.includes("?") ? "&" : "?"}before_revision=${previous.nextBefore}&limit=100`);
      if (request !== historySequence.current || currentPatient.current !== previous.patientId) return;
      if (response.status === 401) { unauthorized(); return; }
      if (!response.ok) throw new Error("Older versions could not be loaded.");
      const result = await response.json() as { items: Revision[]; next_before_revision?: number | null };
      if (request === historySequence.current && currentPatient.current === previous.patientId) setHistory({ ...previous, loadingOlder: false, nextBefore: result.next_before_revision, items: [...new Map([...previous.items, ...result.items].map((item) => [item.revision, item])).values()] });
    } catch { if (request === historySequence.current && currentPatient.current === previous.patientId) setHistory({ ...previous, loadingOlder: false, error: "Older versions could not be loaded. Retry loading older versions." }); }
  }
  function beginEdit(item: JournalItem) {
    if (saving || !item.can_edit || !["note", "tooth_note"].includes(item.source_kind)) return;
    if ((draft.body.trim() || draft.editing) && !window.confirm("Discard the current unsaved draft and edit this note?")) return;
    changeDraft({ ...emptyDraft(), body: item.body ?? "", tooth: item.tooth ?? "", editing: item }); bodyInput.current?.focus();
  }
  function insertTemplate(value: TemplateInsert) {
    changeDraft({ body: [draft.body.trim(), value.body].filter(Boolean).join("\n\n"), category: value.category, template_id: value.template_id, template_revision: value.template_revision, codes: value.codes });
    bodyInput.current?.focus();
  }
  const groups = useMemo(() => groupJournal(data?.items ?? []), [data]);
  const writer = draft.editing ? (draft.editing.source_kind === "tooth_note" ? canWriteClinical : canWriteNotes) : draft.tooth ? canWriteClinical : canWriteNotes;
  return <section ref={panel} tabIndex={-1} className={styles.panel} aria-label="Clinical notes" data-testid="clinical-notes-panel">
    <header className={styles.header}><h3>Clinical notes</h3><div className={styles.actions}>
      <button type="button" onClick={() => void load()} disabled={loading || saving || templateSaving}>Refresh</button>
      {onClose && <button type="button" data-testid="clinical-notes-toggle" aria-expanded="true" disabled={saving || templateSaving} onClick={onClose}>Hide notes</button>}
    </div></header>
    {!canRead ? <p role="status">Clinical notes are unavailable with your current permissions.</p> : <>
      <div className={styles.filters}>
        <label>Search records<input data-testid="clinical-notes-search" type="search" maxLength={200} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search notes and records" /></label>
        <div className={styles.pair}><label>Show<select data-testid="clinical-notes-category" value={category} onChange={(event) => setCategory(event.target.value as JournalCategory)}>{journalCategories.map((value) => <option key={value} value={value}>{journalLabels[value]}</option>)}</select></label>
          <label>Tooth<select data-testid="clinical-notes-tooth-filter" value={toothFilter} onChange={(event) => setToothFilter(event.target.value)}><option value="">All teeth</option>{noteTeeth.map((tooth) => <option key={tooth}>{tooth}</option>)}</select></label></div>
        {selectedTooth && <button type="button" className={styles.textButton} onClick={() => setToothFilter(selectedTooth)}>Show selected tooth {selectedTooth}</button>}
      </div>
      {(canWriteNotes || canWriteClinical) && <details open className={styles.composer} data-testid="clinical-notes-composer"><summary>{draft.editing ? "Amend note" : "Add a note"}</summary>
        <div className={styles.form}>
          {draft.editing ? <p className={styles.muted}>Editing {sourceNames[draft.editing.source_kind]} {draft.editing.tooth || ""} · version {draft.editing.revision}. Earlier text will be retained.</p> : <div className={styles.pair}>
            <label>Note for<select data-testid="clinical-notes-tooth" value={draft.tooth} disabled={saving} onChange={(event) => changeDraft({ tooth: event.target.value })}><option value="" disabled={!canWriteNotes}>Whole patient</option>{canWriteClinical && noteTeeth.map((tooth) => <option key={tooth}>{tooth}</option>)}</select></label>
            <label>Category<select data-testid="clinical-notes-type" value={draft.category} disabled={saving} onChange={(event) => changeDraft({ category: event.target.value })}>{noteCategories.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          </div>}
          {!draft.editing && <ClinicalNoteTemplates canRead={canReadNotes} canWrite={canWriteNotes} disabled={saving} onInsert={insertTemplate} onUnauthorized={unauthorized} onBusyChange={templateBusy} />}
          <div className={styles.noteEditor}>
            <label htmlFor={noteBodyId}>{draft.editing ? "Amended note text" : "Note text"}</label>
            <NoteWritingAssistant key={`${patientId}:${draft.tooth}:${draft.editing?.key ?? "new"}`} disabled={saving || templateSaving || !writer} />
            <textarea id={noteBodyId} data-testid="clinical-notes-body" ref={bodyInput} rows={4} maxLength={JOURNAL_NOTE_MAX_LENGTH} disabled={saving || !writer} value={draft.body} onChange={(event) => changeDraft({ body: event.target.value })} />
          </div>
          {draft.editing ? <label>Reason for amendment (optional)<input disabled={saving} value={draft.reason} onChange={(event) => changeDraft({ reason: event.target.value })} /></label>
            : <details><summary>Clinical date / code labels</summary><div className={styles.form}><label>Clinical date (optional)<input type="date" disabled={saving} value={draft.clinical_date} onChange={(event) => changeDraft({ clinical_date: event.target.value })} /></label><label>Code labels (optional, comma-separated)<input value={draft.codes.join(",")} disabled={saving} onChange={(event) => changeDraft({ codes: event.target.value.split(",") })} /></label></div></details>}
          <div className={styles.actions}><button type="button" data-testid="clinical-notes-save" disabled={!writer || saving || templateSaving || !draft.body.trim()} onClick={() => void save()}>{saving ? "Saving…" : draft.editing ? "Save amendment" : "Save note"}</button>
            <button type="button" data-testid="clinical-notes-cancel" disabled={saving || templateSaving} onClick={() => { if (draft.body.trim() && !window.confirm("Discard this unsaved note draft?")) return; changeDraft(emptyDraft()); }}>Cancel draft</button></div>
          {saveError?.patientId === patientId && <div role="alert" data-testid="clinical-notes-save-error">{saveError.message}</div>}
          {attempts.current[patientId]?.uncertain && !saving && <div className={styles.form}>
            <small>An unchanged retry uses the same request reference to avoid duplicate notes.</small>
            <button type="button" onClick={() => { const owner = patientId; void load().then((ok) => { if (ok && currentPatient.current === owner) setUncertainReviewed(true); }); }}>Check latest history</button>
            {uncertainReviewed && <button type="button" onClick={() => { if (!window.confirm("Have you checked the latest records and confirmed the earlier save did not succeed? Only continue if it is not recorded.")) return; delete attempts.current[patientId]; setUncertainReviewed(false); setSaveError(null); }}>Confirmed not saved — allow changed draft</button>}
          </div>}
          {notice?.patientId === patientId && <div role="status">{notice.message}</div>}
        </div>
      </details>}
      {readOnly && <p className={styles.muted}>This patient record is read-only.</p>}
      {data && <details className={styles.availability} data-testid="clinical-notes-availability"><summary>Record availability</summary>{Object.entries(data.availability).map(([source, value]) => <div key={source}>{source}: {typeof value === "string" ? value : value.availability ?? value.status ?? "unavailable"}</div>)}{data.coverage_notes?.map((message) => <p key={message}>{message}</p>)}<small>Only recorded information is shown. A generated letter is not evidence that it was sent.</small></details>}
      {feedError && <div role="alert" data-testid="clinical-notes-error">{feedError} <button type="button" onClick={() => void load()}>Retry</button></div>}
      <div className={styles.feed} aria-busy={loading}>
        {loading ? <p role="status">Loading clinical notes…</p> : !data ? null : !data.items.length ? <p data-testid="clinical-notes-empty">No matching recorded entries.</p> : groups.map(([day, items]) => <section key={day} className={styles.dateGroup} data-testid={`clinical-notes-date-${day}`}>
          <h4>{journalDayLabel(day)}</h4>{items.map((item) => <article key={item.key} data-testid={`clinical-notes-entry-${item.key}`} className={styles.entry}>
            <div className={styles.entryHeading}><strong>{item.title}</strong>{item.tooth && <span className={styles.tag}>{item.tooth}{item.surface ? ` ${item.surface}` : ""}</span>}</div>
            <div className={styles.meta}>{sourceNames[item.source_kind] ?? (item.source_kind.startsWith("r4_") ? "Imported record" : "Recorded entry")} · {["note", "tooth_note"].includes(item.source_kind) ? "Original author: " : ""}{item.author?.name || (item.author?.source_user_code != null ? `Unmapped author code ${item.author.source_user_code}` : "Author not recorded")}{item.revision !== null ? ` · v${item.revision}` : ""}</div>
            {["note", "tooth_note"].includes(item.source_kind) && (item.revision ?? 0) > 1 && !item.details?.latest_revision && <div className={styles.meta}>Updated record — see earlier versions for authors and times.</div>}
            <div className={styles.meta}>{item.occurred_at && Number.isFinite(Date.parse(item.occurred_at)) ? <time dateTime={item.occurred_at}>Recorded/event time: {new Date(item.occurred_at).toLocaleString("en-GB", { timeZone: "Europe/London" })}</time> : "Recorded/event time not available"}{item.clinical_date ? ` · Clinical date: ${item.clinical_date}` : ""}</div>
            {item.source_kind === "diagnosis" && <div className={styles.meta}>Recorded snapshot</div>}
            {item.source_kind === "diagnosis" ? <div data-testid={`clinical-notes-diagnosis-body-${item.key}`}>
              {journalDiagnosisLines(item).length ? journalDiagnosisLines(item).map((line, index) => <p key={index}>{line}</p>) : <p>Recorded diagnosis — see Source details.</p>}
            </div> : <p>{item.body}</p>}
            {journalDetailLines(item).map((line, index) => <div className={styles.meta} key={index}>{line}</div>)}
            <details className={styles.availability}><summary>Source details</summary>
              <div>Source: {item.source_kind} · Record: {item.source_id}</div><div>Date basis: {item.date_basis || "Not recorded"}</div>
              {item.author?.source_user_code != null && <div>Original author code: {item.author.source_user_code}</div>}
              {item.provenance && <div>{typeof item.provenance === "string" ? item.provenance : Object.entries(item.provenance).map(([key, value]) => `${key}: ${typeof value === "string" || typeof value === "number" ? value : JSON.stringify(value)}`).join(" · ")}</div>}
              {item.source_kind === "diagnosis" && <>
                <strong>Original generated record</strong><p style={{ whiteSpace: "pre-wrap" }}>{item.body ?? "No generated text recorded."}</p>
                <strong>Original diagnosis details</strong><p style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(item.details, null, 2)}</p>
              </>}
            </details>
            <div className={styles.actions}>
              {item.can_edit && !readOnly && (item.source_kind === "note" ? canWriteNotes : item.source_kind === "tooth_note" && canWriteClinical) && <button type="button" disabled={saving} data-testid={`clinical-notes-edit-${item.key}`} onClick={() => beginEdit(item)}>Edit note</button>}
              {safeJournalLink(item.history_url) && <button type="button" data-testid={`clinical-notes-history-${item.key}`} aria-expanded={history?.patientId === patientId && history.key === item.key} onClick={() => void showHistory(item)}>Earlier versions</button>}
              {safeJournalLink(item.link) && <a href={safeJournalLink(item.link)!}>Open record</a>}
              {!item.can_edit && <span className={styles.muted}>Read-only record</span>}
            </div>
            {history?.patientId === patientId && history.key === item.key && <div className={styles.history} data-testid="clinical-notes-history">
              {history.loading ? "Loading earlier versions…" : history.items.map((version) => <div key={version.revision}><strong>Version {version.revision}</strong>{version.baseline && <div className={styles.meta}>Baseline captured; earlier edits unavailable.</div>}<div className={styles.meta}>{version.recorded_by?.name || "Author not recorded"} · {version.recorded_at ? new Date(version.recorded_at).toLocaleString("en-GB", { timeZone: "Europe/London" }) : "Date not recorded"}{version.archived !== undefined ? ` · ${version.archived ? "Archived" : "Active"}` : ""}</div><p>{version.body}</p>{version.reason && <small>Reason: {version.reason}</small>}</div>)}
              {history.error && <p role="alert">{history.error}</p>}
              {history.nextBefore != null && <button type="button" data-testid="clinical-notes-history-older" disabled={history.loadingOlder} onClick={() => void olderHistory()}>{history.loadingOlder ? "Loading older versions…" : "Load older versions"}</button>}
            </div>}
          </article>)}
        </section>)}
      </div>
      {data?.next_cursor && <button type="button" data-testid="clinical-notes-older" disabled={loadingOlder || loading} onClick={() => void load(data.next_cursor!)}>{loadingOlder ? "Loading older…" : "Load older records"}</button>}
    </>}
  </section>;
}
