"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";

type RecallStatus = "due" | "contacted" | "booked" | "not_required";

type RecallRow = {
  id: number;
  first_name: string;
  last_name: string;
  phone?: string | null;
  postcode?: string | null;
  recall_interval_months?: number | null;
  recall_due_date?: string | null;
  recall_status?: RecallStatus | null;
  recall_type?: string | null;
  recall_last_contacted_at?: string | null;
  recall_notes?: string | null;
  recall_last_set_at?: string | null;
  balance_pence?: number | null;
};

const statusLabels: Record<RecallStatus, string> = {
  due: "Pending",
  contacted: "Contacted",
  booked: "Booked",
  not_required: "Declined",
};

type RangeFilter = "overdue" | "30" | "60" | "90" | "all";

type DocumentTemplateKind = "letter" | "prescription";

type DocumentTemplate = {
  id: number;
  name: string;
  kind: DocumentTemplateKind;
  is_active: boolean;
};

type PatientDocument = {
  id: number;
  title: string;
  rendered_content: string;
  unknown_fields?: string[] | null;
};

const RECALL_TEMPLATE_ROUTINE = "Recall Letter – Routine Examination";
const RECALL_TEMPLATE_OVERDUE = "Recall Letter – Overdue Reminder";

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

function filenameFromHeader(header: string | null) {
  if (!header) return null;
  const match = /filename="([^"]+)"/.exec(header);
  return match?.[1] ?? null;
}

function isOverdueRecall(recall: RecallRow) {
  if (!recall.recall_due_date) return false;
  const parsed = new Date(recall.recall_due_date);
  if (Number.isNaN(parsed.getTime())) return false;
  const today = new Date();
  return parsed < new Date(today.getFullYear(), today.getMonth(), today.getDate());
}

