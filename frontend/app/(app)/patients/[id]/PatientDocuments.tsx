"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import { safeDocumentError } from "@/lib/document-errors";
import {
  emptyPrescription, prescriptionInputs, PrescriptionDetails, PrescriptionTemplate,
} from "@/lib/prescriptions";

type DocumentTemplateKind = "letter" | "prescription";

type DocumentTemplate = {
  id: number;
  name: string;
  kind: DocumentTemplateKind;
  is_active: boolean;
  content?: string;
};

type PatientDocument = {
  id: number;
  template_id?: number | null;
  attachment_id?: number | null;
  title: string;
  rendered_content: string;
  created_at: string;
  created_by?: {
    email?: string | null;
  } | null;
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
  { label: "Recall type", value: "{{patient.recall_type}}" },
  { label: "Recall due date (recall.*)", value: "{{recall.due_date}}" },
  { label: "Recall status (recall.*)", value: "{{recall.status}}" },
  { label: "Recall type (recall.*)", value: "{{recall.type}}" },
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

const downloadingPatientDocumentTextIds = new Set<number>();
const downloadingPatientDocumentPdfIds = new Set<number>();
const attachingPatientDocumentPdfIds = new Set<number>();
const deletingPatientDocumentIds = new Set<number>();
const downloadingTemplateIds = new Set<number>();

function filenameFromHeader(header: string | null) {
  if (!header) return null;
  const match = /filename="([^"]+)"/.exec(header);
  return match?.[1] ?? null;
}

function sanitizeTemplateFilename(value: string) {
  const cleaned = value.replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^[._]+|[._]+$/g, "");
  return cleaned || "template";
}

function buildTemplateDownloadFilename(template: DocumentTemplate) {
  return `${sanitizeTemplateFilename(template.name)}-${template.kind}.txt`;
}

function sanitizePatientDocumentFilename(value: string) {
  const cleaned = value.replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^[._]+|[._]+$/g, "");
  return cleaned || "document";
}

function dateSuffixFromHeader(header: string | null) {
  if (!header) return null;
  const parsed = new Date(header);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString().slice(0, 10);
}

function buildPatientDocumentDownloadFilename(
  doc: PatientDocument,
  patientLastName: string | null | undefined,
  extension: "txt" | "pdf",
  responseDateHeader: string | null
) {
  const safeTitle = sanitizePatientDocumentFilename(doc.title);
  const safePatientName = sanitizePatientDocumentFilename(patientLastName || "patient");
  const dateSuffix = dateSuffixFromHeader(responseDateHeader) ?? new Date().toISOString().slice(0, 10);
  return `${safeTitle}_${safePatientName}_${dateSuffix}.${extension}`;
}

