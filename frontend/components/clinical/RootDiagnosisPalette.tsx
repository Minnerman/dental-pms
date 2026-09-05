import { rootDiagnosisActions, rootDiagnosisAction, type RootDiagnosisAction } from "./rootDiagnosis";

type Props = {
  enabled: boolean; saving: boolean; action: RootDiagnosisAction | null; selected: string[];
  onChoose: (action: RootDiagnosisAction) => void; onApply: () => void;
  onCancel: () => void; onBack: () => void;
};

export default function RootDiagnosisPalette({ enabled, saving, action, selected, onChoose, onApply, onCancel, onBack }: Props) {
  return <section className="clinical-diagnosis-palette" data-testid="clinical-root-diagnosis-palette" aria-label="Whole root area diagnosis">
    <div className="clinical-diagnosis-heading"><strong>Diagnosis · Root area</strong>
      <button type="button" className="btn btn-secondary" data-testid="root-diagnosis-back" disabled={saving} onClick={onBack}>Tooth-level choices</button>
    </div>
    <p>Choose an observation, select the root areas of one or more teeth, then Apply. Each choice covers all roots of each selected tooth.</p>
    <div className="clinical-diagnosis-tiles">
      {rootDiagnosisActions.map((item) => <button key={item.id} type="button" className="btn btn-secondary"
        data-testid={`root-diagnosis-palette-${item.id}`} disabled={!enabled}
        aria-pressed={action === item.id} onClick={() => onChoose(item.id)}>
        {item.id === "apicectomy" ? <svg className="clinical-diagnosis-symbol" viewBox="0 0 32 32" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M10 7c2 6 1 13 4 18h4c3-5 2-12 4-18M10 7h12M9 25h14M14 29h4" /></svg>
          : item.id === "reset" ? <svg className="clinical-diagnosis-symbol" viewBox="0 0 32 32" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M8 10a11 11 0 1 1-2 10M8 4v6H2M13 12c0 5 1 9 3 12 2-3 3-7 3-12" /></svg>
          : <span className="clinical-root-swatch clinical-root-palette-swatch" data-condition={item.id} aria-hidden="true" />}
        {item.label}
      </button>)}
    </div>
    <div className="clinical-diagnosis-selection" role="status" data-testid="root-diagnosis-selection">
      {action ? <><strong>{rootDiagnosisAction(action).label}</strong> · {selected.length ? selected.join(", ") : "Select root areas above"}</>
        : selected.length ? `${selected.join(", ")} root area selected · Choose an observation` : "Choose an observation, then select root areas above"}
      {action === "reset" && <span>Clears only root findings and apicectomy markers. Tooth conditions, notes and treatment history are kept.</span>}
    </div>
    <div className="clinical-diagnosis-buttons">
      <button className="btn" type="button" data-testid="root-diagnosis-apply" disabled={!enabled || !action || !selected.length} onClick={onApply}>
        {saving ? "Saving…" : `Apply to ${selected.length || "selected"} ${selected.length === 1 ? "tooth" : "teeth"}`}
      </button>
      <button className="btn btn-secondary" type="button" data-testid="root-diagnosis-cancel" disabled={saving || (!action && !selected.length)} onClick={onCancel}>Cancel selection</button>
    </div>
    <small>Current diagnosis only. These findings do not create treatment or charges. Click a tooth number to return to tooth-level choices.</small>
  </section>;
}
