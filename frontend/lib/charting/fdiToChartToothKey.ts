export type ChartToothQuadrant = "UR" | "UL" | "LL" | "LR";

export type FdiChartToothKey = {
  quadrant: ChartToothQuadrant;
  position: number;
  key: string;
};

const QUADRANT_TO_CHART_KEY: Record<number, ChartToothQuadrant> = {
  1: "UR",
  2: "UL",
  3: "LL",
  4: "LR",
};

export function fdiToChartToothKey(fdi: number): FdiChartToothKey | null {
  if (!Number.isInteger(fdi)) return null;
  const quadrant = Math.floor(fdi / 10);
  const position = fdi % 10;
  if (position < 1 || position > 8) return null;
  const chartQuadrant = QUADRANT_TO_CHART_KEY[quadrant];
  if (!chartQuadrant) return null;
  return {
    quadrant: chartQuadrant,
    position,
    key: `${chartQuadrant}${position}`,
  };
}
