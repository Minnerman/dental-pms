import { bridgeArchTeeth, isDentureCrown, isMaterialCrown, type CrownKind, type BridgeRole } from "./crownDiagnosis";
import type { BridgeConnection } from "./BridgeConnections";
import { getToothAnatomy } from "./toothAnatomy";
import { surfaceKeysForTooth, surfaceMaterials, type SurfaceMaterial } from "./surfaceDiagnosis";
import type { OdontogramToothRestoration } from "./OdontogramToothSvg";
import { planningApplianceError, planningTargetTeeth, type PlanningAppliance, type PlanningItem, type PlanningMaterial, type PlanningNativeRow, type PlanningTarget, type PlanningDrawingKind } from "./treatmentPlanning";

export type PlanningLegacyTooth = { missing?: boolean; extracted?: boolean; restorations: OdontogramToothRestoration[] };
export type PlanningAppearance = {
  row: PlanningNativeRow;
  legacy: PlanningLegacyTooth;
  completionIds: number[];
  projectedItemIds: number[];
  unappliedCompletionIds: number[];
  replacementCompletionId: number | null;
  applianceItemId: number | null;
};
export type CompletedPlanningEffect = {
  item_id: number; procedure_id: number; completed_at: string | null; event_id: number;
  target: PlanningTarget; drawing_kind: PlanningDrawingKind; material?: PlanningMaterial | null;
  appliance?: PlanningAppliance | null;
};
export type ToothObservationEvents = Partial<Record<"anatomy" | "appliance" | "crown" | "root_condition" | "apicectomy" | "dentition" | "movement" | "rotation", number>>
  & { surfaces?: Partial<Record<import("./surfaceDiagnosis").SurfaceKey, number>> };
type ProjectionItem = Pick<PlanningItem, "id" | "patient_id" | "target" | "status" | "completed_procedure_id" | "drawing_kind" | "material" | "appliance">;
type ProjectionMask = { crown: boolean; appliance: boolean; root_condition: boolean; apicectomy: boolean; dentition: boolean; movement: boolean; rotation: boolean; surfaces: Set<string> };
type ProjectionOptions = { masks?: Map<number, ProjectionMask>; order?: Map<number, number> };

/** Pure view projection, not a new diagnosis. The source row and saved items
 * remain untouched. Re-folding only active completions makes Uncomplete restore
 * the prior appearance, including any earlier still-completed treatment. */
