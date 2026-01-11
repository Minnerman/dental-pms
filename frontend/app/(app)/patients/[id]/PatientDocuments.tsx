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

type PatientDocument = {
  id: number;
  template_id?: number | null;
  title: string;
  rendered_content: string;
  created_at: string;
};

const mergeFields = [
  { label: "Patient first name", value: "{{patient.first_name}}" },
  { label: "Patient last name", value: "{{patient.last_name}}" },
  { label: "Patient full name", value: "{{patient.full_name}}" },
  { label: "Patient DOB", value: "{{patient.dob}}" },
  { label: "Patient email", value: "{{patient.email}}" },
  { label: "Patient phone", value: "{{patient.phone}}" },
  { label: "Patient address", value: "{{patient.address}}" },
  { label: "Patient address line 1", value: "{{patient.address_line1}}" },
  { label: "Patient address line 2", value: "{{patient.address_line2}}" },
  { label: "Patient city", value: "{{patient.city}}" },
  { label: "Patient postcode", value: "{{patient.postcode}}" },
  { label: "Patient NHS number", value: "{{patient.nhs_number}}" },
  { label: "Patient category", value: "{{patient.category}}" },
  { label: "Patient care setting", value: "{{patient.care_setting}}" },
  { label: "Patient Denplan member", value: "{{patient.denplan_member_no}}" },
  { label: "Patient Denplan plan", value: "{{patient.denplan_plan_name}}" },
  { label: "Recall due date", value: "{{patient.recall_due_date}}" },
  { label: "Recall status", value: "{{patient.recall_status}}" },
  { label: "Practice name", value: "{{practice.name}}" },
  { label: "Practice address", value: "{{practice.address}}" },
  { label: "Practice address line 1", value: "{{practice.address_line1}}" },
  { label: "Practice website", value: "{{practice.website}}" },
  { label: "Practice phone", value: "{{practice.phone}}" },
  { label: "Today", value: "{{today}}" },
];

const kindLabels: Record<DocumentTemplateKind, string> = {
  letter: "Letter",
  prescription: "Prescription",
};

function filenameFromHeader(header: string | null) {
  if (!header) return null;
  const match = /filename="([^"]+)"/.exec(header);
  return match?.[1] ?? null;
}

