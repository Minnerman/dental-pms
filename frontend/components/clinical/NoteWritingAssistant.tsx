"use client";

import { useId, useState } from "react";
import styles from "./NoteWritingAssistant.module.css";

// Intentionally accepts no note text or patient data. No provider is approved or
// connected yet, so this control must never pretend to produce AI corrections.
export default function NoteWritingAssistant({ disabled = false }: { disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const descriptionId = useId();

  return <>
    <button type="button" className={styles.trigger} data-testid="note-writing-assistant"
      disabled={disabled} aria-label="AI writing assistance — not connected"
      title="AI writing assistance — not connected" aria-expanded={open}
      aria-controls={descriptionId} onClick={() => setOpen((value) => !value)}>
      <svg viewBox="0 0 24 24" width="21" height="21" fill="none" aria-hidden="true" focusable="false">
        <path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z" fill="currentColor" opacity=".18" />
        <path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3ZM20 2v4m-2-2h4M3 18v4m-2-2h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span>AI</span><span className={styles.connection}>Not connected</span>
    </button>
    {open && <div id={descriptionId} className={styles.explanation} data-testid="note-writing-assistant-status" role="status">
      <strong>AI writing correction is not connected yet.</strong>
      <p>No note text has been sent. An on-site model or an approved external service must be configured before suggestions can be generated.</p>
      <p>Once connected, you will review corrections before applying them to the draft. Saving a note will remain a separate step.</p>
    </div>}
  </>;
}
