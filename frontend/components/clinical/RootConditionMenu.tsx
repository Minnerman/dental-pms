import { rootConditions, type RootObservation, type RootPatch } from "./rootDiagnosis";

type Props = {
  enabled: boolean;
  current?: RootObservation;
  onChange: (patch: RootPatch) => void;
};

export default function RootConditionMenu({ enabled, current, onChange }: Props) {
  return <>
    <div className="clinical-chart-action-menu-hint">Diagnosis · Selected root only</div>
    {rootConditions.map(({ value, label }) =>
      <button key={value} type="button" className="btn btn-secondary"
        role="menuitemradio" aria-checked={current?.condition === value} disabled={!enabled}
        data-testid={`clinical-root-condition-${value}`} onClick={() => onChange({ condition: value })}>
        <span aria-hidden="true" className="clinical-root-swatch" data-condition={value} />
        {label}
      </button>
    )}
    <button type="button" className="btn btn-secondary" role="menuitemcheckbox"
      aria-checked={Boolean(current?.apicectomy)} disabled={!enabled}
      data-testid="clinical-root-apicectomy" onClick={() => onChange({ apicectomy: !current?.apicectomy })}>
      <span aria-hidden="true" className="clinical-root-apical-symbol">{current?.apicectomy ? "☑" : "☐"}</span>
      Apicectomy
    </button>
    <div className="clinical-chart-action-menu-hint">A straight line marks the root tip. Root numbers identify positions in this schematic, not measured anatomy.</div>
    <button type="button" className="btn btn-secondary" role="menuitem" disabled={!enabled}
      data-testid="clinical-root-reset" onClick={() => onChange({ condition: null, apicectomy: false })}>
      Reset root
    </button>
  </>;
}
