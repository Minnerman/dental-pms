import { crownKinds, dentureKinds, bridgeRoles, crownIssues, crownDiagnosisLabel, isMaterialCrown, isDentureCrown, toggleCrownIssue, type CrownObservation, type BridgeRole, type BridgeGroup } from "./crownDiagnosis";

export function CrownSymbol({ kind }: { kind: CrownObservation["kind"] }) {
  return <svg className="clinical-diagnosis-symbol clinical-crown-symbol" data-kind={kind ?? "reset"} viewBox="0 0 32 32" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round">
    {isDentureCrown(kind) ? <><path d="M4 23q12 5 24 0v4q-12 5-24 0Z" fill={kind === "denture_cocr" ? "#9eabb9" : "#d995ac"} stroke={kind === "denture_cocr" ? "#516575" : "#915369"} /><path d="M7 21 5 11q0-7 6-5l5 1 5-1q6-2 6 5l-2 10q-9 4-18 0Z" fill="#fff6db" stroke="#8d8065" /></>
      : kind === "missing" ? <><path d="M10 18l2-11h8l2 11Z" fill="var(--clinical-crown-stump, #c8b48b)" /><path d="M10 18c0 4 2 9 4 11l2-9 2 9c2-2 4-7 4-11" /></>
      : kind === null ? <><path d="M8 10a11 11 0 1 1-2 10M8 4v6H2" /><path d="M12 13q4-3 8 0l-1 8h-6Z" /></>
      : <><path className="clinical-crown-symbol-fill" d="M6 21 4 12q-1-8 7-7l5 2 5-2q8-1 7 7l-2 9q-5 3-10 0-5 3-10 0Z" /><path d="m10 25 2 4m10-4-2 4" /></>}
  </svg>;
}

export function BridgeSymbol({ role }: { role: BridgeRole }) {
  return <svg className="clinical-diagnosis-symbol clinical-crown-symbol" viewBox="0 0 32 32" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 16h30" strokeWidth="3" />
    <path d="M9 22 7 11q0-6 5-5l4 2 4-2q5-1 5 5l-2 11q-7 4-14 0Z" fill={role === "pontic" ? "#fff6db" : "var(--panel, white)"} />
    {role === "abutment" && <path d="m11 25 2 5 3-5 3 5 2-5" />}
    {role === "wing" && <path d="M23 6q11 10 0 20" stroke="#8ba0b3" strokeWidth="3" />}
  </svg>;
}

export function CrownIssueChoices({ observation, enabled, prefix, onChange }: {
  observation: CrownObservation; enabled: boolean; prefix: string; onChange: (value: CrownObservation) => void;
}) {
  if (!isMaterialCrown(observation.kind)) return null;
  return <fieldset className="clinical-crown-issues" disabled={!enabled}>
    <legend>Crown condition · select any that apply</legend>
    <div>{crownIssues.map(({ value, label }) => <label key={value}>
      <input type="checkbox" data-testid={`${prefix}-${value}`} checked={observation.issues.includes(value)}
        onChange={() => onChange(toggleCrownIssue(observation, value))} />{label}
    </label>)}</div>
    <small>No conditions selected means condition not specified, not confirmed sound.</small>
  </fieldset>;
}

type Props = {
  enabled: boolean; saving: boolean; observation: CrownObservation | null; selected: string[]; canNote: boolean;
  onChoose: (value: CrownObservation) => void; onApply: () => void;
  onCancel: () => void; onBack: () => void; onNote: () => void;
  onBridge: (role: BridgeRole) => void; bridges: BridgeGroup[]; onBridgeReset: (bridge: BridgeGroup) => void;
};

