import { useState } from "react";
import { crownKinds, dentureKinds, bridgeRoles, type CrownObservation, type BridgeRole, type BridgeGroup } from "./crownDiagnosis";
import { CrownIssueChoices, CrownSymbol, BridgeSymbol } from "./CrownDiagnosisPalette";

export default function CrownConditionMenu({ enabled, current, onApply, onBridge, bridge, onBridgeReset }: {
  enabled: boolean; current?: CrownObservation | null; onApply: (value: CrownObservation) => void;
  onBridge: (role: BridgeRole) => void; bridge?: BridgeGroup; onBridgeReset: (bridge: BridgeGroup) => void;
}) {
  const [draft, setDraft] = useState<CrownObservation | null>(current ?? null);
  return <div className="clinical-crown-menu-choices">
    <div className="clinical-chart-action-menu-hint">Diagnosis · Crown only. Choose a finding and any conditions, then Apply.</div>
    {crownKinds.map(({ value, label }) => <button key={value} type="button" className="btn btn-secondary"
      role="menuitemradio" aria-checked={draft?.kind === value} disabled={!enabled || (Boolean(bridge) && value === "missing")}
      data-testid={`clinical-crown-condition-${value}`} onClick={() => setDraft({ kind: value, issues: [] })}>
      <CrownSymbol kind={value} />{label}
    </button>)}
    {draft && <CrownIssueChoices observation={draft} enabled={enabled} prefix="clinical-crown-issue" onChange={setDraft} />}
    {draft?.kind === "fractured" && <div className="clinical-chart-action-menu-hint">Previously recorded broken-away crown. Choose a current option to change it.</div>}
    {draft?.kind === "missing" && <div className="clinical-chart-action-menu-hint">Restoration missing; prepared stump remains.</div>}
    <button type="button" className="btn btn-secondary" role="menuitemradio" aria-checked={Boolean(draft && draft.kind === null)} disabled={!enabled || Boolean(bridge)}
      data-testid="clinical-crown-reset" onClick={() => setDraft({ kind: null, issues: [] })}>Reset crown</button>
    <div className="clinical-chart-action-menu-hint">Denture teeth</div>
    {dentureKinds.map(({ value, label }) => <button key={value} type="button" className="btn btn-secondary" role="menuitemradio"
      aria-checked={draft?.kind === value} disabled={!enabled || Boolean(bridge)} data-testid={`clinical-crown-condition-${value}`}
      onClick={() => setDraft({ kind: value, issues: [] })}><CrownSymbol kind={value} />{label}</button>)}
    <button type="button" className="btn" role="menuitem" disabled={!enabled || !draft || draft.kind === "fractured"} data-testid="clinical-crown-apply"
      onClick={() => { if (draft) onApply(draft); }}>Apply crown observation</button>
    <div className="clinical-chart-action-menu-hint">{bridge ? `Bridge ${bridge.span_start}–${bridge.span_end}. Material changes keep the bridge connected.` : "Bridge units · define a complete bridge"}</div>
    {bridge ? <button className="btn btn-secondary" type="button" role="menuitem" data-testid={`bridge-reset-${bridge.id}`} disabled={!enabled}
      onClick={() => onBridgeReset(bridge)}>Reset whole bridge</button>
      : bridgeRoles.map(({ value, label }) => <button key={value} type="button" className="btn btn-secondary" role="menuitem" disabled={!enabled}
        data-testid={`clinical-crown-bridge-${value}`} onClick={() => onBridge(value)}><BridgeSymbol role={value} />{label}</button>)}
  </div>;
}
