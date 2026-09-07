"use client";

import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type MouseEvent } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import TreatmentPlanningChart from "./TreatmentPlanningChart";
import { surfaceKeysForTooth, surfaceName, type SurfaceKey } from "./surfaceDiagnosis";
import { planningCustomFeeError, planningDrawingChoices, planningFeeDateLabel, planningFeeError, planningFeeLabel, planningLevels, planningMoney, planningPence, planningRequestId, planningTargetLabel, planningToothLabel, type EarlierPlanningItem, type PlanningCatalogue, type PlanningCatalogueItem, type PlanningDrawingKind, type PlanningFee, type PlanningFeeMode, type PlanningItem, type PlanningResponse, type PlanningSelection, type PlanningStatus, type PlanningTarget } from "./treatmentPlanning";
import styles from "./TreatmentPlanningPanel.module.css";

type Props = { patientId: string; canWriteClinical: boolean; canWriteBilling: boolean; onChanged: () => void | Promise<void>; onOpenEarlierItems?: () => void; onOpenToothNotes?: (tooth: string, event: MouseEvent<SVGElement> | KeyboardEvent<SVGElement>) => void };
type Draft = { target: PlanningTarget; treatment: PlanningCatalogueItem | null; drawing: PlanningDrawingKind | ""; mode: PlanningFeeMode; amount: string; reason: string; editing: PlanningItem | null; custom: boolean; description: string };
const teeth = ["UR", "UL", "LR", "LL"].flatMap((quadrant) => Array.from({ length: 8 }, (_, index) => `${quadrant}${index + 1}`));
const blankDraft = (): Draft => ({ target: { level: "general", tooth: null, surfaces: [] }, treatment: null, drawing: "other", mode: "catalogue", amount: "", reason: "", editing: null, custom: false, description: "" });
const statusNames: Record<PlanningStatus, string> = { proposed: "Proposed", accepted: "Accepted", declined: "Declined", completed: "Completed", cancelled: "Cancelled" };
const feeModes: Record<PlanningFeeMode, string> = { catalogue: "Catalogue fee", agreed: "Agreed fee", override: "Override fee", waived: "Waived fee" };
const planningTabs: { value: PlanningTarget["level"]; label: string }[] = [...planningLevels, { value: "general", label: "Miscellaneous" }];

