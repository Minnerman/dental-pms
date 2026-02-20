import { memo } from "react";

import type { R4SurfaceKey } from "@/lib/charting/r4SurfaceCodeToSurfaceKey";

export type OdontogramToothType = "incisor" | "canine" | "premolar" | "molar";

type SurfaceShape = {
  key: R4SurfaceKey;
  points: string;
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

type Props = {
  toothKey: string;
  toothType: OdontogramToothType;
  selectedSurface?: R4SurfaceKey | null;
  active?: boolean;
  onSurfaceClick?: (surface: R4SurfaceKey) => void;
};

function OdontogramToothSvgImpl({
  toothKey,
  toothType,
  selectedSurface = null,
  active = false,
  onSurfaceClick,
}: Props) {
  const surfaces = surfaceShapesByToothType[toothType];
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
        return (
          <polygon
            key={`${toothKey}-${surface.key}`}
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
        );
      })}
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
