"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import { recallResponseError, sanitizeRecallFilename } from "@/lib/recallErrors";
import styles from "./RecallLetterDialog.module.css";

export type RecallLetterDialogProps = {
  patientId: number;
  recallId: number;
  patientName: string;
  onClose: () => void;
  onDownloaded?: () => void;
};

type LetterPreview = {
  patientId: number;
  recallId: number;
  url: string;
  filename: string;
};

class LetterPreviewError extends Error {}

const PREVIEW_ERROR = "The recall letter could not be loaded. Please try again.";
const PRINT_HELP =
  "If the print window does not open, open the PDF in a new tab and use its Print button, or download it to print.";

export default function RecallLetterDialog({
  patientId,
  recallId,
  patientName,
  onClose,
  onDownloaded,
}: RecallLetterDialogProps) {
  const router = useRouter();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const frameRef = useRef<HTMLIFrameElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  const [preview, setPreview] = useState<LetterPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [frameReady, setFrameReady] = useState(false);
  const [printNotice, setPrintNotice] = useState("");
  const [pdfViewerAvailable, setPdfViewerAvailable] = useState(false);
  const currentPreview = preview?.patientId === patientId && preview.recallId === recallId
    ? preview
    : null;

  useEffect(() => {
    const dialog = dialogRef.current;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    if (!dialog) return;
    setPdfViewerAvailable(navigator.pdfViewerEnabled === true);
    dialog.showModal();
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    return () => {
      dialog.close();
      document.body.style.overflow = previousOverflow;
      if (opener?.isConnected) opener.focus({ preventScroll: true });
    };
  }, []);

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setPreview(null);
    setFrameReady(false);
    setPrintNotice("");

    async function loadLetter() {
      try {
        const response = await apiFetch(
          `/api/patients/${patientId}/recalls/${recallId}/letter.pdf`,
          { signal: controller.signal, cache: "no-store", headers: { Accept: "application/pdf" } }
        );
        if (!active) return;
        if (response.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        if (!response.ok) {
          throw new LetterPreviewError(await recallResponseError(response, PREVIEW_ERROR));
        }

        const contentType = response.headers.get("content-type")?.split(";")[0].trim().toLowerCase();
        const blob = await response.blob();
        // Never embed an HTML error page, even if the server returned HTTP 200.
        if (contentType !== "application/pdf" || (await blob.slice(0, 5).text()) !== "%PDF-") {
          throw new LetterPreviewError("A valid PDF letter was not returned. Please try again.");
        }
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setPreview({
          patientId,
          recallId,
          url: objectUrl,
          filename: sanitizeRecallFilename(
            `recall-${patientId}-${recallId}.pdf`,
            "recall-letter.pdf"
          ),
        });
      } catch (failure) {
        if (!active || controller.signal.aborted) return;
        setError(failure instanceof LetterPreviewError ? failure.message : PREVIEW_ERROR);
      } finally {
        if (active) setLoading(false);
      }
    }

    // Deferring the request skips the discarded Strict Mode effect, so simply
    // opening the preview does not generate the same letter twice.
    queueMicrotask(() => {
      if (active) void loadLetter();
    });

    return () => {
      active = false;
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [patientId, recallId, attempt, router]);

  function downloadLetter() {
    if (!currentPreview) return;
    const link = document.createElement("a");
    link.href = currentPreview.url;
    link.download = currentPreview.filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    onDownloaded?.();
  }

  function printLetter() {
    if (!currentPreview || !frameReady) return;
    setPrintNotice(PRINT_HELP);
    try {
      const frameWindow = frameRef.current?.contentWindow;
      if (!frameWindow) return;
      frameWindow.focus();
      frameWindow.print();
    } catch {
      // Some browsers isolate their PDF viewer. The explicit open/download
      // actions remain available; never print the surrounding patient page.
    }
  }

  return (
    <dialog
      ref={dialogRef}
      className={styles.dialog}
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      data-testid="recall-letter-dialog"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className={styles.layout}>
        <header className={styles.header}>
          <div className={styles.heading}>
            <h2 id={titleId}>Recall letter</h2>
            <p className={styles.patientName}>{patientName}</p>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            className={`btn btn-secondary ${styles.close}`}
            aria-label="Close recall letter"
            onClick={onClose}
          >
            Close
          </button>
        </header>

        <p id={descriptionId} className={styles.description}>
          Preview only. Printing or downloading does not mark this recall as sent.
        </p>

        <div className={styles.previewArea} aria-busy={loading}>
          {loading && (
            <div className={styles.state} role="status" data-testid="recall-letter-loading">
              <span className={styles.documentIcon} aria-hidden="true">PDF</span>
              <p>Preparing your letter…</p>
            </div>
          )}
          {error && (
            <div className={styles.state}>
              <p className={styles.error} role="alert" data-testid="recall-letter-error">{error}</p>
              <button type="button" className="btn btn-secondary" onClick={() => setAttempt((value) => value + 1)}>
                Retry preview
              </button>
            </div>
          )}
          {currentPreview && pdfViewerAvailable && (
            <iframe
              ref={frameRef}
              className={styles.preview}
              src={currentPreview.url}
              title={`Recall letter PDF for ${patientName}`}
              data-testid="recall-letter-preview"
              onLoad={() => setFrameReady(true)}
            />
          )}
          {currentPreview && !pdfViewerAvailable && (
            <div className={styles.state} data-testid="recall-letter-browser-fallback">
              <span className={styles.documentIcon} aria-hidden="true">PDF</span>
              <p>This browser cannot display PDF previews. Download the letter to review and print it, or open it in a PDF-capable browser.</p>
            </div>
          )}
        </div>

        <footer className={styles.footer}>
          <div className={styles.fallback}>
            {currentPreview && (
              <a
                href={currentPreview.url}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.openPdf}
                data-testid="recall-letter-open-pdf"
              >
                Open PDF in new tab
              </a>
            )}
            <p className={styles.printNotice} role="status">{printNotice || (currentPreview ? "If the preview is blank, open the PDF in a new tab." : "")}</p>
          </div>
          <div className={styles.actions}>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={!currentPreview}
              onClick={downloadLetter}
              data-testid="recall-letter-download"
            >
              Download PDF
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={!currentPreview || !frameReady}
              onClick={printLetter}
              data-testid="recall-letter-print"
            >
              Print letter
            </button>
          </div>
        </footer>
      </div>
    </dialog>
  );
}