export default function PatientDocuments({ patientId }: { patientId: string }) {
  const router = useRouter();
  const [templates, setTemplates] = useState<DocumentTemplate[]>([]);
  const [documents, setDocuments] = useState<PatientDocument[]>([]);
  const [kindFilter, setKindFilter] = useState<"all" | DocumentTemplateKind>("all");
  const [loading, setLoading] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [selectedField, setSelectedField] = useState(mergeFields[0].value);
  const [unknownFields, setUnknownFields] = useState<string[]>([]);
  const [attachNotice, setAttachNotice] = useState<string | null>(null);

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

  async function loadDocuments() {
    setLoadingDocs(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/documents`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load documents (HTTP ${res.status})`);
      }
      const data = (await res.json()) as PatientDocument[];
      setDocuments(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoadingDocs(false);
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

  async function previewDocument() {
    if (!selectedTemplateId) {
      setError("Select a template to preview.");
      return;
    }
    setPreviewing(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/documents/preview`, {
        method: "POST",
        body: JSON.stringify({
          template_id: selectedTemplateId,
          title: title || null,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to preview document (HTTP ${res.status})`);
      }
      const data = (await res.json()) as {
        title: string;
        rendered_content: string;
        unknown_fields?: string[];
      };
      setPreview(data.rendered_content);
      setUnknownFields(data.unknown_fields ?? []);
      if (!title) {
        setTitle(data.title);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to preview document");
    } finally {
      setPreviewing(false);
    }
  }

  async function saveDocument() {
    if (!selectedTemplateId) {
      setError("Select a template to save.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/documents`, {
        method: "POST",
        body: JSON.stringify({
          template_id: selectedTemplateId,
          title: title || null,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to save document (HTTP ${res.status})`);
      }
      setPreview(null);
      setUnknownFields([]);
      setTitle("");
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save document");
    } finally {
      setSaving(false);
    }
  }

  async function downloadDocument(doc: PatientDocument) {
    setError(null);
    try {
      const res = await apiFetch(`/api/patient-documents/${doc.id}/download`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to download document (HTTP ${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const filename =
        filenameFromHeader(res.headers.get("Content-Disposition")) || `${doc.title}.txt`;
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download document");
    }
  }

  async function downloadDocumentPdf(doc: PatientDocument) {
    setError(null);
    try {
      const res = await apiFetch(`/api/patient-documents/${doc.id}/download?format=pdf`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to download PDF (HTTP ${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const filename =
        filenameFromHeader(res.headers.get("Content-Disposition")) || `${doc.title}.pdf`;
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download PDF");
    }
  }

  async function attachDocumentPdf(doc: PatientDocument) {
    setError(null);
    setAttachNotice(null);
    try {
      const res = await apiFetch(`/api/patient-documents/${doc.id}/attach-pdf`, {
        method: "POST",
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to attach PDF (HTTP ${res.status})`);
      }
      setAttachNotice("PDF saved to attachments.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to attach PDF");
    }
  }

  async function deleteDocument(doc: PatientDocument) {
    if (!confirm(`Delete "${doc.title}"?`)) return;
    setError(null);
    try {
      const res = await apiFetch(`/api/patient-documents/${doc.id}`, { method: "DELETE" });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to delete document (HTTP ${res.status})`);
      }
      setDocuments((prev) => prev.filter((item) => item.id !== doc.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete document");
    }
  }

  useEffect(() => {
    void loadTemplates();
  }, [kindFilter]);

  useEffect(() => {
    void loadDocuments();
  }, [patientId]);

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
        {attachNotice && <div className="badge">{attachNotice}</div>}

        <div className="card" style={{ margin: 0 }}>
          <div className="stack">
            <h4 style={{ marginTop: 0 }}>Generate document</h4>
            <div className="grid grid-2">
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Template</label>
                <select
                  className="input"
                  value={selectedTemplateId ?? ""}
                  onChange={(e) => {
                    const value = e.target.value ? Number(e.target.value) : null;
                    setSelectedTemplateId(value);
                    setPreview(null);
                    setUnknownFields([]);
                  }}
                >
                  <option value="">Select a template</option>
                  {templates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name} ({kindLabels[template.kind]})
                    </option>
                  ))}
                </select>
              </div>
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Title (optional)</label>
                <input
                  className="input"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>
            </div>
            <div className="row" style={{ alignItems: "flex-end" }}>
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Insert field</label>
                <select
                  className="input"
                  value={selectedField}
                  onChange={(e) => setSelectedField(e.target.value)}
                >
                  {mergeFields.map((field) => (
                    <option key={field.value} value={field.value}>
                      {field.label}
                    </option>
                  ))}
                </select>
              </div>
              <button
                className="btn btn-secondary"
                type="button"
                onClick={() => {
                  setTitle((prev) => (prev ? `${prev} ${selectedField}` : selectedField));
                }}
              >
                Insert
              </button>
            </div>
            <div className="row">
              <button className="btn btn-secondary" type="button" onClick={previewDocument}>
                {previewing ? "Rendering..." : "Preview"}
              </button>
              <button className="btn btn-primary" type="button" onClick={saveDocument}>
                {saving ? "Saving..." : "Save document"}
              </button>
            </div>
            {unknownFields.length > 0 && (
              <div className="notice">
                Unknown fields: {unknownFields.join(", ")}.
              </div>
            )}
            {preview && (
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Preview</label>
                <textarea className="input" rows={8} value={preview} readOnly />
              </div>
            )}
          </div>
        </div>

        <div className="card" style={{ margin: 0 }}>
          <div className="stack">
            <h4 style={{ marginTop: 0 }}>Generated documents</h4>
            {loadingDocs && <div className="badge">Loading documents…</div>}
            {documents.length === 0 && !loadingDocs ? (
              <div className="notice">No documents generated yet.</div>
            ) : (
              <div className="stack" style={{ gap: 8 }}>
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="card"
                    style={{ margin: 0, display: "flex", justifyContent: "space-between", gap: 12 }}
                  >
                    <div>
                      <div style={{ fontWeight: 600 }}>{doc.title}</div>
                      <div style={{ color: "var(--muted)" }}>
                        {new Date(doc.created_at).toLocaleDateString("en-GB")}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        onClick={() => downloadDocument(doc)}
                      >
                        Download text
                      </button>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        onClick={() => downloadDocumentPdf(doc)}
                      >
                        Download PDF
                      </button>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        onClick={() => attachDocumentPdf(doc)}
                      >
                        Save PDF to attachments
                      </button>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        onClick={() => deleteDocument(doc)}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

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
