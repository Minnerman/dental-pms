import {
  newSurfaceObservation,
  surfaceConditions,
  surfaceDefects,
  surfaceDiagnosisLabel,
  surfaceKinds,
  surfaceMaterials,
  surfaceName,
  surfaceSelectionLabel,
  type SurfaceCondition,
  type SurfaceKind,
  type SurfaceMaterial,
  type SurfaceObservation,
  type SurfaceTarget,
} from "./surfaceDiagnosis";

export type SurfaceDiagnosisProps = {
  observation: SurfaceObservation | null;
  targets: SurfaceTarget[];
  disabled: boolean;
  onChange: (observation: SurfaceObservation) => void;
  onApply: () => void;
  onCancel: () => void;
  onAddNote?: () => void;
};

export function selectedSurfaceCount(targets: SurfaceTarget[]) {
  return targets.reduce((total, target) => total + target.surfaces.length, 0);
}

export function SurfaceSymbol({ kind }: { kind: SurfaceKind | null }) {
  return <svg className="clinical-diagnosis-symbol clinical-surface-symbol" data-kind={kind ?? "reset"}
    width="44.85" height="44.85" viewBox="0 0 32 32" aria-hidden="true" focusable="false"
    fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    {kind === null ? <>
      <path d="M8 10a11 11 0 1 1-2 10M8 4v6H2" />
      <path d="M12 12h9v9h-9ZM12 12l3 3m6-3-3 3m3 6-3-3m-6 3 3-3M15 15h3v3h-3Z" />
    </> : <>
      <path d="M5 5h22v22H5ZM5 5l7 7m15-7-7 7m7 15-7-7M5 27l7-7M12 12h8v8h-8Z" opacity=".65" />
      {kind === "carious" && <g className="clinical-surface-symbol-caries" fill="#bc3546" stroke="none">
        <circle cx="15" cy="14.5" r="2.3" /><circle cx="19" cy="18" r="1.7" />
        <circle cx="13" cy="20.5" r="1.3" /><circle cx="21.5" cy="12" r="1" />
      </g>}
      {kind === "defective" && <path className="clinical-surface-symbol-defective"
        d="m18 6-4 7 5 3-6 5 3 5" stroke="#bc3546" strokeWidth="2.2" />}
      {kind === "restored" && <>
        <path d="M12 12h8v8h-8Z" fill="currentColor" fillOpacity=".22" strokeWidth="1.8" />
        <path d="m13.5 18 4.5-4.5m-2 6 3.5-3.5" strokeWidth="1.2" />
      </>}
      {kind === "sealant" && <path d="m10 14 4 3 3-4 5 5m-5-5 1-4m-4 8-2 5"
        strokeWidth="3" />}
    </>}
  </svg>;
}

export function SurfaceKindChoices({ observation, disabled, onChange, prefix, menu = false }: {
  observation: SurfaceObservation | null;
  disabled: boolean;
  onChange: (observation: SurfaceObservation) => void;
  prefix: string;
  menu?: boolean;
}) {
  return <div className={menu ? "clinical-surface-menu-choices" : "clinical-diagnosis-tiles clinical-surface-tiles"}
    role={menu ? "menu" : undefined} aria-label={menu ? "Surface category" : undefined}>
    {[...surfaceKinds, { value: null, label: "Reset selected surfaces" }].map(({ value, label }) => {
      const selected = Boolean(observation && observation.kind === value);
      return <button key={value ?? "reset"} type="button" className="btn btn-secondary"
        data-testid={`${prefix}-${value ?? "reset"}`} disabled={disabled}
        role={menu ? "menuitemradio" : undefined} aria-checked={menu ? selected : undefined}
        aria-pressed={menu ? undefined : selected} onClick={() => onChange(newSurfaceObservation(value))}>
        <SurfaceSymbol kind={value} />{label}
      </button>;
    })}
  </div>;
}

