import { memo } from "react";

import type { R4SurfaceKey } from "@/lib/charting/r4SurfaceCodeToSurfaceKey";

export type OdontogramToothType = "incisor" | "canine" | "premolar" | "molar";
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

type NormalizedRestoration = {
  type: NormalizedRestorationType;
  surfaces: R4SurfaceKey[];
  meta?: Record<string, unknown>;
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
  const availableSurfaceKeys = new Set<R4SurfaceKey>(surfaces.map((surface) => surface.key));
  const normalizedRestorations = restorations
    .map((restoration): NormalizedRestoration => ({
      type: normalizeRestorationType(restoration.type),
      surfaces: normalizeSurfaces(restoration.surfaces).filter((surface) =>
        availableSurfaceKeys.has(surface)
      ),
      meta: restoration.meta,
    }))
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
  const extractedState = extracted || extractionFromRestoration;
  const stateDominant = missing || extractedState;
  const isUpperArch = toothKey.startsWith("U");

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
        fill={active ? "rgba(51, 255, 180, 0.12)" : "rgba(255, 255, 255, 0.82)"}
        stroke="rgba(17, 24, 39, 0.55)"
        strokeWidth={2}
      />

      {surfaces.map((surface) => {
        const isSelected = selectedSurface === surface.key;
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
                onSurfaceClick?.(surface.key);
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
          d={toothOutlinePath[toothType]}
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
          d={toothOutlinePath[toothType]}
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
          d={toothOutlinePath[toothType]}
          fill="rgba(255, 255, 255, 0.66)"
          stroke="none"
          pointerEvents="none"
        />
      )}

      {missing && (
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
