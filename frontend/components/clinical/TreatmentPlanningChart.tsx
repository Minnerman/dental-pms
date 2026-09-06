"use client";

import { useMemo, type KeyboardEvent, type MouseEvent } from "react";
import { fdiToChartToothKey } from "@/lib/charting/fdiToChartToothKey";
import type { R4SurfaceKey } from "@/lib/charting/r4SurfaceCodeToSurfaceKey";
import BridgeConnections from "./BridgeConnections";
import { bridgeArchTeeth } from "./crownDiagnosis";
import OdontogramToothSvg, { getOdontogramToothType, type OdontogramPlannedOverlay, type OdontogramToothRestoration } from "./OdontogramToothSvg";
import { surfaceOrder, type SurfaceKey } from "./surfaceDiagnosis";
import { britishToothLabel } from "./toothDiagnosis";
import { baselineGlyph } from "./useToothConditions";
import type { PlanningItem, PlanningLevel, PlanningSelection, PlanningSnapshot } from "./treatmentPlanning";
import styles from "./TreatmentPlanningChart.module.css";

export type PlanningChartEvent = MouseEvent<SVGElement | HTMLButtonElement> | KeyboardEvent<SVGElement | HTMLButtonElement>;
type Props = {
  snapshot: PlanningSnapshot;
  items: PlanningItem[];
  level: PlanningLevel;
  selection: PlanningSelection | null;
  disabled: boolean;
  onSelect: (selection: PlanningSelection, event: PlanningChartEvent, context?: boolean) => void;
  onOpenToothNotes?: (tooth: string, event: MouseEvent<SVGElement> | KeyboardEvent<SVGElement>) => void;
};

const legacyTypes = new Set(["filling", "crown", "bridge", "root_canal", "rct", "implant", "denture", "veneer", "inlay_onlay", "post", "extraction", "other"]);
const legacySurfaces = new Set<R4SurfaceKey>(["M", "O", "D", "B", "L", "I"]);

/** Only explicit item metadata controls artwork. Names, prices and codes are
 * deliberately not interpreted as clinical findings or drawing instructions. */
export function planningToothOverlays(items: PlanningItem[], tooth: string, patientId: number): OdontogramPlannedOverlay[] {
  return items.filter((item) => item.patient_id === patientId && item.target.tooth === tooth
    && item.target.level !== "general" && ["proposed", "accepted", "completed"].includes(item.status))
    .map((item) => ({ id: item.id, kind: item.drawing_kind, label: item.description,
      surfaces: [...item.target.surfaces], status: item.status === "completed" ? "completed" : "planned" }));
}

/** Present a saved plan snapshot only: no fetches, live fallbacks or diagnosis
 * mutation hooks. The caller owns the treatment catalogue and save workflow. */
