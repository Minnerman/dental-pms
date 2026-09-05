export const crownKinds = [
  { value: "fractured", label: "Crown fractured" },
  { value: "missing", label: "Crown missing" },
  { value: "metal", label: "Metallic crown" },
  { value: "gold", label: "Gold crown" },
  { value: "porcelain", label: "Porcelain crown" },
  { value: "composite", label: "Composite crown" },
] as const;

export const crownIssues = [
  { value: "decayed", label: "Decayed" },
  { value: "defective", label: "Defective" },
  { value: "fractured", label: "Fractured" },
  { value: "poor_fitting", label: "Poor fitting" },
] as const;

export type CrownKind = typeof crownKinds[number]["value"];
export type CrownIssue = typeof crownIssues[number]["value"];
export type CrownObservation = { kind: CrownKind | null; issues: CrownIssue[] };

export function isMaterialCrown(kind: CrownKind | null | undefined) {
  return kind === "metal" || kind === "gold" || kind === "porcelain" || kind === "composite";
}

export function crownDiagnosisLabel(observation: CrownObservation) {
  const label = crownKinds.find((item) => item.value === observation.kind)?.label ?? "Reset crown";
  const issues = crownIssues.filter((item) => observation.issues.includes(item.value)).map((item) => item.label);
  return `${label}${issues.length ? ` · ${issues.join(", ")}` : isMaterialCrown(observation.kind) ? " · Condition not specified" : ""}`;
}

export function toggleCrownIssue(observation: CrownObservation, issue: CrownIssue): CrownObservation {
  if (!isMaterialCrown(observation.kind)) return observation;
  return { ...observation, issues: observation.issues.includes(issue)
    ? observation.issues.filter((value) => value !== issue) : [...observation.issues, issue].sort() };
}
