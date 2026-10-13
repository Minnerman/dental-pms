"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import { medicationInputs, PrescriptionMedication, PrescriptionTemplate } from "@/lib/prescriptions";

type Draft = PrescriptionMedication & { name: string; is_active: boolean };
const emptyDraft = (): Draft => ({ name: "", medicine: "", directions: "", quantity: "", is_active: true });

export default function PrescriptionTemplates() {
  const router = useRouter();
  const [templates, setTemplates] = useState<PrescriptionTemplate[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [canManage, setCanManage] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const savingRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [me, list] = await Promise.all([
          apiFetch("/api/me"), apiFetch("/api/prescription-templates?include_inactive=true"),
        ]);
        if (cancelled) return;
        if (me.status === 401 || list.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        if (!me.ok || !list.ok) throw new Error("Prescription templates could not be loaded.");
        const user = await me.json() as { role: string };
        const data = await list.json() as PrescriptionTemplate[];
        if (!cancelled) {
          setCanManage(user.role === "superadmin");
          setTemplates(data);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load prescription templates.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [router]);

  function chooseTemplate(id: string) {
    const selected = templates.find((item) => String(item.id) === id);
    setSelectedId(selected?.id ?? null);
    setDraft(selected ? {
      name: selected.name, medicine: selected.medicine, directions: selected.directions,
      quantity: selected.quantity, is_active: selected.is_active,
    } : emptyDraft());
    setError(null);
    setNotice(null);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canManage || savingRef.current) return;
    const payload = {
      name: draft.name.trim(), medicine: draft.medicine.trim(), directions: draft.directions.trim(),
      quantity: draft.quantity.trim(), is_active: draft.is_active,
    };
    if (!payload.name || !payload.medicine || !payload.directions) {
      setError("Enter a name, medicine and directions.");
      return;
    }
    savingRef.current = true;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const response = await apiFetch(`/api/prescription-templates${selectedId === null ? "" : `/${selectedId}`}`, {
        method: selectedId === null ? "POST" : "PUT", body: JSON.stringify(payload),
      });
      if (response.status === 401) {
        clearToken(); router.replace("/login"); return;
      }
      if (!response.ok) {
        throw new Error(response.status === 403 ? "Only superadmins can manage prescription templates."
          : response.status === 422 ? "Check the prescription details and try again."
          : "The prescription template could not be saved. Your entries have been kept.");
      }
      const saved = await response.json() as PrescriptionTemplate;
      setTemplates((current) => [...current.filter((item) => item.id !== saved.id), saved]
        .sort((a, b) => a.name.localeCompare(b.name) || a.id - b.id));
      setSelectedId(saved.id);
      setDraft(payload);
      setNotice("Prescription template saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save prescription template.");
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  return (
    <div className="card stack" data-testid="prescription-templates-panel">
      <h2 style={{ margin: 0 }}>Prescription templates</h2>
      <p style={{ margin: 0, color: "var(--muted)" }}>
        Save your usual prescriptions here, then choose one from the dropdown when preparing a patient&apos;s prescription.
      </p>
      {loading && <div className="badge">Loading templates…</div>}
      {error && <div className="notice" role="alert">{error}</div>}
      {notice && <div className="badge" role="status">{notice}</div>}
      {!loading && <>
        <label className="stack" style={{ gap: 6 }}>
          <span className="label">Saved prescriptions</span>
          <select className="input" disabled={saving} value={selectedId ?? ""}
            onChange={(event) => chooseTemplate(event.target.value)} data-testid="prescription-template-select">
            <option value="">New prescription template</option>
            {templates.map((item) => <option value={item.id} key={item.id}>
              {item.name}{item.is_active ? "" : " (inactive)"}
            </option>)}
          </select>
        </label>
        {templates.length === 0 && <div className="notice">No saved prescriptions yet. Add your first template below.</div>}
        {!canManage && <div className="notice">Only superadmins can create or edit prescription templates.</div>}
        <p>Quantity may be left blank here; it must be entered for each patient prescription. Review each favourite against the patient’s needs and current prescribing guidance.</p>
        <form onSubmit={save}>
          <fieldset className="stack" disabled={saving || !canManage} style={{ border: 0, padding: 0, margin: 0 }}>
            <label className="stack" style={{ gap: 6 }}>
              <span className="label">Template name</span>
              <input className="input" required maxLength={200} value={draft.name}
                onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
                data-testid="prescription-template-name" />
            </label>
            {medicationInputs.map((input) => <label className="stack" style={{ gap: 6 }} key={input.key}>
              <span className="label">{input.label}</span>
              <textarea className="input" required={input.key !== "quantity"} rows={input.rows} maxLength={input.maxLength}
                value={draft[input.key]}
                onChange={(event) => setDraft((current) => ({ ...current, [input.key]: event.target.value }))}
                data-testid={`prescription-template-${input.key}`} />
            </label>)}
            <label className="row" style={{ gap: 8 }}>
              <input type="checkbox" checked={draft.is_active}
                onChange={(event) => setDraft((current) => ({ ...current, is_active: event.target.checked }))}
                data-testid="prescription-template-active" />
              Available in the prescription dropdown
            </label>
            <div className="row">
              <button className="btn btn-primary" type="submit" data-testid="prescription-template-save">
                {saving ? "Saving..." : "Save prescription template"}
              </button>
              <button className="btn btn-secondary" type="button" onClick={() => chooseTemplate("")}>New template</button>
            </div>
          </fieldset>
        </form>
      </>}
    </div>
  );
}
