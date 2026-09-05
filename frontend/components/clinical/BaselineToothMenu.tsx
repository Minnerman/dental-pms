import { actionSupportsTeeth, diagnosisAction, diagnosisActions, type DiagnosisAction, type DiagnosisPatch } from "./toothDiagnosis";

type Props = {
  tooth: string;
  enabled: boolean;
  current?: DiagnosisPatch;
  lastAction: DiagnosisAction | null;
  onCondition: (condition: DiagnosisAction) => void;
  onArchMissing: () => void;
};

export default function BaselineToothMenu({ tooth, enabled, current, lastAction, onCondition, onArchMissing }: Props) {
  return (
    <>
      <div className="clinical-chart-action-menu-hint">Diagnosis · Whole tooth</div>
      <button className="btn btn-secondary" type="button" role="menuitem"
        disabled={!enabled || !lastAction || !actionSupportsTeeth(lastAction, [tooth])}
        title="Repeats the last single-tooth condition change. Notes and arch-wide actions are not copied."
        data-testid="clinical-baseline-repeat"
        onClick={() => { if (lastAction) onCondition(lastAction); }}>
        Repeat last action{lastAction ? ` · ${diagnosisAction(lastAction).label}` : ""}
      </button>
      {diagnosisActions.map((item) => {
        const [field, value] = Object.entries(item.patch)[0] as [keyof DiagnosisPatch, string | null];
        return <button key={item.id} className="btn btn-secondary" type="button" role="menuitemradio"
          aria-checked={value !== null && current?.[field] === value}
          disabled={!enabled || !actionSupportsTeeth(item.id, [tooth])}
          title={item.id === "deciduous" ? "Deciduous teeth use positions 1–5 (A–E) only." : undefined}
          data-testid={`clinical-baseline-condition-${item.id}`} onClick={() => onCondition(item.id)}>
          <span aria-hidden="true">{item.symbol}</span> {item.label}
        </button>;
      })}
      <button className="btn btn-secondary" type="button" role="menuitem"
        disabled={!enabled} onClick={onArchMissing} data-testid="clinical-baseline-arch-missing">
        All in {tooth.startsWith("U") ? "upper" : "lower"} arch missing…
      </button>
    </>
  );
}
