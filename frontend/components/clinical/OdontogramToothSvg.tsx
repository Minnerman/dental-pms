import { memo, useId } from "react";

import { getToothAnatomy, getToothAnatomyWidth, implantScrewAnatomy } from "./toothAnatomy";
import { britishToothLabel } from "./toothDiagnosis";

import type { R4SurfaceKey } from "@/lib/charting/r4SurfaceCodeToSurfaceKey";

export type OdontogramToothType = "incisor" | "canine" | "premolar" | "molar";
export type OdontogramBaselineCondition = {
  status?: "present" | "missing" | "implant" | "unerupted" | "impacted";
  dentition?: "permanent" | "deciduous";
  movement?: "forward" | "backward" | null;
  rotation?: "clockwise" | "anticlockwise" | null;
};
export type OdontogramRestorationType =
  | "filling"
  | "crown"
  | "bridge"
  | "root_canal"
  | "rct"
  | "implant"
  | "denture"
  | "veneer"
  | "inlay_onlay"
  | "post"
  | "extraction"
  | "other";

type NormalizedRestorationType = Exclude<OdontogramRestorationType, "rct">;

export type OdontogramToothRestoration = {
  type: OdontogramRestorationType;
  surfaces?: R4SurfaceKey[];
  meta?: Record<string, unknown>;
};

type SurfaceShape = {
  key: R4SurfaceKey;
  points: string;
};

type PointerPosition = {
  clientX: number;
  clientY: number;
};

type NormalizedRestoration = {
  type: NormalizedRestorationType;
  surfaces: R4SurfaceKey[];
  meta?: Record<string, unknown>;
};

const surfaceOutlinePath: Record<OdontogramToothType, string> = {
  incisor:
    "M36 6 C44 4 56 4 64 6 C72 10 78 20 76 30 C74 42 72 52 70 66 C68 78 62 90 50 94 C38 90 32 78 30 66 C28 52 26 42 24 30 C22 20 28 10 36 6 Z",
  canine:
    "M50 4 L66 12 C74 20 76 30 73 40 C70 52 68 64 66 74 C63 84 58 92 50 96 C42 92 37 84 34 74 C32 64 30 52 27 40 C24 30 26 20 34 12 Z",
  premolar:
    "M34 8 C42 4 58 4 66 8 C74 14 80 24 78 34 C76 48 74 60 70 72 C66 84 60 92 50 96 C40 92 34 84 30 72 C26 60 24 48 22 34 C20 24 26 14 34 8 Z",
  molar:
    "M26 10 C34 4 66 4 74 10 C82 18 86 30 84 42 C82 56 80 68 76 78 C72 88 64 94 50 96 C36 94 28 88 24 78 C20 68 18 56 16 42 C14 30 18 18 26 10 Z",
};

// Anatomical silhouettes are separate from the clinical surface map below.

const posteriorSurfaceShapes: SurfaceShape[] = [
  { key: "B", points: "26,12 74,12 66,30 34,30" },
  { key: "M", points: "10,28 32,36 32,64 12,76" },
  { key: "O", points: "34,30 66,30 74,50 66,70 34,70 26,50" },
  { key: "D", points: "90,28 68,36 68,64 88,76" },
  { key: "L", points: "30,70 70,70 78,90 22,90" },
];

const anteriorSurfaceShapes: SurfaceShape[] = [
  { key: "B", points: "30,12 70,12 62,34 38,34" },
  { key: "M", points: "14,28 36,38 36,66 18,82" },
  { key: "I", points: "38,34 62,34 68,50 62,66 38,66 32,50" },
  { key: "D", points: "86,28 64,38 64,66 82,82" },
  { key: "L", points: "34,66 66,66 72,88 28,88" },
];

const surfaceShapesByToothType: Record<OdontogramToothType, SurfaceShape[]> = {
  incisor: anteriorSurfaceShapes,
  canine: anteriorSurfaceShapes,
  premolar: posteriorSurfaceShapes,
  molar: posteriorSurfaceShapes,
};

const surfaceAnchorByType: Record<
  OdontogramToothType,
  Record<R4SurfaceKey, { top: string; left: string }>
