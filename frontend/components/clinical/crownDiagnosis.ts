export const crownKinds = [
  { value: "missing", label: "Crown missing" },
  { value: "metal", label: "Metallic crown" },
  { value: "gold", label: "Gold crown" },
  { value: "porcelain", label: "Porcelain crown" },
  { value: "porcelain_bonded", label: "Porcelain B. Crown" },
  { value: "composite", label: "Composite crown" },
] as const;

export const dentureKinds = [
  { value: "denture_cocr", label: "Denture Co-Cr" },
  { value: "denture_acrylic", label: "Denture Acrylic" },
] as const;
export const bridgeRoles = [
  { value: "abutment", label: "Bridge Abutment" },
  { value: "pontic", label: "Bridge Pontic" },
  { value: "wing", label: "Bridge Wing" },
] as const;
export type BridgeRole = typeof bridgeRoles[number]["value"];
export type BridgeMember = { tooth: string; role: BridgeRole };
export type BridgeGroup = { id: number; arch: "upper" | "lower"; span_start: string; span_end: string; members: BridgeMember[] };
export type BridgeDraft = { members: BridgeMember[]; crown?: CrownObservation };
export const bridgeArchTeeth = (upper: boolean) => [
  ...Array.from({ length: 8 }, (_, i) => `${upper ? "UR" : "LR"}${8 - i}`),
  ...Array.from({ length: 8 }, (_, i) => `${upper ? "UL" : "LL"}${i + 1}`),
];

export const crownIssues = [
  { value: "decayed", label: "Decayed" },
  { value: "defective", label: "Defective" },
  { value: "fractured", label: "Fractured" },
  { value: "poor_fitting", label: "Poor fitting" },
] as const;

// Retired broken-away crown observations stay readable; never reinterpret them.
export type CrownKind = typeof crownKinds[number]["value"] | typeof dentureKinds[number]["value"] | "fractured";
export type CrownIssue = typeof crownIssues[number]["value"];
export type CrownObservation = { kind: CrownKind | null; issues: CrownIssue[] };

export function isMaterialCrown(kind: CrownKind | null | undefined) {
  return kind === "metal" || kind === "gold" || kind === "porcelain" || kind === "porcelain_bonded" || kind === "composite";
}

export function isDentureCrown(kind: CrownKind | null | undefined) {
  return kind === "denture_cocr" || kind === "denture_acrylic";
}

export function crownDiagnosisLabel(observation: CrownObservation) {
  const label = [...crownKinds, ...dentureKinds].find((item) => item.value === observation.kind)?.label
    ?? (observation.kind === "fractured" ? "Crown fractured (previously recorded)" : "Reset crown");
  const issues = crownIssues.filter((item) => observation.issues.includes(item.value)).map((item) => item.label);
  return `${label}${issues.length ? ` · ${issues.join(", ")}` : isMaterialCrown(observation.kind) ? " · Condition not specified" : ""}`;
}

export function toggleCrownIssue(observation: CrownObservation, issue: CrownIssue): CrownObservation {
  if (!isMaterialCrown(observation.kind)) return observation;
  return { ...observation, issues: observation.issues.includes(issue)
    ? observation.issues.filter((value) => value !== issue) : [...observation.issues, issue].sort() };
}
