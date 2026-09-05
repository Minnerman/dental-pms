import { useState } from "react";
import { crownKinds, type CrownObservation } from "./crownDiagnosis";
import { CrownIssueChoices, CrownSymbol } from "./CrownDiagnosisPalette";

export default function CrownConditionMenu({ enabled, current, onApply }: {
  enabled: boolean; current?: CrownObservation | null; onApply: (value: CrownObservation) => void;
}) {
  const [draft, setDraft] = useState<CrownObservation | null>(current ?? null);
  return <div className="clinical-crown-menu-choices">
    <div className="clinical-chart-action-menu-hint">Diagnosis · Crown only. Choose a finding and any conditions, then Apply.</div>
    {crownKinds.map(({ value, label }) => <button key={value} type="button" className="btn btn-secondary"
      role="menuitemradio" aria-checked={draft?.kind === value} disabled={!enabled}
      data-testid={`clinical-crown-condition-${value}`} onClick={() => setDraft({ kind: value, issues: [] })}>
      <CrownSymbol kind={value} />{label}
    </button>)}
    {draft && <CrownIssueChoices observation={draft} enabled={enabled} prefix="clinical-crown-issue" onChange={setDraft} />}
    {draft?.kind === "fractured" && <div className="clinical-chart-action-menu-hint">Crown portion broken away; roots remain.</div>}
    {draft?.kind === "missing" && <div className="clinical-chart-action-menu-hint">Restoration missing; prepared stump remains.</div>}
    <button type="button" className="btn btn-secondary" role="menuitemradio" aria-checked={Boolean(draft && draft.kind === null)} disabled={!enabled}
      data-testid="clinical-crown-reset" onClick={() => setDraft({ kind: null, issues: [] })}>Reset crown</button>
    <button type="button" className="btn" role="menuitem" disabled={!enabled || !draft} data-testid="clinical-crown-apply"
      onClick={() => { if (draft) onApply(draft); }}>Apply crown observation</button>
  </div>;
}