export default function TreatmentPlanningChart({ snapshot, items, level, selection, disabled, onSelect, onOpenToothNotes }: Props) {
  const legacy = useMemo(() => {
    const result = new Map<string, { missing: boolean; extracted: boolean; restorations: OdontogramToothRestoration[] }>();
    if (!snapshot.legacy || snapshot.legacy.patient_id !== snapshot.native.patient_id) return result;
    for (const [key, entry] of Object.entries(snapshot.legacy.teeth)) {
      const tooth = fdiToChartToothKey(Number(key))?.key;
      if (!tooth) continue;
      result.set(tooth, { missing: entry.missing === true, extracted: entry.extracted === true,
        restorations: (entry.restorations ?? []).filter((item) => legacyTypes.has(item.type)).map((item) => ({
          type: item.type, surfaces: (item.surfaces ?? []).filter((surface) => legacySurfaces.has(surface)),
          meta: item.meta ?? undefined,
        })) });
    }
    return result;
  }, [snapshot]);
  const captured = new Date(snapshot.captured_at);
  const capturedLabel = Number.isNaN(captured.getTime()) ? "Capture date not recorded"
    : captured.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/London" });

  const select = (tooth: string, targetLevel: PlanningLevel, event: PlanningChartEvent, context = false, surface?: SurfaceKey) => {
    event.preventDefault(); event.stopPropagation();
    if (disabled) return;
    let surfaces: SurfaceKey[] = [];
    if (surface) {
      const prior = selection?.tooth === tooth && selection.level === "surface" ? selection.surfaces : [];
      // Context-click keeps a multi-surface target; normal click toggles only
      // that cell. Opening a picker never silently drops the existing target.
      surfaces = context ? [...new Set([...prior, surface])]
        : prior.includes(surface) ? prior.filter((value) => value !== surface) : [...prior, surface];
      surfaces.sort((a, b) => surfaceOrder.indexOf(a) - surfaceOrder.indexOf(b));
    }
    onSelect({ tooth, level: targetLevel, surfaces }, event, context);
  };

  return <section className={styles.chart} data-testid="treatment-planning-chart" aria-label="Treatment planning odontogram"
    data-snapshot-captured-at={snapshot.captured_at} data-planning-level={level}>
    <div className={styles.heading}>
      <div><h3>Captured diagnosis</h3><span>{capturedLabel}</span></div>
      <div className={styles.legend} aria-label="Treatment chart legend">
        <span>Tooth colours: captured findings</span><span className={styles.plannedKey}>P · Planned (dashed)</span>
        <span className={styles.completedKey}>C · Completed (solid)</span>
      </div>
    </div>
    {snapshot.coverage.legacy !== "captured" && <p className={styles.coverage} role="note">
      {snapshot.coverage.legacy === "partial" ? "Imported chart coverage is partial in this snapshot." : "Imported chart findings were not available when this snapshot was captured."}
      {" "}No live imported findings are added to this plan.
      {snapshot.coverage.legacy_reason ? ` ${snapshot.coverage.legacy_reason}` : ""}
    </p>}
    <div className={styles.scroll} tabIndex={0} role="region" aria-label="Planning chart, scroll horizontally to see all teeth">
      <div className={styles.canvas}>
        <div className={styles.midline} aria-hidden="true" />
        {[true, false].map((upper) => <div key={upper ? "upper" : "lower"}>
          <div className={`${styles.quadrants} ${upper ? "" : styles.lowerLabels}`} aria-hidden="true">
            <span>{upper ? "Upper right" : "Lower right"}</span><span>{upper ? "Upper left" : "Lower left"}</span>
          </div>
          <div className={styles.arch} data-testid={`planning-${upper ? "upper" : "lower"}-arch`}>
            <BridgeConnections bridges={snapshot.native.bridges ?? []} upper={upper} />
            {bridgeArchTeeth(upper).map((tooth, index) => {
              const row = snapshot.native.teeth[tooth];
              const baseline = baselineGlyph(row);
              const label = britishToothLabel(tooth, baseline?.dentition === "deciduous" ? "deciduous" : undefined);
              const saved = legacy.get(tooth);
              const selected = selection?.tooth === tooth ? selection : null;
              const numberLevel = level === "crown" ? "crown" : "tooth";
              const numberTitle = `${label} ${numberLevel === "crown" ? "crown area" : "whole tooth"} treatment`;
              return <div key={tooth} className={styles.tooth} style={{ gridColumn: index < 8 ? index + 1 : index + 2 }}
                role="group" aria-label={`Planning for ${label}`} data-testid={`planning-tooth-${tooth}`}>
                <OdontogramToothSvg toothKey={tooth} toothType={getOdontogramToothType(tooth)}
                  baselineCondition={baseline} rootConditions={row?.root_observations ?? {}}
                  crownCondition={row?.crown_observation ?? null} surfaceObservations={row?.surface_observations ?? {}}
                  bridgeRole={row?.bridge_role} hasToothNote={snapshot.native.note_teeth.includes(tooth)}
                  onToothNoteClick={onOpenToothNotes ? (event) => onOpenToothNotes(tooth, event) : undefined}
                  restorations={saved?.restorations ?? []} missing={saved?.missing} extracted={saved?.extracted}
                  plannedOverlays={planningToothOverlays(items, tooth, snapshot.native.patient_id)}
                  rootSelected={selected?.level === "root"} crownSelected={selected?.level === "crown"}
                  selectedDiagnosticSurfaces={selected?.level === "surface" ? selected.surfaces : []}
                  onRootClick={disabled ? undefined : (event) => select(tooth, "root", event)}
                  onRootContextMenu={disabled ? undefined : (event) => select(tooth, "root", event, true)}
                  onCrownClick={disabled ? undefined : (event) => select(tooth, "crown", event)}
                  onCrownContextMenu={disabled ? undefined : (event) => select(tooth, "crown", event, true)}
                  onDiagnosticSurfaceClick={disabled ? undefined : (surface, event) => select(tooth, "surface", event, false, surface)}
                  onDiagnosticSurfaceContextMenu={disabled ? undefined : (surface, event) => select(tooth, "surface", event, true, surface)} />
                <button type="button" className={styles.number} disabled={disabled} data-testid={`planning-tooth-number-${tooth}`}
                  aria-label={numberTitle} title={numberTitle} aria-pressed={selected?.level === numberLevel}
                  onClick={(event) => select(tooth, numberLevel, event)} onContextMenu={(event) => select(tooth, numberLevel, event, true)}
                  onKeyDown={(event) => { if (event.key === "ContextMenu" || event.shiftKey && event.key === "F10") select(tooth, numberLevel, event, true); }}>
                  {label}
                </button>
              </div>;
            })}
          </div>
        </div>)}
      </div>
    </div>
  </section>;
}
