"use client";

import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type MouseEvent } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import TreatmentPlanningChart from "./TreatmentPlanningChart";
import { surfaceKeysForTooth, surfaceName, type SurfaceKey } from "./surfaceDiagnosis";
import { planningDrawingChoices, planningFeeError, planningFeeLabel, planningLevels, planningMoney, planningPence, planningRequestId, planningTargetLabel, planningToothLabel, type EarlierPlanningItem, type PlanningCatalogue, type PlanningCatalogueItem, type PlanningDrawingKind, type PlanningFee, type PlanningFeeMode, type PlanningItem, type PlanningLevel, type PlanningResponse, type PlanningSelection, type PlanningStatus, type PlanningTarget } from "./treatmentPlanning";
import styles from "./TreatmentPlanningPanel.module.css";

type Props = { patientId: string; canWriteClinical: boolean; canWriteBilling: boolean; onChanged: () => void | Promise<void>; onOpenEarlierItems?: () => void; onOpenToothNotes?: (tooth: string, event: MouseEvent<SVGElement> | KeyboardEvent<SVGElement>) => void };
type Draft = { target: PlanningTarget; treatment: PlanningCatalogueItem | null; drawing: PlanningDrawingKind | ""; mode: PlanningFeeMode; amount: string; reason: string; editing: PlanningItem | null };
const teeth = ["UR", "UL", "LR", "LL"].flatMap((quadrant) => Array.from({ length: 8 }, (_, index) => `${quadrant}${index + 1}`));
const blankDraft = (): Draft => ({ target: { level: "general", tooth: null, surfaces: [] }, treatment: null, drawing: "other", mode: "catalogue", amount: "", reason: "", editing: null });
const statusNames: Record<PlanningStatus, string> = { proposed: "Proposed", accepted: "Accepted", declined: "Declined", completed: "Completed", cancelled: "Cancelled" };
const feeModes: Record<PlanningFeeMode, string> = { catalogue: "Catalogue fee", agreed: "Agreed fee", override: "Override fee", waived: "Waived fee" };