> = {
  incisor: {
    B: { top: "21%", left: "50%" },
    M: { top: "50%", left: "26%" },
    I: { top: "50%", left: "50%" },
    O: { top: "50%", left: "50%" },
    D: { top: "50%", left: "74%" },
    L: { top: "78%", left: "50%" },
  },
  canine: {
    B: { top: "21%", left: "50%" },
    M: { top: "50%", left: "26%" },
    I: { top: "50%", left: "50%" },
    O: { top: "50%", left: "50%" },
    D: { top: "50%", left: "74%" },
    L: { top: "78%", left: "50%" },
  },
  premolar: {
    B: { top: "21%", left: "50%" },
    M: { top: "50%", left: "22%" },
    I: { top: "50%", left: "50%" },
    O: { top: "50%", left: "50%" },
    D: { top: "50%", left: "78%" },
    L: { top: "78%", left: "50%" },
  },
  molar: {
    B: { top: "21%", left: "50%" },
    M: { top: "50%", left: "22%" },
    I: { top: "50%", left: "50%" },
    O: { top: "50%", left: "50%" },
    D: { top: "50%", left: "78%" },
    L: { top: "78%", left: "50%" },
  },
};

const restorationRenderOrder: Record<NormalizedRestorationType, number> = {
  filling: 1,
  inlay_onlay: 2,
  veneer: 3,
  crown: 4,
  bridge: 5,
  root_canal: 6,
  post: 7,
  implant: 8,
  denture: 9,
  extraction: 10,
  other: 11,
};

function normalizeRestorationType(type: OdontogramRestorationType): NormalizedRestorationType {
  if (type === "rct") return "root_canal";
  return type;
}

function normalizeSurfaces(surfaces: R4SurfaceKey[] | undefined): R4SurfaceKey[] {
  const allowed = new Set<R4SurfaceKey>(["M", "O", "D", "B", "L", "I"]);
  const unique = new Set<R4SurfaceKey>();
  for (const surface of surfaces ?? []) {
    if (allowed.has(surface)) unique.add(surface);
  }
  return Array.from(unique);
}

function restorationSortKey(item: NormalizedRestoration): string {
  const codeLabel = typeof item.meta?.code_label === "string" ? item.meta.code_label : "";
  const codeId =
    typeof item.meta?.code_id === "number" || typeof item.meta?.code_id === "string"
      ? String(item.meta.code_id)
      : "";
  return `${String(restorationRenderOrder[item.type]).padStart(2, "0")}|${item.type}|${item.surfaces.join("")}|${codeLabel}|${codeId}`;
}

function formatRestorationTooltip(restorations: NormalizedRestoration[]): string | undefined {
  if (restorations.length === 0) return undefined;
  const lines = restorations.map((restoration) => {
    const codeLabelValue = restoration.meta?.code_label;
    const codeIdValue = restoration.meta?.code_id;
    const label =
      typeof codeLabelValue === "string" && codeLabelValue.trim()
        ? codeLabelValue.trim()
        : typeof codeIdValue === "number" || typeof codeIdValue === "string"
          ? `Code ${String(codeIdValue)}`
          : "Unknown code";
    const surfaceText =
      restoration.surfaces.length > 0
        ? `Surface: ${restoration.surfaces.join(",")}`
        : "Surface: Whole tooth";
    return `${label} (Completed) - ${surfaceText}`;
  });
  return lines.join("\n");
}

type Props = {
  toothKey: string;
  toothType: OdontogramToothType;
  selectedSurfaces?: R4SurfaceKey[];
  restorations?: OdontogramToothRestoration[];
  missing?: boolean;
  extracted?: boolean;
  active?: boolean;
  baselineCondition?: OdontogramBaselineCondition;
  onSurfaceClick?: (surface: R4SurfaceKey, position: PointerPosition) => void;
  onSurfaceContextMenu?: (surface: R4SurfaceKey, position: PointerPosition) => void;
};

