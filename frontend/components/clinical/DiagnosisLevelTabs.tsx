import type { KeyboardEvent } from "react";

export type DiagnosisLevel = "tooth" | "root" | "crown" | "surface";
const levels = [
  { id: "tooth", label: "Tooth level" },
  { id: "root", label: "Root level" },
  { id: "crown", label: "Crown level" },
  { id: "surface", label: "Surface level" },
] as const;

export default function DiagnosisLevelTabs({ value, disabled, onChange }: {
  value: DiagnosisLevel; disabled: boolean; onChange: (level: DiagnosisLevel) => void;
}) {
  function move(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    event.stopPropagation();
    const next = event.key === "ArrowRight" ? (index + 1) % levels.length
      : event.key === "ArrowLeft" ? (index + levels.length - 1) % levels.length
      : event.key === "Home" ? 0 : event.key === "End" ? levels.length - 1 : null;
    if (next === null || disabled) return;
    event.preventDefault();
    onChange(levels[next].id);
    event.currentTarget.parentElement?.querySelector<HTMLButtonElement>(`#diagnosis-level-${levels[next].id}`)?.focus();
  }
  return <div className="clinical-diagnosis-levels" data-testid="clinical-diagnosis-levels"
    role="tablist" aria-label="Diagnosis level">
    {levels.map((level, index) => <button key={level.id} type="button" role="tab"
      id={`diagnosis-level-${level.id}`} data-testid={`diagnosis-level-${level.id}`}
      aria-selected={value === level.id} aria-controls="clinical-diagnosis-panel"
      tabIndex={value === level.id ? 0 : -1} disabled={disabled}
      onClick={() => onChange(level.id)} onKeyDown={(event) => move(event, index)}>
      {level.label}
    </button>)}
  </div>;
}
