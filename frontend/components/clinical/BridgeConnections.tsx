"use client";

import { useEffect, useRef, useState } from "react";

import { bridgeArchTeeth, type BridgeGroup } from "./crownDiagnosis";

type Props = { bridges: BridgeGroup[]; upper: boolean };
type MeasuredBridge = { id: number; members: string; start: string; end: string; points: string };

/** Connections are relationships from explicitly recorded groups, never guesses
 * based on adjacent crowns. An incomplete/hidden group draws no phantom line. */
export default function BridgeConnections({ bridges, upper }: Props) {
  const overlayRef = useRef<SVGSVGElement>(null);
  const [measured, setMeasured] = useState<MeasuredBridge[]>([]);

  useEffect(() => {
    const overlay = overlayRef.current;
    const grid = overlay?.parentElement;
    if (!overlay || !grid) return;
    const arch = bridgeArchTeeth(upper);
    const groups = bridges.flatMap((bridge) => {
      if (bridge.arch !== (upper ? "upper" : "lower")) return [];
      const start = arch.indexOf(bridge.span_start);
      const end = arch.indexOf(bridge.span_end);
      if (start < 0 || end <= start) return [];
      const teeth = arch.slice(start, end + 1);
      const members = new Set(bridge.members.map((member) => member.tooth));
      if (members.size !== bridge.members.length || members.size !== teeth.length
        || !teeth.every((tooth) => members.has(tooth))) return [];
      return [{ bridge, teeth }];
    });
    let frame: number | null = null;
    let disposed = false;
    const observed = new Set<Element>();
    const resizeObserver = new ResizeObserver(() => scheduleMeasure());

    const measure = () => {
      frame = null;
      if (disposed) return;
      const overlayMatrix = overlay.getScreenCTM();
      const overlayBox = overlay.getBoundingClientRect();
      const next: MeasuredBridge[] = [];
      const targets = new Set<Element>([grid]);
      if (overlayMatrix && overlayBox.width > 0 && overlayBox.height > 0) {
        const inverse = overlayMatrix.inverse();
        for (const { bridge, teeth } of groups) {
          const points: string[] = [];
          for (const tooth of teeth) {
            // Tooth IDs were validated against the fixed arch above, so this
            // selector cannot contain user text or reach outside this arch.
            const crown = grid.querySelector<SVGPathElement>(`[data-testid="tooth-crown-${tooth}"]`);
            if (!crown) break;
            targets.add(crown);
            if (crown.ownerSVGElement) targets.add(crown.ownerSVGElement);
            const matrix = crown.getScreenCTM();
            const box = crown.getBoundingClientRect();
            const visibility = getComputedStyle(crown).visibility;
            if (!matrix || box.width <= 0 || box.height <= 0 || crown.getClientRects().length === 0
              || visibility === "hidden" || visibility === "collapse") break;
            const bounds = crown.getBBox();
            const point = new DOMPoint(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2)
              .matrixTransform(matrix).matrixTransform(inverse);
            if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) break;
            points.push(`${point.x.toFixed(3)},${point.y.toFixed(3)}`);
          }
          if (points.length === teeth.length) next.push({
            id: bridge.id, members: teeth.join(","), start: bridge.span_start,
            end: bridge.span_end, points: points.join(" "),
          });
        }
      }
      for (const target of observed) {
        if (!targets.has(target)) {
          resizeObserver.unobserve(target);
          observed.delete(target);
        }
      }
      for (const target of targets) {
        if (!observed.has(target)) {
          resizeObserver.observe(target);
          observed.add(target);
        }
      }
      setMeasured((previous) => previous.length === next.length && previous.every((item, index) => {
        const value = next[index];
        return item.id === value.id && item.members === value.members && item.start === value.start
          && item.end === value.end && item.points === value.points;
      }) ? previous : next);
    };
    function scheduleMeasure() {
      if (!disposed && frame === null) frame = requestAnimationFrame(measure);
    }
    const mutations = new MutationObserver((records) => {
      if (records.some((record) => record.target !== overlay && !overlay.contains(record.target))) scheduleMeasure();
    });
    mutations.observe(grid, {
      subtree: true, childList: true, attributes: true,
      attributeFilter: ["d", "transform", "viewBox", "width", "height", "class", "style", "hidden"],
    });
    resizeObserver.observe(grid);
    observed.add(grid);
    window.addEventListener("resize", scheduleMeasure);
    window.addEventListener("scroll", scheduleMeasure, true);
    scheduleMeasure();
    return () => {
      disposed = true;
      if (frame !== null) cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      mutations.disconnect();
      window.removeEventListener("resize", scheduleMeasure);
      window.removeEventListener("scroll", scheduleMeasure, true);
    };
  }, [bridges, upper]);

  return <svg ref={overlayRef} aria-hidden="true" focusable="false"
    data-testid={`clinical-bridge-connections-${upper ? "upper" : "lower"}`}
    width="100%" height="100%"
    style={{ position: "absolute", inset: 0, width: "100%", height: "100%", overflow: "visible", pointerEvents: "none", zIndex: 2 }}>
    {measured.filter((value) => bridges.some((bridge) => bridge.id === value.id
      && bridge.arch === (upper ? "upper" : "lower") && bridge.span_start === value.start
      && bridge.span_end === value.end)).map((bridge) => <g key={bridge.id} data-testid={`clinical-bridge-${bridge.id}`}
      data-members={bridge.members} data-span-start={bridge.start} data-span-end={bridge.end}>
      <polyline points={bridge.points} fill="none" stroke="#fff6e8" strokeWidth="8"
        strokeLinecap="round" strokeLinejoin="round" />
      <polyline points={bridge.points} fill="none" stroke="#171717" strokeWidth="5"
        strokeLinecap="round" strokeLinejoin="round" />
    </g>)}
  </svg>;
}
