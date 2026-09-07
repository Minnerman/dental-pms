"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiFetch } from "@/lib/auth";
import type { OdontogramBaselineCondition } from "./OdontogramToothSvg";
import { diagnosisAction, type DiagnosisAction, type DiagnosisPatch, type ToothCondition } from "./toothDiagnosis";
import { rootConditionLabel, type RootObservation, type RootPatch } from "./rootDiagnosis";
import { crownDiagnosisLabel, type CrownObservation, type BridgeRole, type BridgeGroup, type BridgeDraft } from "./crownDiagnosis";
import { surfaceDiagnosisLabel, surfaceSelectionLabel, type SurfaceKey, type SurfaceObservation, type SurfaceTarget } from "./surfaceDiagnosis";
import { projectCurrentCompletedTooth, type CompletedPlanningEffect, type PlanningLegacyTooth, type ToothObservationEvents } from "./planningAppearance";
export { toothConditionLabels, type ToothCondition } from "./toothDiagnosis";

type ConditionRow = DiagnosisPatch & {
  condition: ToothCondition | null;
  revision: number;
  root_observations?: Record<string, RootObservation>;
  crown_observation?: CrownObservation | null;
  surface_observations?: Partial<Record<SurfaceKey, SurfaceObservation>>;
  bridge_group_id?: number | null;
  bridge_role?: BridgeRole | null;
  updated_at: string;
  updated_by: { id: number; email: string; role: string } | null;
};
type ConditionChart = {
  patient_id: number;
  teeth: Record<string, ConditionRow>;
  note_teeth: string[];
  bridges?: BridgeGroup[];
  completed_effects?: CompletedPlanningEffect[];
  observation_events?: Record<string, ToothObservationEvents>;
  projection_revision?: number;
  projection_coverage?: { status: "available" | "unavailable"; reason: string | null };
};

export function baselineGlyph(row?: DiagnosisPatch): OdontogramBaselineCondition | undefined {
  if (!row || (!row.condition && !row.dentition && !row.movement && !row.rotation)) return undefined;
  const { condition, dentition, movement, rotation } = row;
  return {
    ...(condition ? { status: condition === "deciduous" ? "present" as const : condition } : {}),
    dentition: dentition ?? (condition === "deciduous" ? "deciduous" : undefined),
    movement, rotation,
  };
}

function requestId() {
  // getRandomValues also works on the practice's HTTP origin.
  return `tooth-${Date.now()}-${Array.from(crypto.getRandomValues(new Uint32Array(3))).join("-")}`;
}

