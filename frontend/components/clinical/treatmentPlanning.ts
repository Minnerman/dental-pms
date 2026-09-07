import type { SurfaceKey } from "./surfaceDiagnosis";
import type { DiagnosisPatch } from "./toothDiagnosis";
import { britishToothLabel } from "./toothDiagnosis";
import type { RootObservation } from "./rootDiagnosis";
import { crownKinds, dentureKinds, isMaterialCrown, type CrownKind, type CrownObservation, type BridgeGroup, type BridgeRole } from "./crownDiagnosis";
import { surfaceMaterials, type SurfaceMaterial, type SurfaceObservation } from "./surfaceDiagnosis";

export type PlanningLevel = "tooth" | "root" | "crown" | "surface";
export type PlanningSelection = { level: PlanningLevel; tooth: string; surfaces: SurfaceKey[] };
export type PlanningTarget = { level: PlanningLevel | "general"; tooth: string | null; surfaces: SurfaceKey[] };
export type PlanningDrawingKind = "extraction" | "implant" | "root_canal" | "apicectomy" | "post_core" | "crown" | "bridge" | "denture" | "filling" | "inlay_onlay" | "veneer" | "sealant" | "other";
export type PlanningMaterial = Exclude<CrownKind, "missing" | "fractured"> | SurfaceMaterial;
export type PlanningStatus = "proposed" | "accepted" | "declined" | "completed" | "cancelled";
export type PlanningFeeMode = "catalogue" | "agreed" | "override" | "waived";
export type PlanningFee = { type: "FIXED" | "RANGE" | "N_A" | "UNAVAILABLE"; amount_pence: number | null; min_amount_pence: number | null; max_amount_pence: number | null; notes: string | null; version_id?: number | null; effective_from?: string | null };
export type PlanningCatalogueItem = { id: number; code: string | null; name: string; description: string | null; default_duration_minutes: number | null; patient_category: string; level?: PlanningTarget["level"] | null; display_order?: number; fee: PlanningFee; quote_token: string };
export type PlanningCatalogue = { patient_id: number; patient_category: string; currency: "GBP"; practice_today?: string; items: PlanningCatalogueItem[]; total: number };
export type PlanningNativeRow = DiagnosisPatch & { revision: number; root_observations?: Record<string, RootObservation>; crown_observation?: CrownObservation | null; surface_observations?: Partial<Record<SurfaceKey, SurfaceObservation>>; bridge_group_id?: number | null; bridge_role?: BridgeRole | null };
export type PlanningSnapshot = {
  version: 1; captured_at: string;
  native: { patient_id: number; teeth: Record<string, PlanningNativeRow>; note_teeth: string[]; bridges?: BridgeGroup[] };
  legacy: { patient_id: number; teeth: Record<string, { missing?: boolean; extracted?: boolean; restorations?: { type: "filling" | "crown" | "bridge" | "root_canal" | "rct" | "implant" | "denture" | "veneer" | "inlay_onlay" | "post" | "extraction" | "other"; surfaces?: ("M" | "O" | "D" | "B" | "L" | "I")[] | null; meta?: Record<string, unknown> | null }[] | null }> } | null;
  coverage: { native: "captured"; legacy: "captured" | "unavailable" | "partial"; legacy_reason: string | null };
};
export type EarlierPlanningItem = { id: number; patient_id: number; tooth: string | null; surface: string | null; procedure_code: string; description: string; fee_pence: number | null; status: PlanningStatus; created_at: string; updated_at: string };
export type PlanningItem = EarlierPlanningItem & { plan_id: number; treatment_id: number | null; revision: number; target: PlanningTarget; drawing_kind: PlanningDrawingKind; material?: PlanningMaterial | null; catalogue_snapshot: { source?: "catalogue"; fee: PlanningFee; name?: string; code?: string | null; patient_category?: string } | { source: "custom" }; fee_mode: PlanningFeeMode; fee_reason: string | null; completed_procedure_id: number | null };
export type PlanningPlan = { id: number; created_at: string; created_by: unknown; snapshot: PlanningSnapshot; items: PlanningItem[] };
export type PlanningResponse = { patient_id: number; plan: PlanningPlan | null; earlier_items: EarlierPlanningItem[]; earlier_items_total: number };
export const planningDrawingChoices: { value: PlanningDrawingKind; label: string; levels: PlanningTarget["level"][] }[] = [
  { value: "extraction", label: "Extraction", levels: ["tooth"] }, { value: "implant", label: "Implant", levels: ["tooth"] },
  { value: "root_canal", label: "Root canal treatment", levels: ["root"] }, { value: "apicectomy", label: "Apicectomy", levels: ["root"] }, { value: "post_core", label: "Post and core", levels: ["root"] },
  { value: "crown", label: "Crown", levels: ["crown"] }, { value: "bridge", label: "Bridge unit", levels: ["crown"] }, { value: "denture", label: "Denture tooth", levels: ["crown"] },
  { value: "filling", label: "Filling", levels: ["surface"] }, { value: "inlay_onlay", label: "Inlay / onlay", levels: ["crown", "surface"] }, { value: "veneer", label: "Veneer", levels: ["crown"] }, { value: "sealant", label: "Fissure sealant", levels: ["surface"] },
  { value: "other", label: "Other · no specific treatment drawing", levels: ["tooth", "root", "crown", "surface", "general"] },
];
export const planningLevels: { value: PlanningLevel; label: string }[] = [
  { value: "tooth", label: "Tooth level" }, { value: "root", label: "Root level" },
  { value: "crown", label: "Crown level" }, { value: "surface", label: "Surface level" },
];

