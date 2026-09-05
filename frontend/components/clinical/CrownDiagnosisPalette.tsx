import { crownKinds, crownIssues, crownDiagnosisLabel, isMaterialCrown, toggleCrownIssue, type CrownObservation } from "./crownDiagnosis";

export function CrownSymbol({ kind }: { kind: CrownObservation["kind"] }) {
  return <svg className="clinical-diagnosis-symbol clinical-crown-symbol" data-kind={kind ?? "reset"} viewBox="0 0 32 32" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round">
    {kind === "fractured" ? <><path d="M7 17l4-3 4 3 4-3 6 3M9 18c1 5 2 8 4 11l2-9m8-2c-1 5-2 8-4 11l-2-9" /><path d="M10 9l-3-4m9 3V3m6 6 3-4" /></>
      : kind === "missing" ? <><path d="M10 18l2-11h8l2 11Z" fill="var(--clinical-crown-stump, #c8b48b)" /><path d="M10 18c0 4 2 9 4 11l2-9 2 9c2-2 4-7 4-11" /></>
      : kind === null ? <><path d="M8 10a11 11 0 1 1-2 10M8 4v6H2" /><path d="M12 13q4-3 8 0l-1 8h-6Z" /></>
      : <><path className="clinical-crown-symbol-fill" d="M6 21 4 12q-1-8 7-7l5 2 5-2q8-1 7 7l-2 9q-5 3-10 0-5 3-10 0Z" /><path d="m10 25 2 4m10-4-2 4" /></>}
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
};

export default function CrownDiagnosisPalette({ enabled, saving, observation, selected, canNote, onChoose, onApply, onCancel, onBack, onNote }: Props) {
  return <section className="clinical-diagnosis-palette" data-testid="clinical-crown-diagnosis-palette" aria-label="Crown diagnosis">
    <div className="clinical-diagnosis-heading"><strong>Diagnosis · Crown</strong>
      <button type="button" className="btn btn-secondary" data-testid="crown-diagnosis-back" disabled={saving} onClick={onBack}>Tooth-level choices</button>
    </div>
    <p>Choose a crown observation, select one or more crown areas, then Apply. Root findings are kept.</p>
    <div className="clinical-diagnosis-tiles clinical-crown-tiles">
      {[...crownKinds, { value: null, label: "Reset crown" }].map(({ value, label }) => <button key={value ?? "reset"} type="button" className="btn btn-secondary"
        data-testid={`crown-diagnosis-palette-${value ?? "reset"}`} disabled={!enabled}
        aria-pressed={Boolean(observation && observation.kind === value)} onClick={() => onChoose({ kind: value, issues: [] })}>
        <CrownSymbol kind={value} />{label}
      </button>)}
    </div>
    {observation && <CrownIssueChoices observation={observation} enabled={enabled} prefix="crown-diagnosis-issue" onChange={onChoose} />}
    <div className="clinical-diagnosis-selection" role="status" data-testid="crown-diagnosis-selection">
      {observation ? <><strong>{crownDiagnosisLabel(observation)}</strong> · {selected.length ? selected.join(", ") : "Select crown areas above"}</>
        : selected.length ? `${selected.join(", ")} crown area selected · Choose an observation` : "Choose an observation, then select crown areas above"}
      {observation?.kind === "fractured" && <span>Crown portion broken away; roots remain visible.</span>}
      {observation?.kind === "missing" && <span>Restoration missing; a prepared tooth stump remains.</span>}
      {observation && observation.kind === null && <span>Clears only crown findings. Tooth conditions, roots, notes and treatment history are kept.</span>}
    </div>
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
