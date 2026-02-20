import { memo } from "react";

import type { R4SurfaceKey } from "@/lib/charting/r4SurfaceCodeToSurfaceKey";
import {
  TOOTH_STATE_TYPE_LABELS,
  TOOTH_STATE_TYPES,
  type ToothStateType,
} from "@/lib/charting/toothStateTypes";

export type OdontogramToothType = "incisor" | "canine" | "premolar" | "molar";
export type OdontogramRestorationType = ToothStateType;

export type OdontogramToothRestoration = {
  type: OdontogramRestorationType;
  surfaces?: R4SurfaceKey[];
  meta?: Record<string, unknown>;
};

type SurfaceShape = {
  key: R4SurfaceKey;
  points: string;
};

type CompactBadgeType = "bridge" | "veneer" | "inlay_onlay" | "post" | "denture" | "other";

type CompactBadgeStyle = {
  label: string;
  cx: number;
  cy: number;
  fill: string;
  stroke: string;
};

const toothOutlinePath: Record<OdontogramToothType, string> = {
  incisor:
    "M36 6 C44 4 56 4 64 6 C72 10 78 20 76 30 C74 42 72 52 70 66 C68 78 62 90 50 94 C38 90 32 78 30 66 C28 52 26 42 24 30 C22 20 28 10 36 6 Z",
  canine:
    "M50 4 L66 12 C74 20 76 30 73 40 C70 52 68 64 66 74 C63 84 58 92 50 96 C42 92 37 84 34 74 C32 64 30 52 27 40 C24 30 26 20 34 12 Z",
  premolar:
    "M34 8 C42 4 58 4 66 8 C74 14 80 24 78 34 C76 48 74 60 70 72 C66 84 60 92 50 96 C40 92 34 84 30 72 C26 60 24 48 22 34 C20 24 26 14 34 8 Z",
  molar:
    "M26 10 C34 4 66 4 74 10 C82 18 86 30 84 42 C82 56 80 68 76 78 C72 88 64 94 50 96 C36 94 28 88 24 78 C20 68 18 56 16 42 C14 30 18 18 26 10 Z",
};

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
    B: { top: "22%", left: "50%" },
    M: { top: "54%", left: "26%" },
    I: { top: "50%", left: "50%" },
    O: { top: "50%", left: "50%" },
    D: { top: "54%", left: "74%" },
    L: { top: "78%", left: "50%" },
  },
  canine: {
    B: { top: "22%", left: "50%" },
    M: { top: "54%", left: "26%" },
    I: { top: "50%", left: "50%" },
    O: { top: "50%", left: "50%" },
    D: { top: "54%", left: "74%" },
    L: { top: "78%", left: "50%" },
  },
  premolar: {
    B: { top: "22%", left: "50%" },
    M: { top: "50%", left: "22%" },
    I: { top: "50%", left: "50%" },
    O: { top: "50%", left: "50%" },
    D: { top: "50%", left: "78%" },
    L: { top: "80%", left: "50%" },
  },
  molar: {
    B: { top: "22%", left: "50%" },
    M: { top: "50%", left: "22%" },
    I: { top: "50%", left: "50%" },
    O: { top: "50%", left: "50%" },
    D: { top: "50%", left: "78%" },
    L: { top: "80%", left: "50%" },
  },
};

const compactBadgeStyles: Record<CompactBadgeType, CompactBadgeStyle> = {
  bridge: {
    label: "BR",
    cx: 20,
    cy: 14,
    fill: "rgba(14, 116, 144, 0.9)",
    stroke: "rgba(8, 47, 73, 0.95)",
  },
  veneer: {
    label: "VE",
    cx: 35,
    cy: 14,
    fill: "rgba(79, 70, 229, 0.88)",
    stroke: "rgba(49, 46, 129, 0.96)",
  },
  inlay_onlay: {
    label: "IN",
    cx: 50,
    cy: 14,
    fill: "rgba(202, 138, 4, 0.88)",
    stroke: "rgba(120, 53, 15, 0.96)",
  },
  post: {
    label: "PO",
    cx: 65,
    cy: 14,
    fill: "rgba(71, 85, 105, 0.9)",
    stroke: "rgba(15, 23, 42, 0.96)",
  },
  denture: {
    label: "DE",
    cx: 80,
    cy: 14,
    fill: "rgba(217, 119, 6, 0.9)",
    stroke: "rgba(146, 64, 14, 0.96)",
  },
  other: {
    label: "OT",
    cx: 50,
    cy: 27,
    fill: "rgba(99, 102, 241, 0.88)",
    stroke: "rgba(67, 56, 202, 0.96)",
  },
};

