"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";

type DocumentTemplateKind = "letter" | "prescription";

type DocumentTemplate = {
  id: number;
  name: string;
  kind: DocumentTemplateKind;
  is_active: boolean;
};

const kindLabels: Record<DocumentTemplateKind, string> = {
  letter: "Letter",
  prescription: "Prescription",
};

function filenameFromHeader(header: string | null) {
  if (!header) return null;
  const match = /filename="([^"]+)"/.exec(header);
  return match?.[1] ?? null;
}

export default function PatientDocuments() {
  const router = useRouter();
  const [templates, setTemplates] = useState<DocumentTemplate[]>([]);
  const [kindFilter, setKindFilter] = useState<"all" | DocumentTemplateKind>("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadTemplates() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (kindFilter !== "all") {
        params.set("kind", kindFilter);
      }
      const res = await apiFetch(
        `/api/document-templates${params.toString() ? `?${params.toString()}` : ""}`
      );
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load templates (HTTP ${res.status})`);
      }
      const data = (await res.json()) as DocumentTemplate[];
      setTemplates(data.filter((item) => item.is_active));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load templates");
    } finally {
      setLoading(false);
    }
  }

  async function downloadTemplate(template: DocumentTemplate) {
    setError(null);
    try {
      const res = await apiFetch(`/api/document-templates/${template.id}/download`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to download template (HTTP ${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const filename =
        filenameFromHeader(res.headers.get("Content-Disposition")) ||
        `${template.name}.txt`;
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download template");
    }
  }

  useEffect(() => {
    void loadTemplates();
  }, [kindFilter]);

  return (
    <div className="card" style={{ margin: 0 }}>
      <div className="stack">
        <div className="row">
          <div>
            <h4 style={{ marginTop: 0 }}>Documents</h4>
            <div style={{ color: "var(--muted)" }}>
              Download a letter or prescription template.
            </div>
          </div>
          <select
            className="input"
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value as "all" | DocumentTemplateKind)}
          >
            <option value="all">All kinds</option>
            <option value="letter">Letters</option>
            <option value="prescription">Prescriptions</option>
          </select>
        </div>

        {loading && <div className="badge">Loading templates…</div>}
        {error && <div className="notice">{error}</div>}

        {templates.length === 0 ? (
          <div className="notice">No active templates available.</div>
        ) : (
          <div className="stack" style={{ gap: 8 }}>
            {templates.map((template) => (
              <div
                key={template.id}
                className="card"
                style={{ margin: 0, display: "flex", justifyContent: "space-between", gap: 12 }}
              >
                <div>
                  <div style={{ fontWeight: 600 }}>{template.name}</div>
                  <div style={{ color: "var(--muted)" }}>{kindLabels[template.kind]}</div>
                </div>
                <button
                  className="btn btn-secondary"
                  type="button"
                  onClick={() => downloadTemplate(template)}
                >
                  Download
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
