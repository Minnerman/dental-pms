"use client";

import { type CSSProperties, type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import styles from "./ClinicalNotesWorkspace.module.css";

const preferenceKey = "dental-pms:clinical-notes-layout:v1";
const minimumWidth = 280;
const maximumWidth = 600;

type Props = {
  children: ReactNode;
  sidebar: (close: () => void) => ReactNode;
  revealKey?: number;
  saving?: boolean;
};

export default function ClinicalNotesWorkspace({ children, sidebar, revealKey = 0, saving = false }: Props) {
  const [open, setOpen] = useState(true);
  const [width, setWidth] = useState(360);
  const [ready, setReady] = useState(false);
  const [resizing, setResizing] = useState(false);
  const [widthLimit, setWidthLimit] = useState(maximumWidth);
  const [stickyTop, setStickyTop] = useState(12);
  const container = useRef<HTMLDivElement>(null);
  const showButton = useRef<HTMLButtonElement>(null);
  const pointer = useRef<{ id: number; x: number; width: number } | null>(null);
  const lastReveal = useRef(revealKey);

  const boundWidth = useCallback((value: number) => {
    const available = container.current?.clientWidth ?? 1200;
    return Math.max(minimumWidth, Math.min(maximumWidth, Math.floor(available * 0.48), value));
  }, []);

  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(preferenceKey) ?? "null");
      if (stored && typeof stored.open === "boolean") setOpen(stored.open);
      if (stored && Number.isFinite(stored.width)) setWidth(boundWidth(stored.width));
    } catch { /* Layout preferences are optional; no patient data is stored. */ }
    setReady(true);
  }, [boundWidth]);

  useEffect(() => {
    if (!ready) return;
    try { localStorage.setItem(preferenceKey, JSON.stringify({ open, width })); } catch { /* Keep working without browser storage. */ }
  }, [open, ready, width]);

  useEffect(() => {
    if (revealKey === lastReveal.current) return;
    lastReveal.current = revealKey;
    setOpen(true);
  }, [revealKey]);

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const header = document.querySelector<HTMLElement>('[data-testid="patient-header-card"]');
    const measure = () => {
      setWidth((current) => boundWidth(current));
      setWidthLimit(boundWidth(maximumWidth));
      setStickyTop(header && getComputedStyle(header).position === "sticky" ? Math.ceil(header.getBoundingClientRect().height) + 20 : 12);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    if (header) observer.observe(header);
    measure();
    return () => observer.disconnect();
  }, [boundWidth]);

  const close = useCallback(() => {
    if (saving) return;
    setOpen(false);
    requestAnimationFrame(() => showButton.current?.focus());
  }, [saving]);

  return (
    <div ref={container} className={`${styles.workspace} ${open ? styles.open : styles.closed}`}
      style={{ "--clinical-notes-width": `${width}px`, "--clinical-notes-top": `${stickyTop}px` } as CSSProperties}
      data-testid="clinical-notes-workspace" data-notes-open={open}>
      {!open && <div className={styles.reopen}>
        <button ref={showButton} type="button" className="btn btn-secondary"
          data-testid="clinical-notes-toggle" aria-expanded={false} aria-controls="clinical-notes-sidebar"
          onClick={() => setOpen(true)}>Show clinical notes</button>
      </div>}
      <div className={styles.chart}>{children}</div>
      <div role="separator" aria-label="Resize clinical notes" aria-orientation="vertical"
        aria-valuemin={minimumWidth} aria-valuemax={widthLimit} aria-valuenow={width}
        aria-valuetext={`${width} pixels wide`} tabIndex={open ? 0 : -1}
        hidden={!open} className={`${styles.resize} ${resizing ? styles.resizing : ""}`}
        data-testid="clinical-notes-resize"
        onKeyDown={(event) => {
          if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
          event.preventDefault();
          setWidth((current) => boundWidth(event.key === "Home" ? minimumWidth
            : event.key === "End" ? maximumWidth : current + (event.key === "ArrowLeft" ? 20 : -20)));
        }}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          event.preventDefault();
          event.currentTarget.setPointerCapture(event.pointerId);
          pointer.current = { id: event.pointerId, x: event.clientX, width };
          setResizing(true);
        }}
        onPointerMove={(event) => {
          const start = pointer.current;
          if (!start || start.id !== event.pointerId) return;
          setWidth(boundWidth(start.width + start.x - event.clientX));
        }}
        onPointerUp={(event) => {
          if (pointer.current?.id !== event.pointerId) return;
          pointer.current = null;
          setResizing(false);
          if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
        }}
        onPointerCancel={() => { pointer.current = null; setResizing(false); }}
        onLostPointerCapture={() => { pointer.current = null; setResizing(false); }} />
      <aside id="clinical-notes-sidebar" aria-label="Patient clinical notes" hidden={!open} className={styles.sidebar}>
        {sidebar(close)}
      </aside>
    </div>
  );
}