function createRestorationBuckets(): Record<OdontogramRestorationType, OdontogramToothRestoration[]> {
  return TOOTH_STATE_TYPES.reduce(
    (acc, type) => {
      acc[type] = [];
      return acc;
    },
    {} as Record<OdontogramRestorationType, OdontogramToothRestoration[]>
  );
}

function coerceOptionalBoolean(value: unknown): boolean | null {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value !== "string") return null;
  const normalized = value.trim().toLowerCase();
  if (!normalized) return null;
  if (["1", "true", "yes", "y", "on"].includes(normalized)) return true;
  if (["0", "false", "no", "n", "off"].includes(normalized)) return false;
  return null;
}

function restorationCodeLabel(restoration: OdontogramToothRestoration) {
  const codeLabelValue = restoration.meta?.code_label;
  const codeIdValue = restoration.meta?.code_id;
  if (typeof codeLabelValue === "string" && codeLabelValue.trim()) {
    return codeLabelValue.trim();
  }
  if (typeof codeIdValue === "number" || typeof codeIdValue === "string") {
    return `Code ${String(codeIdValue)}`;
  }
  return "Unknown code";
}

function restorationStatusLabel(restoration: OdontogramToothRestoration) {
  const completed = coerceOptionalBoolean(restoration.meta?.completed);
  return completed === false ? "Planned" : "Completed";
}

type Props = {
  toothKey: string;
  toothType: OdontogramToothType;
  selectedSurface?: R4SurfaceKey | null;
  restorations?: OdontogramToothRestoration[];
  missing?: boolean;
  extracted?: boolean;
  active?: boolean;
  onSurfaceClick?: (surface: R4SurfaceKey) => void;
};

