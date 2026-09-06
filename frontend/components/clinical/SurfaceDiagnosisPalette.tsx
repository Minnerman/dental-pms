import {
  SurfaceDiagnosisActions,
  SurfaceKindChoices,
  SurfaceObservationControls,
  SurfaceSelectionSummary,
  type SurfaceDiagnosisProps,
} from "./SurfaceDiagnosisControls";

export default function SurfaceDiagnosisPalette(props: SurfaceDiagnosisProps) {
  const { observation, targets, disabled, onChange } = props;
  return <section className="clinical-diagnosis-palette clinical-surface-palette"
    data-testid="clinical-surface-diagnosis-palette" aria-label="Surface diagnosis">
    <SurfaceKindChoices observation={observation} disabled={disabled} onChange={onChange} prefix="surface-diagnosis-palette" />
    {observation && <SurfaceObservationControls observation={observation} disabled={disabled} onChange={onChange} prefix="surface-diagnosis" />}
    <SurfaceSelectionSummary observation={observation} targets={targets} testId="surface-diagnosis-selection" />
    <SurfaceDiagnosisActions {...props} prefix="surface-diagnosis" />
    <small>Current diagnosis only. No treatment or charges are created. Click a tooth number, root area or crown to change level.</small>
  </section>;
}