function OdontogramToothSvgImpl({
  toothKey,
  toothType,
  selectedSurfaces = [],
  restorations = [],
  missing = false,
  extracted = false,
  active = false,
  baselineCondition,
  onSurfaceClick,
  onSurfaceContextMenu,
}: Props) {
  const surfaces = surfaceShapesByToothType[toothType];
  const selectedSurfaceKeys = new Set(selectedSurfaces);
  const availableSurfaceKeys = new Set<R4SurfaceKey>(surfaces.map((surface) => surface.key));
  const normalizedRestorations = restorations
    .map((restoration): NormalizedRestoration => ({
      type: normalizeRestorationType(restoration.type),
      surfaces: normalizeSurfaces(restoration.surfaces).filter((surface) =>
        availableSurfaceKeys.has(surface)
      ),
      meta: restoration.meta,
    }))
    .filter((restoration) => {
      if (!baselineCondition) return true;
      // A current primary/unerupted tooth must not inherit the permanent
      // predecessor's historical restorations. The history itself is untouched.
      if (baselineCondition.dentition === "deciduous" || baselineCondition.status === "unerupted") {
        return false;
      }
      if (baselineCondition.status === "implant" || baselineCondition.status === "impacted") {
        return !["root_canal", "post", "implant", "extraction"].includes(restoration.type);
      }
      if (baselineCondition.status === "present" && restoration.type === "implant") return false;
      return true;
    })
    .sort((a, b) => restorationSortKey(a).localeCompare(restorationSortKey(b)));

  const restorationsByType = new Map<NormalizedRestorationType, NormalizedRestoration[]>();
  for (const restoration of normalizedRestorations) {
    const bucket = restorationsByType.get(restoration.type) ?? [];
    bucket.push(restoration);
    restorationsByType.set(restoration.type, bucket);
  }

  const hasRestoration = (type: NormalizedRestorationType) =>
    (restorationsByType.get(type) ?? []).length > 0;
  const restorationsForType = (type: NormalizedRestorationType) => restorationsByType.get(type) ?? [];
  const tooltipForType = (type: NormalizedRestorationType) =>
    formatRestorationTooltip(restorationsForType(type));

  const fillingSurfaces = new Set<R4SurfaceKey>();
  for (const restoration of restorationsForType("filling")) {
    for (const surface of restoration.surfaces) {
      fillingSurfaces.add(surface);
    }
  }
  const hasWholeToothFilling = restorationsForType("filling").some(
    (restoration) => restoration.surfaces.length === 0
  );

  const veneerSurfaces = new Set<R4SurfaceKey>();
  for (const restoration of restorationsForType("veneer")) {
    if (restoration.surfaces.length === 0) {
      veneerSurfaces.add("B");
      continue;
    }
    for (const surface of restoration.surfaces) {
      veneerSurfaces.add(surface);
    }
  }
  if (!availableSurfaceKeys.has("B")) {
    veneerSurfaces.delete("B");
  }

  const inlayOnlaySurfaces = new Set<R4SurfaceKey>();
  for (const restoration of restorationsForType("inlay_onlay")) {
    if (restoration.surfaces.length === 0) continue;
    for (const surface of restoration.surfaces) {
      inlayOnlaySurfaces.add(surface);
    }
  }
  if (inlayOnlaySurfaces.size === 0 && hasRestoration("inlay_onlay")) {
    const defaultSurface: R4SurfaceKey = toothType === "incisor" || toothType === "canine" ? "I" : "O";
    if (availableSurfaceKeys.has(defaultSurface)) {
      inlayOnlaySurfaces.add(defaultSurface);
    }
  }

  const crownTooltip = tooltipForType("crown");
  const bridgeTooltip = tooltipForType("bridge");
  const rootCanalTooltip = tooltipForType("root_canal");
  const postTooltip = tooltipForType("post");
  const implantTooltip = tooltipForType("implant");
  const dentureTooltip = tooltipForType("denture");
  const veneerTooltip = tooltipForType("veneer");
  const inlayOnlayTooltip = tooltipForType("inlay_onlay");
  const otherTooltip = tooltipForType("other");

  const extractionFromRestoration = hasRestoration("extraction");
  const extractedState = !baselineCondition?.status && (extracted || extractionFromRestoration);
  const legacyMissing = !baselineCondition?.status && missing;
  const stateDominant = legacyMissing || extractedState;
  const baselineMissing = baselineCondition?.status === "missing";
  const baselineImplant = baselineCondition?.status === "implant";
  const baselineUnerupted = baselineCondition?.status === "unerupted";
  const baselineImpacted = baselineCondition?.status === "impacted";
  const isDeciduous = baselineCondition?.dentition === "deciduous";
  const displayLabel = britishToothLabel(toothKey, isDeciduous ? "deciduous" : undefined);
  const showAnatomy = !baselineMissing;
  const showSurfaceMap = !baselineMissing && !baselineUnerupted;
  const showNaturalRoots = !baselineImplant && !baselineUnerupted;
  const isUpperArch = toothKey.startsWith("U");
  const illustrationId = useId().replace(/:/g, "");
  const enamelFillId = `enamel-${illustrationId}`;
  const rootFillId = `root-${illustrationId}`;
  const implantFillId = `implant-${illustrationId}`;
  const anatomy = getToothAnatomy(toothKey, baselineCondition?.dentition);
  const anatomyWidth = getToothAnatomyWidth(toothKey) * (isDeciduous ? 0.86 : 1);
  const anatomyScaleX = toothKey[1] === "L" ? -anatomyWidth : anatomyWidth;
  const anatomyTransform = `translate(50 ${isUpperArch ? 0 : 280}) scale(${anatomyScaleX} ${isUpperArch ? 1 : -1}) translate(-50 0)`;
  // The inclination is a visual status marker, not a measured clinical angle.
  // Left/right mirroring makes both quadrants incline toward the adjacent tooth
  // on the midline side without moving the tooth slot or surface hit targets.
  const crownTransform = baselineImpacted ? "rotate(-28 50 125)" : undefined;
  const movement = baselineCondition?.movement;
  const rotation = baselineCondition?.rotation;
  const movementDirection = (toothKey[1] === "R" ? 1 : -1) * (movement === "backward" ? -1 : 1);
  const baselineDescription = [
    isDeciduous ? "current condition deciduous" : baselineCondition?.status ? `current condition ${baselineCondition.status}` : "",
    movement ? `movement ${movement} (${movement === "forward" ? "toward" : "away from"} the midline)` : "",
    rotation ? `rotation ${rotation}` : "",
  ].filter(Boolean).map((description) => `, ${description}`).join("");

  return (
    <svg
      viewBox="0 0 100 280"
      width="72"
      height="202"
      className="odontogram-tooth-svg"
      role="img"
      aria-label={`${displayLabel} ${isDeciduous && Number(toothKey.slice(-1)) >= 4 ? "molar" : toothType}${baselineDescription}${showAnatomy ? ", anatomical tooth" : ""}${showSurfaceMap ? " and surface map" : ""}${displayLabel !== toothKey ? `, chart position ${toothKey}` : ""}`}
      data-testid={`tooth-svg-${toothKey}`}
      data-baseline-status={baselineCondition?.status}
      data-dentition={baselineCondition?.dentition}
      data-movement={movement ?? undefined}
      data-rotation={rotation ?? undefined}
      style={{ display: "block", overflow: "visible" }}
    >
      <defs>
        <radialGradient id={enamelFillId} cx="42%" cy="38%" r="72%">
          <stop offset="0%" stopColor={active ? "#f0fff8" : "#ffffff"} />
          <stop offset="72%" stopColor={active ? "#e5fff3" : "#fafbf8"} />
          <stop offset="100%" stopColor={active ? "#d4f5e7" : "#e3e7e1"} />
        </radialGradient>
        <linearGradient id={rootFillId} x1="0%" x2="100%">
          <stop offset="0%" stopColor="#e9e5b6" />
          <stop offset="42%" stopColor="#ffffdf" />
          <stop offset="78%" stopColor="#faf7cf" />
          <stop offset="100%" stopColor="#e8e1ac" />
        </linearGradient>
        <linearGradient id={implantFillId} x1="0%" x2="100%">
          <stop offset="0%" stopColor="#7d939d" />
          <stop offset="38%" stopColor="#e3edf0" />
          <stop offset="72%" stopColor="#acbfc7" />
          <stop offset="100%" stopColor="#657e89" />
        </linearGradient>
      </defs>
      {showAnatomy && <g
        data-testid={`tooth-anatomy-${toothKey}`}
        data-anatomy-parts={baselineUnerupted ? "crown gum" : baselineImplant ? "crown implant" : "crown root"}
        data-dentition={baselineCondition?.dentition}
        transform={anatomyTransform}
        pointerEvents="none"
      >
        {showNaturalRoots && anatomy.roots.map((path, index) => (
          <path
            key={`${toothKey}-root-${index}`}
            d={path}
            fill={`url(#${rootFillId})`}
            stroke="#686958"
            strokeWidth={1.05}
            strokeLinejoin="round"
            data-testid={`tooth-root-${toothKey}-${index + 1}`}
          />
        ))}
        {baselineImplant && (
          <g data-testid={`tooth-baseline-implant-${toothKey}`}>
            <path d={implantScrewAnatomy.body} fill={`url(#${implantFillId})`}
              stroke="#425d69" strokeWidth={1.3} strokeLinejoin="round"
              data-testid={`tooth-implant-body-${toothKey}`} />
            {implantScrewAnatomy.threads.map((path, index) => (
              <path key={index} d={path} fill={`url(#${implantFillId})`}
                stroke="#425d69" strokeWidth={1} strokeLinejoin="round"
                data-testid={`tooth-implant-thread-${toothKey}-${index + 1}`} />
            ))}
            <path d={implantScrewAnatomy.collar} fill={`url(#${implantFillId})`}
              stroke="#425d69" strokeWidth={1.3} strokeLinejoin="round"
              data-testid={`tooth-implant-collar-${toothKey}`} />
          </g>
        )}
        {baselineUnerupted && (
          <path
            d={isUpperArch
              ? "M8 80 Q15 73 22 80 T36 80 T50 80 T64 80 T78 80 T92 80"
              : "M8 177 Q15 184 22 177 T36 177 T50 177 T64 177 T78 177 T92 177"}
            fill="none" stroke="#9e6674" strokeWidth={2.8} strokeLinecap="round"
            data-testid={`tooth-baseline-gum-${toothKey}`}
          />
        )}
        <g transform={crownTransform} data-testid={`tooth-crown-appearance-${toothKey}`}
          data-impacted={baselineImpacted ? "true" : undefined}>
        <path
          d={anatomy.crown}
          fill={`url(#${enamelFillId})`}
          stroke="#444d49"
          strokeWidth={1.2}
          strokeLinejoin="round"
          data-testid={`tooth-crown-${toothKey}`}
        />

        {anatomy.grooves.map((path, index) => (
          <path key={index} d={path} fill="none" stroke="#60665f" strokeWidth={1}
            strokeLinecap="round" data-testid={`tooth-crown-groove-${toothKey}-${index + 1}`} />
        ))}

        {hasRestoration("crown") && (
          <path
            d={anatomy.crown}
            fill="rgba(128, 123, 47, 0.72)"
            stroke="rgba(85, 82, 30, 0.96)"
            strokeWidth={1.7}
            data-testid={`tooth-anatomy-restoration-${toothKey}-crown`}
          />
        )}
        </g>

        {hasRestoration("root_canal") && (
          <g data-testid={`tooth-anatomy-restoration-${toothKey}-root_canal`}>
            {anatomy.canals.map((path, index) => (
              <path key={index} d={path} fill="none" stroke="rgba(220, 38, 38, 0.92)"
                strokeWidth={2.2} strokeLinecap="round" />
            ))}
          </g>
        )}

        {hasRestoration("post") && (
          <rect
            x="46"
            y="74"
            width="8"
            height="64"
            rx="2"
            fill="rgba(250, 204, 21, 0.92)"
            stroke="rgba(161, 98, 7, 0.95)"
            strokeWidth={1}
            data-testid={`tooth-anatomy-restoration-${toothKey}-post`}
          />
        )}

        {hasRestoration("implant") && (
          <g data-testid={`tooth-anatomy-restoration-${toothKey}-implant`}>
            <rect
              x="42"
              y="20"
              width="16"
              height="88"
              rx="3"
              fill="rgba(103, 232, 249, 0.9)"
              stroke="rgba(14, 116, 144, 0.96)"
              strokeWidth={1.2}
            />
            {[33, 52, 71, 90].map((y) => (
              <circle
                key={`${toothKey}-implant-${y}`}
                cx="50"
                cy={y}
                r="3.1"
                fill="rgba(255,255,255,0.9)"
                stroke="rgba(14, 116, 144, 0.96)"
                strokeWidth={0.9}
              />
            ))}
          </g>
        )}

        {stateDominant && (
          <rect x="4" y="0" width="92" height="170" fill="rgba(255,255,255,0.55)" />
        )}
        {legacyMissing && (
          <line
            x1="20"
            y1="160"
            x2="80"
            y2="8"
            stroke="rgba(220, 38, 38, 0.9)"
            strokeWidth={4}
          />
        )}
        {extractedState && (
          <line
            x1="20"
            y1="8"
            x2="80"
            y2="160"
            stroke="rgba(220, 38, 38, 0.9)"
            strokeWidth={4}
          />
        )}
      </g>}

      {showAnatomy && (movement || rotation) && (
        <g
          transform={`translate(50 ${isUpperArch ? -14 : 294})`}
          pointerEvents="none"
          data-testid={`tooth-position-markers-${toothKey}`}
          data-marker-side={isUpperArch ? "above" : "below"}
        >
          {movement && (
            <g
              transform={`translate(${rotation ? -21 : 0} 0) scale(${movementDirection} 1)`}
              data-testid={`tooth-movement-${toothKey}`}
              data-direction={movement}
              stroke="var(--odontogram-movement, #b96708)"
              strokeWidth={2.6}
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
            >
              <path d="M-13 0 H13 M6 -7 L13 0 L6 7" />
            </g>
          )}
          {rotation && (
            <g
              transform={`translate(${movement ? 21 : 0} 0) scale(${rotation === "anticlockwise" ? -1 : 1} 1)`}
              data-testid={`tooth-rotation-${toothKey}`}
              data-direction={rotation}
              stroke="var(--odontogram-rotation, #8057c8)"
              strokeWidth={2.3}
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
            >
              <path d="M8 6 A10 10 0 1 1 9 -4 M9 -4 L3 -5 M9 -4 L10 -10" />
            </g>
          )}
        </g>
      )}

      {showSurfaceMap && <g
        transform={isUpperArch ? "translate(0 180)" : undefined}
        data-testid={`tooth-surface-map-${toothKey}`}
      >
      <path
        d={surfaceOutlinePath[toothType]}
        fill={active ? "rgba(51, 255, 180, 0.12)" : "rgba(255, 255, 255, 0.82)"}
        stroke="rgba(17, 24, 39, 0.55)"
        strokeWidth={2}
      />

      {surfaces.map((surface) => {
        const isSelected = selectedSurfaceKeys.has(surface.key);
        const hasFilling = fillingSurfaces.has(surface.key);
        const hasVeneer = veneerSurfaces.has(surface.key);
        const hasInlayOnlay = inlayOnlaySurfaces.has(surface.key);
        return (
          <g key={`${toothKey}-${surface.key}`}>
            <polygon
              points={surface.points}
              data-surface={surface.key}
              data-selected={isSelected ? "true" : "false"}
              data-testid={`tooth-surface-${toothKey}-${surface.key}`}
              fill={isSelected ? "rgba(51, 255, 180, 0.42)" : "rgba(148, 163, 184, 0.08)"}
              stroke={isSelected ? "var(--accent)" : "rgba(51, 65, 85, 0.35)"}
              strokeWidth={isSelected ? 2.4 : 1.2}
              style={{ cursor: "pointer" }}
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                onSurfaceClick?.(surface.key, {
                  clientX: event.clientX,
                  clientY: event.clientY,
                });
              }}
              onContextMenu={(event) => {
                event.preventDefault();
                event.stopPropagation();
                onSurfaceContextMenu?.(surface.key, {
                  clientX: event.clientX,
                  clientY: event.clientY,
                });
              }}
            />
            {hasFilling && (
              <polygon
                points={surface.points}
                fill="rgba(239, 68, 68, 0.30)"
                stroke="rgba(220, 38, 38, 0.88)"
                strokeWidth={1.15}
                pointerEvents="none"
                data-testid={`tooth-restoration-${toothKey}-filling-${surface.key}`}
              />
            )}
            {hasVeneer && (
              <polygon
                points={surface.points}
                fill="rgba(59, 130, 246, 0.24)"
                stroke="rgba(37, 99, 235, 0.8)"
                strokeWidth={1}
                pointerEvents="none"
                data-testid={`tooth-restoration-${toothKey}-veneer-${surface.key}`}
              />
            )}
            {hasInlayOnlay && (
              <polygon
                points={surface.points}
                fill="rgba(16, 185, 129, 0.23)"
                stroke="rgba(5, 150, 105, 0.85)"
                strokeWidth={1}
                pointerEvents="none"
                data-testid={`tooth-restoration-${toothKey}-inlay_onlay-${surface.key}`}
              />
            )}
          </g>
        );
      })}

      {hasWholeToothFilling && (
        <g pointerEvents="none" data-testid={`tooth-restoration-${toothKey}-filling-generic`}>
          <rect
            x="40"
            y="44"
            width="20"
            height="14"
            rx="3"
            fill="rgba(239, 68, 68, 0.25)"
            stroke="rgba(220, 38, 38, 0.9)"
            strokeWidth={1.2}
          />
          <line x1="42" y1="51" x2="58" y2="51" stroke="rgba(220, 38, 38, 0.9)" strokeWidth={1.1} />
        </g>
      )}

      {hasRestoration("crown") && (
        <path
          d={surfaceOutlinePath[toothType]}
          fill="rgba(251, 191, 36, 0.19)"
          stroke="rgba(180, 83, 9, 0.95)"
          strokeWidth={4}
          pointerEvents="none"
          data-tooltip={crownTooltip}
          data-testid={`tooth-restoration-${toothKey}-crown`}
        >
          {crownTooltip ? <title>{crownTooltip}</title> : null}
        </path>
      )}

      {hasRestoration("bridge") && (
        <g
          pointerEvents="none"
          data-tooltip={bridgeTooltip}
          data-testid={`tooth-restoration-${toothKey}-bridge`}
        >
          {bridgeTooltip ? <title>{bridgeTooltip}</title> : null}
          <line x1="18" y1="18" x2="82" y2="18" stroke="rgba(15, 118, 110, 0.95)" strokeWidth={3.2} />
          <circle
            cx="50"
            cy="18"
            r="4.2"
            fill="rgba(204, 251, 241, 0.95)"
            stroke="rgba(15, 118, 110, 0.95)"
            strokeWidth={1.4}
          />
        </g>
      )}

      {hasRestoration("root_canal") && (
        <g
          pointerEvents="none"
          data-tooltip={rootCanalTooltip}
          data-testid={`tooth-restoration-${toothKey}-root_canal`}
        >
          {rootCanalTooltip ? <title>{rootCanalTooltip}</title> : null}
          <line x1="50" y1="36" x2="50" y2="82" stroke="rgba(2, 132, 199, 0.95)" strokeWidth={2.4} />
          <line x1="45" y1="40" x2="41" y2="76" stroke="rgba(2, 132, 199, 0.88)" strokeWidth={1.8} />
          <line x1="55" y1="40" x2="59" y2="76" stroke="rgba(2, 132, 199, 0.88)" strokeWidth={1.8} />
          <circle cx="50" cy="33" r="4" fill="rgba(186, 230, 253, 0.98)" stroke="rgba(2, 132, 199, 0.95)" strokeWidth={1.2} />
          <circle cx="50" cy="83" r="2.8" fill="rgba(2, 132, 199, 0.95)" />
        </g>
      )}

      {hasRestoration("post") && (
        <g
          pointerEvents="none"
          data-tooltip={postTooltip}
          data-testid={`tooth-restoration-${toothKey}-post`}
        >
          {postTooltip ? <title>{postTooltip}</title> : null}
          <rect
            x="47"
            y="46"
            width="6"
            height="30"
            rx="2"
            fill="rgba(146, 64, 14, 0.9)"
            stroke="rgba(120, 53, 15, 0.95)"
            strokeWidth={1}
          />
        </g>
      )}

      {hasRestoration("implant") && (
        <g
          pointerEvents="none"
          data-tooltip={implantTooltip}
          data-testid={`tooth-restoration-${toothKey}-implant`}
        >
          {implantTooltip ? <title>{implantTooltip}</title> : null}
          <rect
            x="43"
            y="66"
            width="14"
            height="22"
            rx="2.5"
            fill="rgba(107, 114, 128, 0.87)"
            stroke="rgba(55, 65, 81, 0.95)"
            strokeWidth={1}
          />
          <line x1="43" y1="72" x2="57" y2="72" stroke="rgba(243, 244, 246, 0.85)" strokeWidth={1} />
          <line x1="43" y1="78" x2="57" y2="78" stroke="rgba(243, 244, 246, 0.85)" strokeWidth={1} />
          <line x1="43" y1="84" x2="57" y2="84" stroke="rgba(243, 244, 246, 0.85)" strokeWidth={1} />
        </g>
      )}

      {hasRestoration("denture") && (
        <g
          pointerEvents="none"
          data-tooltip={dentureTooltip}
          data-testid={`tooth-restoration-${toothKey}-denture`}
        >
          {dentureTooltip ? <title>{dentureTooltip}</title> : null}
          {isUpperArch ? (
            <path
              d="M18 18 Q50 2 82 18"
              fill="none"
              stroke="rgba(217, 119, 6, 0.92)"
              strokeWidth={4}
            />
          ) : (
            <path
              d="M18 82 Q50 98 82 82"
              fill="none"
              stroke="rgba(217, 119, 6, 0.92)"
              strokeWidth={4}
            />
          )}
        </g>
      )}

      {hasRestoration("veneer") && (
        <path
          d={surfaceOutlinePath[toothType]}
          fill="none"
          stroke="rgba(37, 99, 235, 0.8)"
          strokeWidth={1.2}
          strokeDasharray="2 2"
          pointerEvents="none"
          data-tooltip={veneerTooltip}
          data-testid={`tooth-restoration-${toothKey}-veneer`}
        >
          {veneerTooltip ? <title>{veneerTooltip}</title> : null}
        </path>
      )}

      {hasRestoration("inlay_onlay") && (
        <circle
          cx="50"
          cy="50"
          r="8"
          fill="rgba(16, 185, 129, 0.22)"
          stroke="rgba(5, 150, 105, 0.9)"
          strokeWidth={1.6}
          pointerEvents="none"
          data-tooltip={inlayOnlayTooltip}
          data-testid={`tooth-restoration-${toothKey}-inlay_onlay`}
        >
          {inlayOnlayTooltip ? <title>{inlayOnlayTooltip}</title> : null}
        </circle>
      )}

      {hasRestoration("other") && (
        <circle
          cx="50"
          cy="14"
          r="5"
          fill="rgba(99, 102, 241, 0.85)"
          stroke="rgba(67, 56, 202, 0.95)"
          strokeWidth={1.5}
          pointerEvents="none"
          data-tooltip={otherTooltip}
          data-testid={`tooth-restoration-${toothKey}-other`}
        >
          {otherTooltip ? <title>{otherTooltip}</title> : null}
        </circle>
      )}

      {stateDominant && (
        <path
          d={surfaceOutlinePath[toothType]}
          fill="rgba(255, 255, 255, 0.66)"
          stroke="none"
          pointerEvents="none"
        />
      )}

      {legacyMissing && (
        <line
          x1="16"
          y1="86"
          x2="84"
          y2="14"
          stroke="rgba(220, 38, 38, 0.9)"
          strokeWidth={4}
          pointerEvents="none"
          data-testid={`tooth-restoration-${toothKey}-missing`}
        />
      )}

      {extractedState && (
        <g data-testid={`tooth-restoration-${toothKey}-extraction`} pointerEvents="none">
          <line
            x1="16"
            y1="14"
            x2="84"
            y2="86"
            stroke="rgba(220, 38, 38, 0.9)"
            strokeWidth={4}
            data-testid={`tooth-restoration-${toothKey}-extracted`}
          />
        </g>
      )}
      </g>}
    </svg>
  );
}

export function getOdontogramToothType(toothKey: string): OdontogramToothType {
  const match = toothKey.match(/(\d)$/);
  const position = match ? Number(match[1]) : NaN;
  if (position === 1 || position === 2) return "incisor";
  if (position === 3) return "canine";
  if (position === 4 || position === 5) return "premolar";
  return "molar";
}

export function getOdontogramSurfaceAnchor(
  toothType: OdontogramToothType,
  surface: R4SurfaceKey,
  isUpperArch: boolean = true
) {
  const anchor = surfaceAnchorByType[toothType][surface];
  // Surface-map coordinates remain unchanged for both arches; only anatomy is reflected.
  const surfaceY = Number.parseFloat(anchor.top);
  return {
    ...anchor,
    top: `${((isUpperArch ? 180 + surfaceY : surfaceY) / 280) * 100}%`,
  };
}

const OdontogramToothSvg = memo(OdontogramToothSvgImpl);

export default OdontogramToothSvg;
