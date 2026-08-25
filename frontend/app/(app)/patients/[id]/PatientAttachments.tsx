"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { clearToken, getToken } from "@/lib/auth";
import { safeDocumentError } from "@/lib/document-errors";

type Actor = { id: number; email: string; role: string };

type Attachment = {
  id: number;
  patient_id: number;
  original_filename: string;
  content_type: string;
  byte_size: number;
  created_at: string;
  created_by: Actor;
};

function buildApiUrl(path: string) {
  const apiBase = (process.env.NEXT_PUBLIC_API_BASE ?? "/api").replace(/\/$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return path.startsWith("http")
    ? path
    : apiBase && (normalizedPath === apiBase || normalizedPath.startsWith(`${apiBase}/`))
      ? normalizedPath
      : `${apiBase}${normalizedPath}`;
}

function filenameFromHeader(header: string | null) {
  if (!header) return null;
  const match = /filename="([^"]+)"/.exec(header);
  return match?.[1] ?? null;
}

function sanitizeAttachmentFilename(value: string) {
  const cleaned = value.replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^[._]+|[._]+$/g, "");
  return cleaned || "attachment";
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
}

const downloadingAttachmentIds = new Set<number>();

export default function PatientAttachments({
  patientId,
  embedded = false,
  capabilities,
  capabilityError = null,
  patientArchived = false,
}: {
  patientId: number;
  embedded?: boolean;
  capabilities: string[] | null;
  capabilityError?: string | null;
  patientArchived?: boolean;
}) {
  const router = useRouter();
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [previewingId, setPreviewingId] = useState<number | null>(null);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const uploadingAttachmentRef = useRef(false);
  const previewingAttachmentRef = useRef(false);
  const deletingAttachmentRef = useRef<number | null>(null);
  const attachmentLoadRequestIdRef = useRef(0);
  const capabilitiesReady = capabilities !== null;
  const canDownload = Boolean(capabilities?.includes("documents.download"));
  const canUpload = Boolean(canDownload && capabilities?.includes("documents.upload"));
  const canDelete = Boolean(canDownload && capabilities?.includes("documents.delete"));
  const accessState = !capabilitiesReady
    ? "loading"
    : patientArchived
      ? "archived"
      : canDownload
        ? canUpload || canDelete
          ? "write"
          : "read-only"
        : "denied";

  const authFetch = useCallback((path: string, init: RequestInit = {}) => {
    const token = getToken();
    const headers = new Headers(init.headers || {});
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(buildApiUrl(path), { ...init, headers });
  }, []);

  const loadAttachments = useCallback(async () => {
    if (!capabilitiesReady || !canDownload || patientArchived) {
      setAttachments([]);
      setLoading(false);
      return;
    }
    const requestId = ++attachmentLoadRequestIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(`/api/patients/${patientId}/attachments`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(await safeDocumentError(res, "Failed to load attachments."));
      }
      const data = (await res.json()) as Attachment[];
      if (requestId !== attachmentLoadRequestIdRef.current) {
        return;
      }
      setAttachments(data);
    } catch (err) {
      if (requestId === attachmentLoadRequestIdRef.current) {
        setError(err instanceof Error ? err.message : "Failed to load attachments");
      }
    } finally {
      if (requestId === attachmentLoadRequestIdRef.current) {
        setLoading(false);
      }
    }
  }, [authFetch, canDownload, capabilitiesReady, patientArchived, patientId, router]);

  async function uploadAttachment(file: File) {
    if (!canUpload || patientArchived || uploadingAttachmentRef.current) {
      return;
    }
    uploadingAttachmentRef.current = true;
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await authFetch(`/api/patients/${patientId}/attachments`, {
        method: "POST",
        headers: { "Request-Id": crypto.randomUUID() },
        body: form,
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(await safeDocumentError(res, "Failed to upload attachment."));
      }
      const created = (await res.json()) as Attachment;
      attachmentLoadRequestIdRef.current += 1;
      setAttachments((prev) => [created, ...prev.filter((item) => item.id !== created.id)]);
      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload attachment");
    } finally {
      uploadingAttachmentRef.current = false;
      setUploading(false);
    }
  }

  function isPreviewable(attachment: Attachment) {
    if (attachment.content_type?.startsWith("image/")) return true;
    if (attachment.content_type === "application/pdf") return true;
    return attachment.original_filename.toLowerCase().endsWith(".pdf");
  }

  async function previewAttachment(attachment: Attachment) {
    if (!canDownload || patientArchived || previewingAttachmentRef.current) {
      return;
    }
    previewingAttachmentRef.current = true;
    setPreviewingId(attachment.id);
    setError(null);
    try {
      const res = await authFetch(`/api/attachments/${attachment.id}/preview`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(await safeDocumentError(res, "Failed to preview attachment."));
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to preview attachment");
    } finally {
      previewingAttachmentRef.current = false;
      setPreviewingId(null);
    }
  }

  async function downloadAttachment(
    attachment: Attachment,
    button?: HTMLButtonElement | null
  ) {
    if (
      !canDownload ||
      patientArchived ||
      !button ||
      downloadingAttachmentIds.has(attachment.id) ||
      button.disabled
    ) {
      return;
    }
    downloadingAttachmentIds.add(attachment.id);
    button.disabled = true;
    setError(null);
    setDownloadingId(attachment.id);
    try {
      const res = await authFetch(`/api/attachments/${attachment.id}/download`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(await safeDocumentError(res, "Failed to download attachment."));
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const filename =
        filenameFromHeader(res.headers.get("Content-Disposition")) ||
        attachment.original_filename;
      link.href = url;
      link.download = sanitizeAttachmentFilename(filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download attachment");
    } finally {
      downloadingAttachmentIds.delete(attachment.id);
      if (button?.isConnected) {
        button.disabled = false;
      }
      setDownloadingId(null);
    }
  }

  async function deleteAttachment(attachment: Attachment) {
    if (!canDelete || patientArchived || deletingAttachmentRef.current === attachment.id) {
      return;
    }
    if (!confirm(`Delete "${attachment.original_filename}"?`)) return;
    setError(null);
    deletingAttachmentRef.current = attachment.id;
    setDeletingId(attachment.id);
    try {
      const res = await authFetch(`/api/attachments/${attachment.id}`, { method: "DELETE" });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(await safeDocumentError(res, "Failed to delete attachment."));
      }
      setAttachments((prev) => prev.filter((item) => item.id !== attachment.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete attachment");
    } finally {
      if (deletingAttachmentRef.current === attachment.id) {
        deletingAttachmentRef.current = null;
      }
      setDeletingId((current) => (current === attachment.id ? null : current));
    }
  }

  useEffect(() => {
    void loadAttachments();
  }, [loadAttachments]);

  useEffect(() => {
    const refresh = () => void loadAttachments();
    window.addEventListener("patient-attachments-changed", refresh);
    return () => window.removeEventListener("patient-attachments-changed", refresh);
  }, [loadAttachments]);

  const content = (
    <div
      className="stack"
      data-testid="patient-attachments-access"
      data-state={accessState}
    >
        <div className="row">
          <div>
            <h4 style={{ marginTop: 0 }}>Attachments</h4>
            <div style={{ color: "var(--muted)" }}>
              Upload files for this patient (stored locally).
            </div>
          </div>
          {canUpload && !patientArchived && (
            <label className="btn btn-secondary" data-testid="attachment-upload">
              {uploading ? "Uploading..." : "Upload document"}
              <input
                type="file"
                style={{ display: "none" }}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    void uploadAttachment(file);
                  }
                  e.currentTarget.value = "";
                }}
                disabled={uploading}
              />
            </label>
          )}
        </div>

        {!capabilitiesReady && <div className="badge">Checking document permissions…</div>}
        {capabilitiesReady && capabilityError && <div className="notice">{capabilityError}</div>}
        {patientArchived && (
          <div className="notice">Archived patient attachments are unavailable.</div>
        )}
        {capabilitiesReady && !patientArchived && !canDownload && (
          <div className="notice">You do not have permission to view patient attachments.</div>
        )}
        {capabilitiesReady && canDownload && !canUpload && !patientArchived && (
          <div className="notice">Attachments are read-only.</div>
        )}
        {loading && <div className="badge">Loading attachments…</div>}
        {error && <div className="notice">{error}</div>}

        {capabilitiesReady && canDownload && !patientArchived && attachments.length === 0 && !loading ? (
          <div className="notice">
            {canUpload
              ? "No attachments yet. Use \"Upload document\" to add one."
              : "No attachments are available."}
          </div>
        ) : capabilitiesReady && canDownload && !patientArchived && attachments.length > 0 ? (
          <div className="stack" style={{ gap: 8 }}>
            {attachments.map((attachment) => (
              <div
                key={attachment.id}
                className="card"
                data-testid={`attachment-card-${attachment.id}`}
                style={{ margin: 0, display: "flex", justifyContent: "space-between", gap: 12 }}
              >
                <div>
                  <div style={{ fontWeight: 600 }}>{attachment.original_filename}</div>
                  <div style={{ color: "var(--muted)" }}>
                    {formatBytes(attachment.byte_size)} · {attachment.content_type}
                  </div>
                  <div style={{ color: "var(--muted)" }}>
                    Uploaded{" "}
                    {new Date(attachment.created_at).toLocaleString("en-GB", {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}{" "}
                    by {attachment.created_by?.email || "—"}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  {canDownload && isPreviewable(attachment) && (
                    <button
                      className="btn btn-secondary"
                      type="button"
                      onClick={() => previewAttachment(attachment)}
                      data-testid={`attachment-preview-${attachment.id}`}
                      disabled={previewingId === attachment.id}
                    >
                      {previewingId === attachment.id ? "Opening..." : "Preview"}
                    </button>
                  )}
                  {canDownload && (
                    <button
                      className="btn btn-secondary"
                      type="button"
                      onClick={(event) =>
                        void downloadAttachment(attachment, event.currentTarget)
                      }
                      data-testid={`attachment-download-${attachment.id}`}
                      disabled={downloadingId === attachment.id}
                    >
                      {downloadingId === attachment.id ? "Downloading..." : "Download"}
                    </button>
                  )}
                  {canDelete && (
                    <button
                      className="btn btn-secondary"
                      type="button"
                      onClick={() => deleteAttachment(attachment)}
                      data-testid={`attachment-delete-${attachment.id}`}
                      disabled={deletingId === attachment.id}
                    >
                      {deletingId === attachment.id ? "Deleting..." : "Delete"}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : null}
    </div>
  );

  if (embedded) {
    return content;
  }

  return (
    <div className="card" style={{ margin: 0 }}>
      {content}
    </div>
  );
}
