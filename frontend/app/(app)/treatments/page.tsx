"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import styles from "./treatments.module.css";

type Category = "CLINIC_PRIVATE" | "DOMICILIARY_PRIVATE" | "DENPLAN";
type Level = "tooth" | "root" | "crown" | "surface" | "general";
type FeeType = "FIXED" | "RANGE" | "N_A" | null;
type Fee = { version_id: number | null; effective_from: string | null; revision: number; source: "legacy" | "version"; fee_type: FeeType; amount_pence: number | null; min_amount_pence: number | null; max_amount_pence: number | null; notes: string | null };
type Treatment = { id: number; name: string; code: string | null; description: string | null; level: Level | null; display_order: number; is_active: boolean; default_duration_minutes: number | null; is_denplan_included_default: boolean; current_fee: Fee | null; scheduled_fees: Fee[]; fee_revision: number };
type Index = { practice_today: string; patient_category: Category; items: Treatment[] };
type History = { treatment_id: number; patient_category: Category; fee_revision: number; baseline_fee: Fee | null; items: Fee[]; next_before_revision: number | null };
type TreatmentDraft = { id: number | null; name: string; code: string; description: string; level: Level | ""; order: string; duration: string; active: boolean; denplan: boolean };
type FeeDraft = { treatment: Treatment; category: Category; type: FeeType; amount: string; min: string; max: string; date: string; notes: string };
const categories: Record<Category, string> = { CLINIC_PRIVATE: "Clinic (Private)", DOMICILIARY_PRIVATE: "Home visits (Private)", DENPLAN: "Denplan" };
const groups: { level: Level | "unassigned"; title: string }[] = [{ level: "tooth", title: "Tooth level fees" }, { level: "root", title: "Root level fees" }, { level: "crown", title: "Crown level fees" }, { level: "surface", title: "Surface level fees" }, { level: "general", title: "Miscellaneous fees" }, { level: "unassigned", title: "Other existing treatments · choose a level" }];
const money = (pence: number) => new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(pence / 100);
const dateLabel = (value: string) => new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${value}T12:00:00Z`));
const feeLabel = (fee: Fee | null) => !fee || fee.fee_type === null ? "Not set" : fee.fee_type === "N_A" ? "Not applicable" : fee.fee_type === "FIXED" ? fee.amount_pence === null ? "Not set" : money(fee.amount_pence) : fee.min_amount_pence === null || fee.max_amount_pence === null ? "Not set" : `${money(fee.min_amount_pence)}–${money(fee.max_amount_pence)}`;
const amountText = (value: number | null | undefined) => value == null ? "" : (value / 100).toFixed(2);
const requestId = () => typeof crypto.randomUUID === "function" ? crypto.randomUUID() : Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) => byte.toString(16).padStart(2, "0")).join("");
function pence(value: string) {
  if (!/^\d+(?:\.\d{1,2})?$/.test(value.trim())) throw new Error("Enter a non-negative amount in pounds, with no more than two decimal places.");
  const [whole, fraction = ""] = value.trim().split(".");
  const result = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  if (!Number.isSafeInteger(result) || result > 100_000_000) throw new Error("The fee must be £1,000,000.00 or less.");
  return result;
}

export default function TreatmentsPage() {
  const router = useRouter();
  const [category, setCategory] = useState<Category>("CLINIC_PRIVATE");
  const [inactive, setInactive] = useState(false);
  const [query, setQuery] = useState("");
  const [data, setData] = useState<Index | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [treatmentDraft, setTreatmentDraft] = useState<TreatmentDraft | null>(null);
  const [feeDraft, setFeeDraft] = useState<FeeDraft | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [stale, setStale] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const opener = useRef<Element | null>(null);
  const busy = useRef(false);
  const sequence = useRef(0);
  const historySequence = useRef(0);
  const attempt = useRef<{ key: string; id: string; uncertain: boolean } | null>(null);
  const open = Boolean(treatmentDraft || feeDraft);

  const check = useCallback(async (response: Response) => {
    if (response.status === 401) { clearToken(); router.replace("/login"); throw new Error("Please sign in again."); }
    if (response.status === 403) throw new Error("Only a practice administrator can manage treatments and fees.");
    if (response.status === 409) throw new Error("This record has changed. Close and reopen it to review the latest saved fees before making another change.");
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(response.status < 500 && typeof body?.detail === "string" ? body.detail : "The request could not be confirmed. Refresh and check the saved record before trying again.");
    }
  }, [router]);

  // List reads must not depend on the selected record or on editable draft state.
  const load = useCallback(async () => {
    const ticket = ++sequence.current;
    setLoading(true); setError(null);
    try {
      const response = await apiFetch(`/api/treatments/index?${new URLSearchParams({ patient_category: category, include_inactive: String(inactive) })}`);
      await check(response);
      const next = await response.json() as Index;
      if (ticket === sequence.current) { setData(next); return true; }
    } catch (cause) { if (ticket === sequence.current) setError(cause instanceof Error ? cause.message : "Treatments could not be loaded."); }
    finally { if (ticket === sequence.current) setLoading(false); }
    return false;
  }, [category, inactive, check]);
  useEffect(() => { setData(null); void load(); return () => { sequence.current += 1; }; }, [load]);
  useEffect(() => {
    if (open && dialog.current && !dialog.current.open) dialog.current.showModal();
    if (!open && dialog.current?.open) dialog.current.close();
  }, [open]);
  useEffect(() => { if (saving && dialog.current?.open) dialog.current.focus(); }, [saving]);
  useEffect(() => () => { historySequence.current += 1; }, []);

  function close() {
    if (busy.current) return;
    if (attempt.current?.uncertain && !window.confirm("The save result is unknown. Close this draft and check the saved treatment list before making another change?")) return;
    historySequence.current += 1; setTreatmentDraft(null); setFeeDraft(null); setHistory(null); setHistoryError(null); setDialogError(null); setUncertain(false); setStale(false); attempt.current = null;
    void load();
    requestAnimationFrame(() => { if (opener.current?.isConnected) (opener.current as HTMLElement).focus?.(); });
  }
  function prepare() { opener.current = document.activeElement; setDialogError(null); setNotice(null); setUncertain(false); setStale(false); attempt.current = null; }
  function editTreatment(treatment: Treatment | null, level: Level | "" = "") {
    prepare(); setFeeDraft(null);
    setTreatmentDraft(treatment ? { id: treatment.id, name: treatment.name, code: treatment.code ?? "", description: treatment.description ?? "", level: treatment.level ?? "", order: String(treatment.display_order), duration: treatment.default_duration_minutes?.toString() ?? "", active: treatment.is_active, denplan: treatment.is_denplan_included_default } : { id: null, name: "", code: "", description: "", level, order: "100", duration: "", active: true, denplan: false });
  }
  const readHistory = async (treatmentId: number, scheme: Category, before?: number) => {
    const ticket = ++historySequence.current;
    setHistoryLoading(true); setHistoryError(null);
    try {
      const params = new URLSearchParams({ patient_category: scheme, limit: "50" });
      if (before !== undefined) params.set("before_revision", String(before));
      const response = await apiFetch(`/api/treatments/${treatmentId}/fee-history?${params}`); await check(response);
      const next = await response.json() as History;
      if (ticket === historySequence.current) setHistory((previous) => before && previous ? { ...next, items: [...previous.items, ...next.items] } : next);
    } catch (cause) { if (ticket === historySequence.current) setHistoryError(cause instanceof Error ? cause.message : "Fee history could not be loaded."); }
    finally { if (ticket === historySequence.current) setHistoryLoading(false); }
  };
  function editFees(treatment: Treatment) {
    if (!data) return;
    prepare(); setTreatmentDraft(null); setHistory(null);
    const fee = treatment.current_fee;
    setFeeDraft({ treatment, category, type: fee?.fee_type ?? "FIXED", amount: amountText(fee?.amount_pence), min: amountText(fee?.min_amount_pence), max: amountText(fee?.max_amount_pence), date: data.practice_today, notes: "" });
    void readHistory(treatment.id, category);
  }
  async function save(path: string, method: "POST" | "PATCH", payload: Record<string, unknown>, success: string) {
    if (busy.current) return;
    const key = JSON.stringify({ path, method, payload });
    if (attempt.current?.uncertain && attempt.current.key !== key) { setDialogError("Retry the unchanged request, or close and check the saved record first."); return; }
    const current = attempt.current?.key === key ? attempt.current : { key, id: requestId(), uncertain: false };
    attempt.current = current; busy.current = true; setSaving(true); setDialogError(null); setError(null); setNotice(null);
    let receivedResponse = false;
    try {
      const response = await apiFetch(path, { method, headers: { "Request-Id": current.id }, body: JSON.stringify(payload) });
      receivedResponse = true;
      if (!response.ok) {
        current.uncertain = current.uncertain || response.status >= 500; setUncertain(current.uncertain);
        if (response.status === 409) setStale(true);
        await check(response);
      }
      attempt.current = null; setUncertain(false); setStale(false); setTreatmentDraft(null); setFeeDraft(null); setHistory(null); historySequence.current += 1;
      setNotice(success); await load();
      requestAnimationFrame(() => { if (opener.current?.isConnected) (opener.current as HTMLElement).focus?.(); });
    } catch (cause) {
      // A lost response may follow a committed write. Do not silently change its payload.
      if (!receivedResponse) { current.uncertain = true; setUncertain(true); }
      const message = cause instanceof Error ? cause.message : "The save could not be confirmed.";
      if (open) setDialogError(message); else setError(message);
      if (!current.uncertain) attempt.current = null;
    } finally { busy.current = false; setSaving(false); }
  }
  async function saveTreatment(event: FormEvent) {
    event.preventDefault(); if (!treatmentDraft || busy.current || uncertain || stale) return;
    const draft = treatmentDraft;
    if (!draft.name.trim()) { setDialogError("Enter a treatment name."); return; }
    const order = Number(draft.order), duration = draft.duration === "" ? null : Number(draft.duration);
    if (!Number.isSafeInteger(order) || order < 0 || order > 100_000 || (duration !== null && (!Number.isInteger(duration) || duration < 1))) { setDialogError("Use a whole-number display order up to 100,000 and a positive duration, or leave duration blank."); return; }
    await save(`/api/treatments${draft.id === null ? "" : `/${draft.id}`}`, draft.id === null ? "POST" : "PATCH", { name: draft.name.trim(), code: draft.code.trim() || null, description: draft.description.trim() || null, level: draft.level || null, display_order: order, default_duration_minutes: duration, is_active: draft.active, is_denplan_included_default: draft.denplan }, draft.id === null ? "Treatment added. Choose Edit fee to set its price." : "Treatment details saved.");
  }
  async function saveFee(event: FormEvent) {
    event.preventDefault(); if (!feeDraft || busy.current || stale || !data) return;
    const draft = feeDraft;
    try {
      if (!draft.date || draft.date < data.practice_today) throw new Error("Choose today or a future date. Historical fees are kept unchanged.");
      const payload: Record<string, unknown> = { patient_category: draft.category, fee_type: draft.type, effective_from: draft.date, expected_revision: draft.treatment.fee_revision, notes: draft.notes.trim() || null };
      if (draft.type === "FIXED") payload.amount_pence = pence(draft.amount);
      if (draft.type === "RANGE") { payload.min_amount_pence = pence(draft.min); payload.max_amount_pence = pence(draft.max); if (Number(payload.min_amount_pence) > Number(payload.max_amount_pence)) throw new Error("The minimum fee cannot be greater than the maximum."); }
      await save(`/api/treatments/${draft.treatment.id}/fee-changes`, "POST", payload, `Fee saved from ${dateLabel(draft.date)}. Existing patient-plan fees are unchanged.`);
    } catch (cause) { setDialogError(cause instanceof Error ? cause.message : "Check the fee and date."); }
  }

  const rows = data?.patient_category === category ? data.items.filter((item) => `${item.name} ${item.code ?? ""}`.toLowerCase().includes(query.toLowerCase().trim())) : [];
  const locked = saving || uncertain || stale;
  const ready = Boolean(data && !loading && !error);

  return <div className={styles.page} data-testid="treatments-page">
    <header className={styles.heading}><div><h1>Practice treatments &amp; fees</h1><p>Your routine treatment index. New prices apply from the date you choose; saved patient-plan fees stay unchanged.</p></div><button className="btn btn-secondary" onClick={() => void load()} disabled={saving || open || loading}>Refresh</button></header>
    {error && <div className="notice" role="alert" data-testid="treatments-error">{error}</div>}
    {notice && <div className={styles.status} role="status">{notice}</div>}
    <div className={styles.toolbar}>
      <label className={styles.field}>Fee scheme<select className="input" data-testid="treatment-fee-category" value={category} disabled={saving || open} onChange={(event) => { setNotice(null); setCategory(event.target.value as Category); }}>{Object.entries(categories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className={`${styles.field} ${styles.search}`}>Find a treatment<input className="input" type="search" placeholder="Search by treatment or code…" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
      <label className={styles.check}><input type="checkbox" checked={inactive} disabled={saving || open} onChange={(event) => setInactive(event.target.checked)} />Show inactive</label>
      <button className="btn btn-secondary" data-testid="treatments-add-routine" disabled={!ready || saving || open} onClick={() => { if (window.confirm("Add any missing routine treatments in the five levels? Existing treatments and prices will be kept. No prices will be invented.")) void save("/api/treatments/routine-defaults", "POST", {}, "Routine treatment list is ready. Enter the fees for your practice."); }}>Add missing routine treatments</button>
    </div>
    <nav className={styles.jumps} aria-label="Treatment fee levels">{groups.slice(0, 5).map((group) => <a key={group.level} href={`#fees-${group.level}`}>{group.title.replace(" fees", "")}</a>)}</nav>
    {loading && <p role="status" data-testid="treatments-loading">Loading treatments…</p>}
    {data && <p className={styles.help}>Current fees on {dateLabel(data.practice_today)} · UK practice date · {categories[category]}. “Not set” does not mean free.</p>}
    {!loading && !error && groups.map((group) => {
      const items = rows.filter((item) => (item.level ?? "unassigned") === group.level).sort((a, b) => a.display_order - b.display_order || a.name.localeCompare(b.name) || a.id - b.id);
      if (group.level === "unassigned" && !items.length) return null;
      return <section className={styles.group} id={`fees-${group.level}`} data-testid={`treatments-group-${group.level}`} key={group.level}>
        <header className={styles.sectionHeading}><h2>{group.title}<span className={styles.count}>{items.length}</span></h2><button className={styles.smallButton} disabled={!ready || saving} onClick={() => editTreatment(null, group.level === "unassigned" ? "" : group.level)}>+ Add treatment</button></header>
        {items.length ? <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>Treatment</th><th>Current fee</th><th>Scheduled change</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{items.map((item) => <tr key={item.id} data-testid={`treatment-row-${item.id}`}>
          <td><strong>{item.name}</strong>{(item.code || !item.is_active) && <small>{item.code}{!item.is_active ? " · Inactive" : ""}</small>}</td>
          <td className={styles.fee} data-label="Current fee" data-testid={`fee-current-${item.id}`}><strong>{feeLabel(item.current_fee)}</strong>{item.current_fee?.effective_from && <small>From {dateLabel(item.current_fee.effective_from)}</small>}</td>
          <td className={styles.scheduled} data-label="Scheduled change" data-testid={`fee-scheduled-${item.id}`}>{item.scheduled_fees.length ? <><span className={styles.fee}>{feeLabel(item.scheduled_fees[0])}</span><small>From {dateLabel(item.scheduled_fees[0].effective_from!)}{item.scheduled_fees.length > 1 ? ` · +${item.scheduled_fees.length - 1} more` : ""}</small></> : <span className={styles.help}>No change scheduled</span>}</td>
          <td><div className={styles.rowActions}><button className={styles.smallButton} data-testid={`treatment-fees-${item.id}`} onClick={() => editFees(item)} disabled={saving}>Edit fee</button><button className={styles.smallButton} data-testid={`treatment-edit-${item.id}`} onClick={() => editTreatment(item)} disabled={saving}>Details</button></div></td>
        </tr>)}</tbody></table></div> : <p className={styles.empty}>{query ? "No matching treatments in this level." : "No routine treatments yet. Add the routine list above or enter a treatment here."}</p>}
        {group.level !== "unassigned" && <div className={styles.other}><strong>Other treatment</strong><span>Enter a description and patient-specific fee when planning at this level. Use “Add treatment” for a repeatable practice fee.</span></div>}
      </section>;
    })}
    <dialog className={styles.dialog} ref={dialog} tabIndex={-1} aria-busy={saving} onCancel={(event) => { event.preventDefault(); close(); }} aria-labelledby="treatment-dialog-title" data-testid={feeDraft ? "fee-editor" : "treatment-editor"}>
      <div className={styles.dialogHeading}><h2 id="treatment-dialog-title">{feeDraft ? `Fees · ${feeDraft.treatment.name}` : treatmentDraft?.id === null ? "Add treatment" : "Treatment details"}</h2><button className={styles.smallButton} onClick={close} disabled={saving} aria-label="Close treatment editor">Close</button></div>
      {dialogError && <div className="notice" role="alert">{dialogError}</div>}
      {treatmentDraft && <form className={styles.form} onSubmit={saveTreatment}><fieldset disabled={locked} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }} className={styles.form}>
        <label className={styles.field}>Treatment name<input className="input" data-testid="treatment-name" required maxLength={200} value={treatmentDraft.name} onChange={(e) => setTreatmentDraft({ ...treatmentDraft, name: e.target.value })} /></label>
        <div className={styles.twoColumns}><label className={styles.field}>Level<select className="input" data-testid="treatment-level" value={treatmentDraft.level} onChange={(e) => setTreatmentDraft({ ...treatmentDraft, level: e.target.value as Level | "" })}><option value="">Unassigned</option>{groups.slice(0, 5).map((group) => <option key={group.level} value={group.level}>{group.title.replace(" fees", "")}</option>)}</select></label><label className={styles.field}>Practice code (optional)<input className="input" maxLength={50} value={treatmentDraft.code} onChange={(e) => setTreatmentDraft({ ...treatmentDraft, code: e.target.value })} /></label></div>
        <label className={styles.field}>Description (optional)<textarea className="input" rows={3} maxLength={2000} value={treatmentDraft.description} onChange={(e) => setTreatmentDraft({ ...treatmentDraft, description: e.target.value })} /></label>
        <div className={styles.twoColumns}><label className={styles.field}>Display order<input className="input" type="number" min="0" max="100000" step="1" required value={treatmentDraft.order} onChange={(e) => setTreatmentDraft({ ...treatmentDraft, order: e.target.value })} /></label><label className={styles.field}>Duration in minutes (optional)<input className="input" type="number" min="1" step="1" value={treatmentDraft.duration} onChange={(e) => setTreatmentDraft({ ...treatmentDraft, duration: e.target.value })} /></label></div>
        <label className={styles.check}><input type="checkbox" checked={treatmentDraft.active} onChange={(e) => setTreatmentDraft({ ...treatmentDraft, active: e.target.checked })} />Active in treatment planning</label><label className={styles.check}><input type="checkbox" checked={treatmentDraft.denplan} onChange={(e) => setTreatmentDraft({ ...treatmentDraft, denplan: e.target.checked })} />Denplan included by default</label>
        <div className={styles.actions}><button className="btn btn-primary" data-testid="treatment-save" type="submit">{saving ? "Saving…" : "Save treatment"}</button></div>
      </fieldset>{uncertain && <p className={styles.help}>The result is unknown. Close and check the saved index before entering this treatment again.</p>}</form>}
      {feeDraft && <><form className={styles.form} onSubmit={saveFee}>
        <div className={styles.feeSummary}><div className={styles.help}>{categories[feeDraft.category]} · Current fee</div><strong>{feeLabel(feeDraft.treatment.current_fee)}</strong></div>
        <fieldset disabled={locked} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }} className={styles.form}>
          <div className={styles.twoColumns}><label className={styles.field}>New fee type<select className="input" data-testid="fee-type" value={feeDraft.type ?? "UNSET"} onChange={(e) => setFeeDraft({ ...feeDraft, type: e.target.value === "UNSET" ? null : e.target.value as FeeType })}><option value="FIXED">Fixed fee</option><option value="RANGE">Fee range · agreed when planning</option><option value="N_A">Not applicable</option><option value="UNSET">Not set · agreed when planning</option></select></label><label className={styles.field}>Effective from<input className="input" data-testid="fee-effective-date" type="date" required min={data?.practice_today} value={feeDraft.date} onChange={(e) => setFeeDraft({ ...feeDraft, date: e.target.value })} /></label></div>
          {feeDraft.type === "FIXED" && <label className={styles.field}>Fee (£)<input className="input" data-testid="fee-amount" inputMode="decimal" required placeholder="e.g. 125.00" value={feeDraft.amount} onChange={(e) => setFeeDraft({ ...feeDraft, amount: e.target.value })} /></label>}
          {feeDraft.type === "RANGE" && <div className={styles.twoColumns}><label className={styles.field}>Minimum (£)<input className="input" data-testid="fee-min" inputMode="decimal" required value={feeDraft.min} onChange={(e) => setFeeDraft({ ...feeDraft, min: e.target.value })} /></label><label className={styles.field}>Maximum (£)<input className="input" data-testid="fee-max" inputMode="decimal" required value={feeDraft.max} onChange={(e) => setFeeDraft({ ...feeDraft, max: e.target.value })} /></label></div>}
          <label className={styles.field}>Change note (optional)<input className="input" data-testid="fee-notes" maxLength={2000} placeholder="Reason for the new price" value={feeDraft.notes} onChange={(e) => setFeeDraft({ ...feeDraft, notes: e.target.value })} /></label>
          <p className={styles.help}>Today&apos;s date changes the current fee. A future date schedules it. To correct a scheduled fee, enter its date again. Earlier versions and saved patient plans are retained.</p>
        </fieldset>
        <div className={styles.actions}><button className="btn btn-primary" data-testid="fee-save" type="submit" disabled={saving || stale}>{saving ? "Saving…" : uncertain ? "Retry unchanged fee" : "Save fee & date"}</button></div>
      </form>
      {feeDraft.treatment.scheduled_fees.length > 0 && <div className={styles.history}><strong>Upcoming fees</strong><ul>{feeDraft.treatment.scheduled_fees.map((fee) => <li key={fee.revision}><span>{dateLabel(fee.effective_from!)} · {feeLabel(fee)}</span><button className={styles.smallButton} disabled={locked} onClick={() => setFeeDraft({ ...feeDraft, date: fee.effective_from!, type: fee.fee_type, amount: amountText(fee.amount_pence), min: amountText(fee.min_amount_pence), max: amountText(fee.max_amount_pence), notes: "" })}>Change this date&apos;s fee</button></li>)}</ul></div>}
      <details className={styles.history} data-testid="fee-history"><summary>Fee history · earlier versions are retained</summary>
        {historyLoading && <p role="status">Loading history…</p>}{historyError && <div role="alert"><p>{historyError}</p><button className={styles.smallButton} onClick={() => void readHistory(feeDraft.treatment.id, feeDraft.category)}>Retry history</button></div>}
        {history && <><ul>{history.items.map((fee) => <li key={fee.revision}><span>{fee.effective_from ? dateLabel(fee.effective_from) : "Undated original"}</span><strong>{feeLabel(fee)}</strong><small>Version {fee.revision}{fee.notes ? ` · ${fee.notes}` : ""}</small></li>)}{!history.next_before_revision && history.baseline_fee && <li><span>Original fee · date not recorded</span><strong>{feeLabel(history.baseline_fee)}</strong></li>}</ul>{!history.items.length && !history.baseline_fee && <p className={styles.help}>No fee has been recorded for this scheme.</p>}{history.next_before_revision !== null && <button className={styles.smallButton} data-testid="fee-history-load-older" disabled={historyLoading} onClick={() => void readHistory(feeDraft.treatment.id, feeDraft.category, history.next_before_revision!)}>Load earlier fees</button>}</>}
      </details></>}
    </dialog>
  </div>;
}
