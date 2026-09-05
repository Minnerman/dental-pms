export type ToothCondition = "present" | "missing" | "deciduous" | "implant" | "unerupted" | "impacted";
export type ToothMovement = "forward" | "backward";
export type ToothRotation = "clockwise" | "anticlockwise";
export type DiagnosisPatch = { condition?: ToothCondition | null; movement?: ToothMovement | null; rotation?: ToothRotation | null };

// One catalogue drives both the number menu and the rectangular palette.
export const diagnosisActions = [
  { id: "missing", label: "Tooth missing", symbol: "×", patch: { condition: "missing" } },
  { id: "deciduous", label: "Deciduous tooth", symbol: "A–E", patch: { condition: "deciduous" } },
  { id: "implant", label: "Implant", symbol: "▤", patch: { condition: "implant" } },
  { id: "unerupted", label: "Unerupted tooth", symbol: "∿", patch: { condition: "unerupted" } },
  { id: "impacted", label: "Impacted tooth", symbol: "◩", patch: { condition: "impacted" } },
  { id: "present", label: "Tooth present", symbol: "✓", patch: { condition: "present" } },
  { id: "movement_forward", label: "Forward · mesial", symbol: "→←", patch: { movement: "forward" } },
  { id: "movement_backward", label: "Backward · distal", symbol: "←→", patch: { movement: "backward" } },
  { id: "rotation_clockwise", label: "Clockwise rotation", symbol: "↻", patch: { rotation: "clockwise" } },
  { id: "rotation_anticlockwise", label: "Anticlockwise rotation", symbol: "↺", patch: { rotation: "anticlockwise" } },
  { id: "clear_movement", label: "Clear movement", symbol: "↔", patch: { movement: null } },
  { id: "clear_rotation", label: "Clear rotation", symbol: "○", patch: { rotation: null } },
] as const satisfies readonly { id: string; label: string; symbol: string; patch: DiagnosisPatch }[];
export type DiagnosisAction = typeof diagnosisActions[number]["id"];
export function diagnosisAction(id: DiagnosisAction) { return diagnosisActions.find((item) => item.id === id)!; }
export const toothConditionLabels = Object.fromEntries(
  diagnosisActions.filter((item) => "condition" in item.patch).map((item) => [item.id, item.label])
) as Record<ToothCondition, string>;
export function britishToothLabel(tooth: string, condition?: ToothCondition | null) {
  return condition === "deciduous" && /^[UL][RL][1-5]$/.test(tooth)
    ? `${tooth.slice(0, 2)}${"ABCDE"[Number(tooth[2]) - 1]}` : tooth;
}
export function actionSupportsTeeth(action: DiagnosisAction, teeth: string[]) {
  return action !== "deciduous" || teeth.every((tooth) => /^[UL][RL][1-5]$/.test(tooth));
}
