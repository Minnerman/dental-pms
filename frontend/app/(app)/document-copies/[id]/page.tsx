"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/auth";

type Copy = { id: number; patient_id: number; title: string; document_kind: string;
  method: string; status: string; recipient: string | null; sender: string | null };

export default function DocumentCopyPage() {
  const { id } = useParams<{id: string}>();
  const [copy, setCopy] = useState<Copy | null>(null);
  const [pdf, setPdf] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [canRecord, setCanRecord] = useState(false);
  const [pdfLoaded, setPdfLoaded] = useState(false);
  const [printOpened, setPrintOpened] = useState(false);
  const lock = useRef(false);
  const frame = useRef<HTMLIFrameElement>(null);
  useEffect(() => {
    let active = true; let objectUrl = "";
    setCopy(null); setPdf(""); setError(""); setPrintOpened(false); setPdfLoaded(false);
    void (async () => {
      try {
        const [metadata, content, me] = await Promise.all([
          apiFetch(`/api/document-copies/${id}`), apiFetch(`/api/document-copies/${id}/pdf`), apiFetch("/api/me/capabilities"),
        ]);
        if (!metadata.ok || !content.ok) throw new Error("This saved document is unavailable or you do not have permission to view it.");
        const data = await metadata.json();
        const capabilities = me.ok ? await me.json() : [];
        objectUrl = URL.createObjectURL(await content.blob());
        if (!active) { URL.revokeObjectURL(objectUrl); return; }
        setCopy(data); setPdf(objectUrl);
        setCanRecord(capabilities.includes("notes.write") && capabilities.includes("documents.download"));
      } catch (err) { if (active) setError(err instanceof Error ? err.message : "Could not load document."); }
    })();
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [id]);
  async function complete() {
    if (!copy || lock.current) return;
    lock.current = true; setBusy(true); setError("");
    try {
      const result = await apiFetch(`/api/document-copies/${copy.id}/${copy.method === "print" ? "confirm-print" : "send-email"}`, { method: "POST" });
      if (!result.ok) {
        const data = await result.json().catch(() => ({}));
        throw new Error(typeof data.detail === "string" ? data.detail : "Could not record the document. Refresh to check its status before retrying.");
      }
      setCopy(await result.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not record document.");
      // Refresh durable state after an uncertain response; never offer an automatic email retry.
      const response = await apiFetch(`/api/document-copies/${copy.id}`).catch(() => null);
      if (response?.ok) setCopy(await response.json());
    } finally { lock.current = false; setBusy(false); }
  }
  return <div className="stack">
    <h1>{copy?.title ?? "Saved document"}</h1>
    {error && <div className="notice" role="alert">{error}</div>}
    {copy && <>
      <Link href={`/patients/${copy.patient_id}/documents`}>Back to patient documents</Link>
      {copy.document_kind === "prescription" && <p>Print and sign in ink. This saved copy does not contain the handwritten signature.</p>}
      {copy.status === "prepared" && canRecord && <div className="card stack">
        {copy.method === "print" ? <>
          <p>Print the PDF below, then confirm it printed successfully to add the clinical-note entry. If you cancel printing, leave without confirming.</p>
          <div className="row">
            <button className="btn btn-secondary" disabled={!pdfLoaded || busy} onClick={() => {
              setPrintOpened(true);
              try { frame.current?.contentWindow?.focus(); frame.current?.contentWindow?.print(); }
              catch { setError("Use the PDF toolbar to print, then confirm below."); }
            }} data-testid="open-print-dialog">Print PDF</button>
            <button className="btn btn-primary" disabled={busy || !pdf || !printOpened} onClick={() => void complete()}
              data-testid="confirm-document-print">{busy ? "Recording…" : "Printed — add clinical note"}</button>
          </div>
        </> : <>
          <p>From: {copy.sender}<br />To: {copy.recipient}</p>
          <p>The PDF below will be attached to the recall email.</p>
          <button className="btn btn-primary" disabled={busy || !pdf} onClick={() => void complete()}>Send recall email & record</button>
        </>}
      </div>}
      {["printed", "sent"].includes(copy.status) && <div role="status" className="badge">
        {copy.status === "printed" ? "Printed and recorded in clinical notes." : "Accepted by the mail server and recorded in clinical notes."}
      </div>}
      {["sending", "uncertain"].includes(copy.status) && <p role="alert">Email outcome is unconfirmed. Check the mail service before sending another copy.</p>}
    </>}
    {pdf && <div className="row">
      <a className="btn btn-secondary" href={pdf} target="_blank" rel="noreferrer" onClick={() => setPrintOpened(true)}>Open PDF in a new tab</a>
      <a className="btn btn-secondary" href={pdf} download={`document-copy-${id}.pdf`} onClick={() => setPrintOpened(true)}>Download saved PDF</a>
      <span>If the preview is unavailable, open or download this saved copy to print it.</span>
    </div>}
    {pdf && <iframe onLoad={() => setPdfLoaded(true)} ref={frame} src={pdf} title="Saved document PDF" style={{ width: "100%", height: "75vh", border: "1px solid var(--border)" }} />}
  </div>;
}
