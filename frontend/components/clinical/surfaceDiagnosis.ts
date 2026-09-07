export type SurfaceKey = "M" | "O" | "I" | "D" | "B" | "P" | "L";
export const surfaceKinds = [
  { value: "carious", label: "Caries" },
  { value: "defective", label: "Defective" },
  { value: "restored", label: "Restored" },
  { value: "sealant", label: "Fissure sealant" },
] as const;
export const surfaceMaterials = [
  { value: "amalgam", label: "Amalgam", colour: "#9aa3af" },
  { value: "precious_metal", label: "Precious metal", colour: "#d2bd83" },
  { value: "carbon_fibre", label: "Carbon fibre", colour: "#626e80" },
  { value: "gold", label: "Gold", colour: "#e9c34e" },
  { value: "glass_ionomer", label: "Glass ionomer", colour: "#c8a6dc" },
  { value: "cast_metal_alloy", label: "Cast metal alloy", colour: "#a9afb9" },
  { value: "metallic", label: "Metallic", colour: "#b8c2cc" },
  { value: "porcelain", label: "Porcelain", colour: "#f0b5d0" },
  { value: "resin", label: "Composite / Resin", colour: "#85c7a0" },
  { value: "stainless_steel", label: "Stainless steel", colour: "#a8bbc6" },
  { value: "unknown", label: "Unknown material", colour: "#c1c6cb" },
  { value: "vmk", label: "VMK", colour: "#af8e7e" },
  { value: "combination", label: "Material combination", colour: "#b5abcb" },
] as const;
export const surfaceConditions = [
  { value: "sound", label: "Sound" },
  { value: "carious_early", label: "Carious · Early" },
  { value: "carious_arrested", label: "Carious · Arrested" },
  { value: "carious_established", label: "Carious · Established" },
  { value: "defective", label: "Defective" },
] as const;
export const surfaceDefects = [
  { value: "open_contact", label: "Open contact" },
  { value: "cracked", label: "Cracked" },
  { value: "broken", label: "Broken" },
  { value: "faceted", label: "Faceted" },
  { value: "overhang", label: "Overhang" },
  { value: "over_contour", label: "Over contour" },
  { value: "under_contour", label: "Under contour" },
  { value: "cosmetic", label: "Cosmetic" },
  { value: "leaking", label: "Leaking" },
] as const;
export type SurfaceKind = typeof surfaceKinds[number]["value"];
export type SurfaceMaterial = typeof surfaceMaterials[number]["value"];
export type SurfaceCondition = typeof surfaceConditions[number]["value"];
export type SurfaceDefect = typeof surfaceDefects[number]["value"];
export type SurfaceObservation = { kind: SurfaceKind | null; material: SurfaceMaterial | null; condition: SurfaceCondition | null; defects: SurfaceDefect[] };
export type SurfaceTarget = { tooth: string; surfaces: SurfaceKey[] };
export const surfaceOrder: SurfaceKey[] = ["M", "O", "I", "D", "B", "P", "L"];
export const surfaceKeysForTooth = (tooth: string): SurfaceKey[] => ["M", Number(tooth.slice(-1)) <= 3 ? "I" : "O", "D", "B", tooth.startsWith("U") ? "P" : "L"];
export const surfaceName = (surface: SurfaceKey) => ({ M: "Mesial", O: "Occlusal", I: "Incisal", D: "Distal", B: "Buccal", P: "Palatal", L: "Lingual" })[surface];
export function newSurfaceObservation(kind: SurfaceKind | null): SurfaceObservation {
  return { kind, material: kind === "restored" ? "unknown" : null, condition: kind === "restored" ? "sound" : kind === "defective" ? "defective" : null, defects: [] };
}
export function surfaceDiagnosisLabel(observation: SurfaceObservation) {
  if (observation.kind === null) return "Reset selected surfaces · unspecified";
  const kind = surfaceKinds.find((entry) => entry.value === observation.kind)?.label ?? "Surface observation";
  const material = surfaceMaterials.find((entry) => entry.value === observation.material)?.label;
  const condition = surfaceConditions.find((entry) => entry.value === observation.condition)?.label;
  const defects = surfaceDefects.filter((entry) => observation.defects.includes(entry.value)).map((entry) => entry.label);
  return [kind, material, condition ?? (observation.kind === "carious" ? "Stage unspecified" : "Condition unspecified"), ...defects].filter(Boolean).join(" · ");
}
export function surfaceSelectionLabel(targets: SurfaceTarget[]) {
  return targets.map(({ tooth, surfaces }) => `${tooth} ${surfaceOrder.filter((value) => surfaces.includes(value)).join("")}`).join(" · ");
}
export function toggleSurfaceTarget(targets: SurfaceTarget[], tooth: string, surface: SurfaceKey, includeOnly = false): SurfaceTarget[] {
  const existing = targets.find((target) => target.tooth === tooth);
  const surfaces = existing?.surfaces ?? [];
  const next = surfaces.includes(surface) ? includeOnly ? surfaces : surfaces.filter((value) => value !== surface) : [...surfaces, surface];
  return [...targets.filter((target) => target.tooth !== tooth), ...(next.length ? [{ tooth, surfaces: surfaceOrder.filter((value) => next.includes(value)) }] : [])];
}