function OdontogramToothSvgImpl({
  toothKey,
  toothType,
  selectedSurface = null,
  restorations = [],
  missing = false,
  extracted = false,
  active = false,
  onSurfaceClick,
}: Props) {
  const surfaces = surfaceShapesByToothType[toothType];
  const restorationsByType = createRestorationBuckets();
  for (const restoration of restorations) {
    restorationsByType[restoration.type].push(restoration);
  }
  const fillingSurfaces = new Set<R4SurfaceKey>();
  for (const restoration of restorationsByType.filling) {
    for (const surface of restoration.surfaces ?? []) {
      fillingSurfaces.add(surface);
    }
  }
  const hasWholeToothFilling = restorationsByType.filling.some(
    (restoration) => (restoration.surfaces?.length ?? 0) === 0
  );

  const restorationTooltipForType = (type: OdontogramRestorationType): string | undefined => {
    const matches = restorationsByType[type];
    if (matches.length === 0) return undefined;

    const lines = matches.map((restoration) => {
      const label = restorationCodeLabel(restoration);
      const typeLabel = TOOTH_STATE_TYPE_LABELS[type];
      const status = restorationStatusLabel(restoration);
      const surfaceText =
        restoration.surfaces && restoration.surfaces.length > 0
          ? restoration.surfaces.join(",")
          : "Whole tooth";
      return `${label} | Type: ${typeLabel} | Status: ${status} | Surface: ${surfaceText}`;
    });

    return lines.join("\n");
  };

  const extractionCompleted = restorationsByType.extraction.some(
    (restoration) => restorationStatusLabel(restoration) === "Completed"
  );
  const extractionPlanned = restorationsByType.extraction.some(
    (restoration) => restorationStatusLabel(restoration) === "Planned"
  );
  const hasExtraction = extracted || extractionCompleted || extractionPlanned;
  const extractionState: "completed" | "planned" | "mixed" =
    hasExtraction && extractionPlanned && !extracted && !extractionCompleted
      ? "planned"
      : hasExtraction && extractionPlanned && (extracted || extractionCompleted)
        ? "mixed"
        : "completed";

  function renderCompactBadge(type: CompactBadgeType) {
    if (restorationsByType[type].length === 0) return null;
    const tooltip = restorationTooltipForType(type);
    const style = compactBadgeStyles[type];
    return (
      <g
        pointerEvents="none"
        data-testid={`tooth-restoration-${toothKey}-${type}`}
        data-tooltip={tooltip}
      >
        {tooltip ? <title>{tooltip}</title> : null}
        <circle
          cx={style.cx}
          cy={style.cy}
          r="5.5"
          fill={style.fill}
          stroke={style.stroke}
          strokeWidth="1"
        />
        <text
          x={style.cx}
          y={style.cy + 1.8}
          textAnchor="middle"
          fontSize="4.8"
          fontWeight="700"
          fill="rgba(255,255,255,0.92)"
          pointerEvents="none"
        >
          {style.label}
        </text>
      </g>
    );
  }

  const restorationRenderers: Record<OdontogramRestorationType, () => JSX.Element | null> = {
    filling: () => {
      if (restorationsByType.filling.length === 0) return null;
      const tooltip = restorationTooltipForType("filling");
      return (
        <g
          pointerEvents="none"
          data-testid={`tooth-restoration-${toothKey}-filling`}
          data-tooltip={tooltip}
        >
          {tooltip ? <title>{tooltip}</title> : null}
          {hasWholeToothFilling && (
            <rect
              x="45"
              y="45"
              width="10"
              height="10"
              rx="2"
              fill="rgba(239, 68, 68, 0.28)"
              stroke="rgba(239, 68, 68, 0.76)"
              strokeWidth="1.2"
            />
          )}
        </g>
      );
    },
    crown: () => {
      if (restorationsByType.crown.length === 0) return null;
      const tooltip = restorationTooltipForType("crown");
      return (
        <path
          d={toothOutlinePath[toothType]}
          fill="rgba(251, 191, 36, 0.14)"
          stroke="rgba(202, 138, 4, 0.95)"
          strokeWidth={4}
          pointerEvents="none"
          data-tooltip={tooltip}
          data-testid={`tooth-restoration-${toothKey}-crown`}
        >
          {tooltip ? <title>{tooltip}</title> : null}
        </path>
      );
    },
    bridge: () => renderCompactBadge("bridge"),
    veneer: () => renderCompactBadge("veneer"),
    inlay_onlay: () => renderCompactBadge("inlay_onlay"),
    post: () => renderCompactBadge("post"),
    root_canal: () => {
      if (restorationsByType.root_canal.length === 0) return null;
      const tooltip = restorationTooltipForType("root_canal");
      return (
        <g
          pointerEvents="none"
          data-tooltip={tooltip}
          data-testid={`tooth-restoration-${toothKey}-root_canal`}
        >
          {tooltip ? <title>{tooltip}</title> : null}
          <line x1="44" y1="30" x2="44" y2="84" stroke="rgba(14, 116, 144, 0.95)" strokeWidth="2.2" />
          <line x1="50" y1="28" x2="50" y2="84" stroke="rgba(14, 116, 144, 0.95)" strokeWidth="2.2" />
          <line x1="56" y1="30" x2="56" y2="84" stroke="rgba(14, 116, 144, 0.95)" strokeWidth="2.2" />
        </g>
      );
    },
    implant: () => {
      if (restorationsByType.implant.length === 0) return null;
      const tooltip = restorationTooltipForType("implant");
      return (
        <g
          pointerEvents="none"
          data-tooltip={tooltip}
          data-testid={`tooth-restoration-${toothKey}-implant`}
        >
          {tooltip ? <title>{tooltip}</title> : null}
          <rect
            x="43"
            y="70"
            width="14"
            height="22"
            rx="2"
            fill="rgba(107, 114, 128, 0.86)"
            stroke="rgba(55, 65, 81, 0.94)"
            strokeWidth="1"
          />
          <line x1="43" y1="76" x2="57" y2="76" stroke="rgba(255, 255, 255, 0.72)" strokeWidth="1" />
          <line x1="43" y1="82" x2="57" y2="82" stroke="rgba(255, 255, 255, 0.72)" strokeWidth="1" />
          <line x1="43" y1="88" x2="57" y2="88" stroke="rgba(255, 255, 255, 0.72)" strokeWidth="1" />
        </g>
      );
    },
    extraction: () => {
      if (!hasExtraction) return null;
      const tooltip =
        restorationTooltipForType("extraction") ??
        "Unknown code | Type: extraction | Status: Completed | Surface: Whole tooth";
      const plannedOnly = extractionState === "planned";
      const mixedState = extractionState === "mixed";
      return (
        <g
          pointerEvents="none"
          data-tooltip={tooltip}
          data-status={extractionState}
          data-testid={`tooth-restoration-${toothKey}-extraction`}
        >
          {tooltip ? <title>{tooltip}</title> : null}
          <line
            x1="22"
            y1="18"
            x2="78"
            y2="82"
            stroke={plannedOnly ? "rgba(220, 38, 38, 0.9)" : "rgba(185, 28, 28, 0.92)"}
            strokeWidth={mixedState ? "3.2" : "3.8"}
            strokeDasharray={plannedOnly ? "5 4" : mixedState ? "2 2" : undefined}
          />
          <line
            x1="78"
            y1="18"
            x2="22"
            y2="82"
            stroke={plannedOnly ? "rgba(220, 38, 38, 0.9)" : "rgba(185, 28, 28, 0.92)"}
            strokeWidth={mixedState ? "3.2" : "3.8"}
            strokeDasharray={plannedOnly ? "5 4" : mixedState ? "2 2" : undefined}
          />
        </g>
      );
    },
    denture: () => renderCompactBadge("denture"),
    other: () => renderCompactBadge("other"),
  };

  return (
    <svg
      viewBox="0 0 100 100"
      width="40"
      height="40"
      role="img"
      aria-label={`${toothKey} ${toothType}`}
      data-testid={`tooth-svg-${toothKey}`}
      style={{ display: "block", overflow: "visible" }}
    >
      <path
        d={toothOutlinePath[toothType]}
        fill={active ? "rgba(51, 255, 180, 0.12)" : "rgba(255, 255, 255, 0.8)"}
        stroke="rgba(17, 24, 39, 0.55)"
        strokeWidth={2}
      />
      {surfaces.map((surface) => {
        const isSelected = selectedSurface === surface.key;
        const hasFilling = fillingSurfaces.has(surface.key);
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
                onSurfaceClick?.(surface.key);
              }}
            />
            {hasFilling && (
              <polygon
                points={surface.points}
                fill="rgba(239, 68, 68, 0.26)"
                stroke="rgba(239, 68, 68, 0.6)"
                strokeWidth={1}
                pointerEvents="none"
                data-testid={`tooth-restoration-${toothKey}-filling-${surface.key}`}
              />
            )}
          </g>
        );
      })}
      {TOOTH_STATE_TYPES.map((type) => {
        const content = restorationRenderers[type]();
        if (!content) return null;
        return <g key={`${toothKey}-${type}`}>{content}</g>;
      })}
      {missing && (
        <line
          x1="18"
          y1="86"
          x2="82"
          y2="14"
          stroke="rgba(220, 38, 38, 0.85)"
          strokeWidth={3}
          pointerEvents="none"
          data-testid={`tooth-restoration-${toothKey}-missing`}
        />
      )}
      {extracted && (
        <g
          pointerEvents="none"
          style={{ display: "none" }}
          data-testid={`tooth-restoration-${toothKey}-extracted`}
        />
      )}
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
  surface: R4SurfaceKey
) {
  return surfaceAnchorByType[toothType][surface];
}

const OdontogramToothSvg = memo(OdontogramToothSvgImpl);

export default OdontogramToothSvg;