export function useToothConditions(patientId: string, enabled: boolean, writable: boolean) {
  const [chart, setChart] = useState<ConditionChart | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [lastAction, setLastAction] = useState<DiagnosisAction | null>(null);
  const currentPatient = useRef(patientId);
  currentPatient.current = patientId;
  const generation = useRef(0);
  const saveLock = useRef<symbol | null>(null);
  const endpoint = `/api/patients/${patientId}/clinical/tooth-conditions`;

  const load = useCallback(async () => {
    if (!enabled || saveLock.current) return;
    const ticket = ++generation.current;
    setLoading(true);
    setError(null);
    try {
      const response = await apiFetch(endpoint);
      if (!response.ok) throw new Error("Current tooth conditions could not be loaded. Refresh before editing.");
      const data = await response.json() as ConditionChart;
      if (ticket === generation.current && currentPatient.current === patientId) setChart(data);
    } catch (cause) {
      if (ticket === generation.current) {
        // Keep last-known observations visible on a failed refresh. The error
        // blocks edits; silently redrawing absent teeth as natural is unsafe.
        setError(cause instanceof Error ? cause.message : "Current tooth conditions are unavailable.");
      }
    } finally {
      if (ticket === generation.current) setLoading(false);
    }
  }, [enabled, endpoint, patientId]);

  useEffect(() => {
    setChart(null);
    setLastAction(null);
    setNotice(null);
    setError(null);
    setSaving(false);
    saveLock.current = null;
    return () => { generation.current += 1; saveLock.current = null; };
  }, [patientId]);

  useEffect(() => {
    if (!enabled) {
      generation.current += 1;
      // A tab switch hides data via currentChart, but must not release a
      // pending save. Its response reconciles the same patient's chart.
      setLoading(false);
      setLastAction(null);
      setNotice(null);
      setError(null);
      return;
    }
    void load();
  }, [enabled, load]);

  const currentChart = enabled && chart?.patient_id === Number(patientId) ? chart : null;
  const projectionError = currentChart?.projection_coverage?.status === "unavailable"
    ? "Completed treatment appearances could not be verified. Current chart editing is paused; refresh and review the treatment history." : null;
  const canSave = enabled && writable && Boolean(currentChart) && !loading && !saving && !error && !projectionError;
  const appearanceForTooth = (tooth: string, legacy?: PlanningLegacyTooth) => projectCurrentCompletedTooth(
    tooth, Number(patientId), currentChart?.teeth[tooth], legacy,
    currentChart?.completed_effects ?? [], currentChart?.observation_events?.[tooth],
  );
  const visibleAppearances = useMemo(() => {
    if (!currentChart) return {};
    const teeth = new Set([...Object.keys(currentChart.teeth), ...(currentChart.completed_effects ?? []).flatMap((effect) => effect.target.tooth ? [effect.target.tooth] : [])]);
    return Object.fromEntries([...teeth].map((tooth) => [tooth, projectCurrentCompletedTooth(
      tooth, Number(patientId), currentChart.teeth[tooth], undefined, currentChart.completed_effects ?? [], currentChart.observation_events?.[tooth],
    )]));
  }, [currentChart, patientId]);
  const visibleTeeth = Object.fromEntries(Object.entries(visibleAppearances).map(([tooth, appearance]) => [tooth, appearance.row]));
  // A removed bridge member must not leave a line through an absent tooth.
  // Keep raw group identity for the explicit whole-bridge correction workflow.
  const visibleBridges = (currentChart?.bridges ?? []).filter((bridge) => bridge.members.every((member) => visibleTeeth[member.tooth]?.bridge_group_id === bridge.id));

  const saveObservation = async (
    path: string, payload: Record<string, unknown>, message: string, rememberAction?: DiagnosisAction
  ) => {
    if (!canSave || !currentChart || saveLock.current) return false;
    const operation = Symbol("tooth-condition-save");
    saveLock.current = operation;
    generation.current += 1; // An earlier refresh must not overwrite this mutation.
    setSaving(true);
    setNotice(null);
    setError(null);
    try {
      const response = await apiFetch(path, {
        method: "POST",
        headers: { "Request-Id": requestId() },
        body: JSON.stringify({ ...payload, ...(currentChart.projection_revision == null ? {} : { expected_projection_revision: currentChart.projection_revision }) }),
      });
      if (!response.ok) {
        if (response.status === 409) throw new Error("The tooth chart changed elsewhere. Refresh and review it before trying again.");
        if (response.status === 403) throw new Error("You do not have permission to change current tooth conditions.");
        if (response.status === 422) throw new Error("This condition is not valid for the selection. Review tooth and root findings; bridge units must be changed or reset as a whole group before changing their anatomy.");
        throw new Error("The change could not be confirmed. Refresh the chart before trying again.");
      }
      const data = await response.json() as ConditionChart;
      if (currentPatient.current !== patientId || saveLock.current !== operation) return false;
      generation.current += 1;
      setLoading(false);
      setChart(data);
      if (rememberAction) setLastAction(rememberAction);
      setNotice(`${message} saved. Notes and history retained.`);
      return true;
    } catch (cause) {
      if (currentPatient.current === patientId && saveLock.current === operation) {
        setError(cause instanceof Error ? cause.message : "Current condition could not be saved.");
      }
      return false;
    } finally {
      if (saveLock.current === operation) {
        saveLock.current = null;
        setSaving(false);
      }
    }
  };

  const saveAction = (teeth: string[], action: DiagnosisAction, remember = true) =>
    saveObservation(endpoint, {
      teeth, ...diagnosisAction(action).patch,
      expected_revisions: Object.fromEntries(teeth.map((tooth) => [tooth, currentChart?.teeth[tooth]?.revision ?? 0])),
    }, `${teeth.length === 1 ? teeth[0] : `${teeth.length} teeth`} · ${diagnosisAction(action).label}`,
    remember ? action : undefined);

  const saveRoots = (teeth: string[], patch: RootPatch) =>
    saveObservation(`/api/patients/${patientId}/clinical/root-conditions`, {
      teeth, ...patch,
      expected_revisions: Object.fromEntries(teeth.map((tooth) => [tooth, currentChart?.teeth[tooth]?.revision ?? 0])),
    }, `${teeth.length === 1 ? teeth[0] : `${teeth.length} teeth`} · Whole root area · ${"condition" in patch ? rootConditionLabel(patch.condition) : patch.apicectomy ? "Apicectomy" : "Apicectomy marker removed"}`);

  const saveCrowns = (teeth: string[], observation: CrownObservation) =>
    saveObservation(`/api/patients/${patientId}/clinical/crown-conditions`, {
      teeth, ...observation,
      expected_revisions: Object.fromEntries(teeth.map((tooth) => [tooth, currentChart?.teeth[tooth]?.revision ?? 0])),
    }, `${teeth.length === 1 ? teeth[0] : `${teeth.length} teeth`} · ${crownDiagnosisLabel(observation)}`);

  const saveSurfaces = (targets: SurfaceTarget[], observation: SurfaceObservation) =>
    saveObservation(`/api/patients/${patientId}/clinical/surface-conditions`, {
      targets, observation,
      expected_revisions: Object.fromEntries(targets.map(({ tooth }) => [tooth, currentChart?.teeth[tooth]?.revision ?? 0])),
    }, `${surfaceSelectionLabel(targets)} · ${surfaceDiagnosisLabel(observation)}`);

  const saveBridge = (draft: BridgeDraft) => saveObservation(`/api/patients/${patientId}/clinical/bridges`, {
    ...draft,
    expected_revisions: Object.fromEntries(draft.members.map(({ tooth }) => [tooth, currentChart?.teeth[tooth]?.revision ?? 0])),
  }, "Bridge");

  const resetBridge = (bridge: BridgeGroup) => saveObservation(`/api/patients/${patientId}/clinical/bridges/${bridge.id}/reset`, {
    expected_revisions: Object.fromEntries(bridge.members.map(({ tooth }) => [tooth, currentChart?.teeth[tooth]?.revision ?? 0])),
  }, "Whole bridge reset");

  return {
    teeth: visibleTeeth,
    recordedTeeth: currentChart?.teeth ?? {},
    appearanceForTooth,
    noteTeeth: new Set(currentChart?.note_teeth ?? []),
    bridges: visibleBridges,
    recordedBridges: currentChart?.bridges ?? [],
    completedEffectsCount: currentChart?.completed_effects?.length ?? 0,
    hasUnappliedCompletions: Object.values(visibleAppearances).some((appearance) => appearance.unappliedCompletionIds.length > 0),
    projectionRevision: currentChart?.projection_revision,
    loading, saving, error: error || projectionError, notice, lastAction, canSave, load, saveAction, saveRoots, saveCrowns, saveSurfaces, saveBridge, resetBridge,
    save: (teeth: string[], condition: Exclude<ToothCondition, "unrecorded" | "present">) => saveAction(teeth, condition, teeth.length === 1),
  };
}