function formatDocumentCreatedAt(value: string) {
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function PatientDocuments({
  patientId,
  patientLastName,
  embedded = false,
  capabilities,
  capabilityError = null,
  patientArchived = false,
}: {
  patientId: string;
  patientLastName?: string | null;
  embedded?: boolean;
  capabilities: string[] | null;
  capabilityError?: string | null;
  patientArchived?: boolean;
}) {
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
  const [prescription, setPrescription] = useState<PrescriptionDetails>(emptyPrescription);
  const [prescriptionTemplates, setPrescriptionTemplates] = useState<PrescriptionTemplate[]>([]);
  const [prescriptionTemplateId, setPrescriptionTemplateId] = useState("");
  const [prescriptionTemplatesError, setPrescriptionTemplatesError] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [selectedField, setSelectedField] = useState(mergeFields[0].value);
  const [unknownFields, setUnknownFields] = useState<string[]>([]);
  const [attachNotice, setAttachNotice] = useState<string | null>(null);
  const [downloadingDocumentTextId, setDownloadingDocumentTextId] = useState<number | null>(null);
  const [downloadingDocumentPdfId, setDownloadingDocumentPdfId] = useState<number | null>(null);
  const [attachingDocumentPdfId, setAttachingDocumentPdfId] = useState<number | null>(null);
  const [deletingDocumentId, setDeletingDocumentId] = useState<number | null>(null);
  const [downloadingTemplateId, setDownloadingTemplateId] = useState<number | null>(null);
  const previewingDocumentRef = useRef(false);
  const savingDocumentRef = useRef(false);
  const draftVersionRef = useRef(0);
  const selectedTemplate = templates.find((template) => template.id === selectedTemplateId);
  const isTypedPrescription = selectedTemplate?.kind === "prescription" &&
    /\{\{\s*prescription\./.test(selectedTemplate.content ?? "");
  const documentBusy = previewing || saving;

  function clearPreview() {
    draftVersionRef.current += 1;
    setPreview(null);
    setUnknownFields([]);
  }

  function validatePrescription() {
    if (!isTypedPrescription) return true;
    const missing = prescriptionInputs.find((input) => !prescription[input.key].trim());
    if (missing) {
      setError(`Enter ${missing.label.toLowerCase()} before previewing or saving.`);
      return false;
    }
    return true;
  }
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

  const loadTemplates = useCallback(async () => {
    if (!capabilitiesReady || !canDownload || patientArchived) {
      setTemplates([]);
      setLoading(false);
      return;
    }
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
        throw new Error(await safeDocumentError(res, "Failed to load templates."));
      }
      const data = (await res.json()) as DocumentTemplate[];
      setTemplates(data.filter((item) => item.is_active));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load templates");
    } finally {
      setLoading(false);
    }
  }, [canDownload, capabilitiesReady, kindFilter, patientArchived, router]);

  const loadDocuments = useCallback(async () => {
    if (!capabilitiesReady || !canDownload || patientArchived) {
      setDocuments([]);
      setLoadingDocs(false);
      return;
    }
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
        throw new Error(await safeDocumentError(res, "Failed to load documents."));
      }
      const data = (await res.json()) as PatientDocument[];
      setDocuments(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoadingDocs(false);
    }
  }, [canDownload, capabilitiesReady, patientArchived, patientId, router]);

  async function downloadTemplate(template: DocumentTemplate, button?: HTMLButtonElement | null) {
    if (
      !canDownload ||
      patientArchived ||
      !button ||
      downloadingTemplateIds.has(template.id) ||
      button.disabled
    ) return;
    downloadingTemplateIds.add(template.id);
    button.disabled = true;
    setError(null);
    setDownloadingTemplateId(template.id);
    try {
      const res = await apiFetch(`/api/document-templates/${template.id}/download`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(await safeDocumentError(res, "Failed to download template."));
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const filename =
        filenameFromHeader(res.headers.get("Content-Disposition")) ||
        buildTemplateDownloadFilename(template);
      link.href = url;
      link.download = sanitizeTemplateFilename(filename.replace(/\.txt$/i, "")) + ".txt";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download template");
    } finally {
      downloadingTemplateIds.delete(template.id);
      if (button?.isConnected) {
        button.disabled = false;
      }
      setDownloadingTemplateId(null);
    }
  }

  async function previewDocument() {
    if (!canUpload || patientArchived || previewingDocumentRef.current || savingDocumentRef.current) {
      return;
    }
    if (!selectedTemplateId) {
      setError("Select a template to preview.");
      return;
    }
    if (!validatePrescription()) return;
    const draftVersion = draftVersionRef.current;
    previewingDocumentRef.current = true;
    setPreviewing(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/documents/preview`, {
        method: "POST",
        body: JSON.stringify({
          template_id: selectedTemplateId,
          title: title || null,
          ...(isTypedPrescription ? { prescription } : {}),
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(await safeDocumentError(res, "Failed to preview document."));
      }
      const data = (await res.json()) as {
        title: string;
        rendered_content: string;
        unknown_fields?: string[];
      };
      if (draftVersionRef.current !== draftVersion) return;
      setPreview(data.rendered_content);
      setUnknownFields(data.unknown_fields ?? []);
      if (!title) {
        setTitle(data.title);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to preview document");
    } finally {
      setPreviewing(false);
      previewingDocumentRef.current = false;
    }
  }

  async function saveDocument() {
    if (!canUpload || patientArchived || savingDocumentRef.current || previewingDocumentRef.current) {
      return;
    }
    if (!selectedTemplateId) {
      setError("Select a template to save.");
      return;
    }
    if (!validatePrescription()) return;
    savingDocumentRef.current = true;
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/documents`, {
        method: "POST",
        headers: { "Request-Id": crypto.randomUUID() },
        body: JSON.stringify({
          template_id: selectedTemplateId,
          title: title || null,
          ...(isTypedPrescription ? { prescription } : {}),
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(await safeDocumentError(res, "Failed to save document."));
      }
      setPreview(null);
      setUnknownFields([]);
      setTitle("");
      setPrescription(emptyPrescription());
      setPrescriptionTemplateId("");
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save document");
    } finally {
      setSaving(false);
      savingDocumentRef.current = false;
    }
  }

  async function downloadDocument(doc: PatientDocument, button?: HTMLButtonElement | null) {
    if (
      !canDownload ||
      patientArchived ||
      !button ||
      downloadingPatientDocumentTextIds.has(doc.id) ||
      button.disabled
    ) return;
    downloadingPatientDocumentTextIds.add(doc.id);
    button.disabled = true;
    setError(null);
    setDownloadingDocumentTextId(doc.id);
    try {
      const res = await apiFetch(`/api/patient-documents/${doc.id}/download`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(await safeDocumentError(res, "Failed to download document."));
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const filename = sanitizePatientDocumentFilename(
        filenameFromHeader(res.headers.get("Content-Disposition")) ||
        buildPatientDocumentDownloadFilename(doc, patientLastName, "txt", res.headers.get("Date"))
      );
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download document");
    } finally {
      downloadingPatientDocumentTextIds.delete(doc.id);
      if (button?.isConnected) {
        button.disabled = false;
      }
      setDownloadingDocumentTextId(null);
    }
  }

  async function downloadDocumentPdf(doc: PatientDocument, button?: HTMLButtonElement | null) {
    if (
      !canDownload ||
      patientArchived ||
      !button ||
      downloadingPatientDocumentPdfIds.has(doc.id) ||
      button.disabled
    ) return;
    downloadingPatientDocumentPdfIds.add(doc.id);
    button.disabled = true;
    setError(null);
    setDownloadingDocumentPdfId(doc.id);
    try {
      const res = await apiFetch(`/api/patient-documents/${doc.id}/download?format=pdf`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(await safeDocumentError(res, "Failed to download PDF."));
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const filename = sanitizePatientDocumentFilename(
        filenameFromHeader(res.headers.get("Content-Disposition")) ||
        buildPatientDocumentDownloadFilename(doc, patientLastName, "pdf", res.headers.get("Date"))
      );
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download PDF");
    } finally {
      downloadingPatientDocumentPdfIds.delete(doc.id);
      if (button?.isConnected) {
        button.disabled = false;
      }
      setDownloadingDocumentPdfId(null);
    }
  }

  async function attachDocumentPdf(doc: PatientDocument, button?: HTMLButtonElement | null) {
    if (
      !canUpload ||
      patientArchived ||
      !button ||
      attachingPatientDocumentPdfIds.has(doc.id) ||
      button.disabled
    ) {
      return;
    }
    attachingPatientDocumentPdfIds.add(doc.id);
    button.disabled = true;
    setError(null);
    setAttachNotice(null);
    setAttachingDocumentPdfId(doc.id);
    try {
      const res = await apiFetch(`/api/patient-documents/${doc.id}/attach-pdf`, {
        method: "POST",
        headers: { "Request-Id": crypto.randomUUID() },
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(await safeDocumentError(res, "Failed to attach PDF."));
      }
      const attachment = (await res.json()) as { id: number };
      setDocuments((current) =>
        current.map((item) =>
          item.id === doc.id ? { ...item, attachment_id: attachment.id } : item
        )
      );
      setAttachNotice("PDF saved to attachments.");
      window.dispatchEvent(new Event("patient-attachments-changed"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to attach PDF");
    } finally {
      attachingPatientDocumentPdfIds.delete(doc.id);
      setAttachingDocumentPdfId(null);
    }
  }

  async function deleteDocument(doc: PatientDocument, button?: HTMLButtonElement | null) {
    if (
      !canDelete ||
      patientArchived ||
      !button ||
      deletingPatientDocumentIds.has(doc.id) ||
      button.disabled
    ) return;
    if (!confirm(`Delete "${doc.title}"?`)) return;
    deletingPatientDocumentIds.add(doc.id);
    button.disabled = true;
    setError(null);
    setDeletingDocumentId(doc.id);
    try {
      const res = await apiFetch(`/api/patient-documents/${doc.id}`, { method: "DELETE" });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(await safeDocumentError(res, "Failed to delete document."));
      }
      setDocuments((prev) => prev.filter((item) => item.id !== doc.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete document");
    } finally {
      deletingPatientDocumentIds.delete(doc.id);
      if (button?.isConnected) {
        button.disabled = false;
      }
      setDeletingDocumentId((current) => (current === doc.id ? null : current));
    }
  }

  useEffect(() => {
    void loadTemplates();
  }, [loadTemplates]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  useEffect(() => {
    if (!isTypedPrescription || !canUpload || patientArchived) return;
    let cancelled = false;
    setPrescriptionTemplates([]);
    setPrescriptionTemplatesError(null);
    async function loadPrescriptionTemplates() {
      try {
        const res = await apiFetch("/api/prescription-templates");
        if (!res.ok) throw new Error("Saved prescriptions could not be loaded. You can still enter details manually.");
        const data = (await res.json()) as PrescriptionTemplate[];
        if (!cancelled) {
          setPrescriptionTemplates(data);
          setPrescriptionTemplatesError(null);
        }
      } catch (err) {
        if (!cancelled) setPrescriptionTemplatesError(err instanceof Error ? err.message : "Could not load saved prescriptions.");
      }
    }
    void loadPrescriptionTemplates();
    window.addEventListener("focus", loadPrescriptionTemplates);
    return () => {
      cancelled = true;
      window.removeEventListener("focus", loadPrescriptionTemplates);
    };
  }, [isTypedPrescription, canUpload, patientArchived, patientId]);

  useEffect(() => {
    draftVersionRef.current += 1;
    setSelectedTemplateId(null);
    setTitle("");
    setPrescription(emptyPrescription());
    setPrescriptionTemplateId("");
    setPreview(null);
    setUnknownFields([]);
  }, [patientId]);

  const content = (
    <div
      className="stack"
      data-testid="patient-documents-access"
      data-state={accessState}
    >
        <div className="row">
          <div>
            <h4 style={{ marginTop: 0 }}>Documents</h4>
            <div style={{ color: "var(--muted)" }}>
              Create a letter or enter a prescription, then save and download its PDF.
            </div>
          </div>
          {canDownload && !patientArchived && (
            <select
              className="input"
              value={kindFilter}
              onChange={(e) => setKindFilter(e.target.value as "all" | DocumentTemplateKind)}
            >
              <option value="all">All kinds</option>
              <option value="letter">Letters</option>
              <option value="prescription">Prescriptions</option>
            </select>
          )}
        </div>

        {!capabilitiesReady && <div className="badge">Checking document permissions…</div>}
        {capabilitiesReady && capabilityError && <div className="notice">{capabilityError}</div>}
        {patientArchived && (
          <div className="notice">Archived patient documents are unavailable.</div>
        )}
        {capabilitiesReady && !patientArchived && !canDownload && (
          <div className="notice">You do not have permission to view patient documents.</div>
        )}
        {capabilitiesReady && canDownload && !canUpload && !patientArchived && (
          <div className="notice">Patient documents are read-only.</div>
        )}
        {loading && <div className="badge">Loading templates…</div>}
        {error && <div className="notice">{error}</div>}
        {attachNotice && <div className="badge">{attachNotice}</div>}

        {canUpload && !patientArchived && <div className="card" style={{ margin: 0 }}>
          <div className="stack">
            <h4 style={{ marginTop: 0 }}>Generate document</h4>
            <div className="grid grid-2">
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Template</label>
                <select
                  className="input"
                  value={selectedTemplateId ?? ""}
                  disabled={documentBusy}
                  onChange={(e) => {
                    const value = e.target.value ? Number(e.target.value) : null;
                    setSelectedTemplateId(value);
                    setTitle("");
                    setPrescription(emptyPrescription());
                    setPrescriptionTemplateId("");
                    clearPreview();
                  }}
                  data-testid="patient-document-template-select"
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
                  disabled={documentBusy}
                  onChange={(e) => { setTitle(e.target.value); clearPreview(); }}
                  maxLength={200}
                  data-testid="patient-document-title-input"
                />
              </div>
            </div>
            {isTypedPrescription && (
              <fieldset className="stack" disabled={documentBusy} style={{ border: 0, padding: 0, margin: 0 }}>
                <legend style={{ fontWeight: 600 }}>Prescription details</legend>
                <div style={{ color: "var(--muted)" }}>Enter the prescription, review the preview, then save and download the PDF for signing.</div>
                <label className="stack" style={{ gap: 6 }}>
                  <span className="label">Saved prescription</span>
                  <select
                    className="input"
                    value={prescriptionTemplateId}
                    data-testid="prescription-saved-template"
                    onChange={(event) => {
                      const id = event.target.value;
                      const saved = prescriptionTemplates.find((item) => String(item.id) === id);
                      setPrescriptionTemplateId(id);
                      setPrescription((current) => ({
                        ...current,
                        medicine: saved?.medicine ?? "",
                        directions: saved?.directions ?? "",
                        quantity: saved?.quantity ?? "",
                      }));
                      clearPreview();
                    }}
                  >
                    <option value="">Enter manually</option>
                    {prescriptionTemplates.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <div style={{ color: "var(--muted)" }}>
                  Choose a saved prescription, then adjust the details for this patient.
                  {" "}<a href="/templates?tab=prescriptions" target="_blank" rel="noreferrer">Manage prescription templates</a>
                </div>
                {prescriptionTemplatesError && <div className="notice">{prescriptionTemplatesError}</div>}
                {prescriptionInputs.map((input) => (
                  <label className="stack" style={{ gap: 6 }} key={input.key}>
                    <span className="label">{input.label}</span>
                    <textarea
                      className="input"
                      rows={input.rows}
                      maxLength={input.maxLength}
                      required
                      value={prescription[input.key]}
                      onChange={(event) => {
                        setPrescription((current) => ({ ...current, [input.key]: event.target.value }));
                        if (["medicine", "directions", "quantity"].includes(input.key)) setPrescriptionTemplateId("");
                        clearPreview();
                      }}
                      data-testid={`prescription-${input.key}`}
                    />
                  </label>
                ))}
              </fieldset>
            )}
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
                disabled={documentBusy}
                onClick={() => {
                  setTitle((prev) => (prev ? `${prev} ${selectedField}` : selectedField));
                  clearPreview();
                }}
              >
                Insert
              </button>
            </div>
            <div className="row">
              <button
                className="btn btn-secondary"
                type="button"
                onClick={previewDocument}
                disabled={documentBusy}
                data-testid="patient-document-preview"
              >
                {previewing ? "Rendering..." : "Preview"}
              </button>
              <button
                className="btn btn-primary"
                type="button"
                onClick={saveDocument}
                disabled={documentBusy}
                data-testid="patient-document-save"
              >
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
        </div>}

        {canDownload && !patientArchived && <div className="card" style={{ margin: 0 }}>
          <div className="stack">
            <h4 style={{ marginTop: 0 }}>Generated documents</h4>
            {loadingDocs && <div className="badge">Loading documents…</div>}
            {documents.length === 0 && !loadingDocs ? (
              <div className="notice">
                No documents generated yet. Use a template above to create the first.
              </div>
            ) : (
              <div className="stack" style={{ gap: 8 }}>
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="card"
                    style={{ margin: 0, display: "flex", justifyContent: "space-between", gap: 12 }}
                    data-testid={`patient-document-card-${doc.id}`}
                  >
                    <div>
                      <div style={{ fontWeight: 600 }}>{doc.title}</div>
                      <div
                        style={{ color: "var(--muted)" }}
                        data-testid={`patient-document-meta-${doc.id}`}
                      >
                        Created {formatDocumentCreatedAt(doc.created_at)} by{" "}
                        {doc.created_by?.email || "—"}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 8 }}>
                      {canDownload && <button
                        className="btn btn-secondary"
                        type="button"
                        onClick={(event) =>
                          void downloadDocument(doc, event.currentTarget)
                        }
                        disabled={downloadingDocumentTextId !== null}
                        data-testid={`patient-document-download-text-${doc.id}`}
                      >
                        {downloadingDocumentTextId === doc.id
                          ? "Downloading text..."
                          : "Download text"}
                      </button>}
                      {canDownload && <button
                        className="btn btn-secondary"
                        type="button"
                        onClick={(event) =>
                          void downloadDocumentPdf(doc, event.currentTarget)
                        }
                        disabled={downloadingDocumentPdfId !== null}
                        data-testid={`patient-document-download-pdf-${doc.id}`}
                      >
                        {downloadingDocumentPdfId === doc.id ? "Downloading PDF..." : "Download PDF"}
                      </button>}
                      {canUpload && <button
                        className="btn btn-secondary"
                        type="button"
                        onClick={(event) =>
                          void attachDocumentPdf(doc, event.currentTarget)
                        }
                        disabled={attachingDocumentPdfId !== null || Boolean(doc.attachment_id)}
                        data-testid={`patient-document-attach-pdf-${doc.id}`}
                      >
                        {doc.attachment_id
                          ? "PDF in attachments"
                          : attachingDocumentPdfId === doc.id
                          ? "Saving PDF..."
                          : "Save PDF to attachments"}
                      </button>}
                      {canDelete && (
                        <button
                          className="btn btn-secondary"
                          type="button"
                          onClick={(event) => void deleteDocument(doc, event.currentTarget)}
                          data-testid={`patient-document-delete-${doc.id}`}
                          disabled={deletingDocumentId === doc.id}
                        >
                          {deletingDocumentId === doc.id ? "Deleting..." : "Delete"}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>}

        {canDownload && !patientArchived && templates.length === 0 && !loading ? (
          <div className="notice">No active templates available.</div>
        ) : canDownload && !patientArchived && templates.length > 0 ? (
          <div className="stack" style={{ gap: 8 }}>
            {templates.map((template) => (
              <div
                key={template.id}
                className="card"
                style={{ margin: 0, display: "flex", justifyContent: "space-between", gap: 12 }}
                data-testid={`patient-template-card-${template.id}`}
              >
                <div>
                  <div style={{ fontWeight: 600 }}>{template.name}</div>
                  <div style={{ color: "var(--muted)" }}>{kindLabels[template.kind]}</div>
                </div>
                <button
                  className="btn btn-secondary"
                  type="button"
                  onClick={(event) => void downloadTemplate(template, event.currentTarget)}
                  disabled={downloadingTemplateId !== null}
                  data-testid={`patient-template-download-${template.id}`}
                >
                  {downloadingTemplateId === template.id ? "Downloading..." : "Download"}
                </button>
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
