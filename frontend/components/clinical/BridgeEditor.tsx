"use client";

import { useEffect, useRef, useState } from "react";
import { bridgeArchTeeth, bridgeRoles, crownKinds, isMaterialCrown, type BridgeDraft, type BridgeGroup, type BridgeRole, type CrownKind } from "./crownDiagnosis";

export default function BridgeEditor({ tooth, role, bridges, enabled, saving, error, onSave, onCancel }: {
  tooth: string; role: BridgeRole; bridges: BridgeGroup[]; enabled: boolean; saving: boolean; error: string | null;
  onSave: (draft: BridgeDraft) => void; onCancel: () => void;
}) {
  const [first, setFirst] = useState(tooth);
  const [last, setLast] = useState(tooth);
  const [roles, setRoles] = useState<Record<string, BridgeRole | "">>({ [tooth]: role });
  const [material, setMaterial] = useState<CrownKind | "keep">("keep");
  const dialog = useRef<HTMLDivElement>(null);
  const cancelRef = useRef(onCancel);
  cancelRef.current = onCancel;
  useEffect(() => {
    const trigger = document.activeElement;
    (dialog.current?.querySelector<HTMLSelectElement>("select:not(:disabled)") ?? dialog.current)?.focus();
    return () => { if (trigger instanceof HTMLElement || trigger instanceof SVGElement) { if (trigger.isConnected) trigger.focus(); } };
  }, []);
  useEffect(() => { if (saving) dialog.current?.focus(); }, [saving]);
  const arch = bridgeArchTeeth(first.startsWith("U"));
  const start = arch.indexOf(first);
  const end = arch.indexOf(last);
  const span = end < 0 ? [] : arch.slice(Math.min(start, end), Math.max(start, end) + 1);
  const overlap = bridges.some((bridge) => bridge.members.some((member) => span.includes(member.tooth)));
  const hasSupport = span.some((value) => roles[value] === "abutment" || roles[value] === "wing");
  const hasPontic = span.some((value) => roles[value] === "pontic");
  const complete = span.length >= 2 && span.every((value) => roles[value]) && hasSupport && hasPontic && !overlap;
  return <div className="clinical-bridge-backdrop">
    <div ref={dialog} className="clinical-bridge-editor" role="dialog" tabIndex={-1} aria-modal="true" aria-labelledby="bridge-title" data-testid="clinical-bridge-editor"
      onKeyDown={(event) => {
        if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); if (!saving) cancelRef.current(); }
        if (event.key !== "Tab") return;
        const controls = Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), select:not(:disabled), input:not(:disabled), [tabindex="0"]') ?? []);
        const firstControl = controls[0]; const lastControl = controls[controls.length - 1];
        if (!controls.length) { event.preventDefault(); dialog.current?.focus(); }
        else if (!controls.includes(document.activeElement as HTMLElement)) { event.preventDefault(); (event.shiftKey ? lastControl : firstControl)?.focus(); }
        else if (event.shiftKey && document.activeElement === firstControl) { event.preventDefault(); lastControl?.focus(); }
        else if (!event.shiftKey && document.activeElement === lastControl) { event.preventDefault(); firstControl?.focus(); }
      }}>
      <h3 id="bridge-title">Record an existing bridge</h3>
      <p>Choose the first and last tooth, then identify every unit. No bridge roles are guessed.</p>
      <div className="clinical-bridge-endpoints">
        <label>First tooth<select data-testid="bridge-first" value={first} disabled={!enabled} onChange={(event) => {
          const value = event.target.value; setFirst(value); if (value[0] !== last[0]) setLast(value);
        }}>{[...bridgeArchTeeth(true), ...bridgeArchTeeth(false)].map((value) => <option key={value}>{value}</option>)}</select></label>
        <label>Last tooth<select data-testid="bridge-last" value={last} disabled={!enabled} onChange={(event) => setLast(event.target.value)}>
          {arch.map((value) => <option key={value}>{value}</option>)}
        </select></label>
      </div>
      <div className="clinical-bridge-members">{span.map((value) => <label key={value}><strong>{value}</strong>
        <select data-testid={`bridge-role-${value}`} value={roles[value] ?? ""} disabled={!enabled} onChange={(event) => setRoles((previous) => ({ ...previous, [value]: event.target.value as BridgeRole | "" }))}>
          <option value="">Choose unit role</option>{bridgeRoles.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}
        </select></label>)}</div>
      <label className="clinical-bridge-material">Crown material for this bridge<select data-testid="bridge-material" value={material ?? "keep"} disabled={!enabled} onChange={(event) => setMaterial(event.target.value as CrownKind | "keep")}>
        <option value="keep">Keep existing / unspecified</option>
        {crownKinds.filter(({ value }) => isMaterialCrown(value)).map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
      </select></label>
      <small>Keeping existing findings does not assume a material or sound condition. Choosing a material replaces crown findings on all units; individual crown conditions can then be recorded.</small>
      <p>Pontics replace absent teeth and have no natural roots. Review conflicting tooth or root findings before saving. A wing is shown as a curved bracket.</p>
      {overlap ? <p role="alert">This span includes an existing bridge. Reset that whole bridge first.</p> : !complete && <p role="status">Choose at least two teeth, including a pontic and an abutment or wing, and assign every unit.</p>}
      {error && <p role="alert">{error} Cancel to return to the chart and refresh. Review the saved findings before trying again; cancelling discards only this local draft.</p>}
      <div className="clinical-diagnosis-buttons">
        <button type="button" className="btn" data-testid="bridge-save" disabled={!enabled || !complete} onClick={() => onSave({
          members: span.map((value) => ({ tooth: value, role: roles[value] as BridgeRole })),
          ...(material !== "keep" && isMaterialCrown(material) ? { crown: { kind: material, issues: [] } } : {}),
        })}>{saving ? "Saving…" : "Save bridge"}</button>
        <button type="button" className="btn btn-secondary" data-testid="bridge-cancel" disabled={saving} onClick={onCancel}>Cancel</button>
      </div>
      <small>Current diagnosis only · no treatment plan, extraction or charge is created.</small>
    </div>
  </div>;
}