export function planningMaterialChoices(kind: PlanningDrawingKind | "", level: PlanningTarget["level"]): { value: PlanningMaterial; label: string }[] {
  if (kind === "denture") return [...dentureKinds];
  if (["crown", "bridge", "veneer"].includes(kind) || kind === "inlay_onlay" && level === "crown") return crownKinds.filter((entry) => isMaterialCrown(entry.value)).map((entry) => ({ value: entry.value as PlanningMaterial, label: entry.label }));
  if (kind === "filling" || kind === "inlay_onlay" && level === "surface") return [...surfaceMaterials];
  return [];
}

export function planningMaterialLabel(item: Pick<PlanningItem, "drawing_kind" | "material" | "target">) {
  return planningMaterialChoices(item.drawing_kind, item.target.level).find((choice) => choice.value === item.material)?.label ?? "Material not specified";
}

export function planningMoney(pence: number | null | undefined) {
  return pence == null ? "Not priced" : new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(pence / 100);
}

export function planningPence(value: string): number | null {
  if (!/^\d+(\.\d{1,2})?$/.test(value.trim())) return null;
  const pence = Math.round(Number(value.trim()) * 100);
  return Number.isSafeInteger(pence) && pence >= 0 && pence <= 100_000_000 ? pence : null;
}

export function planningRequestId() {
  return `planning-${Date.now()}-${Array.from(crypto.getRandomValues(new Uint32Array(3))).join("-")}`;
}

export function planningFeeLabel(fee: PlanningFee) {
  if (fee.type === "FIXED") return planningMoney(fee.amount_pence);
  if (fee.type === "RANGE") return `${planningMoney(fee.min_amount_pence)}–${planningMoney(fee.max_amount_pence)}`;
  return fee.type === "N_A" ? "No applicable catalogue fee" : "No catalogue fee recorded";
}
export function planningFeeDateLabel(date: string | null | undefined) {
  if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
  const parsed = new Date(`${date}T12:00:00Z`);
  return Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== date ? null : parsed.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}
export function planningToothLabel(tooth: string, snapshot?: PlanningSnapshot) {
  const row = snapshot?.native.teeth[tooth];
  const label = britishToothLabel(tooth, row?.condition, row?.dentition);
  return label === tooth ? tooth : `${label} (chart position ${tooth})`;
}
export function planningTargetLabel(target: PlanningTarget, snapshot?: PlanningSnapshot) {
  return target.level === "general" ? "General treatment" : `${target.tooth ? planningToothLabel(target.tooth, snapshot) : "Select tooth"} · ${target.level}${target.surfaces.length ? ` · ${target.surfaces.join("")}` : ""}`;
}
export function planningFeeError(fee: PlanningFee, mode: PlanningFeeMode, amount: string, reason: string) {
  if (mode === "catalogue") return fee.type === "FIXED" && fee.amount_pence != null ? null : "Choose an agreed fee or an explicit waiver.";
  if (mode === "waived") return reason.trim() ? null : "Enter the reason for waiving this fee.";
  const pence = planningPence(amount);
  if (pence === null) return "Enter a valid fee in pounds with no more than two decimal places.";
  if (pence === 0) return "Use Waive fee and record a reason for a zero charge.";
  if (mode === "override") return reason.trim() ? null : "Enter the reason for overriding the fee.";
  if (fee.type === "FIXED") return "Use the catalogue fee or select Override fee.";
  if (fee.type === "RANGE" && (fee.min_amount_pence == null || fee.max_amount_pence == null || pence < fee.min_amount_pence || pence > fee.max_amount_pence)) return "This amount is outside the quoted range. Choose Override fee and record a reason.";
  if (fee.type !== "RANGE" && !reason.trim()) return "Enter a reason for the agreed fee where no catalogue price is available.";
  return null;
}

export function planningCustomFeeError(mode: PlanningFeeMode, amount: string, reason: string) {
  if (mode === "waived") return reason.trim() ? null : "Enter the reason for waiving this fee.";
  if (mode !== "agreed") return "Enter an agreed fee or explicitly waive it.";
  const pence = planningPence(amount);
  if (pence === null) return "Enter a valid fee in pounds with no more than two decimal places.";
  return pence === 0 ? "Select Waive fee and record a reason for a zero charge." : null;
}
