"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/auth";
import type { OdontogramBaselineCondition } from "./OdontogramToothSvg";
import { diagnosisAction, type DiagnosisAction, type DiagnosisPatch, type ToothCondition } from "./toothDiagnosis";
export { toothConditionLabels, type ToothCondition } from "./toothDiagnosis";

type ConditionRow = DiagnosisPatch & {
  condition: ToothCondition | null;
  revision: number;
  updated_at: string;
  updated_by: { id: number; email: string; role: string } | null;
};
type ConditionChart = {
  patient_id: number;
  teeth: Record<string, ConditionRow>;
  note_teeth: string[];
};

export function baselineGlyph(row?: DiagnosisPatch): OdontogramBaselineCondition | undefined {
  if (!row || (!row.condition && !row.movement && !row.rotation)) return undefined;
  const { condition, movement, rotation } = row;
  return {
    ...(condition ? condition === "deciduous"
      ? { status: "present" as const, dentition: "deciduous" as const }
      : { status: condition, dentition: "permanent" as const } : {}),
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
  const canSave = enabled && writable && Boolean(currentChart) && !loading && !saving && !error;

  const saveAction = async (teeth: string[], action: DiagnosisAction, remember = true) => {
    if (!canSave || !currentChart || saveLock.current) return false;
    const operation = Symbol("tooth-condition-save");
    saveLock.current = operation;
    generation.current += 1; // An earlier refresh must not overwrite this mutation.
    setSaving(true);
    setNotice(null);
    setError(null);
    try {
      const response = await apiFetch(endpoint, {
        method: "POST",
        headers: { "Request-Id": requestId() },
        body: JSON.stringify({
          teeth,
          ...diagnosisAction(action).patch,
          expected_revisions: Object.fromEntries(teeth.map((tooth) => [tooth, currentChart.teeth[tooth]?.revision ?? 0])),
        }),
      });
      if (!response.ok) {
        if (response.status === 409) throw new Error("The tooth chart changed elsewhere. Refresh and review it before trying again.");
        if (response.status === 403) throw new Error("You do not have permission to change current tooth conditions.");
        if (response.status === 422) throw new Error("This condition is not valid for the selected tooth. Refresh and check the selection.");
        throw new Error("The change could not be confirmed. Refresh the chart before trying again.");
      }
      const data = await response.json() as ConditionChart;
      if (currentPatient.current !== patientId || saveLock.current !== operation) return false;
      generation.current += 1;
      setLoading(false);
      setChart(data);
      if (remember) setLastAction(action);
      setNotice(`${teeth.length === 1 ? teeth[0] : `${teeth.length} teeth`} · ${diagnosisAction(action).label} saved. Notes and history retained.`);
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

  return {
    teeth: currentChart?.teeth ?? {},
    noteTeeth: new Set(currentChart?.note_teeth ?? []),
    loading, saving, error, notice, lastAction, canSave, load, saveAction,
    save: (teeth: string[], condition: ToothCondition) => saveAction(teeth, condition, teeth.length === 1),
  };
}
