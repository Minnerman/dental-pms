import { toothConditionLabels, type ToothCondition } from "./useToothConditions";

type Props = {
  tooth: string;
  enabled: boolean;
  current?: ToothCondition | null;
  lastAction: ToothCondition | null;
  onCondition: (condition: ToothCondition) => void;
  onArchMissing: () => void;
};

export default function BaselineToothMenu({ tooth, enabled, current, lastAction, onCondition, onArchMissing }: Props) {
  const supportsDeciduous = Number(tooth.slice(-1)) <= 5;
  const choices: ToothCondition[] = ["missing", "deciduous", "implant", "unerupted", "impacted", "present"];
  return (
    <>
      <div className="clinical-chart-action-menu-hint">Current tooth condition</div>
      <button className="btn btn-secondary" type="button" role="menuitem"
        disabled={!enabled || !lastAction || (lastAction === "deciduous" && !supportsDeciduous)}
        title="Repeats the last single-tooth condition change. Notes and arch-wide actions are not copied."
        data-testid="clinical-baseline-repeat"
        onClick={() => { if (lastAction) onCondition(lastAction); }}>
        Repeat last action{lastAction ? ` · ${toothConditionLabels[lastAction]}` : ""}
      </button>
      {choices.map((condition) => (
        <button key={condition} className="btn btn-secondary" type="button" role="menuitemradio"
          aria-checked={current === condition}
          disabled={!enabled || (condition === "deciduous" && !supportsDeciduous)}
          title={condition === "deciduous" && !supportsDeciduous ? "Deciduous teeth use positions 1–5 only." : undefined}
          data-testid={`clinical-baseline-condition-${condition}`}
          onClick={() => onCondition(condition)}>
          <span aria-hidden="true">{current === condition ? "✓" : "·"}</span> {toothConditionLabels[condition]}
        </button>
      ))}
      <button className="btn btn-secondary" type="button" role="menuitem"
        disabled={!enabled} onClick={onArchMissing} data-testid="clinical-baseline-arch-missing">
        All in {tooth.startsWith("U") ? "upper" : "lower"} arch missing…
      </button>
    </>
  );
}
