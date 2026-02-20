export type R4SurfaceKey = "M" | "O" | "D" | "B" | "L" | "I";

const R4_SURFACE_NUMERIC_MAP: Record<number, R4SurfaceKey> = {
  1: "M",
  2: "O",
  3: "D",
  4: "B",
  5: "L",
  6: "I",
};

const R4_SURFACE_LETTERS = new Set<R4SurfaceKey>(["M", "O", "D", "B", "L", "I"]);

export function r4SurfaceCodeToSurfaceKey(code: number | string | null | undefined): R4SurfaceKey | null {
  if (code == null) return null;

  if (typeof code === "string") {
    const normalized = code.trim().toUpperCase();
    if (!normalized || normalized === "0") return null;
    if (R4_SURFACE_LETTERS.has(normalized as R4SurfaceKey)) {
      return normalized as R4SurfaceKey;
    }
    const parsed = Number(normalized);
    if (!Number.isInteger(parsed)) return null;
    return R4_SURFACE_NUMERIC_MAP[parsed] ?? null;
  }

  if (!Number.isFinite(code) || !Number.isInteger(code) || code === 0) return null;
  return R4_SURFACE_NUMERIC_MAP[code] ?? null;
}
