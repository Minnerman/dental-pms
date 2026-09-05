import { rootConditions, type RootObservation, type RootPatch } from "./rootDiagnosis";

type Props = {
  enabled: boolean;
  current?: Partial<RootObservation> & { mixed?: boolean; apicectomyMixed?: boolean };
  onChange: (patch: RootPatch) => void;
};

export default function RootConditionMenu({ enabled, current, onChange }: Props) {
  return <>
    <div className="clinical-chart-action-menu-hint">Diagnosis · Whole root area of this tooth</div>
    {current?.mixed && <div className="clinical-chart-action-menu-hint">Existing root findings differ. Your choice will apply across this tooth’s root area.</div>}
    {rootConditions.map(({ value, label }) =>
      <button key={value} type="button" className="btn btn-secondary"
        role="menuitemradio" aria-checked={current?.condition === value} disabled={!enabled}
        data-testid={`clinical-root-condition-${value}`} onClick={() => onChange({ condition: value })}>
        <span aria-hidden="true" className="clinical-root-swatch" data-condition={value} />
        {label}
      </button>
    )}
    <button type="button" className="btn btn-secondary" role="menuitemcheckbox"
      aria-checked={current?.apicectomyMixed ? "mixed" : Boolean(current?.apicectomy)} disabled={!enabled}
      data-testid="clinical-root-apicectomy" onClick={() => onChange({ apicectomy: !current?.apicectomy })}>
      <span aria-hidden="true" className="clinical-root-apical-symbol">{current?.apicectomyMixed ? "⊟" : current?.apicectomy ? "☑" : "☐"}</span>
      Apicectomy
    </button>
    <div className="clinical-chart-action-menu-hint">A straight line marks the root tips. This choice applies to the whole root area.</div>
    <button type="button" className="btn btn-secondary" role="menuitem" disabled={!enabled}
      data-testid="clinical-root-reset" onClick={() => onChange({ condition: null, apicectomy: false })}>
      Reset root area
    </button>
  </>;
}
