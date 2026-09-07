"use client";
import { useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/auth";
import { JOURNAL_NOTE_MAX_LENGTH, noteRequestHeaders, renderNoteTemplate, type ClinicalNoteTemplate } from "./clinicalNotes";
import styles from "./ClinicalNotesPanel.module.css";

export type TemplateInsert = { body: string; template_id: number; template_revision: number; codes: string[]; category: string };
type Props = { canRead: boolean; canWrite: boolean; disabled: boolean; onInsert: (value: TemplateInsert) => void; onUnauthorized: () => void; onBusyChange?: (busy: boolean) => void };
const categories = [["clinical", "Clinical"], ["admin", "Admin"], ["medical", "Medical"], ["soft_tissue", "Soft tissue"], ["correspondence", "Correspondence"]];
export { categories as noteCategories };
type Editor = Pick<ClinicalNoteTemplate, "title" | "body" | "category" | "codes" | "fields"> & { id?: number; revision?: number };
const emptyEditor = (): Editor => ({ title: "", body: "", category: "clinical", codes: [], fields: [] });

export default function ClinicalNoteTemplates({ canRead, canWrite, disabled, onInsert, onUnauthorized, onBusyChange }: Props) {
  const [items, setItems] = useState<ClinicalNoteTemplate[]>([]);
  const [selected, setSelected] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [editor, setEditor] = useState<Editor | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const lock = useRef(false);
  const attempt = useRef<{ fingerprint: string; headers: Record<string, string> } | null>(null);
  const template = items.find((item) => String(item.id) === selected);
  useEffect(() => {
    if (!canRead) { setItems([]); return; }
    let current = true;
    setLoading(true);
    void apiFetch("/api/clinical-note-templates").then(async (response) => {
      if (!current) return;
      if (response.status === 401) { onUnauthorized(); return; }
      if (!response.ok) throw new Error("Note templates could not be loaded.");
      const data = await response.json() as ClinicalNoteTemplate[];
      if (current) setItems(data);
    }).catch(() => { if (current) setError("Note templates could not be loaded."); }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [canRead, onUnauthorized]);
  async function saveTemplate() {
    if (!editor || !canWrite || disabled || loading || lock.current) return;
    if (!editor.title.trim() || !editor.body.trim()) { setError("Enter a template name and text."); return; }
    lock.current = true; setSaving(true); onBusyChange?.(true); setError(null);
    try {
      const { id, revision } = editor;
      const values = { title: editor.title.trim(), body: editor.body, category: editor.category,
        codes: editor.codes.map((code) => code.trim()).filter(Boolean),
        fields: editor.fields.map((field) => ({ key: field.key.trim(), label: field.label.trim(), options: field.options.map((option) => option.trim()).filter(Boolean), required: field.required })) };
      const fingerprint = JSON.stringify({ id, revision, ...values });
      if (attempt.current && attempt.current.fingerprint !== fingerprint) throw new Error("A previous template save was not confirmed. Reload and check the template list before changing this draft.");
      if (!attempt.current) attempt.current = { fingerprint, headers: noteRequestHeaders() };
      const response = await apiFetch(`/api/clinical-note-templates${id ? `/${id}` : ""}`, {
        method: id ? "PATCH" : "POST", headers: attempt.current.headers,
        body: JSON.stringify({ ...values, ...(id ? { expected_revision: revision } : {}) }),
      });
      if (response.status === 401) { onUnauthorized(); return; }
      if (!response.ok) {
        if (response.status < 500) attempt.current = null;
        throw new Error(response.status === 409 ? "Template changed. Close this editor and reload before editing again." : "Template was not confirmed saved. Check its name, questions and text, then try again.");
      }
      attempt.current = null;
      const saved = await response.json() as ClinicalNoteTemplate;
      setItems((old) => [...old.filter((item) => item.id !== saved.id), saved]); setSelected(String(saved.id)); setAnswers({}); setEditor(null);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Template could not be saved."); }
    finally { lock.current = false; setSaving(false); onBusyChange?.(false); }
  }
  if (!canRead) return null;
  return <details className={styles.templates} data-testid="clinical-note-templates">
    <summary>Note templates</summary>
    <div className={styles.form}>
      {error && <div role="alert">{error}</div>}
      <label>Template<select data-testid="clinical-note-template-select" value={selected} disabled={disabled || saving || loading}
        onChange={(event) => { setSelected(event.target.value); setAnswers({}); setError(null); }}>
        <option value="">{loading ? "Loading templates…" : "Choose a template"}</option>
        {items.map((item) => <option key={item.id} value={item.id}>{item.title}{item.codes.length ? ` · ${item.codes.join(", ")}` : ""}</option>)}
      </select></label>
      {template && <>
        {template.fields.map((field) => <label key={field.key}>{field.label}{field.required ? " (required)" : " (optional)"}
          <select data-testid={`clinical-note-template-answer-${field.key}`} value={answers[field.key] ?? ""} disabled={disabled || saving}
            onChange={(event) => setAnswers((old) => ({ ...old, [field.key]: event.target.value }))}>
            <option value="">Choose an answer</option>{field.options.map((option) => <option key={option} value={option}>{option}</option>)}
          </select>
        </label>)}
        <button type="button" data-testid="clinical-note-template-use" disabled={disabled || saving}
          onClick={() => { const rendered = renderNoteTemplate(template, answers); if (rendered.missing.length) { setError(`Answer: ${rendered.missing.join(", ")}.`); return; } setError(null); onInsert({ body: rendered.body, template_id: template.id, template_revision: template.revision, codes: template.codes, category: template.category }); }}>
          Insert into draft
        </button>
        <small>Review the draft before saving. Codes are labels only; no treatment, prescription or charge is created.</small>
      </>}
      {canWrite && <div className={styles.actions}>
        <button type="button" data-testid="clinical-note-template-new" disabled={disabled || saving || loading} onClick={() => { setEditor(emptyEditor()); setError(null); }}>New template</button>
        <button type="button" data-testid="clinical-note-template-edit" disabled={!template || disabled || saving || loading} onClick={() => { if (template) setEditor({ id: template.id, revision: template.revision, title: template.title, body: template.body, category: template.category, codes: [...template.codes], fields: template.fields.map((field) => ({ ...field })) }); }}>Edit template</button>
      </div>}
      {editor && <fieldset className={styles.form} disabled={disabled || saving} data-testid="clinical-note-template-editor">
        <legend>{editor.id ? "Edit template" : "New template"}</legend>
        <label>Name<input value={editor.title} maxLength={160} onChange={(event) => setEditor({ ...editor, title: event.target.value })} /></label>
        <label>Category<select value={editor.category} onChange={(event) => setEditor({ ...editor, category: event.target.value })}>{categories.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Template text<textarea rows={5} maxLength={JOURNAL_NOTE_MAX_LENGTH} value={editor.body} onChange={(event) => setEditor({ ...editor, body: event.target.value })} /></label>
        <label>Codes (optional, comma-separated)<input value={editor.codes.join(",")} onChange={(event) => setEditor({ ...editor, codes: event.target.value.split(",") })} /></label>
        {editor.fields.map((field, index) => <div className={styles.question} key={index}>
          <label>Question {index + 1} key<input value={field.key} onChange={(event) => setEditor({ ...editor, fields: editor.fields.map((f, i) => i === index ? { ...f, key: event.target.value } : f) })} /></label>
          <label>Question {index + 1} label<input value={field.label} onChange={(event) => setEditor({ ...editor, fields: editor.fields.map((f, i) => i === index ? { ...f, label: event.target.value } : f) })} /></label>
          <label>Question {index + 1} answers (one per line)<textarea value={field.options.join("\n")} onChange={(event) => setEditor({ ...editor, fields: editor.fields.map((f, i) => i === index ? { ...f, options: event.target.value.split("\n") } : f) })} /></label>
          <label className={styles.check}><input type="checkbox" checked={field.required} onChange={(event) => setEditor({ ...editor, fields: editor.fields.map((f, i) => i === index ? { ...f, required: event.target.checked } : f) })} />Required answer</label>
          <div className={styles.actions}><button type="button" onClick={() => setEditor({ ...editor, body: `${editor.body}{{${field.key}}}` })}>Insert question {index + 1}</button><button type="button" onClick={() => setEditor({ ...editor, fields: editor.fields.filter((_, i) => i !== index) })}>Remove question {index + 1}</button></div>
        </div>)}
        <button type="button" onClick={() => setEditor({ ...editor, fields: [...editor.fields, { key: `question${editor.fields.length + 1}`, label: "", options: [], required: true }] })}>Add dropdown question</button>
        <div className={styles.actions}><button type="button" data-testid="clinical-note-template-save" onClick={() => void saveTemplate()}>{saving ? "Saving…" : "Save template"}</button><button type="button" onClick={() => setEditor(null)}>Cancel template edit</button></div>
      </fieldset>}
    </div>
  </details>;
}