export default function CrownDiagnosisPalette({ enabled, saving, observation, selected, canNote, onChoose, onApply, onCancel, onNote, onBridge, bridges, onBridgeReset }: Props) {
  return <section className="clinical-diagnosis-palette" data-testid="clinical-crown-diagnosis-palette" aria-label="Crown diagnosis">
    <div className="clinical-diagnosis-tiles clinical-crown-tiles">
      {[...crownKinds, { value: null, label: "Reset crown" }].map(({ value, label }) => <button key={value ?? "reset"} type="button" className="btn btn-secondary"
        data-testid={`crown-diagnosis-palette-${value ?? "reset"}`} disabled={!enabled}
        aria-pressed={Boolean(observation && observation.kind === value)} onClick={() => onChoose({ kind: value, issues: [] })}>
        <CrownSymbol kind={value} />{label}
      </button>)}
    </div>
    <div className="clinical-restoration-sections">
      <div><div className="clinical-restoration-heading">Bridge units · define a complete bridge</div>
        <div className="clinical-diagnosis-tiles clinical-bridge-tiles">
          {bridgeRoles.map(({ value, label }) => <button key={value} type="button" className="btn btn-secondary" disabled={!enabled}
            data-testid={`crown-diagnosis-bridge-${value}`} onClick={() => onBridge(value)}><BridgeSymbol role={value} />{label}</button>)}
        </div>
      </div>
      <div><div className="clinical-restoration-heading">Denture teeth</div>
        <div className="clinical-diagnosis-tiles clinical-denture-tiles">
          {dentureKinds.map(({ value, label }) => <button key={value} type="button" className="btn btn-secondary" disabled={!enabled}
            data-testid={`crown-diagnosis-palette-${value}`} aria-pressed={observation?.kind === value} onClick={() => onChoose({ kind: value, issues: [] })}>
            <CrownSymbol kind={value} />{label}</button>)}
        </div>
      </div>
    </div>
    {observation && <CrownIssueChoices observation={observation} enabled={enabled} prefix="crown-diagnosis-issue" onChange={onChoose} />}
    <div className="clinical-diagnosis-selection" role="status" data-testid="crown-diagnosis-selection">
      {observation ? <><strong>{crownDiagnosisLabel(observation)}</strong> · {selected.length ? selected.join(", ") : "Select crown areas above"}</>
        : selected.length ? `${selected.join(", ")} crown area selected · Choose an observation` : "Choose an observation, then select crown areas above"}
      {observation?.kind === "missing" && <span>Restoration missing; a prepared tooth stump remains.</span>}
      {isDentureCrown(observation?.kind) && <span>Select crown areas or the dashed gap targets above. Artificial teeth have no natural roots; conflicting tooth/root findings must be reviewed first.</span>}
      {observation && observation.kind === null && <span>Clears only crown findings. Tooth conditions, roots, notes and treatment history are kept.</span>}
    </div>
    {bridges.length > 0 && <div className="clinical-bridge-list" aria-label="Recorded bridges">
      {bridges.map((bridge) => <div key={bridge.id}>
        <span><strong>Bridge {bridge.span_start}–{bridge.span_end}</strong> · {bridge.members.map((member) => `${member.tooth} ${member.role}`).join(" · ")}</span>
        <button className="btn btn-secondary" type="button" data-testid={`bridge-reset-${bridge.id}`} disabled={!enabled}
          onClick={() => onBridgeReset(bridge)}>Reset whole bridge</button>
      </div>)}
    </div>}
    <div className="clinical-diagnosis-buttons">
      <button className="btn" type="button" data-testid="crown-diagnosis-apply" disabled={!enabled || !observation || !selected.length} onClick={onApply}>
        {saving ? "Saving…" : `Apply to ${selected.length || "selected"} ${selected.length === 1 ? "tooth" : "teeth"}`}
      </button>
      <button className="btn btn-secondary" type="button" data-testid="crown-diagnosis-cancel" disabled={saving || (!observation && !selected.length)} onClick={onCancel}>Cancel selection</button>
      <button className="btn btn-secondary" type="button" data-testid="crown-diagnosis-note" disabled={saving || !canNote || selected.length !== 1} onClick={onNote}>Add tooth note</button>
    </div>
    <small>Current diagnosis only. No treatment or charges are created. Select one tooth to add a note.</small>
  </section>;
}