export function projectCompletedPlanningTooth(
  tooth: string, patientId: number, source: PlanningNativeRow | undefined,
  sourceLegacy: PlanningLegacyTooth | undefined, items: ProjectionItem[], options: ProjectionOptions = {},
): PlanningAppearance {
  const row: PlanningNativeRow = { ...source, revision: source?.revision ?? 0,
    root_observations: Object.fromEntries(Object.entries(source?.root_observations ?? {}).map(([key, value]) => [key, { ...value }])),
    crown_observation: source?.crown_observation ? { ...source.crown_observation, issues: [...source.crown_observation.issues] } : null,
    surface_observations: Object.fromEntries(Object.entries(source?.surface_observations ?? {}).map(([key, value]) => [key, value ? { ...value, defects: [...value.defects] } : value])),
  };
  const result: PlanningAppearance = { row,
    legacy: { ...sourceLegacy, restorations: [...sourceLegacy?.restorations ?? []] },
    completionIds: [], projectedItemIds: [], unappliedCompletionIds: [], replacementCompletionId: null, applianceItemId: null };
  const completed = items.filter((item) => item.patient_id === patientId && planningTargetTeeth(item).includes(tooth)
    && item.status === "completed" && Number.isSafeInteger(item.completed_procedure_id) && item.completed_procedure_id! > 0)
    .sort((a, b) => (options.order?.get(a.id) ?? a.completed_procedure_id!) - (options.order?.get(b.id) ?? b.completed_procedure_id!) || a.id - b.id);

  const artificial = () => isDentureCrown(row.crown_observation?.kind) || row.bridge_role === "pontic";
  const legacyHas = (kind: string) => result.legacy.restorations.some((entry) => entry.type === kind);
  const rootEvidence = () => Object.keys(row.root_observations ?? {}).length > 0;
  const crownEvidence = () => row.crown_observation != null;
  const legacyAbsent = (surfaceEvidence = false) => !row.condition && !rootEvidence() && !crownEvidence()
    && !(surfaceEvidence && Object.keys(row.surface_observations ?? {}).length)
    && (result.legacy.missing || result.legacy.extracted || legacyHas("extraction"));
  const implant = () => row.condition === "implant" || !["present", "unrecorded", "impacted", "deciduous"].includes(row.condition ?? "")
    && row.dentition !== "deciduous" && !rootEvidence() && legacyHas("implant");
  const available = (surfaceEvidence = false) => !["missing", "unerupted"].includes(row.condition ?? "") && !legacyAbsent(surfaceEvidence);
  const natural = (surfaceEvidence = false) => available(surfaceEvidence) && !implant() && !artificial() && !legacyHas("denture");
  const record = (item: ProjectionItem) => {
    result.completionIds.push(item.completed_procedure_id!);
    result.projectedItemIds.push(item.id);
  };

  for (const item of completed) {
    const kind = item.drawing_kind;
    const mask = options.masks?.get(item.id);
    const allow = (field: Exclude<keyof ProjectionMask, "surfaces">) => mask?.[field] ?? true;
    const allowSurface = (surface: string) => !mask || mask.surfaces.has(surface);
    const clearReplacedFields = () => {
      if (allow("movement")) row.movement = null;
      if (allow("rotation")) row.rotation = null;
      if (allow("root_condition") && allow("apicectomy")) row.root_observations = {};
      else row.root_observations = Object.fromEntries(Object.entries(row.root_observations ?? {}).map(([key, value]) =>
        [key, { condition: allow("root_condition") ? null : value.condition, apicectomy: allow("apicectomy") ? false : value.apicectomy }]));
      if (allow("crown")) { row.crown_observation = null; row.bridge_role = null; row.bridge_group_id = null; }
      result.applianceItemId = null;
      row.surface_observations = Object.fromEntries(Object.entries(row.surface_observations ?? {}).filter(([surface]) => !allowSurface(surface)));
      result.legacy = { missing: false, extracted: false, restorations: [] };
      result.replacementCompletionId = item.completed_procedure_id!;
    };
    if (item.appliance) {
      // A group is one treatment, expanded only for display. Native bridge IDs
      // stay null so this projection can never target a native reset endpoint.
      const member = item.appliance.members.find((entry) => entry.tooth === tooth);
      if (!member || planningApplianceError(item.appliance) || item.appliance.kind !== kind || !allow("appliance")) continue;
      if (row.condition === "unerupted") { result.unappliedCompletionIds.push(item.completed_procedure_id!); continue; }
      if (member.role === "denture" || member.role === "pontic") {
        if (member.role === "denture" && !isDentureCrown(item.material as CrownKind)) {
          result.unappliedCompletionIds.push(item.completed_procedure_id!); continue;
        }
        clearReplacedFields();
        if (allow("crown")) row.crown_observation = { kind: member.role === "denture" ? item.material as CrownKind
          : isMaterialCrown(item.material as CrownKind) ? item.material as CrownKind : null, issues: [] };
        row.bridge_role = member.role === "pontic" ? "pontic" : null;
      } else if (available() && row.condition !== "impacted" && !artificial()
          && !(member.role === "wing" && implant())
          && !(!row.condition && !rootEvidence() && !crownEvidence() && legacyHas("denture"))) {
        // A wing is a retainer beside its existing support crown, not an
        // instruction to replace that crown with the appliance material.
        if (member.role === "abutment" && allow("crown")) row.crown_observation = { kind: isMaterialCrown(item.material as CrownKind) ? item.material as CrownKind : null, issues: [] };
        row.bridge_role = member.role;
        row.bridge_group_id = null;
      } else { result.unappliedCompletionIds.push(item.completed_procedure_id!); continue; }
      result.applianceItemId = item.id;
      record(item);
    } else if ((kind === "extraction" || kind === "implant") && item.target.level === "tooth") {
      row.condition = kind === "extraction" ? "missing" : "implant";
      if (kind === "implant" && allow("dentition")) row.dentition = "permanent";
      clearReplacedFields();
      record(item);
    } else if (["root_canal", "post_core", "apicectomy"].includes(kind) && item.target.level === "root" && natural()
        && allow(kind === "apicectomy" ? "apicectomy" : "root_condition")) {
      const deciduous = row.dentition === "deciduous" || row.condition === "deciduous";
      row.root_observations = Object.fromEntries(getToothAnatomy(tooth, deciduous ? "deciduous" : undefined).roots.map((_, index) => {
        const prior = row.root_observations?.[String(index + 1)] ?? { condition: null, apicectomy: false };
        return [String(index + 1), kind === "apicectomy" ? { ...prior, apicectomy: true }
          : { ...prior, condition: kind === "root_canal" ? "filled_sound" : "post_core_sound" }];
      }));
      record(item);
    } else if (kind === "denture" && item.target.level === "crown" && row.condition !== "unerupted"
        && allow("crown") && isDentureCrown(item.material as CrownKind)) {
      clearReplacedFields();
      row.crown_observation = { kind: item.material as CrownKind, issues: [] };
      record(item);
    } else if ((["crown", "bridge", "veneer"].includes(kind) || kind === "inlay_onlay")
        && item.target.level === "crown" && (available() || row.bridge_role === "pontic" && row.condition !== "unerupted")
        && allow("crown") && !isDentureCrown(row.crown_observation?.kind) && !legacyHas("denture")) {
      // An unspecified material is neutral, never guessed from name or price.
      row.crown_observation = { kind: isMaterialCrown(item.material as CrownKind) ? item.material as CrownKind : null, issues: [] };
      record(item);
    } else if (["filling", "inlay_onlay", "sealant"].includes(kind) && item.target.level === "surface"
        && natural(true) && row.crown_observation?.kind !== "fractured") {
      const targets = item.target.surfaces.filter((surface) => surfaceKeysForTooth(tooth).includes(surface) && allowSurface(surface));
      if (!targets.length) continue;
      const material = surfaceMaterials.some((entry) => entry.value === item.material) ? item.material as SurfaceMaterial : null;
      for (const surface of targets) row.surface_observations![surface] = { kind: kind === "sealant" ? "sealant" : "restored",
        material: kind === "sealant" ? null : material, condition: "sound", defects: [] };
      record(item);
    }
    const fieldAllowed = item.target.level === "tooth" || item.target.level === "root" && allow(kind === "apicectomy" ? "apicectomy" : "root_condition")
      || item.target.level === "crown" && allow("crown") || item.target.level === "surface" && item.target.surfaces.some(allowSurface);
    if (kind !== "other" && fieldAllowed && !result.projectedItemIds.includes(item.id)) result.unappliedCompletionIds.push(item.completed_procedure_id!);
  }
  return result;
}

