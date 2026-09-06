import { actionSupportsTeeth, diagnosisAction, diagnosisActions, type DiagnosisAction } from "./toothDiagnosis";
import DiagnosisIcon from "./DiagnosisIcon";
type Props = {
  enabled: boolean; saving: boolean; action: DiagnosisAction | null; selected: string[];
  lastAction: DiagnosisAction | null; activeTooth: string | null;
  onChoose: (action: DiagnosisAction) => void; onApply: () => void; onCancel: () => void;
  onArchMissing: (tooth: string) => void; onNote: () => void; onDetails: () => void;
};
export default function DiagnosisPalette(props: Props) {
  const { enabled, saving, action, selected, lastAction } = props;
  const invalid = action && !actionSupportsTeeth(action, selected);
  return <section className="clinical-diagnosis-palette" data-testid="clinical-diagnosis-palette" aria-label="Whole-tooth diagnosis">
    <div className="clinical-diagnosis-heading"><strong>Diagnosis · Whole tooth</strong><span>Use the level tabs, or click a tooth number, root, crown or surface. Right-click opens its menu.</span></div>
    <p>Choose a condition, select one or more tooth numbers, then Apply. No treatment or charges are created.</p>
    <div className="clinical-diagnosis-tiles">
      {diagnosisActions.map((item) => <button key={item.id} className="btn btn-secondary" type="button"
        data-testid={`diagnosis-palette-${item.id}`} aria-pressed={action === item.id}
        disabled={!enabled} onClick={() => props.onChoose(item.id)}>
        <DiagnosisIcon action={item.id} className="clinical-diagnosis-symbol" />{item.label}
      </button>)}
    </div>
    <div className="clinical-diagnosis-selection" role="status" data-testid="diagnosis-selection">
      {action ? <><strong>{diagnosisAction(action).label}</strong> · {selected.length ? selected.join(", ") : "Select tooth numbers above"}</> : "No condition selected"}
      {invalid && <span role="alert">Deciduous teeth use positions 1–5 (A–E). Deselect positions 6–8.</span>}
      {action === "reset" && <span>Clears current tooth, root, crown and surface findings, movement and rotation. Notes and treatment history are kept; no healthy or present finding is recorded.</span>}
    </div>
    <div className="clinical-diagnosis-buttons">
      <button className="btn" type="button" data-testid="diagnosis-apply" disabled={!enabled || !action || !selected.length || Boolean(invalid)} onClick={props.onApply}>
        {saving ? "Saving…" : `Apply to ${selected.length || "selected"} ${selected.length === 1 ? "tooth" : "teeth"}`}
      </button>
      <button className="btn btn-secondary" type="button" data-testid="diagnosis-cancel" disabled={saving || (!action && !selected.length)} onClick={props.onCancel}>Cancel selection</button>
      <button className="btn btn-secondary" type="button" disabled={!enabled || !lastAction} onClick={() => lastAction && props.onChoose(lastAction)} title={lastAction ? diagnosisAction(lastAction).label : "No successful action yet"}>Repeat last action</button>
    </div>
    <div className="clinical-diagnosis-buttons clinical-diagnosis-secondary">
      <button className="btn btn-secondary" type="button" disabled={!enabled} onClick={() => props.onArchMissing("UR1")}>Upper arch missing…</button>
      <button className="btn btn-secondary" type="button" disabled={!enabled} onClick={() => props.onArchMissing("LR1")}>Lower arch missing…</button>
      <button className="btn btn-secondary" type="button" disabled={!enabled || !props.activeTooth || Boolean(action)} onClick={props.onNote}>Add tooth note</button>
      <button className="btn btn-secondary" type="button" disabled={!props.activeTooth || Boolean(action)} onClick={props.onDetails}>Tooth details</button>
    </div>
    <small>Forward = toward the arch centre (mesial); backward = away (distal). Arrows describe the observed position, not a planned movement. Rotation is schematic, not an angle measurement.</small>
  </section>;
}