export function SurfaceObservationControls({ observation, disabled, onChange, prefix }: {
  observation: SurfaceObservation;
  disabled: boolean;
  onChange: (observation: SurfaceObservation) => void;
  prefix: string;
}) {
  const showDefects = observation.kind === "defective" || observation.condition === "defective";
  const setCondition = (condition: SurfaceCondition | null) => onChange({
    ...observation, condition, defects: condition === "defective" ? observation.defects : [],
  });
  return <div className="clinical-surface-controls">
    {observation.kind === "restored" && <label className="clinical-surface-control">
      Restoration material
      <select data-testid={`${prefix}-material`} value={observation.material ?? ""} disabled={disabled}
        onChange={(event) => onChange({ ...observation, material: event.target.value as SurfaceMaterial })}>
        <option value="" disabled>Material unspecified</option>
        {surfaceMaterials.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
      </select>
    </label>}
    {observation.kind === "carious" && <label className="clinical-surface-control">
      Caries stage
      <select data-testid={`${prefix}-stage`} value={observation.condition ?? ""} disabled={disabled}
        onChange={(event) => setCondition(event.target.value ? event.target.value as SurfaceCondition : null)}>
        <option value="">Stage unspecified</option>
        {surfaceConditions.filter(({ value }) => value.startsWith("carious_")).map(({ value, label }) =>
          <option key={value} value={value}>{label.replace("Carious · ", "")}</option>)}
      </select>
    </label>}
    {(observation.kind === "restored" || observation.kind === "sealant") && <label className="clinical-surface-control">
      Surface condition
      <select data-testid={`${prefix}-condition`} value={observation.condition ?? ""} disabled={disabled}
        onChange={(event) => setCondition(event.target.value ? event.target.value as SurfaceCondition : null)}>
        <option value="">Condition unspecified</option>
        {surfaceConditions.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
      </select>
    </label>}
    {showDefects && <fieldset className="clinical-surface-defects" disabled={disabled}>
      <legend>Defect details · select any that apply</legend>
      <div>{surfaceDefects.map(({ value, label }) => <label key={value}>
        <input type="checkbox" data-testid={`${prefix}-defect-${value}`} checked={observation.defects.includes(value)}
          onChange={() => onChange({ ...observation, defects: observation.defects.includes(value)
            ? observation.defects.filter((defect) => defect !== value)
            : [...observation.defects, value].sort() })} />{label}
      </label>)}</div>
      <small>No details selected means the defect type is unspecified.</small>
    </fieldset>}
    {observation.kind !== null && <small className="clinical-surface-unspecified-help">
      Record only what is known. An unspecified stage or condition does not mean early caries or sound tooth structure.
    </small>}
  </div>;
}

export function SurfaceSelectionSummary({ observation, targets, testId }: {
  observation: SurfaceObservation | null;
  targets: SurfaceTarget[];
  testId: string;
}) {
  const count = selectedSurfaceCount(targets);
  const description = targets.map(({ tooth, surfaces }) => `${tooth}: ${surfaces.map(surfaceName).join(", ")}`).join("; ");
  return <div className="clinical-diagnosis-selection clinical-surface-selection-summary" role="status" data-testid={testId}>
    {observation && <strong>{surfaceDiagnosisLabel(observation)}</strong>}
    {count > 0 ? <span className="clinical-surface-selected-targets" aria-label={description}>
      {observation && " · "}{surfaceSelectionLabel(targets)}
    </span> : <span>{observation ? " · " : ""}Select tooth surfaces above</span>}
    {!observation && count > 0 && <span> · Choose a surface observation</span>}
    {observation?.kind === null && <span className="clinical-surface-reset-warning">
      Resets only the selected surfaces to unspecified. Tooth, root and crown findings, notes and treatment history are kept.
    </span>}
  </div>;
}

export function SurfaceDiagnosisActions({ observation, targets, disabled, onApply, onCancel, onAddNote, prefix, menu = false }: SurfaceDiagnosisProps & {
  prefix: string;
  menu?: boolean;
}) {
  const count = selectedSurfaceCount(targets);
  return <div className="clinical-diagnosis-buttons clinical-surface-actions">
    <button type="button" className="btn" data-testid={`${prefix}-apply`}
      disabled={disabled || !observation || count === 0} onClick={onApply}>
      {count ? `Apply to ${count} ${count === 1 ? "surface" : "surfaces"}` : "Apply to selected surfaces"}
    </button>
    <button type="button" className="btn btn-secondary"
      data-testid={`${prefix}-cancel`} onClick={onCancel}>
      {menu ? "Cancel" : "Cancel selection"}
    </button>
    {onAddNote && <button type="button" className="btn btn-secondary"
      data-testid={`${prefix}-note`} disabled={disabled || targets.length !== 1 || count === 0} onClick={onAddNote}>
      Add tooth note
    </button>}
  </div>;
}