/** Current view uses audit order and masks explicitly re-recorded fields. A
 * later movement/primary-identity change cannot resurrect an extracted tooth;
 * a later whole-tooth condition/reset intentionally supersedes older effects. */
export function projectCurrentCompletedTooth(
  tooth: string, patientId: number, source: PlanningNativeRow | undefined, legacy: PlanningLegacyTooth | undefined,
  effects: CompletedPlanningEffect[], events: ToothObservationEvents = {},
): PlanningAppearance {
  const active = effects.filter((effect) => planningTargetTeeth(effect).includes(tooth) && Number.isSafeInteger(effect.event_id)
    && effect.event_id > (events.anatomy ?? 0));
  const order = new Map(active.map((effect) => [effect.item_id, effect.event_id]));
  const masks = new Map(active.map((effect) => [effect.item_id, {
    appliance: effect.event_id > (events.appliance ?? 0),
    crown: effect.event_id > (events.crown ?? 0), root_condition: effect.event_id > (events.root_condition ?? 0),
    apicectomy: effect.event_id > (events.apicectomy ?? 0), dentition: effect.event_id > (events.dentition ?? 0),
    movement: effect.event_id > (events.movement ?? 0), rotation: effect.event_id > (events.rotation ?? 0),
    surfaces: new Set(surfaceKeysForTooth(tooth).filter((surface) => effect.event_id > (events.surfaces?.[surface] ?? 0))),
  }]));
  return projectCompletedPlanningTooth(tooth, patientId, source, legacy, active.map((effect) => ({
    id: effect.item_id, patient_id: patientId, status: "completed", completed_procedure_id: effect.procedure_id,
    target: effect.target, drawing_kind: effect.drawing_kind, material: effect.material, appliance: effect.appliance,
  })), { masks, order });
}

/** Display-only namespace: never expose a completed appliance as a native
 * bridge record that could be passed to the diagnosis bridge-reset endpoint. */
export function planningApplianceConnections(
  items: { id: number; appliance?: PlanningAppliance | null; status: string }[],
  appearances: Record<string, PlanningAppearance>, includePlanned = true,
): BridgeConnection[] {
  return items.flatMap((item) => {
    const appliance = item.appliance;
    if (!appliance || appliance.kind !== "bridge" || planningApplianceError(appliance)) return [];
    const completed = item.status === "completed";
    if (!completed && (!includePlanned || !["proposed", "accepted"].includes(item.status))) return [];
    if (completed && !appliance.members.every((member) => appearances[member.tooth]?.applianceItemId === item.id)) return [];
    const arch = bridgeArchTeeth(appliance.arch === "upper");
    const members = [...appliance.members].sort((a, b) => arch.indexOf(a.tooth) - arch.indexOf(b.tooth));
    return [{ id: `planning-${item.id}`, arch: appliance.arch,
      span_start: members[0].tooth, span_end: members[members.length - 1].tooth,
      members: members.map((member) => ({ tooth: member.tooth, role: member.role as BridgeRole })),
      planningStatus: completed ? "completed" as const : "planned" as const, planningItemId: item.id }];
  });
}
