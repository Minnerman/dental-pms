import {
  SurfaceDiagnosisActions,
  SurfaceKindChoices,
  SurfaceObservationControls,
  SurfaceSelectionSummary,
  type SurfaceDiagnosisProps,
} from "./SurfaceDiagnosisControls";

export default function SurfaceConditionMenu(props: SurfaceDiagnosisProps) {
  const { observation, targets, disabled, onChange } = props;
  return <div className="clinical-surface-menu-content" data-testid="clinical-surface-menu-content">
    <div className="clinical-chart-action-menu-hint">Diagnosis · Selected surfaces. Choose the finding, then Apply.</div>
    <SurfaceSelectionSummary observation={observation} targets={targets} testId="clinical-surface-selection" />
    <SurfaceKindChoices observation={observation} disabled={disabled} onChange={onChange} prefix="clinical-surface-condition" menu />
    {observation && <SurfaceObservationControls observation={observation} disabled={disabled} onChange={onChange} prefix="clinical-surface" />}
    <SurfaceDiagnosisActions {...props} prefix="clinical-surface" menu />
    <small>Tooth, root and crown findings are separate. No treatment or charges are created.</small>
  </div>;
}