export default function TreatmentPlanningPanel({ patientId, canWriteClinical, canWriteBilling, onChanged, onOpenEarlierItems, onOpenToothNotes }: Props) {
  const router = useRouter();
  const [data, setData] = useState<PlanningResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [level, setLevel] = useState<PlanningTarget["level"]>("tooth");
  const [customDescription, setCustomDescription] = useState("");
  const [customAmount, setCustomAmount] = useState("");
  const [customWaived, setCustomWaived] = useState(false);
  const [customReason, setCustomReason] = useState("");
  const [selection, setSelection] = useState<PlanningSelection | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detailsItem, setDetailsItem] = useState<PlanningItem | null>(null);
  const [uncompleteItem, setUncompleteItem] = useState<PlanningItem | null>(null);
  const [uncompleteReason, setUncompleteReason] = useState("");
  const [catalogue, setCatalogue] = useState<PlanningCatalogue | null>(null);
  const [catalogueLoading, setCatalogueLoading] = useState(false);
  const [catalogueError, setCatalogueError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [catalogueScope, setCatalogueScope] = useState<"target" | "all">("target");
  const dialog = useRef<HTMLDialogElement>(null);
  const customProgressDialog = useRef<HTMLDialogElement>(null);
  const detailsDialog = useRef<HTMLDialogElement>(null);
  const uncompleteDialog = useRef<HTMLDialogElement>(null);
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
  const selectedItem = items.find((item) => item.id === selectedId) ?? null;
  const selectedOutstanding = selectedItem?.status === "proposed" || selectedItem?.status === "accepted";
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
  useEffect(() => { setCustomDescription(""); setCustomAmount(""); setCustomWaived(false); setCustomReason(""); }, [patientId]);

  const pickerOpen = Boolean(draft && !draft.editing && !draft.custom);
  const catalogueLevel = draft?.target.level ?? "general";
  const loadCatalogue = useCallback(async () => {
    if (!pickerOpen) return;
    const ticket = ++catalogueSequence.current;
    setCatalogueLoading(true); setCatalogueError(null); setCatalogue(null);
    try {
      const parameters = new URLSearchParams({ q: search, limit: "50", offset: String(offset) });
      if (catalogueScope === "target") { parameters.set("level", catalogueLevel); parameters.set("include_unassigned", "true"); }
      const response = await apiFetch(`${base}/catalogue?${parameters}`);
      if (response.status === 401) { unauthorised(); return; }
      if (!response.ok) throw new Error(response.status === 403 ? "You do not have permission to view the treatment catalogue." : "The treatment catalogue could not be loaded. Retry before adding treatment.");
      const next = await response.json() as PlanningCatalogue;
      if (alive.current && ticket === catalogueSequence.current && owner.current === patientId) setCatalogue(next);
    } catch (cause) { if (alive.current && ticket === catalogueSequence.current) setCatalogueError(cause instanceof Error ? cause.message : "The catalogue is unavailable."); }
    finally { if (alive.current && ticket === catalogueSequence.current) setCatalogueLoading(false); }
  }, [base, catalogueLevel, catalogueScope, offset, patientId, pickerOpen, search, unauthorised]);
  useEffect(() => { void loadCatalogue(); return () => { catalogueSequence.current += 1; }; }, [loadCatalogue]);

  useEffect(() => {
    if (draft && dialog.current && !dialog.current.open) { dialog.current.showModal(); dialog.current.querySelector<HTMLElement>("button:not(:disabled), input:not(:disabled)")?.focus(); }
    if (!draft && dialog.current?.open) dialog.current.close();
  }, [draft]);
  useEffect(() => {
    if (detailsItem && detailsDialog.current && !detailsDialog.current.open) { detailsDialog.current.showModal(); detailsDialog.current.querySelector<HTMLButtonElement>("button")?.focus(); }
    if (!detailsItem && detailsDialog.current?.open) detailsDialog.current.close();
  }, [detailsItem]);
  useEffect(() => {
    if (uncompleteItem && uncompleteDialog.current && !uncompleteDialog.current.open) { uncompleteDialog.current.showModal(); uncompleteDialog.current.querySelector<HTMLTextAreaElement>("textarea")?.focus(); }
    if (!uncompleteItem && uncompleteDialog.current?.open) uncompleteDialog.current.close();
  }, [uncompleteItem]);
  useEffect(() => { if (saving) { if (dialog.current?.open) dialog.current.focus(); if (uncompleteDialog.current?.open) uncompleteDialog.current.focus(); if (customProgressDialog.current?.open) customProgressDialog.current.focus(); } }, [saving]);

  const close = () => {
    if (busy.current) return;
    if (attempt.current?.uncertain && !window.confirm("The last save result is unknown. Close this draft and check the refreshed plan before adding anything again?")) return;
    if (attempt.current?.uncertain) void load();
    attempt.current = null; setUncertain(false); setDraft(null); setUncompleteItem(null); setError(null);
    requestAnimationFrame(() => { if (opener.current?.isConnected) (opener.current as HTMLElement).focus?.({ preventScroll: true }); });
  };
  const openDraft = (target: PlanningTarget) => {
    if (!writable || !plan) return;
    opener.current = document.activeElement; setQuery(""); setSearch(""); setOffset(0); setCatalogueScope("target"); setError(null); setNotice(null);
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
        request.uncertain = request.uncertain || response.status >= 500; setUncertain(request.uncertain);
        if (!request.uncertain) attempt.current = null;
        const message = response.status === 409 ? path.endsWith("/uncomplete") ? "This completion could not be reversed safely. Close this dialog, refresh the plan and review its clinical and financial record before trying again." : "This plan or catalogue quote changed. Close this draft, refresh, and review the latest saved details before trying again."
          : response.status === 403 ? "You do not have permission to make this change."
          : response.status === 422 ? path.endsWith("/uncomplete") ? "This completion cannot be reversed automatically. Check the correction reason and review the completion's account links. No records were changed." : "Check the selected treatment, target and fee. The change was not accepted."
          : response.status === 404 ? "This patient or treatment is no longer available. Refresh before continuing."
          : "The save result could not be confirmed. Retry the unchanged request or close and check the latest plan before making another change.";
        throw new Error(message);
      }
      attempt.current = null;
      if (!alive.current || owner.current !== patientId) return true;
      setUncertain(false); setDraft(null); setUncompleteItem(null); setSelection(null); setNotice(success);
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

  const customEditing = draft?.editing?.catalogue_snapshot.source === "custom";
  const customDraft = Boolean(customEditing || draft?.custom);
  const draftFee: PlanningFee | null = customDraft ? null : draft?.editing ? draft.editing.catalogue_snapshot.source === "custom" ? null : draft.editing.catalogue_snapshot.fee : draft?.treatment?.fee ?? null;
  const feeError = draft ? customDraft ? planningCustomFeeError(draft.mode, draft.amount, draft.reason) : draftFee ? planningFeeError(draftFee, draft.mode, draft.amount, draft.reason) : null : null;
  const descriptionError = draft?.custom && !draft.editing ? !draft.description.trim() ? "Enter a treatment description." : draft.description.trim().length > 2000 ? "Keep the description to 2,000 characters." : null : null;
  const customFeeError = planningCustomFeeError(customWaived ? "waived" : "agreed", customAmount, customReason);
  const customError = !customDescription.trim() ? "Enter a treatment description." : customDescription.trim().length > 2000 ? "Keep the description to 2,000 characters." : customFeeError;
  const clearCustom = () => { setCustomDescription(""); setCustomAmount(""); setCustomWaived(false); setCustomReason(""); };
  const closeCustomProgress = () => {
    customProgressDialog.current?.close();
    requestAnimationFrame(() => { if (opener.current?.isConnected) (opener.current as HTMLElement).focus?.({ preventScroll: true }); });
  };
  const saveCustom = async () => {
    if (customError || !plan || busy.current || !ready || !canWriteClinical) return;
    if (!customProgressDialog.current?.open) { opener.current = document.activeElement; customProgressDialog.current?.showModal(); customProgressDialog.current?.focus(); }
    const saved = await mutate(`${base}/custom-items`, "POST", { description: customDescription.trim(), fee_pence: customWaived ? 0 : planningPence(customAmount), fee_mode: customWaived ? "waived" : "agreed", fee_reason: customWaived ? customReason.trim() : null }, "Miscellaneous treatment added to the plan. No charge has been created.");
    if (!alive.current || owner.current !== patientId) return;
    if (saved) clearCustom();
    if (!attempt.current?.uncertain) closeCustomProgress();
  };
  const reviewCustomResult = async () => {
    if (busy.current || loading || !window.confirm("This treatment may already have been added. Refresh the saved plan and discard this unsent draft? Check the outstanding list before adding it again.")) return;
    if (await load()) { attempt.current = null; setUncertain(false); setError(null); clearCustom(); setNotice("Plan refreshed. Check the outstanding list before adding this treatment again."); closeCustomProgress(); }
  };
  const abandonCustomAfterLoadFailure = () => {
    if (!loadError || loading || busy.current || !window.confirm("The save result is still unknown and the plan could not be refreshed. Close and discard this draft without retrying? You must reload and check the saved plan before adding this treatment again.")) return;
    attempt.current = null; setUncertain(false); clearCustom();
    setError("The previous save result remains unconfirmed. Reload and check the saved plan before adding that treatment again.");
    closeCustomProgress();
  };
  const categoryError = draft && !draft.editing && !draft.custom && draft.treatment?.level && draft.treatment.level !== draft.target.level
    ? `This catalogue treatment belongs to ${draft.treatment.level === "general" ? "general treatment" : `the ${draft.treatment.level} level`}. Select that target level or choose a different treatment.` : null;
  const targetError = draft && draft.target.level !== "general" && !draft.target.tooth ? "Select a tooth." : draft?.target.level === "surface" && !draft.target.surfaces.length ? "Select at least one surface." : categoryError;
  const saveDraft = () => {
    if (!draft || (!draftFee && !customDraft) || feeError || targetError || descriptionError || !draft.drawing || (!draft.editing && !draft.custom && !draft.treatment)) return;
    const fee = { fee_mode: draft.mode, ...(draft.mode === "catalogue" ? {} : { fee_pence: draft.mode === "waived" ? 0 : planningPence(draft.amount) }), fee_reason: draft.mode === "catalogue" ? null : draft.reason.trim() || null };
    if (draft.editing) void mutate(`${base}/items/${draft.editing.id}`, "PATCH", { expected_revision: draft.editing.revision, ...fee }, "Treatment fee updated. No charge has been created.");
    else if (draft.custom) void mutate(`${base}/custom-items`, "POST", { target: draft.target, description: draft.description.trim(), ...fee }, "Other treatment added to the plan. No charge has been created.");
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
  const changeTarget = (target: PlanningTarget) => {
    setOffset(0);
    setDraft((previous) => previous ? { ...previous, target, drawing: previous.custom || target.level === "general" ? "other" : "" } : null);
  };
  const chooseTreatment = (treatment: PlanningCatalogueItem) => setDraft((previous) => previous ? { ...previous, custom: false, treatment, mode: treatment.fee.type === "FIXED" ? "catalogue" : "agreed", amount: "", reason: "" } : null);
  const chooseOtherTreatment = () => setDraft((previous) => previous && !previous.custom ? { ...previous, custom: true, treatment: null, drawing: "other", mode: "agreed", amount: "", reason: "" } : previous);
  const chooseCatalogue = () => setDraft((previous) => previous?.custom ? { ...previous, custom: false, treatment: null, drawing: previous.target.level === "general" ? "other" : "", mode: "catalogue", amount: "", reason: "" } : previous);
  const openDetails = () => { if (selectedItem) { opener.current = document.activeElement; setDetailsItem(selectedItem); } };
  const closeDetails = () => { setDetailsItem(null); requestAnimationFrame(() => { if (opener.current?.isConnected) (opener.current as HTMLElement).focus?.({ preventScroll: true }); }); };
  const openUncomplete = () => { if (!writable || !canWriteBilling || selectedItem?.status !== "completed") return; opener.current = document.activeElement; setError(null); setUncompleteReason(""); setUncompleteItem(selectedItem); };
  const saveUncomplete = () => {
    if (!uncompleteItem || !canWriteBilling || !uncompleteReason.trim()) return;
    void mutate(`${base}/items/${uncompleteItem.id}/uncomplete`, "POST", { expected_revision: uncompleteItem.revision, reason: uncompleteReason.trim(), confirm_finance: true }, "Completion reversed. Treatment is outstanding again; the original history is retained. Payments are unchanged.");
  };
  const renderItem = (item: PlanningItem) => <button type="button" className={styles.item} key={item.id} data-testid={`planning-item-${item.id}`} data-status={item.status} data-selected={selectedItem?.id === item.id} aria-pressed={selectedItem?.id === item.id} disabled={saving || uncertain || !ready} onClick={() => setSelectedId(item.id)} onKeyDown={(event) => {
    if (!["ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return;
    event.preventDefault(); const rows = [...outstanding, ...completed, ...other].filter((row) => document.querySelector(`[data-testid="planning-item-${row.id}"]`)?.getClientRects().length); const index = rows.findIndex((row) => row.id === item.id);
    const next = event.key === "Home" ? 0 : event.key === "End" ? rows.length - 1 : Math.max(0, Math.min(rows.length - 1, index + (event.key === "ArrowDown" ? 1 : -1)));
    setSelectedId(rows[next].id); document.querySelector<HTMLButtonElement>(`[data-testid="planning-item-${rows[next].id}"]`)?.focus();
  }}>
    <span className={styles.selectionMark} aria-hidden="true">{selectedItem?.id === item.id ? "✓" : ""}</span>
    <span className={styles.itemContent}><strong title={item.description}>{item.description}</strong><span title={`${planningTargetLabel(item.target, plan?.snapshot)} · ${item.procedure_code} · ${statusNames[item.status]} · ${feeModes[item.fee_mode]}`}>{planningTargetLabel(item.target, plan?.snapshot)} · {item.procedure_code} · {statusNames[item.status]} · {feeModes[item.fee_mode]}</span></span>
    <strong className={styles.itemFee}>{planningMoney(item.fee_pence)}</strong>
  </button>;
  const total = (entries: EarlierPlanningItem[]) => planningMoney(entries.reduce((sum, item) => sum + (item.fee_pence ?? 0), 0));

  return <section className={styles.panel} data-testid="treatment-planning-panel" aria-label="Treatment planning">
    <header className={styles.header}><div><h2>Treatment plan</h2>{plan && <small>Baseline captured {new Date(plan.snapshot.captured_at).toLocaleString("en-GB", { timeZone: "Europe/London" })} · current diagnosis is unchanged</small>}</div>
      <div className={styles.actions}><button type="button" className="btn btn-secondary" data-testid="planning-refresh" disabled={saving} onClick={() => { setError(null); void load(); }}>Refresh plan</button>{plan && <button type="button" className="btn" data-testid="planning-add-treatment" disabled={!writable} onClick={() => openDraft({ level: "general", tooth: null, surfaces: [] })}>Add treatment</button>}</div>
    </header>
    {loading && <p role="status" data-testid="planning-loading">Loading treatment plan…</p>}
    {loadError && <p role="alert" className={styles.error} data-testid="planning-load-error">{loadError}</p>}
    {error && !draft && !uncompleteItem && <p role="alert" className={styles.error} data-testid="planning-error">{error}</p>}
    {notice && <p role="status" className={styles.notice} data-testid="planning-notice">{notice}</p>}
    {uncertain && !draft && !uncompleteItem && <p className={styles.error}>The previous save result is unknown. Refresh and review the plan before making another change. <button type="button" className="btn btn-secondary" disabled={saving || loading} onClick={() => { if (window.confirm("Have you checked the refreshed plan and any completed treatment before continuing?")) { attempt.current = null; setUncertain(false); setError(null); } }}>I have reviewed the saved plan</button></p>}
    {ready && !canWriteClinical && <p className={styles.muted} data-testid="planning-read-only">Read-only treatment plan. Clinical write permission is required to make changes.</p>}
    {ready && !plan && <div className={styles.empty} data-testid="planning-not-started"><p>Start a treatment plan to capture the current chart once. Later diagnosis changes will not replace this saved baseline. Planning does not create a charge.</p><button type="button" className="btn" data-testid="planning-start" disabled={!writable} onClick={() => void mutate(`${base}/start`, "POST", {}, "Treatment plan started. The current chart baseline has been captured.")}>{saving ? "Starting…" : "Start treatment plan"}</button></div>}
    {plan && <>
      <div className={styles.tabs} role="tablist" aria-label="Planning level">{planningTabs.map((entry, index) => <button key={entry.value} type="button" role="tab" id={`planning-tab-${entry.value}`} aria-controls="planning-chart-panel" aria-selected={level === entry.value} tabIndex={level === entry.value ? 0 : -1} data-testid={`planning-level-${entry.value}`} disabled={saving || uncertain} onClick={() => { setLevel(entry.value); setSelection(null); }} onKeyDown={(event) => { if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return; event.preventDefault(); const next = event.key === "Home" ? 0 : event.key === "End" ? planningTabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : planningTabs.length - 1)) % planningTabs.length; setLevel(planningTabs[next].value); setSelection(null); document.getElementById(`planning-tab-${planningTabs[next].value}`)?.focus(); }}>{entry.label}</button>)}</div>
      <div id="planning-chart-panel" className={styles.chartPanel} role="tabpanel" aria-labelledby={`planning-tab-${level}`}>
        {level === "general" ? <form className={styles.miscellaneous} data-testid="planning-miscellaneous" onSubmit={(event) => { event.preventDefault(); void saveCustom(); }}>
          <div className={styles.header}><h3>Miscellaneous treatment</h3><small>Patient-specific · not added to the practice price list</small></div>
          <fieldset disabled={!ready || !canWriteClinical || saving || uncertain}>
            <div className={styles.customGrid}>
              <label>Treatment description<textarea data-testid="planning-custom-description" maxLength={2000} rows={2} value={customDescription} onChange={(event) => setCustomDescription(event.target.value)} placeholder="e.g. bite splint, removable or fixed retainer, sedation, examination and cleaning" /></label>
              <label>Fee (£)<input data-testid="planning-custom-fee-amount" inputMode="decimal" value={customWaived ? "0.00" : customAmount} disabled={customWaived} onChange={(event) => setCustomAmount(event.target.value)} placeholder="Enter the agreed fee" /></label>
            </div>
            <label className={styles.waiver}><input type="checkbox" data-testid="planning-custom-waived" checked={customWaived} onChange={(event) => setCustomWaived(event.target.checked)} />Waive fee · £0.00</label>
            {customWaived && <label>Reason for waiving the fee<textarea data-testid="planning-custom-fee-reason" maxLength={500} rows={2} value={customReason} onChange={(event) => setCustomReason(event.target.value)} /></label>}
          </fieldset>
          <div className={styles.header}><small className={styles.muted} data-testid="planning-custom-validation">{customError || "Adding to the plan does not charge the patient."}</small><button type="submit" className="btn" data-testid="planning-custom-save" disabled={!ready || !canWriteClinical || saving || Boolean(customError)}>{saving ? "Saving…" : uncertain ? "Retry unchanged save" : "Add to plan"}</button></div>
        </form> : <TreatmentPlanningChart snapshot={plan.snapshot} items={items} level={level} selection={selection} disabled={!writable} onSelect={onSelect} onOpenToothNotes={onOpenToothNotes} />}
      </div>
      {level !== "general" && plan.snapshot.coverage.legacy !== "captured" && <details className={styles.muted} data-testid="planning-coverage"><summary>Baseline source coverage</summary>Native current observations captured. Imported chart coverage: {plan.snapshot.coverage.legacy}.{plan.snapshot.coverage.legacy_reason ? ` ${plan.snapshot.coverage.legacy_reason}` : " No missing findings have been inferred."}</details>}
      <div className={styles.summary} data-testid="planning-summary">
        <div className={styles.totals}><div><small>Outstanding · {outstanding.length} items</small><strong data-testid="planning-total-outstanding">{total(outstanding)}</strong>{outstanding.some((item) => item.fee_pence == null) && <small>Plus {outstanding.filter((item) => item.fee_pence == null).length} unpriced items</small>}</div><div><small>Completed · {completed.length} items</small><strong data-testid="planning-total-completed">{total(completed)}</strong></div></div>
        <div className={styles.actionBar}>
          <div role="toolbar" aria-label="Selected treatment actions" className={styles.actions} data-testid="planning-actions">
            <button type="button" className="btn btn-secondary" data-testid="planning-action-details" disabled={!selectedItem || !ready || saving || uncertain} onClick={openDetails}>Details</button>
            <button type="button" className="btn btn-secondary" data-testid="planning-action-edit-fee" disabled={!writable || !selectedOutstanding} onClick={() => selectedItem && editFee(selectedItem)}>Edit fee</button>
            <button type="button" className="btn btn-secondary" data-testid="planning-action-accept" disabled={!writable || selectedItem?.status !== "proposed"} onClick={() => selectedItem && changeStatus(selectedItem, "accepted")}>Accept</button>
            <button type="button" className="btn btn-secondary" data-testid="planning-action-cancel" disabled={!writable || !selectedOutstanding} onClick={() => selectedItem && changeStatus(selectedItem, "cancelled")}>Cancel treatment</button>
            <button type="button" className="btn" data-testid="planning-action-complete" disabled={!writable || !canWriteBilling || !selectedOutstanding || selectedItem?.fee_pence == null} onClick={() => selectedItem && changeStatus(selectedItem, "completed")}>Complete</button>
            <button type="button" className="btn btn-secondary" data-testid="planning-action-uncomplete" disabled={!writable || !canWriteBilling || selectedItem?.status !== "completed"} onClick={openUncomplete}>Uncomplete</button>
          </div>
          <span className={styles.selectedSummary} data-testid="planning-selected-item" data-item-id={selectedItem?.id ?? ""} aria-live="polite" title={selectedItem ? `${selectedItem.description} · ${planningTargetLabel(selectedItem.target, plan?.snapshot)} · ${planningMoney(selectedItem.fee_pence)}` : undefined}>{selectedItem ? `Selected: ${selectedItem.description} · ${planningTargetLabel(selectedItem.target, plan?.snapshot)} · ${planningMoney(selectedItem.fee_pence)}` : "Select a treatment row to use these actions."}</span>
        </div>
      </div>
      <section className={styles.group} aria-label="Outstanding treatment"><h3>Outstanding</h3><div className={styles.list}>{outstanding.length ? outstanding.map(renderItem) : <p className={styles.empty}>No outstanding treatment in this plan.</p>}</div></section>
      <section className={styles.group} aria-label="Completed treatment"><h3>Completed</h3><div className={styles.list}>{completed.length ? completed.map(renderItem) : <p className={styles.muted}>No treatment has been completed in this plan.</p>}</div></section>
      {other.length > 0 && <details><summary>Cancelled or declined · {other.length}</summary><div className={styles.list}>{other.map(renderItem)}</div></details>}
    </>}
    {ready && Boolean(data?.earlier_items_total) && <details data-testid="planning-earlier-items"><summary>Earlier treatment plan items · {data!.earlier_items_total}</summary><p className={styles.muted}>These items pre-date this planning workspace. They are kept separately and have not been given an inferred baseline or drawing.</p>{data!.earlier_items.map((item) => <div className={styles.earlierItem} key={item.id}><span>{item.tooth ?? "General"} · {item.description} · {statusNames[item.status]}</span><span>{planningMoney(item.fee_pence)}</span></div>)}{data!.earlier_items_total > data!.earlier_items.length && <p>Showing the latest {data!.earlier_items.length} items. Open earlier plan items for the full list.</p>}{onOpenEarlierItems && <button type="button" className="btn btn-secondary" disabled={saving} onClick={onOpenEarlierItems}>Open earlier plan items</button>}</details>}

    <dialog ref={customProgressDialog} className={styles.dialog} data-testid="planning-custom-progress" aria-label="Saving miscellaneous treatment" tabIndex={-1} onCancel={(event) => { event.preventDefault(); if (!busy.current && uncertain) void reviewCustomResult(); }} onKeyDown={(event) => { if (saving && event.key === "Tab") { event.preventDefault(); customProgressDialog.current?.focus(); } }}>
      <div className={styles.detailBody}>
        <h3>{uncertain && !saving ? "Check the save result" : "Saving miscellaneous treatment…"}</h3>
        {saving ? <p role="status">Please wait while the treatment is saved.</p> : uncertain ? <><p role="alert">{error}</p>{loadError && <p className={styles.error}>{loadError}</p>}<p>The description and fee are kept unchanged. Retry safely, or refresh and review the saved plan before adding anything again.</p><div className={styles.actions}>{loadError && <button type="button" className="btn btn-secondary" data-testid="planning-custom-abandon" disabled={loading} onClick={abandonCustomAfterLoadFailure}>Close without retrying</button>}<button type="button" className="btn btn-secondary" data-testid="planning-custom-review" disabled={loading} onClick={() => void reviewCustomResult()}>Refresh and review plan</button><button type="button" className="btn" data-testid="planning-custom-retry" disabled={!ready || !canWriteClinical} onClick={() => void saveCustom()}>Retry unchanged save</button></div></> : <p role="status">Checking the saved plan…</p>}
      </div>
    </dialog>
    <dialog ref={dialog} className={styles.dialog} data-testid="planning-treatment-dialog" aria-label={draft?.editing ? "Edit treatment fee" : "Add treatment to plan"} onCancel={(event) => { event.preventDefault(); close(); }} onKeyDown={(event) => { if (saving && event.key === "Tab") { event.preventDefault(); dialog.current?.focus(); } }} tabIndex={-1}>
      {draft && <form onSubmit={(event) => { event.preventDefault(); saveDraft(); }}><header className={styles.header}><h3>{draft.editing ? "Edit treatment fee" : "Add treatment"}</h3><button type="button" className="btn btn-secondary" aria-label="Close treatment editor" disabled={saving} onClick={close}>Close</button></header>
        {error && <p role="alert" className={styles.error} data-testid="planning-error">{error}</p>}
        <fieldset disabled={saving || uncertain}>
          {!draft.editing && <>
            <div className={styles.sourceChoice} role="group" aria-label="Treatment source">
              <button type="button" className="btn btn-secondary" data-testid="planning-use-catalogue" aria-pressed={!draft.custom} onClick={chooseCatalogue}>Treatment catalogue</button>
              <button type="button" className="btn btn-secondary" data-testid="planning-other-treatment" aria-pressed={draft.custom} onClick={chooseOtherTreatment}>Other treatment</button>
            </div>
            {!draft.custom && <>
              <div className={styles.formGrid}>
                <label>Search treatment catalogue<input data-testid="planning-catalogue-search" maxLength={200} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Treatment name or code" /></label>
                <label>Show treatments<select data-testid="planning-catalogue-scope" value={catalogueScope} onChange={(event) => { setOffset(0); setCatalogueScope(event.target.value as "target" | "all"); }}><option value="target">Selected level + unassigned</option><option value="all">All levels</option></select></label>
              </div>
              <small className={styles.muted}>Unassigned catalogue entries remain available without guessing their anatomical category.{catalogue?.practice_today && ` Prices shown for ${planningFeeDateLabel(catalogue.practice_today) ?? catalogue.practice_today}.`}</small>
            {catalogueLoading && <p role="status">Loading catalogue…</p>}{catalogueError && <p role="alert" className={styles.error}>{catalogueError} <button type="button" onClick={() => void loadCatalogue()}>Retry catalogue</button></p>}
            {catalogue && <><div className={styles.catalogue} aria-label="Treatment catalogue" data-testid="planning-catalogue">{catalogue.items.map((treatment) => <button type="button" key={treatment.id} data-testid={`planning-catalogue-item-${treatment.id}`} aria-pressed={draft.treatment?.id === treatment.id} onClick={() => chooseTreatment(treatment)}><span><strong>{treatment.name}</strong><small>{treatment.code ?? "No catalogue code"} · {treatment.patient_category.replaceAll("_", " ")} · {treatment.level === "general" ? "General" : treatment.level ? `${treatment.level} level` : "Unassigned level"}</small></span><span>{planningFeeLabel(treatment.fee)}{treatment.fee.effective_from && <small>From {planningFeeDateLabel(treatment.fee.effective_from) ?? treatment.fee.effective_from}</small>}</span></button>)}{!catalogue.items.length && <p>No matching active treatment. Try another name or code, show all levels, or choose Other treatment.</p>}</div>{catalogue.total > 50 && <div className={styles.actions}><button type="button" className="btn btn-secondary" disabled={offset === 0} onClick={() => setOffset((value) => Math.max(0, value - 50))}>Previous treatments</button><span>{offset + 1}–{Math.min(offset + 50, catalogue.total)} of {catalogue.total}</span><button type="button" className="btn btn-secondary" disabled={offset + 50 >= catalogue.total} onClick={() => setOffset((value) => value + 50)}>Next treatments</button></div>}</>}
            {draft.treatment && <p className={styles.quote}>Selected: <strong>{draft.treatment.name}</strong>{draft.treatment.description && <><br />{draft.treatment.description}</>}</p>}
            </>}
            {draft.custom && <label>Treatment description<textarea data-testid="planning-other-description" rows={3} maxLength={2000} value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} placeholder="Describe the treatment for this selected target" /></label>}
            <div className={styles.formGrid}><label>Treatment level<select data-testid="planning-target-level" value={draft.target.level} onChange={(event) => changeTarget({ level: event.target.value as PlanningTarget["level"], tooth: event.target.value === "general" ? null : draft.target.tooth, surfaces: [] })}><option value="general">General treatment</option>{planningLevels.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label>
              {draft.target.level !== "general" && <label>Tooth<select data-testid="planning-target-tooth" value={draft.target.tooth ?? ""} onChange={(event) => changeTarget({ ...draft.target, tooth: event.target.value || null, surfaces: [] })}><option value="">Select tooth</option>{teeth.map((tooth) => <option key={tooth} value={tooth}>{planningToothLabel(tooth, plan?.snapshot)}</option>)}</select></label>}
            </div>
            {draft.target.level === "surface" && draft.target.tooth && <div className={styles.surfaces} role="group" aria-label="Treatment surfaces">{surfaceKeysForTooth(draft.target.tooth).map((surface) => <label key={surface}><input type="checkbox" data-testid={`planning-target-surface-${surface}`} checked={draft.target.surfaces.includes(surface)} onChange={() => setDraft({ ...draft, target: { ...draft.target, surfaces: surfaceKeysForTooth(draft.target.tooth!).filter((key) => key === surface ? !draft.target.surfaces.includes(key) : draft.target.surfaces.includes(key)) as SurfaceKey[] } })} />{surface} · {surfaceName(surface)}</label>)}</div>}
            {draft.custom ? <p className={styles.muted}>Other treatment is recorded against this selected target, without an inferred treatment drawing.</p> : <label>Chart drawing<select data-testid="planning-drawing-kind" value={draft.drawing} onChange={(event) => setDraft({ ...draft, drawing: event.target.value as PlanningDrawingKind })}><option value="">Choose the treatment drawing explicitly</option>{planningDrawingChoices.filter((choice) => choice.levels.includes(draft.target.level)).map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}</select><small className={styles.muted}>The drawing is selected by you, not inferred from the treatment name.</small></label>}
          </>}
          {draft.editing && <p>{draft.editing.description} · {planningTargetLabel(draft.target, plan?.snapshot)}</p>}
          {customDraft && <>
            <p className={styles.muted}>Patient-specific treatment. There is no catalogue quote or practice price-list change.</p>
            <div className={styles.formGrid}><label>Fee choice<select data-testid="planning-fee-mode" value={draft.mode} onChange={(event) => setDraft({ ...draft, mode: event.target.value as PlanningFeeMode })}><option value="agreed">Agreed fee</option><option value="waived">Waive fee · £0.00</option></select></label>
              {draft.mode === "agreed" && <label>Fee (£)<input data-testid="planning-fee-amount" inputMode="decimal" value={draft.amount} onChange={(event) => setDraft({ ...draft, amount: event.target.value })} /></label>}
            </div>
            <label>Fee reason {draft.mode === "waived" ? "(required)" : "(optional)"}<textarea data-testid="planning-fee-reason" maxLength={500} value={draft.reason} onChange={(event) => setDraft({ ...draft, reason: event.target.value })} /></label>
            {(descriptionError || targetError || feeError) && <p className={styles.muted} data-testid="planning-validation">{descriptionError || targetError || feeError}</p>}
          </>}
          {draftFee && <><div className={styles.quote} data-testid="planning-fee-quote">Saved catalogue quote: <strong>{planningFeeLabel(draftFee)}</strong>{draftFee.effective_from && <><br /><span data-testid="planning-fee-effective-from">Effective from {planningFeeDateLabel(draftFee.effective_from) ?? draftFee.effective_from}</span></>}{draftFee.notes && <><br />{draftFee.notes}</>}</div>
            <div className={styles.formGrid}><label>Fee choice<select data-testid="planning-fee-mode" value={draft.mode} onChange={(event) => setDraft({ ...draft, mode: event.target.value as PlanningFeeMode })}><option value="catalogue" disabled={draftFee.type !== "FIXED"}>Use catalogue fee</option><option value="agreed" disabled={draftFee.type === "FIXED"}>Agreed fee</option><option value="override">Override fee</option><option value="waived">Waive fee · £0.00</option></select></label>
              {(draft.mode === "agreed" || draft.mode === "override") && <label>Fee (£)<input data-testid="planning-fee-amount" inputMode="decimal" value={draft.amount} onChange={(event) => setDraft({ ...draft, amount: event.target.value })} placeholder="Explicit agreed amount" /></label>}
            </div>
            {draft.mode !== "catalogue" && <label>Fee reason{draft.mode === "agreed" && draftFee.type === "RANGE" ? " (optional)" : " (required)"}<textarea data-testid="planning-fee-reason" maxLength={500} value={draft.reason} onChange={(event) => setDraft({ ...draft, reason: event.target.value })} /></label>}
            {(feeError || targetError) && <p className={styles.muted} data-testid="planning-validation">{feeError || targetError}</p>}
            {draft.mode === "waived" && <p className={styles.muted}>This item will be recorded as explicitly waived. Completing it creates a clinical procedure but no finance charge.</p>}
          </>}
        </fieldset>
        <p className={styles.muted}>Adding or changing a plan item does not charge the patient. Complete the saved treatment to record the procedure and its saved fee in finance.</p>
        <div className={styles.actions}><button type="button" className="btn btn-secondary" data-testid="planning-cancel" disabled={saving} onClick={close}>Cancel</button><button type="submit" className="btn" data-testid="planning-save" disabled={saving || !canWriteClinical || !ready || Boolean(feeError || targetError || descriptionError) || (!draftFee && !customDraft) || !draft.drawing || (!draft.editing && !draft.custom && (!draft.treatment || catalogueLoading || Boolean(catalogueError)))}>{saving ? "Saving…" : uncertain ? "Retry unchanged save" : draft.editing ? "Save fee" : "Add to plan"}</button></div>
      </form>}
    </dialog>
    <dialog ref={detailsDialog} className={styles.dialog} data-testid="planning-item-details" aria-label="Treatment details" onCancel={(event) => { event.preventDefault(); closeDetails(); }}>
      {detailsItem && <div className={styles.detailBody}>
        <header className={styles.header}><h3>Treatment details</h3><button type="button" className="btn btn-secondary" onClick={closeDetails}>Close treatment details</button></header>
        <h4>{detailsItem.description}</h4><p>{planningTargetLabel(detailsItem.target, plan?.snapshot)} · {detailsItem.procedure_code} · {statusNames[detailsItem.status]}</p>
        <p><strong>{planningMoney(detailsItem.fee_pence)}</strong> · {feeModes[detailsItem.fee_mode]}</p>{detailsItem.fee_reason && <p className={styles.fullText}>{detailsItem.fee_reason}</p>}
        {detailsItem.catalogue_snapshot.source === "custom" ? <p>Patient-specific treatment. No catalogue quote or practice price-list change.</p> : <>
          <p>Saved catalogue quote: {planningFeeLabel(detailsItem.catalogue_snapshot.fee)} · {detailsItem.catalogue_snapshot.patient_category ?? "Category not recorded"}</p>
          {detailsItem.catalogue_snapshot.fee.effective_from && <p>Effective from {planningFeeDateLabel(detailsItem.catalogue_snapshot.fee.effective_from) ?? detailsItem.catalogue_snapshot.fee.effective_from}</p>}
          {detailsItem.catalogue_snapshot.fee.notes && <p className={styles.fullText}>{detailsItem.catalogue_snapshot.fee.notes}</p>}
        </>}
        <p>Drawing: {planningDrawingChoices.find((choice) => choice.value === detailsItem.drawing_kind)?.label ?? "Not recorded"}. Revision {detailsItem.revision}.</p>
      </div>}
    </dialog>
    <dialog ref={uncompleteDialog} className={styles.dialog} data-testid="planning-uncomplete-dialog" aria-label="Uncomplete treatment" tabIndex={-1} onCancel={(event) => { event.preventDefault(); close(); }} onKeyDown={(event) => { if (saving && event.key === "Tab") { event.preventDefault(); uncompleteDialog.current?.focus(); } }}>
      {uncompleteItem && <form onSubmit={(event) => { event.preventDefault(); saveUncomplete(); }}><h3>Uncomplete treatment</h3><p><strong>{uncompleteItem.description}</strong> · {planningTargetLabel(uncompleteItem.target, plan?.snapshot)}</p><p>This returns the treatment to outstanding and marks the original completion as voided, keeping its history.</p><p>{uncompleteItem.fee_pence ? `A ${planningMoney(uncompleteItem.fee_pence)} credit adjustment will reverse this completion's charge.` : "The saved fee is zero, so there is no charge to reverse."} Payments remain unchanged. No refund is issued.</p>{error && <p role="alert" className={styles.error} data-testid="planning-error">{error}</p>}<label>Reason for correction<textarea data-testid="planning-uncomplete-reason" maxLength={500} value={uncompleteReason} disabled={saving || uncertain} onChange={(event) => setUncompleteReason(event.target.value)} /></label><div className={styles.actions}><button type="button" className="btn btn-secondary" data-testid="planning-uncomplete-cancel" disabled={saving} onClick={close}>Cancel</button><button type="submit" className="btn" data-testid="planning-uncomplete-confirm" disabled={saving || !ready || !canWriteClinical || !canWriteBilling || !uncompleteReason.trim()}>{saving ? "Reversing…" : uncertain ? "Retry unchanged reversal" : "Confirm uncomplete"}</button></div></form>}
    </dialog>
  </section>;
}