export default function RecallsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<RecallRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<RecallStatus | "all">("all");
  const [rangeFilter, setRangeFilter] = useState<RangeFilter>("overdue");
  const [templates, setTemplates] = useState<DocumentTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [selectedRecallId, setSelectedRecallId] = useState<number | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [selectedField, setSelectedField] = useState(mergeFields[0].value);
  const [title, setTitle] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [unknownFields, setUnknownFields] = useState<string[]>([]);
  const [generating, setGenerating] = useState(false);
  const [generatedDoc, setGeneratedDoc] = useState<PatientDocument | null>(null);
  const [recallType, setRecallType] = useState("");
  const [recallNotes, setRecallNotes] = useState("");
  const [recallDueDate, setRecallDueDate] = useState("");
  const [recallStatus, setRecallStatus] = useState<RecallStatus>("due");
  const [savingRecall, setSavingRecall] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const selectedRecall = rows.find((row) => row.id === selectedRecallId) || null;

  function formatDate(value?: string | null) {
    if (!value) return "—";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "—";
    return parsed.toLocaleDateString("en-GB");
  }

  function formatCurrency(pence?: number | null) {
    if (pence === null || pence === undefined) return "—";
    return new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency: "GBP",
    }).format(pence / 100);
  }

  function buildRangeParams(filter: RangeFilter) {
    if (filter === "all") return {};
    const today = new Date();
    const end = new Date(today);
    if (filter === "overdue") {
      return { end: today.toISOString().slice(0, 10) };
    }
    const days = Number(filter);
    end.setDate(end.getDate() + days);
    return {
      start: today.toISOString().slice(0, 10),
      end: end.toISOString().slice(0, 10),
    };
  }

  async function loadTemplates() {
    setTemplatesLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/api/document-templates?kind=letter");
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to load templates (HTTP ${res.status})`);
      }
      const data = (await res.json()) as DocumentTemplate[];
      setTemplates(data.filter((item) => item.is_active));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load templates");
    } finally {
      setTemplatesLoading(false);
    }
  }

  async function loadRecalls() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      const range = buildRangeParams(rangeFilter);
      if (range.start) params.set("start", range.start);
      if (range.end) params.set("end", range.end);
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (query.trim()) params.set("q", query.trim());
      const res = await apiFetch(`/api/recalls?${params.toString()}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to load recalls (HTTP ${res.status})`);
      }
      const data = (await res.json()) as RecallRow[];
      setRows(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load recalls");
    } finally {
      setLoading(false);
    }
  }

  async function updateRecall(patientId: number, payload: Partial<{
    status: RecallStatus;
    due_date: string | null;
    recall_type: string | null;
    notes: string | null;
  }>) {
    setSavingRecall(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/recalls/${patientId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
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
        throw new Error(msg || `Failed to update recall (HTTP ${res.status})`);
      }
      await loadRecalls();
      setNotice("Recall updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update recall");
    } finally {
      setSavingRecall(false);
    }
  }

  async function previewRecallDocument() {
    if (!selectedRecall || !selectedTemplateId) {
      setError("Select a recall and template to preview.");
      return;
    }
    setPreviewing(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/patients/${selectedRecall.id}/documents/preview`, {
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
        throw new Error(msg || `Failed to preview recall letter (HTTP ${res.status})`);
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
      setError(err instanceof Error ? err.message : "Failed to preview recall letter");
    } finally {
      setPreviewing(false);
    }
  }

  async function generateRecallDocument() {
    if (!selectedRecall || !selectedTemplateId) {
      setError("Select a recall and template to generate.");
      return;
    }
    setGenerating(true);
    setError(null);
    setNotice(null);
    try {
      const res = await apiFetch(`/api/recalls/${selectedRecall.id}/generate-document`, {
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
        throw new Error(msg || `Failed to generate recall letter (HTTP ${res.status})`);
      }
      const data = (await res.json()) as PatientDocument;
      setGeneratedDoc(data);
      setUnknownFields(data.unknown_fields ?? []);
      setNotice("Recall letter saved to patient documents.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate recall letter");
    } finally {
      setGenerating(false);
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
    setNotice(null);
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
      setNotice("PDF saved to attachments.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to attach PDF");
    }
  }

  useEffect(() => {
    void loadRecalls();
  }, [rangeFilter, statusFilter]);

  useEffect(() => {
    const handle = setTimeout(() => {
      void loadRecalls();
    }, 300);
    return () => clearTimeout(handle);
  }, [query]);

  useEffect(() => {
    void loadTemplates();
  }, []);

  useEffect(() => {
    if (!selectedRecall) return;
    setRecallType(selectedRecall.recall_type ?? "");
    setRecallNotes(selectedRecall.recall_notes ?? "");
    setRecallDueDate(selectedRecall.recall_due_date ?? "");
    setRecallStatus(selectedRecall.recall_status ?? "due");
    setPreview(null);
    setUnknownFields([]);
    setGeneratedDoc(null);
    setTitle("");
    setSelectedTemplateId(null);
  }, [selectedRecallId]);

  useEffect(() => {
    if (!selectedRecall || selectedTemplateId || templates.length === 0) return;
    const overdue = isOverdueRecall(selectedRecall);
    const preferredName = overdue ? RECALL_TEMPLATE_OVERDUE : RECALL_TEMPLATE_ROUTINE;
    const match = templates.find((template) => template.name === preferredName);
    if (match) {
      setSelectedTemplateId(match.id);
    }
  }, [selectedRecall, selectedTemplateId, templates]);

  return (
    <div className="app-grid">
      <div className="card">
        <div className="stack">
          <div className="row">
            <div>
              <h2 style={{ marginTop: 0 }}>Recalls</h2>
              <div style={{ color: "var(--muted)" }}>
                Worklist of patients due for recall.
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <select
                className="input"
                value={rangeFilter}
                onChange={(e) => setRangeFilter(e.target.value as RangeFilter)}
              >
                <option value="overdue">Overdue</option>
                <option value="30">Due in 30 days</option>
                <option value="60">Due in 60 days</option>
                <option value="90">Due in 90 days</option>
                <option value="all">All recalls</option>
              </select>
              <select
                className="input"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as RecallStatus | "all")}
              >
                <option value="all">All statuses</option>
                <option value="due">Due</option>
                <option value="contacted">Contacted</option>
                <option value="booked">Booked</option>
                <option value="not_required">Not required</option>
              </select>
              <button className="btn btn-secondary" onClick={() => void loadRecalls()}>
                Refresh
              </button>
            </div>
          </div>
          <div className="row" style={{ gap: 12 }}>
            <input
              className="input"
              placeholder="Search name, phone, postcode"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
            {loading && <span className="badge">Loading…</span>}
            {error && <span className="badge">{error}</span>}
            {notice && <span className="badge">{notice}</span>}
          </div>
          {rows.length === 0 && !loading ? (
            <div className="notice">No recalls found.</div>
          ) : (
            <table className="table table-compact table-hover table-sticky">
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>Phone</th>
                  <th>Postcode</th>
                  <th>Type</th>
                  <th>Recall due</th>
                  <th>Status</th>
                  <th>Last set</th>
                  <th>Last contacted</th>
                  <th>Balance</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      {row.last_name.toUpperCase()}, {row.first_name}
                    </td>
                    <td>{row.phone || "—"}</td>
                    <td>{row.postcode || "—"}</td>
                    <td>{row.recall_type || "—"}</td>
                    <td>{formatDate(row.recall_due_date)}</td>
                    <td>
                      <span className="badge">
                        {statusLabels[row.recall_status || "due"]}
                      </span>
                    </td>
                    <td>{formatDate(row.recall_last_set_at)}</td>
                    <td>{formatDate(row.recall_last_contacted_at)}</td>
                    <td>{formatCurrency(row.balance_pence)}</td>
                    <td>
                      <div className="table-actions">
                        <button
                          className="btn btn-secondary"
                          onClick={() => router.push(`/patients/${row.id}`)}
                        >
                          Open
                        </button>
                        <button
                          className="btn btn-secondary"
                          onClick={() =>
                            void updateRecall(row.id, {
                              status: "contacted",
                            })
                          }
                        >
                          Contacted
                        </button>
                        <button
                          className="btn btn-secondary"
                          onClick={() =>
                            void updateRecall(row.id, {
                              status: "booked",
                            })
                          }
                        >
                          Booked
                        </button>
                        <button
                          className="btn btn-secondary"
                          onClick={() =>
                            void updateRecall(row.id, {
                              status: "not_required",
                            })
                          }
                        >
                          Declined
                        </button>
                        <button
                          className="btn btn-secondary"
                          onClick={() => router.push(`/patients/${row.id}?book=1`)}
                        >
                          Book recall
                        </button>
                        <button
                          className="btn btn-secondary"
                          onClick={() => setSelectedRecallId(row.id)}
                        >
                          Generate letter
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {selectedRecall && (
            <div className="card" style={{ margin: 0 }}>
              <div className="stack">
                <div className="row">
                  <div>
                    <h4 style={{ marginTop: 0 }}>
                      Recall letter for {selectedRecall.last_name.toUpperCase()},{" "}
                      {selectedRecall.first_name}
                    </h4>
                    <div style={{ color: "var(--muted)" }}>
                      Generate a recall letter and store it as a patient document.
                    </div>
                  </div>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    onClick={() => setSelectedRecallId(null)}
                  >
                    Close
                  </button>
                </div>

                <div className="grid grid-3">
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Recall type</label>
                    <input
                      className="input"
                      value={recallType}
                      onChange={(e) => setRecallType(e.target.value)}
                    />
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Recall due</label>
                    <input
                      className="input"
                      type="date"
                      value={recallDueDate}
                      onChange={(e) => setRecallDueDate(e.target.value)}
                    />
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Status</label>
                    <select
                      className="input"
                      value={recallStatus}
                      onChange={(e) => setRecallStatus(e.target.value as RecallStatus)}
                    >
                      <option value="due">Pending</option>
                      <option value="contacted">Contacted</option>
                      <option value="booked">Booked</option>
                      <option value="not_required">Declined</option>
                    </select>
                  </div>
                </div>

                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">Recall notes</label>
                  <textarea
                    className="input"
                    rows={3}
                    value={recallNotes}
                    onChange={(e) => setRecallNotes(e.target.value)}
                  />
                </div>

                <button
                  className="btn btn-secondary"
                  type="button"
                  disabled={savingRecall}
                  onClick={() =>
                    void updateRecall(selectedRecall.id, {
                      status: recallStatus,
                      due_date: recallDueDate || null,
                      recall_type: recallType || null,
                      notes: recallNotes || null,
                    })
                  }
                >
                  {savingRecall ? "Saving..." : "Save recall details"}
                </button>

                <div className="card" style={{ margin: 0 }}>
                  <div className="stack">
                    <h4 style={{ marginTop: 0 }}>Generate letter</h4>
                    {templatesLoading && <div className="badge">Loading templates…</div>}
                    {templates.length === 0 && !templatesLoading ? (
                      <div className="notice">No active letter templates found.</div>
                    ) : (
                      <>
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
                                setGeneratedDoc(null);
                              }}
                            >
                              <option value="">Select a template</option>
                              {templates.map((template) => (
                                <option key={template.id} value={template.id}>
                                  {template.name}
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
                              setTitle((prev) =>
                                prev ? `${prev} ${selectedField}` : selectedField
                              );
                            }}
                          >
                            Insert
                          </button>
                        </div>
                        <div className="row">
                          <button
                            className="btn btn-secondary"
                            type="button"
                            onClick={previewRecallDocument}
                          >
                            {previewing ? "Rendering..." : "Preview"}
                          </button>
                          <button
                            className="btn btn-primary"
                            type="button"
                            onClick={generateRecallDocument}
                          >
                            {generating ? "Saving..." : "Save letter"}
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
                        {generatedDoc && (
                          <div className="row">
                            <button
                              className="btn btn-secondary"
                              type="button"
                              onClick={() => downloadDocument(generatedDoc)}
                            >
                              Download text
                            </button>
                            <button
                              className="btn btn-secondary"
                              type="button"
                              onClick={() => downloadDocumentPdf(generatedDoc)}
                            >
                              Download PDF
                            </button>
                            <button
                              className="btn btn-secondary"
                              type="button"
                              onClick={() => attachDocumentPdf(generatedDoc)}
                            >
                              Save PDF to attachments
                            </button>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
