export const rootConditions = [
  { value: "filled_sound", label: "Filled sound" },
  { value: "filled_defective", label: "Filled defective" },
  { value: "post_core_sound", label: "Post & core sound" },
  { value: "post_core_defective", label: "Post & core defective" },
] as const;

export type RootCondition = typeof rootConditions[number]["value"];
export type RootObservation = { condition: RootCondition | null; apicectomy: boolean };
export type RootPatch = Partial<RootObservation>;

export const rootDiagnosisActions = [
  ...rootConditions.map(({ value, label }) => ({ id: value, label, patch: { condition: value } as RootPatch })),
  { id: "apicectomy", label: "Apicectomy", patch: { apicectomy: true } as RootPatch },
  { id: "reset", label: "Reset root area", patch: { condition: null, apicectomy: false } as RootPatch },
] as const;
export type RootDiagnosisAction = typeof rootDiagnosisActions[number]["id"];
export function rootDiagnosisAction(action: RootDiagnosisAction) {
  return rootDiagnosisActions.find((item) => item.id === action)!;
}

// Older native maps may contain different findings. Do not label those as one
// uniform finding until the clinician explicitly applies a whole-area change.
export function rootAreaSummary(tooth: string, deciduous: boolean, roots: Record<string, RootObservation> = {}) {
  const position = Number(tooth.slice(-1));
  const upper = tooth.startsWith("U");
  const count = deciduous ? position >= 4 ? upper ? 3 : 2 : 1
    : position >= 6 ? upper ? 3 : 2 : upper && position === 4 ? 2 : 1;
  const entries = Array.from({ length: count }, (_, index) => roots[String(index + 1)] ?? { condition: null, apicectomy: false });
  const condition = entries.every((entry) => entry.condition === entries[0].condition) ? entries[0].condition : undefined;
  const apicectomy = entries.every((entry) => entry.apicectomy);
  const apicectomyMixed = entries.some((entry) => entry.apicectomy !== entries[0].apicectomy);
  return { condition, apicectomy, apicectomyMixed, mixed: condition === undefined || apicectomyMixed };
}

export function rootConditionLabel(condition: RootCondition | null | undefined) {
  return rootConditions.find((item) => item.value === condition)?.label ?? "Unspecified";
}
