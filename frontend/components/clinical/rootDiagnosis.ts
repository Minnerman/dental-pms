export const rootConditions = [
  { value: "filled_sound", label: "Filled sound" },
  { value: "filled_defective", label: "Filled defective" },
  { value: "post_core_sound", label: "Post & core sound" },
  { value: "post_core_defective", label: "Post & core defective" },
] as const;

export type RootCondition = typeof rootConditions[number]["value"];
export type RootObservation = { condition: RootCondition | null; apicectomy: boolean };
export type RootPatch = Partial<RootObservation>;

export function rootConditionLabel(condition: RootCondition | null | undefined) {
  return rootConditions.find((item) => item.value === condition)?.label ?? "Unspecified";
}