export default function TreatmentPlanningPanel({ patientId, canWriteClinical, canWriteBilling, onChanged, onOpenEarlierItems, onOpenToothNotes }: Props) {
  const router = useRouter();
  const [data, setData] = useState<PlanningResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [level, setLevel] = useState<PlanningLevel>("tooth");
  const [selection, setSelection] = useState<PlanningSelection | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [catalogue, setCatalogue] = useState<PlanningCatalogue | null>(null);
  const [catalogueLoading, setCatalogueLoading] = useState(false);
  const [catalogueError, setCatalogueError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const dialog = useRef<HTMLDialogElement>(null);
  const opener = useRef<Element | null>(null);
  const alive = useRef(true);
  const owner = useRef(patientId); owner.current = patientId;
  const sequence = useRef(0);
  const catalogueSequence = useRef(0);
  const busy = useRef(false);
  const attempt = useRef<{ fingerprint: string; id: string; uncertain: boolean } | null>(null);
  const base = `/api/patients/${patientId}/planning`;
  const ready = Boolean(data && data.patient_id === Number(patientId) && !loading && !loadError);
  const writable = ready && canWriteClinical && !saving && !uncertain;
  const plan = data?.patient_id === Number(patientId) ? data.plan : null;
  const items = plan?.items ?? [];
  const outstanding = items.filter((item) => item.status === "proposed" || item.status === "accepted");
  const completed = items.filter((item) => item.status === "completed");
  const other = items.filter((item) => item.status === "cancelled" || item.status === "declined");
  const unauthorised = useCallback(() => { clearToken(); router.replace("/login"); }, [router]);

  useEffect(() => { alive.current = true; return () => { alive.current = false; sequence.current += 1; catalogueSequence.current += 1; }; }, []);
  useEffect(() => { const timer = setTimeout(() => { setSearch(query.trim()); setOffset(0); }, 200); return () => clearTimeout(timer); }, [query]);

  const load = useCallback(async () => {
    const ticket = ++sequence.current;
    setLoading(true); setLoadError(null);
    try {
      const response = await apiFetch(base);
      if (response.status === 401) { unauthorised(); return false; }
      if (!response.ok) throw new Error(response.status === 403 ? "You do not have permission to view this treatment plan." : "The treatment plan could not be loaded. Please retry before making changes.");
      const next = await response.json() as PlanningResponse;
      if (alive.current && ticket === sequence.current && owner.current === patientId) { setData(next); return true; }
    } catch (cause) { if (alive.current && ticket === sequence.current) setLoadError(cause instanceof Error ? cause.message : "The treatment plan could not be loaded."); }
    finally { if (alive.current && ticket === sequence.current) setLoading(false); }
    return false;
  }, [base, patientId, unauthorised]);
  useEffect(() => { setData(null); void load(); }, [load]);

  const pickerOpen = Boolean(draft && !draft.editing);
  const loadCatalogue = useCallback(async () => {
    if (!pickerOpen) return;
    const ticket = ++catalogueSequence.current;
    setCatalogueLoading(true); setCatalogueError(null); setCatalogue(null);
    try {
      const response = await apiFetch(`${base}/catalogue?${new URLSearchParams({ q: search, limit: "50", offset: String(offset) })}`);
      if (response.status === 401) { unauthorised(); return; }
      if (!response.ok) throw new Error(response.status === 403 ? "You do not have permission to view the treatment catalogue." : "The treatment catalogue could not be loaded. Retry before adding treatment.");
      const next = await response.json() as PlanningCatalogue;
      if (alive.current && ticket === catalogueSequence.current && owner.current === patientId) setCatalogue(next);
    } catch (cause) { if (alive.current && ticket === catalogueSequence.current) setCatalogueError(cause instanceof Error ? cause.message : "The catalogue is unavailable."); }
    finally { if (alive.current && ticket === catalogueSequence.current) setCatalogueLoading(false); }
  }, [base, offset, patientId, pickerOpen, search, unauthorised]);
  useEffect(() => { void loadCatalogue(); return () => { catalogueSequence.current += 1; }; }, [loadCatalogue]);

  useEffect(() => {
    if (draft && dialog.current && !dialog.current.open) { dialog.current.showModal(); dialog.current.querySelector<HTMLElement>("button:not(:disabled), input:not(:disabled)")?.focus(); }
    if (!draft && dialog.current?.open) dialog.current.close();
  }, [draft]);
  useEffect(() => { if (saving && dialog.current?.open) dialog.current.focus(); }, [saving]);

  const close = () => {
    if (busy.current) return;
    if (attempt.current?.uncertain && !window.confirm("The last save result is unknown. Close this draft and check the refreshed plan before adding anything again?")) return;
    if (attempt.current?.uncertain) void load();
    attempt.current = null; setUncertain(false); setDraft(null); setError(null);
    requestAnimationFrame(() => { if (opener.current?.isConnected) (opener.current as HTMLElement).focus?.({ preventScroll: true }); });
  };
  const openDraft = (target: PlanningTarget) => {
    if (!writable || !plan) return;
    opener.current = document.activeElement; setQuery(""); setSearch(""); setOffset(0); setError(null); setNotice(null);
    setDraft({ ...blankDraft(), target, drawing: target.level === "general" ? "other" : "" });
  };
  const onSelect = (next: PlanningSelection, event: MouseEvent<SVGElement | HTMLButtonElement> | KeyboardEvent<SVGElement | HTMLButtonElement>) => {
    if (!writable) return;
    setLevel(next.level); setSelection(next); openDraft(next); opener.current = event.currentTarget;
  };

  const mutate = async (path: string, method: "POST" | "PATCH", payload: Record<string, unknown>, success: string) => {
    if (busy.current || !canWriteClinical || !ready) return false;
    const fingerprint = JSON.stringify({ patientId, path, method, payload });
    if (attempt.current?.uncertain && attempt.current.fingerprint !== fingerprint) { setError("The previous save result is unknown. Retry that unchanged request, or close and review the latest plan first."); return false; }
    const request = attempt.current?.fingerprint === fingerprint ? attempt.current : { fingerprint, id: planningRequestId(), uncertain: false };
    attempt.current = request; busy.current = true; setSaving(true); setError(null); setNotice(null);
    try {
      const response = await apiFetch(path, { method, headers: { "Request-Id": request.id }, body: JSON.stringify(payload) });
      if (response.status === 401) { unauthorised(); return false; }
      if (!response.ok) {
        request.uncertain = response.status >= 500; setUncertain(request.uncertain);
        if (!request.uncertain) attempt.current = null;
        const message = response.status === 409 ? "This plan or catalogue quote changed. Close this draft, refresh, and review the latest saved details before trying again."
          : response.status === 403 ? "You do not have permission to make this change."
          : response.status === 422 ? "Check the selected treatment, target and fee. The change was not accepted."
          : response.status === 404 ? "This patient or treatment is no longer available. Refresh before continuing."
          : "The save result could not be confirmed. Retry the unchanged request or close and check the latest plan before making another change.";
        throw new Error(message);
      }
      attempt.current = null;
      if (!alive.current || owner.current !== patientId) return true;
      setUncertain(false); setDraft(null); setSelection(null); setNotice(success);
      requestAnimationFrame(() => { if (opener.current?.isConnected) (opener.current as HTMLElement).focus?.({ preventScroll: true }); });
      await load();
      if (alive.current && owner.current === patientId) await onChanged();
      return true;
    } catch (cause) {
      if (attempt.current === request && !request.uncertain) { request.uncertain = true; setUncertain(true); }
      if (alive.current && owner.current === patientId) setError(request.uncertain ? "The save result could not be confirmed. Retry the unchanged request or close and check the latest plan before making another change." : cause instanceof Error ? cause.message : "The change could not be confirmed. Refresh and review the plan.");
      return false;
    } finally { busy.current = false; if (alive.current && owner.current === patientId) setSaving(false); }
  };

  const draftFee: PlanningFee | null = draft?.editing?.catalogue_snapshot.fee ?? draft?.treatment?.fee ?? null;
  const feeError = draft && draftFee ? planningFeeError(draftFee, draft.mode, draft.amount, draft.reason) : null;
  const targetError = draft && draft.target.level !== "general" && !draft.target.tooth ? "Select a tooth." : draft?.target.level === "surface" && !draft.target.surfaces.length ? "Select at least one surface." : null;
  const saveDraft = () => {
    if (!draft || !draftFee || feeError || targetError || !draft.drawing || (!draft.editing && !draft.treatment)) return;
    const fee = { fee_mode: draft.mode, ...(draft.mode === "catalogue" ? {} : { fee_pence: draft.mode === "waived" ? 0 : planningPence(draft.amount) }), fee_reason: draft.mode === "catalogue" ? null : draft.reason.trim() || null };
    if (draft.editing) void mutate(`${base}/items/${draft.editing.id}`, "PATCH", { expected_revision: draft.editing.revision, ...fee }, "Treatment fee updated. No charge has been created.");
    else void mutate(`${base}/items`, "POST", { treatment_id: draft.treatment!.id, quote_token: draft.treatment!.quote_token, target: draft.target, drawing_kind: draft.drawing, ...fee }, "Treatment added to the plan. No charge has been created.");
  };
  const changeStatus = (item: PlanningItem, status: PlanningStatus) => {
    if (!writable || (status === "completed" && !canWriteBilling)) return;
    if (status === "completed" && item.fee_pence == null) { setError("Set an agreed fee or explicit waiver before completing this treatment."); return; }
    const message = status === "completed" ? `Complete ${item.description}? This records a completed clinical procedure and ${item.fee_pence ? `adds ${planningMoney(item.fee_pence)} to patient finance` : "adds no finance charge (saved zero fee)"}.`
      : `Mark ${item.description} as ${statusNames[status].toLowerCase()}?`;
    if (!window.confirm(message)) return;
    void mutate(`${base}/items/${item.id}`, "PATCH", { expected_revision: item.revision, status, ...(status === "completed" ? { confirm_finance: true } : {}) }, status === "completed" ? `Treatment completed. ${item.fee_pence ? `${planningMoney(item.fee_pence)} added to patient finance.` : "No finance charge was added."}` : `Treatment ${statusNames[status].toLowerCase()}.`);
  };
  const editFee = (item: PlanningItem) => {
    if (!writable) return;
    opener.current = document.activeElement; setError(null);
    setDraft({ ...blankDraft(), editing: item, target: item.target, drawing: item.drawing_kind, mode: item.fee_mode, amount: item.fee_pence == null ? "" : (item.fee_pence / 100).toFixed(2), reason: item.fee_reason ?? "" });
  };
  const changeTarget = (target: PlanningTarget) => setDraft((previous) => previous ? { ...previous, target, drawing: target.level === "general" ? "other" : "" } : null);
  const chooseTreatment = (treatment: PlanningCatalogueItem) => setDraft((previous) => previous ? { ...previous, treatment, mode: treatment.fee.type === "FIXED" ? "catalogue" : "agreed", amount: "", reason: "" } : null);
  const renderItem = (item: PlanningItem) => <article className={styles.item} key={item.id} data-testid={`planning-item-${item.id}`} data-status={item.status}>
    <div className={styles.itemContent}><strong>{item.description}</strong><span>{planningTargetLabel(item.target, plan?.snapshot)} · {item.procedure_code} · {statusNames[item.status]}</span>
      <small>{feeModes[item.fee_mode]}{item.fee_reason ? ` · ${item.fee_reason}` : ""}</small>
      <details><summary>Saved quote and treatment details</summary><p>{planningFeeLabel(item.catalogue_snapshot.fee)} · {item.catalogue_snapshot.patient_category ?? "Category not recorded"}</p><p>Drawing: {planningDrawingChoices.find((choice) => choice.value === item.drawing_kind)?.label ?? "Not recorded"}. Revision {item.revision}.</p></details>
      {(item.status === "proposed" || item.status === "accepted") && <div className={styles.actions}>
        <button type="button" className="btn btn-secondary" data-testid={`planning-edit-fee-${item.id}`} disabled={!writable} onClick={() => editFee(item)}>Edit fee</button>
        {item.status === "proposed" && <button type="button" className="btn btn-secondary" disabled={!writable} onClick={() => changeStatus(item, "accepted")}>Accept</button>}
        <button type="button" className="btn btn-secondary" disabled={!writable} onClick={() => changeStatus(item, "cancelled")}>Cancel treatment</button>
      </div>}
    </div>
    <div className={styles.itemFee}><strong>{planningMoney(item.fee_pence)}</strong>{(item.status === "proposed" || item.status === "accepted") && <button type="button" className="btn" data-testid={`planning-complete-${item.id}`} disabled={!writable || !canWriteBilling || item.fee_pence == null} title={!canWriteBilling ? "Billing permission is required to complete treatment." : undefined} onClick={() => changeStatus(item, "completed")}>Complete</button>}</div>
  </article>;
  const total = (entries: EarlierPlanningItem[]) => planningMoney(entries.reduce((sum, item) => sum + (item.fee_pence ?? 0), 0));

  return <section className={styles.panel} data-testid="treatment-planning-panel" aria-label="Treatment planning">
    <header className={styles.header}><div><h2>Treatment plan</h2>{plan && <small>Baseline captured {new Date(plan.snapshot.captured_at).toLocaleString("en-GB", { timeZone: "Europe/London" })} · current diagnosis is unchanged</small>}</div>
      <div className={styles.actions}><button type="button" className="btn btn-secondary" data-testid="planning-refresh" disabled={saving} onClick={() => { setError(null); void load(); }}>Refresh plan</button>{plan && <button type="button" className="btn" data-testid="planning-add-treatment" disabled={!writable} onClick={() => openDraft({ level: "general", tooth: null, surfaces: [] })}>Add treatment</button>}</div>
    </header>
    {loading && <p role="status" data-testid="planning-loading">Loading treatment plan…</p>}
    {loadError && <p role="alert" className={styles.error} data-testid="planning-load-error">{loadError}</p>}
    {error && !draft && <p role="alert" className={styles.error} data-testid="planning-error">{error}</p>}
    {notice && <p role="status" className={styles.notice} data-testid="planning-notice">{notice}</p>}
    {uncertain && !draft && <p className={styles.error}>The previous save result is unknown. Refresh and review the plan before making another change. <button type="button" className="btn btn-secondary" disabled={saving || loading} onClick={() => { if (window.confirm("Have you checked the refreshed plan and any completed treatment before continuing?")) { attempt.current = null; setUncertain(false); setError(null); } }}>I have reviewed the saved plan</button></p>}
    {ready && !canWriteClinical && <p className={styles.muted} data-testid="planning-read-only">Read-only treatment plan. Clinical write permission is required to make changes.</p>}
    {ready && !plan && <div className={styles.empty} data-testid="planning-not-started"><p>Start a treatment plan to capture the current chart once. Later diagnosis changes will not replace this saved baseline. Planning does not create a charge.</p><button type="button" className="btn" data-testid="planning-start" disabled={!writable} onClick={() => void mutate(`${base}/start`, "POST", {}, "Treatment plan started. The current chart baseline has been captured.")}>{saving ? "Starting…" : "Start treatment plan"}</button></div>}
    {plan && <>
      <div className={styles.tabs} role="tablist" aria-label="Planning level"><strong>Planning:</strong>{planningLevels.map((entry, index) => <button key={entry.value} type="button" role="tab" id={`planning-tab-${entry.value}`} aria-controls="planning-chart-panel" aria-selected={level === entry.value} tabIndex={level === entry.value ? 0 : -1} data-testid={`planning-level-${entry.value}`} disabled={saving || uncertain} onClick={() => { setLevel(entry.value); setSelection(null); }} onKeyDown={(event) => { if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return; event.preventDefault(); const next = event.key === "Home" ? 0 : event.key === "End" ? 3 : (index + (event.key === "ArrowRight" ? 1 : 3)) % 4; setLevel(planningLevels[next].value); setSelection(null); document.getElementById(`planning-tab-${planningLevels[next].value}`)?.focus(); }}>{entry.label}</button>)}</div>
      <div id="planning-chart-panel" className={styles.chartPanel} role="tabpanel" aria-labelledby={`planning-tab-${level}`}><TreatmentPlanningChart snapshot={plan.snapshot} items={items} level={level} selection={selection} disabled={!writable} onSelect={onSelect} onOpenToothNotes={onOpenToothNotes} /></div>
      {plan.snapshot.coverage.legacy !== "captured" && <details className={styles.muted} data-testid="planning-coverage"><summary>Baseline source coverage</summary>Native current observations captured. Imported chart coverage: {plan.snapshot.coverage.legacy}.{plan.snapshot.coverage.legacy_reason ? ` ${plan.snapshot.coverage.legacy_reason}` : " No missing findings have been inferred."}</details>}
      <div className={styles.summary} data-testid="planning-summary"><div><small>Outstanding · {outstanding.length} items</small><strong data-testid="planning-total-outstanding">{total(outstanding)}</strong>{outstanding.some((item) => item.fee_pence == null) && <small>Plus {outstanding.filter((item) => item.fee_pence == null).length} unpriced items</small>}</div><div><small>Completed · {completed.length} items</small><strong data-testid="planning-total-completed">{total(completed)}</strong></div></div>
      <section className={styles.group} aria-label="Outstanding treatment"><h3>Outstanding</h3><div className={styles.list}>{outstanding.length ? outstanding.map(renderItem) : <p className={styles.empty}>No outstanding treatment in this plan.</p>}</div></section>
      <section className={styles.group} aria-label="Completed treatment"><h3>Completed</h3><div className={styles.list}>{completed.length ? completed.map(renderItem) : <p className={styles.muted}>No treatment has been completed in this plan.</p>}</div></section>
      {other.length > 0 && <details><summary>Cancelled or declined · {other.length}</summary><div className={styles.list}>{other.map(renderItem)}</div></details>}
    </>}
    {ready && Boolean(data?.earlier_items_total) && <details data-testid="planning-earlier-items"><summary>Earlier treatment plan items · {data!.earlier_items_total}</summary><p className={styles.muted}>These items pre-date this planning workspace. They are kept separately and have not been given an inferred baseline or drawing.</p>{data!.earlier_items.map((item) => <div className={styles.item} key={item.id}><span>{item.tooth ?? "General"} · {item.description} · {statusNames[item.status]}</span><span>{planningMoney(item.fee_pence)}</span></div>)}{data!.earlier_items_total > data!.earlier_items.length && <p>Showing the latest {data!.earlier_items.length} items. Open earlier plan items for the full list.</p>}{onOpenEarlierItems && <button type="button" className="btn btn-secondary" disabled={saving} onClick={onOpenEarlierItems}>Open earlier plan items</button>}</details>}

    <dialog ref={dialog} className={styles.dialog} data-testid="planning-treatment-dialog" aria-label={draft?.editing ? "Edit treatment fee" : "Add treatment to plan"} onCancel={(event) => { event.preventDefault(); close(); }} onKeyDown={(event) => { if (saving && event.key === "Tab") { event.preventDefault(); dialog.current?.focus(); } }} tabIndex={-1}>
      {draft && <form onSubmit={(event) => { event.preventDefault(); saveDraft(); }}><header className={styles.header}><h3>{draft.editing ? "Edit treatment fee" : "Add treatment"}</h3><button type="button" className="btn btn-secondary" aria-label="Close treatment editor" disabled={saving} onClick={close}>Close</button></header>
        {error && <p role="alert" className={styles.error} data-testid="planning-error">{error}</p>}
        <fieldset disabled={saving || uncertain}>
          {!draft.editing && <><label>Search treatment catalogue<input data-testid="planning-catalogue-search" maxLength={200} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Treatment name or code" /></label>
            {catalogueLoading && <p role="status">Loading catalogue…</p>}{catalogueError && <p role="alert" className={styles.error}>{catalogueError} <button type="button" onClick={() => void loadCatalogue()}>Retry catalogue</button></p>}
            {catalogue && <><div className={styles.catalogue} aria-label="Treatment catalogue" data-testid="planning-catalogue">{catalogue.items.map((treatment) => <button type="button" key={treatment.id} data-testid={`planning-catalogue-item-${treatment.id}`} aria-pressed={draft.treatment?.id === treatment.id} onClick={() => chooseTreatment(treatment)}><span><strong>{treatment.name}</strong><small>{treatment.code ?? "No catalogue code"} · {treatment.patient_category.replaceAll("_", " ")}</small></span><span>{planningFeeLabel(treatment.fee)}</span></button>)}{!catalogue.items.length && <p>No matching active treatment. Try another name or code.</p>}</div>{catalogue.total > 50 && <div className={styles.actions}><button type="button" className="btn btn-secondary" disabled={offset === 0} onClick={() => setOffset((value) => Math.max(0, value - 50))}>Previous treatments</button><span>{offset + 1}–{Math.min(offset + 50, catalogue.total)} of {catalogue.total}</span><button type="button" className="btn btn-secondary" disabled={offset + 50 >= catalogue.total} onClick={() => setOffset((value) => value + 50)}>Next treatments</button></div>}</>}
            {draft.treatment && <p className={styles.quote}>Selected: <strong>{draft.treatment.name}</strong>{draft.treatment.description && <><br />{draft.treatment.description}</>}</p>}
            <div className={styles.formGrid}><label>Treatment level<select data-testid="planning-target-level" value={draft.target.level} onChange={(event) => changeTarget({ level: event.target.value as PlanningTarget["level"], tooth: event.target.value === "general" ? null : draft.target.tooth, surfaces: [] })}><option value="general">General treatment</option>{planningLevels.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label>
              {draft.target.level !== "general" && <label>Tooth<select data-testid="planning-target-tooth" value={draft.target.tooth ?? ""} onChange={(event) => changeTarget({ ...draft.target, tooth: event.target.value || null, surfaces: [] })}><option value="">Select tooth</option>{teeth.map((tooth) => <option key={tooth} value={tooth}>{planningToothLabel(tooth, plan?.snapshot)}</option>)}</select></label>}
            </div>
            {draft.target.level === "surface" && draft.target.tooth && <div className={styles.surfaces} role="group" aria-label="Treatment surfaces">{surfaceKeysForTooth(draft.target.tooth).map((surface) => <label key={surface}><input type="checkbox" data-testid={`planning-target-surface-${surface}`} checked={draft.target.surfaces.includes(surface)} onChange={() => setDraft({ ...draft, target: { ...draft.target, surfaces: surfaceKeysForTooth(draft.target.tooth!).filter((key) => key === surface ? !draft.target.surfaces.includes(key) : draft.target.surfaces.includes(key)) as SurfaceKey[] } })} />{surface} · {surfaceName(surface)}</label>)}</div>}
            <label>Chart drawing<select data-testid="planning-drawing-kind" value={draft.drawing} onChange={(event) => setDraft({ ...draft, drawing: event.target.value as PlanningDrawingKind })}><option value="">Choose the treatment drawing explicitly</option>{planningDrawingChoices.filter((choice) => choice.levels.includes(draft.target.level)).map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}</select><small className={styles.muted}>The drawing is selected by you, not inferred from the treatment name.</small></label>
          </>}
          {draft.editing && <p>{draft.editing.description} · {planningTargetLabel(draft.target, plan?.snapshot)}</p>}
          {draftFee && <><div className={styles.quote} data-testid="planning-fee-quote">Saved catalogue quote: <strong>{planningFeeLabel(draftFee)}</strong>{draftFee.notes && <><br />{draftFee.notes}</>}</div>
            <div className={styles.formGrid}><label>Fee choice<select data-testid="planning-fee-mode" value={draft.mode} onChange={(event) => setDraft({ ...draft, mode: event.target.value as PlanningFeeMode })}><option value="catalogue" disabled={draftFee.type !== "FIXED"}>Use catalogue fee</option><option value="agreed" disabled={draftFee.type === "FIXED"}>Agreed fee</option><option value="override">Override fee</option><option value="waived">Waive fee · £0.00</option></select></label>
              {(draft.mode === "agreed" || draft.mode === "override") && <label>Fee (£)<input data-testid="planning-fee-amount" inputMode="decimal" value={draft.amount} onChange={(event) => setDraft({ ...draft, amount: event.target.value })} placeholder="Explicit agreed amount" /></label>}
            </div>
            {draft.mode !== "catalogue" && <label>Fee reason{draft.mode === "agreed" && draftFee.type === "RANGE" ? " (optional)" : " (required)"}<textarea data-testid="planning-fee-reason" maxLength={500} value={draft.reason} onChange={(event) => setDraft({ ...draft, reason: event.target.value })} /></label>}
            {(feeError || targetError) && <p className={styles.muted} data-testid="planning-validation">{feeError || targetError}</p>}
            {draft.mode === "waived" && <p className={styles.muted}>This item will be recorded as explicitly waived. Completing it creates a clinical procedure but no finance charge.</p>}
          </>}
        </fieldset>
        <p className={styles.muted}>Adding or changing a plan item does not charge the patient. Complete the saved treatment to record the procedure and its saved fee in finance.</p>
        <div className={styles.actions}><button type="button" className="btn btn-secondary" data-testid="planning-cancel" disabled={saving} onClick={close}>Cancel</button><button type="submit" className="btn" data-testid="planning-save" disabled={saving || !canWriteClinical || !ready || Boolean(feeError || targetError) || !draftFee || !draft.drawing || (!draft.editing && (!draft.treatment || catalogueLoading || Boolean(catalogueError)))}>{saving ? "Saving…" : uncertain ? "Retry unchanged save" : draft.editing ? "Save fee" : "Add to plan"}</button></div>
      </form>}
    </dialog>
  </section>;
}
