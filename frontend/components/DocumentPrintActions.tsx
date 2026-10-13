"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/auth";

export default function DocumentPrintActions({ documentId, kind, canRecord }: {
  documentId: number; kind: string; canRecord: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [emailReady, setEmailReady] = useState(false);
  const requestKeys = useRef<{print?: string; email?: string}>({});
  const lock = useRef(false);
  useEffect(() => {
    let active = true;
    if (canRecord && kind === "recall") void apiFetch("/api/document-delivery-settings")
      .then(async res => { if (res.ok && active) setEmailReady((await res.json()).recall_email_ready); })
      .catch(() => {});
    return () => { active = false; };
  }, [canRecord, kind]);
  async function prepare(method: "print" | "email") {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError("");
    requestKeys.current[method] ??= crypto.randomUUID();
    try {
      const response = await apiFetch(`/api/patient-documents/${documentId}/copies`, {
        method: "POST", headers: { "Request-Id": requestKeys.current[method]! }, body: JSON.stringify({ method }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(typeof data.detail === "string" && response.status < 500 ? data.detail : "Could not prepare the document. Please retry.");
      }
      const copy = await response.json();
      router.push(`/document-copies/${copy.id}`);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not prepare the document."); }
    finally { lock.current = false; setBusy(false); }
  }
  if (!canRecord) return null;
  return <div className="stack" style={{ gap: 6 }}>
    <div className="row">
      <button className="btn btn-primary" disabled={busy} onClick={() => void prepare("print")}
        data-testid={`document-print-${documentId}`}>{busy ? "Preparing…" : "Print & record"}</button>
      {kind === "recall" && <button className="btn btn-secondary" disabled={busy || !emailReady}
        title={emailReady ? "Review the recipient and letter before sending" : "Email is switched off. Print recalls for now."}
        onClick={() => void prepare("email")}>Email recall{emailReady ? "" : " (off)"}</button>}
    </div>
    {error && <div role="alert" className="notice">{error}</div>}
  </div>;
}
