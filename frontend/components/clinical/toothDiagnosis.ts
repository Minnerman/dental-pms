export type ToothCondition = "present" | "missing" | "deciduous" | "implant" | "unerupted" | "impacted" | "unrecorded";
export type ToothMovement = "forward" | "backward";
export type ToothRotation = "clockwise" | "anticlockwise";
export type DiagnosisPatch = { condition?: ToothCondition | null; movement?: ToothMovement | null; rotation?: ToothRotation | null };

// One catalogue drives both the number menu and the rectangular palette.
export const diagnosisActions = [
  { id: "missing", label: "Tooth missing", patch: { condition: "missing" } },
  { id: "deciduous", label: "Deciduous tooth", patch: { condition: "deciduous" } },
  { id: "implant", label: "Implant", patch: { condition: "implant" } },
  { id: "unerupted", label: "Unerupted tooth", patch: { condition: "unerupted" } },
  { id: "impacted", label: "Impacted tooth", patch: { condition: "impacted" } },
  { id: "present", label: "Tooth present", patch: { condition: "present" } },
  { id: "movement_forward", label: "Forward · mesial", patch: { movement: "forward" } },
  { id: "movement_backward", label: "Backward · distal", patch: { movement: "backward" } },
  { id: "rotation_clockwise", label: "Clockwise rotation", patch: { rotation: "clockwise" } },
  { id: "rotation_anticlockwise", label: "Anticlockwise rotation", patch: { rotation: "anticlockwise" } },
  { id: "reset", label: "Reset the tooth", patch: { condition: "unrecorded", movement: null, rotation: null } },
] as const satisfies readonly { id: string; label: string; patch: DiagnosisPatch }[];
export type DiagnosisAction = typeof diagnosisActions[number]["id"];
export function diagnosisAction(id: DiagnosisAction) { return diagnosisActions.find((item) => item.id === id)!; }
export const toothConditionLabels: Record<ToothCondition, string> = {
  present: "Tooth present", missing: "Tooth missing", deciduous: "Deciduous tooth",
  implant: "Implant", unerupted: "Unerupted tooth", impacted: "Impacted tooth",
  unrecorded: "Current tooth observations reset · unspecified",
};
export function britishToothLabel(tooth: string, condition?: ToothCondition | null) {
  return condition === "deciduous" && /^[UL][RL][1-5]$/.test(tooth)
    ? `${tooth.slice(0, 2)}${"ABCDE"[Number(tooth[2]) - 1]}` : tooth;
}
export function actionSupportsTeeth(action: DiagnosisAction, teeth: string[]) {
  return action !== "deciduous" || teeth.every((tooth) => /^[UL][RL][1-5]$/.test(tooth));
}
