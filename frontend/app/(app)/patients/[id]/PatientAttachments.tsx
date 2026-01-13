"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken, getToken } from "@/lib/auth";

type Attachment = {
  id: number;
  patient_id: number;
  original_filename: string;
  content_type: string;
  byte_size: number;
  created_at: string;
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

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
}

export default function PatientAttachments({
  patientId,
  embedded = false,
}: {
  patientId: number;
  embedded?: boolean;
}) {
  const router = useRouter();
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSuperadmin, setIsSuperadmin] = useState(false);

  async function authFetch(path: string, init: RequestInit = {}) {
    const token = getToken();
    const headers = new Headers(init.headers || {});
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(buildApiUrl(path), { ...init, headers });
  }

  async function loadAttachments() {
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
        throw new Error(`Failed to load attachments (HTTP ${res.status})`);
      }
      const data = (await res.json()) as Attachment[];
      setAttachments(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load attachments");
    } finally {
      setLoading(false);
    }
  }

  async function loadMe() {
    try {
      const res = await apiFetch("/api/me");
      if (res.status === 401 || res.status === 403) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) return;
      const data = (await res.json()) as { role: string };
      setIsSuperadmin(data.role === "superadmin");
    } catch {
      setIsSuperadmin(false);
    }
  }

  async function uploadAttachment(file: File) {
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await authFetch(`/api/patients/${patientId}/attachments`, {
        method: "POST",
        body: form,
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to upload attachment (HTTP ${res.status})`);
      }
      await loadAttachments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload attachment");
    } finally {
      setUploading(false);
    }
  }

  async function downloadAttachment(attachment: Attachment) {
    setError(null);
    try {
      const res = await authFetch(`/api/attachments/${attachment.id}/download`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to download attachment (HTTP ${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const filename =
        filenameFromHeader(res.headers.get("Content-Disposition")) ||
        attachment.original_filename;
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download attachment");
    }
  }

  async function deleteAttachment(attachment: Attachment) {
    if (!confirm(`Delete "${attachment.original_filename}"?`)) return;
    setError(null);
    try {
      const res = await authFetch(`/api/attachments/${attachment.id}`, { method: "DELETE" });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.status === 403) {
        setError("You don't have permission to do that. Please ask an administrator.");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to delete attachment (HTTP ${res.status})`);
      }
      setAttachments((prev) => prev.filter((item) => item.id !== attachment.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete attachment");
    }
  }

  useEffect(() => {
    void loadAttachments();
  }, [patientId]);

  useEffect(() => {
    void loadMe();
  }, []);

  const content = (
    <div className="stack">
        <div className="row">
          <div>
            <h4 style={{ marginTop: 0 }}>Attachments</h4>
            <div style={{ color: "var(--muted)" }}>
              Upload files for this patient (stored locally).
            </div>
          </div>
          <label className="btn btn-secondary">
            {uploading ? "Uploading..." : "Upload file"}
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
        </div>

        {loading && <div className="badge">Loading attachments…</div>}
        {error && <div className="notice">{error}</div>}

        {attachments.length === 0 ? (
          <div className="notice">No attachments yet. Use \"Upload file\" to add one.</div>
        ) : (
          <div className="stack" style={{ gap: 8 }}>
            {attachments.map((attachment) => (
              <div
                key={attachment.id}
                className="card"
                style={{ margin: 0, display: "flex", justifyContent: "space-between", gap: 12 }}
              >
                <div>
                  <div style={{ fontWeight: 600 }}>{attachment.original_filename}</div>
                  <div style={{ color: "var(--muted)" }}>
                    {formatBytes(attachment.byte_size)} ·{" "}
                    {new Date(attachment.created_at).toLocaleDateString("en-GB")}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    onClick={() => downloadAttachment(attachment)}
                  >
                    Download
                  </button>
                  {isSuperadmin && (
                    <button
                      className="btn btn-secondary"
                      type="button"
                      onClick={() => deleteAttachment(attachment)}
                    >
                      Delete
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
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
