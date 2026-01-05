"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Timeline from "@/components/timeline/Timeline";
import { apiFetch, clearToken } from "@/lib/auth";

type Actor = {
  id: number;
  email: string;
  role: string;
};

type Patient = {
  id: number;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  phone?: string | null;
  email?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  postcode?: string | null;
  notes?: string | null;
  allergies?: string | null;
  medical_alerts?: string | null;
  safeguarding_notes?: string | null;
  created_at: string;
  updated_at: string;
  created_by: Actor;
  updated_by?: Actor | null;
  deleted_at?: string | null;
  deleted_by?: Actor | null;
};

type Note = {
  id: number;
  body: string;
  note_type: string;
  created_at: string;
  created_by: Actor;
  deleted_at?: string | null;
};

type InvoiceSummary = {
  id: number;
  patient_id: number;
  appointment_id?: number | null;
  invoice_number: string;
  issue_date?: string | null;
  due_date?: string | null;
  status: string;
  subtotal_pence: number;
  discount_pence: number;
  total_pence: number;
  paid_pence: number;
  balance_pence: number;
  created_at: string;
  updated_at: string;
};

type InvoiceLine = {
  id: number;
  description: string;
  quantity: number;
  unit_price_pence: number;
  line_total_pence: number;
};

type Payment = {
  id: number;
  amount_pence: number;
  method: string;
  paid_at: string;
  reference?: string | null;
  received_by_user_id: number;
};

type InvoiceDetail = InvoiceSummary & {
  notes?: string | null;
  lines: InvoiceLine[];
  payments: Payment[];
};

type TimelineItem = {
  entity_type: string;
  entity_id: string;
  action: string;
  occurred_at: string;
  actor_email?: string | null;
  actor_role?: string | null;
  summary: string;
  link?: string | null;
};

export default function PatientDetailClient({ id }: { id: string }) {
  const router = useRouter();
  const patientId = id;
  const [patient, setPatient] = useState<Patient | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [tab, setTab] = useState<"summary" | "notes" | "invoices">("summary");
  const [loading, setLoading] = useState(true);
  const [noteBody, setNoteBody] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [savingPatient, setSavingPatient] = useState(false);
  const [showArchivedNotes, setShowArchivedNotes] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [copyNotice, setCopyNotice] = useState<string | null>(null);
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([]);
  const [loadingInvoices, setLoadingInvoices] = useState(false);
  const [invoiceError, setInvoiceError] = useState<string | null>(null);
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceDetail | null>(null);
  const [creatingInvoice, setCreatingInvoice] = useState(false);
  const [newInvoiceNotes, setNewInvoiceNotes] = useState("");
  const [newInvoiceDiscount, setNewInvoiceDiscount] = useState("");
  const [lineDescription, setLineDescription] = useState("");
  const [lineQuantity, setLineQuantity] = useState("1");
  const [lineUnitPrice, setLineUnitPrice] = useState("");
  const [lineDrafts, setLineDrafts] = useState<
    Record<number, { description: string; quantity: string; unit_price: string }>
  >({});
  const [invoiceNotes, setInvoiceNotes] = useState("");
  const [invoiceDiscount, setInvoiceDiscount] = useState("");
  const [recordingPayment, setRecordingPayment] = useState(false);
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("card");
  const [paymentReference, setPaymentReference] = useState("");
  const [paymentDate, setPaymentDate] = useState("");

  async function loadPatient() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/patients/${patientId}?include_deleted=1`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load patient (HTTP ${res.status})`);
      }
      const data = (await res.json()) as Patient;
      setPatient(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load patient");
    } finally {
      setLoading(false);
    }
  }

  async function loadNotes(includeDeleted: boolean = showArchivedNotes) {
    try {
      const params = new URLSearchParams();
      if (includeDeleted) params.set("include_deleted", "1");
      const res = await apiFetch(`/api/patients/${patientId}/notes?${params.toString()}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.ok) {
        const data = (await res.json()) as Note[];
        setNotes(data);
      }
    } catch {
      setNotes([]);
    }
  }

  async function loadTimeline() {
    try {
      const res = await apiFetch(`/api/patients/${patientId}/timeline`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.ok) {
        const data = (await res.json()) as TimelineItem[];
        setTimeline(data);
      }
    } catch {
      setTimeline([]);
    }
  }

  async function loadInvoices() {
    setLoadingInvoices(true);
    setInvoiceError(null);
    try {
      const res = await apiFetch(`/api/invoices?patient_id=${patientId}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load invoices (HTTP ${res.status})`);
      }
      const data = (await res.json()) as InvoiceSummary[];
      setInvoices(data);
    } catch (err) {
      setInvoiceError(err instanceof Error ? err.message : "Failed to load invoices");
    } finally {
      setLoadingInvoices(false);
    }
  }

  async function loadInvoiceDetail(invoiceId: number) {
    setInvoiceError(null);
    try {
      const res = await apiFetch(`/api/invoices/${invoiceId}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to load invoice (HTTP ${res.status})`);
      }
      const data = (await res.json()) as InvoiceDetail;
      setSelectedInvoice(data);
      setInvoiceNotes(data.notes || "");
      setInvoiceDiscount((data.discount_pence / 100).toFixed(2));
      const drafts: Record<number, { description: string; quantity: string; unit_price: string }> =
        {};
      data.lines.forEach((line) => {
        drafts[line.id] = {
          description: line.description,
          quantity: String(line.quantity),
          unit_price: (line.unit_price_pence / 100).toFixed(2),
        };
      });
      setLineDrafts(drafts);
    } catch (err) {
      setInvoiceError(err instanceof Error ? err.message : "Failed to load invoice");
    }
  }

  useEffect(() => {
    void loadPatient();
    void loadNotes();
    void loadTimeline();
    void loadInvoices();
  }, [patientId]);

  const alerts = [
    patient?.allergies ? { label: "Allergies", tone: "danger" } : null,
    patient?.medical_alerts ? { label: "Medical alert", tone: "warning" } : null,
    patient?.safeguarding_notes ? { label: "Safeguarding", tone: "warning" } : null,
  ].filter(Boolean) as { label: string; tone: "danger" | "warning" }[];

  function buildAddress(p: Patient | null) {
    if (!p) return "";
    return [p.address_line1, p.address_line2, p.city, p.postcode]
      .filter(Boolean)
      .join(", ");
  }

  async function copyAddress() {
    if (!patient) return;
    const address = buildAddress(patient);
    if (!address) {
      setCopyNotice("No address on file.");
      return;
    }
    try {
      await navigator.clipboard.writeText(address);
      setCopyNotice("Address copied.");
    } catch {
      setCopyNotice("Copy failed. Please copy manually.");
    }
  }

  function formatPence(value: number) {
    return new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency: "GBP",
    }).format(value / 100);
  }

  function toPence(raw: string) {
    const parsed = Number(raw);
    if (Number.isNaN(parsed)) return null;
    return Math.max(0, Math.round(parsed * 100));
  }

  async function savePatient(e: React.FormEvent) {
    e.preventDefault();
    if (!patient) return;
    setSavingPatient(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/patients/${patient.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          first_name: patient.first_name,
          last_name: patient.last_name,
          email: patient.email,
          phone: patient.phone,
          date_of_birth: patient.date_of_birth,
          address_line1: patient.address_line1,
          address_line2: patient.address_line2,
          city: patient.city,
          postcode: patient.postcode,
          allergies: patient.allergies,
          medical_alerts: patient.medical_alerts,
          safeguarding_notes: patient.safeguarding_notes,
          notes: patient.notes,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to update patient (HTTP ${res.status})`);
      }
      const data = (await res.json()) as Patient;
      setPatient(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update patient");
    } finally {
      setSavingPatient(false);
    }
  }

  async function addNote() {
    if (!noteBody.trim()) return;
    setSavingNote(true);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/notes`, {
        method: "POST",
        body: JSON.stringify({ body: noteBody, note_type: "clinical" }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to add note (HTTP ${res.status})`);
      }
      setNoteBody("");
      await loadNotes();
      await loadTimeline();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add note");
    } finally {
      setSavingNote(false);
    }
  }

  async function createInvoice() {
    if (creatingInvoice) return;
    setCreatingInvoice(true);
    setInvoiceError(null);
    const discountPence = toPence(newInvoiceDiscount || "0");
    if (discountPence === null) {
      setInvoiceError("Discount must be a number.");
      setCreatingInvoice(false);
      return;
    }
    try {
      const res = await apiFetch("/api/invoices", {
        method: "POST",
        body: JSON.stringify({
          patient_id: Number(patientId),
          notes: newInvoiceNotes.trim() || undefined,
          discount_pence: discountPence,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to create invoice (HTTP ${res.status})`);
      }
      const invoice = (await res.json()) as InvoiceDetail;
      setNewInvoiceNotes("");
      setNewInvoiceDiscount("");
      await loadInvoices();
      setSelectedInvoice(invoice);
      setInvoiceNotes(invoice.notes || "");
      setInvoiceDiscount((invoice.discount_pence / 100).toFixed(2));
    } catch (err) {
      setInvoiceError(err instanceof Error ? err.message : "Failed to create invoice");
    } finally {
      setCreatingInvoice(false);
    }
  }

  async function saveInvoiceMeta() {
    if (!selectedInvoice) return;
    setInvoiceError(null);
    const discountPence = toPence(invoiceDiscount || "0");
    if (discountPence === null) {
      setInvoiceError("Discount must be a number.");
      return;
    }
    const payload: { notes?: string | null; discount_pence?: number } = {
      notes: invoiceNotes.trim() || null,
    };
    if (selectedInvoice.status === "draft") {
      payload.discount_pence = discountPence;
    }
    try {
      const res = await apiFetch(`/api/invoices/${selectedInvoice.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to update invoice (HTTP ${res.status})`);
      }
      const data = (await res.json()) as InvoiceDetail;
      setSelectedInvoice(data);
      await loadInvoices();
    } catch (err) {
      setInvoiceError(err instanceof Error ? err.message : "Failed to update invoice");
    }
  }

  async function addInvoiceLine() {
    if (!selectedInvoice) return;
    const quantity = Number(lineQuantity);
    const unitPence = toPence(lineUnitPrice);
    if (!lineDescription.trim() || Number.isNaN(quantity) || quantity < 1 || unitPence === null) {
      setInvoiceError("Enter a description, quantity, and unit price.");
      return;
    }
    setInvoiceError(null);
    try {
      const res = await apiFetch(`/api/invoices/${selectedInvoice.id}/lines`, {
        method: "POST",
        body: JSON.stringify({
          description: lineDescription.trim(),
          quantity,
          unit_price_pence: unitPence,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to add line (HTTP ${res.status})`);
      }
      setLineDescription("");
      setLineQuantity("1");
      setLineUnitPrice("");
      await loadInvoiceDetail(selectedInvoice.id);
      await loadInvoices();
    } catch (err) {
      setInvoiceError(err instanceof Error ? err.message : "Failed to add line");
    }
  }

  async function updateInvoiceLine(lineId: number) {
    if (!selectedInvoice) return;
    const draft = lineDrafts[lineId];
    if (!draft) return;
    const quantity = Number(draft.quantity);
    const unitPence = toPence(draft.unit_price);
    if (!draft.description.trim() || Number.isNaN(quantity) || quantity < 1 || unitPence === null) {
      setInvoiceError("Enter a description, quantity, and unit price.");
      return;
    }
    setInvoiceError(null);
    try {
      const res = await apiFetch(`/api/invoices/${selectedInvoice.id}/lines/${lineId}`, {
        method: "PATCH",
        body: JSON.stringify({
          description: draft.description.trim(),
          quantity,
          unit_price_pence: unitPence,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to update line (HTTP ${res.status})`);
      }
      await loadInvoiceDetail(selectedInvoice.id);
      await loadInvoices();
    } catch (err) {
      setInvoiceError(err instanceof Error ? err.message : "Failed to update line");
    }
  }

  async function deleteInvoiceLine(lineId: number) {
    if (!selectedInvoice) return;
    if (!confirm("Remove this line item?")) return;
    setInvoiceError(null);
    try {
      const res = await apiFetch(`/api/invoices/${selectedInvoice.id}/lines/${lineId}`, {
        method: "DELETE",
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok && res.status !== 204) {
        const msg = await res.text();
        throw new Error(msg || `Failed to delete line (HTTP ${res.status})`);
      }
      await loadInvoiceDetail(selectedInvoice.id);
      await loadInvoices();
    } catch (err) {
      setInvoiceError(err instanceof Error ? err.message : "Failed to delete line");
    }
  }

  async function issueInvoice() {
    if (!selectedInvoice) return;
    setInvoiceError(null);
    try {
      const res = await apiFetch(`/api/invoices/${selectedInvoice.id}/issue`, { method: "POST" });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to issue invoice (HTTP ${res.status})`);
      }
      const data = (await res.json()) as InvoiceDetail;
      setSelectedInvoice(data);
      await loadInvoices();
    } catch (err) {
      setInvoiceError(err instanceof Error ? err.message : "Failed to issue invoice");
    }
  }

  async function voidInvoice() {
    if (!selectedInvoice) return;
    if (!confirm("Void this invoice?")) return;
    setInvoiceError(null);
    try {
      const res = await apiFetch(`/api/invoices/${selectedInvoice.id}/void`, { method: "POST" });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to void invoice (HTTP ${res.status})`);
      }
      const data = (await res.json()) as InvoiceDetail;
      setSelectedInvoice(data);
      await loadInvoices();
    } catch (err) {
      setInvoiceError(err instanceof Error ? err.message : "Failed to void invoice");
    }
  }

  async function addPayment() {
    if (!selectedInvoice) return;
    if (recordingPayment) return;
    const amountPence = toPence(paymentAmount);
    if (amountPence === null || amountPence <= 0) {
      setInvoiceError("Payment amount must be a number.");
      return;
    }
    setRecordingPayment(true);
    setInvoiceError(null);
    try {
      const paidAt =
        paymentDate.trim() !== ""
          ? new Date(paymentDate).toISOString()
          : new Date().toISOString();
      const res = await apiFetch(`/api/invoices/${selectedInvoice.id}/payments`, {
        method: "POST",
        body: JSON.stringify({
          amount_pence: amountPence,
          method: paymentMethod,
          paid_at: paidAt,
          reference: paymentReference.trim() || null,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to add payment (HTTP ${res.status})`);
      }
      setPaymentAmount("");
      setPaymentReference("");
      setPaymentDate("");
      await loadInvoiceDetail(selectedInvoice.id);
      await loadInvoices();
    } catch (err) {
      setInvoiceError(err instanceof Error ? err.message : "Failed to add payment");
    } finally {
      setRecordingPayment(false);
    }
  }

  async function archivePatient() {
    if (!confirm("Archive this patient?")) return;
    try {
      const res = await apiFetch(`/api/patients/${patientId}/archive`, { method: "POST" });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to archive patient (HTTP ${res.status})`);
      }
      void loadPatient();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to archive patient");
    }
  }

  async function restorePatient() {
    try {
      const res = await apiFetch(`/api/patients/${patientId}/restore`, { method: "POST" });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to restore patient (HTTP ${res.status})`);
      }
      void loadPatient();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to restore patient");
    }
  }

  return (
    <div className="app-grid">
      <div>
        <Link className="btn btn-secondary" href="/patients">
          ← Back to patients
        </Link>
      </div>

      {loading ? (
        <div className="badge">Loading patient…</div>
      ) : error ? (
        <div className="notice">{error}</div>
      ) : patient ? (
        <div className="stack">
          <div className="card" style={{ position: "sticky", top: 12, zIndex: 1 }}>
            <div className="stack" style={{ gap: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
                <div>
                  <h2 style={{ margin: 0 }}>
                    {patient.first_name} {patient.last_name}
                  </h2>
                  <div style={{ color: "var(--muted)" }}>
                    Patient #{patient.id} • Created by {patient.created_by.email}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  {alerts.length === 0 && <span className="badge">No alerts</span>}
                  {alerts.map((alert) => (
                    <span
                      key={alert.label}
                      className="badge"
                      style={{
                        background: alert.tone === "danger" ? "#b13636" : "#b07b24",
                        color: "white",
                      }}
                    >
                      {alert.label}
                    </span>
                  ))}
                </div>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                  gap: 12,
                }}
              >
                <div>
                  <div className="label">DOB</div>
                  <div>{patient.date_of_birth || "—"}</div>
                </div>
                <div>
                  <div className="label">Phone</div>
                  <div>{patient.phone || "—"}</div>
                </div>
                <div>
                  <div className="label">Email</div>
                  <div>{patient.email || "—"}</div>
                </div>
                <div>
                  <div className="label">Address</div>
                  <div>{buildAddress(patient) || "—"}</div>
                </div>
              </div>

              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <button className="btn btn-secondary" type="button" onClick={copyAddress}>
                  Copy address
                </button>
                {copyNotice && <span className="badge">{copyNotice}</span>}
              </div>

              {(patient.allergies || patient.medical_alerts || patient.safeguarding_notes) && (
                <div className="grid grid-3">
                  <div className="stack" style={{ gap: 6 }}>
                    <div className="label">Allergies</div>
                    <div>{patient.allergies || "—"}</div>
                  </div>
                  <div className="stack" style={{ gap: 6 }}>
                    <div className="label">Medical alerts</div>
                    <div>{patient.medical_alerts || "—"}</div>
                  </div>
                  <div className="stack" style={{ gap: 6 }}>
                    <div className="label">Safeguarding</div>
                    <div>{patient.safeguarding_notes || "—"}</div>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <div className="stack">
              <div className="tabs">
                <button
                  className={`tab ${tab === "summary" ? "active" : ""}`}
                  onClick={() => setTab("summary")}
                >
                  Summary
                </button>
                <button
                  className={`tab ${tab === "notes" ? "active" : ""}`}
                  onClick={() => setTab("notes")}
                >
                  Notes ({notes.length})
                </button>
                <button
                  className={`tab ${tab === "invoices" ? "active" : ""}`}
                  onClick={() => setTab("invoices")}
                >
                  Invoices ({invoices.length})
                </button>
                <Link className="tab" href={`/patients/${patientId}/timeline`}>
                  Timeline
                </Link>
                <Link className="tab" href={`/patients/${patientId}/audit`}>
                  Audit
                </Link>
              </div>

              {tab === "summary" ? (
                <form onSubmit={savePatient} className="stack">
                  <div className="grid grid-2">
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">First name</label>
                      <input
                        className="input"
                        value={patient.first_name}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, first_name: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Last name</label>
                      <input
                        className="input"
                        value={patient.last_name}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, last_name: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="grid grid-2">
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Email</label>
                      <input
                        className="input"
                        value={patient.email ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, email: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Phone</label>
                      <input
                        className="input"
                        value={patient.phone ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, phone: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="grid grid-2">
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Date of birth</label>
                      <input
                        className="input"
                        value={patient.date_of_birth ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, date_of_birth: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="grid grid-2">
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Address line 1</label>
                      <input
                        className="input"
                        value={patient.address_line1 ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, address_line1: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Address line 2</label>
                      <input
                        className="input"
                        value={patient.address_line2 ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, address_line2: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="grid grid-2">
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">City</label>
                      <input
                        className="input"
                        value={patient.city ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, city: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Postcode</label>
                      <input
                        className="input"
                        value={patient.postcode ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, postcode: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="grid grid-3">
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Allergies</label>
                      <textarea
                        className="input"
                        rows={3}
                        value={patient.allergies ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, allergies: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Medical alerts</label>
                      <textarea
                        className="input"
                        rows={3}
                        value={patient.medical_alerts ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, medical_alerts: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Safeguarding notes</label>
                      <textarea
                        className="input"
                        rows={3}
                        value={patient.safeguarding_notes ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, safeguarding_notes: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Notes</label>
                    <textarea
                      className="input"
                      rows={4}
                      value={patient.notes ?? ""}
                      onChange={(e) =>
                        setPatient((prev) => (prev ? { ...prev, notes: e.target.value } : prev))
                      }
                    />
                  </div>

                  <div className="row">
                    <button className="btn btn-primary" disabled={savingPatient}>
                      {savingPatient ? "Saving..." : "Save changes"}
                    </button>
                    {patient.deleted_at ? (
                      <button className="btn btn-secondary" type="button" onClick={restorePatient}>
                        Restore patient
                      </button>
                    ) : (
                      <button className="btn btn-secondary" type="button" onClick={archivePatient}>
                        Archive patient
                      </button>
                    )}
                  </div>
                </form>
              ) : tab === "notes" ? (
                <div className="stack">
                  <div className="row">
                    <button
                      className="btn btn-secondary"
                      type="button"
                      onClick={() => {
                        setShowArchivedNotes((prev) => !prev);
                        void loadNotes(!showArchivedNotes);
                      }}
                    >
                      {showArchivedNotes ? "Hide archived" : "Show archived"}
                    </button>
                  </div>

                  <div className="card">
                    <div className="stack">
                      <label className="label">Add a note</label>
                      <textarea
                        className="input"
                        rows={3}
                        value={noteBody}
                        onChange={(e) => setNoteBody(e.target.value)}
                        placeholder="Write a clinical or admin note..."
                      />
                      <button className="btn btn-primary" onClick={addNote} disabled={savingNote}>
                        {savingNote ? "Saving..." : "Add note"}
                      </button>
                    </div>
                  </div>

                  <div className="stack">
                    {notes.length === 0 ? (
                      <div className="notice">No notes yet.</div>
                    ) : (
                      notes.map((note) => (
                        <div className="card" key={note.id}>
                          <div className="row">
                            <div>
                              <strong>{note.note_type}</strong>
                              <div style={{ color: "var(--muted)" }}>
                                {new Date(note.created_at).toLocaleString()} • {note.created_by.email}
                              </div>
                            </div>
                            <Link className="btn btn-secondary" href={`/notes/${note.id}/audit`}>
                              View audit
                            </Link>
                          </div>
                          <p style={{ marginBottom: 0 }}>{note.body}</p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ) : (
                <div className="stack">
                  <div className="row">
                    <button className="btn btn-secondary" type="button" onClick={loadInvoices}>
                      Refresh
                    </button>
                  </div>

                  {invoiceError && <div className="notice">{invoiceError}</div>}
                  {loadingInvoices ? (
                    <div className="badge">Loading invoices…</div>
                  ) : invoices.length === 0 ? (
                    <div className="notice">No invoices yet.</div>
                  ) : (
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Invoice</th>
                          <th>Issued</th>
                          <th>Status</th>
                          <th>Total</th>
                          <th>Balance</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {invoices.map((invoice) => (
                          <tr key={invoice.id}>
                            <td>{invoice.invoice_number}</td>
                            <td>{invoice.issue_date || "—"}</td>
                            <td>{invoice.status}</td>
                            <td>{formatPence(invoice.total_pence)}</td>
                            <td>{formatPence(invoice.balance_pence)}</td>
                            <td>
                              <div className="table-actions">
                                <button
                                  className="btn btn-secondary"
                                  onClick={() => loadInvoiceDetail(invoice.id)}
                                >
                                  View
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}

                  <div className="card" style={{ margin: 0 }}>
                    <div className="stack">
                      <h4 style={{ marginTop: 0 }}>New invoice details</h4>
                      <div className="stack" style={{ gap: 8 }}>
                        <label className="label">Notes</label>
                        <textarea
                          className="input"
                          rows={3}
                          value={newInvoiceNotes}
                          onChange={(e) => setNewInvoiceNotes(e.target.value)}
                          placeholder="Optional notes for this invoice"
                        />
                      </div>
                      <div className="stack" style={{ gap: 8 }}>
                        <label className="label">Discount (£)</label>
                        <input
                          className="input"
                          value={newInvoiceDiscount}
                          onChange={(e) => setNewInvoiceDiscount(e.target.value)}
                          placeholder="0.00"
                        />
                      </div>
                      <button className="btn btn-primary" type="button" onClick={createInvoice}>
                        {creatingInvoice ? "Creating..." : "New invoice"}
                      </button>
                    </div>
                  </div>

                  {selectedInvoice && (
                    <div className="card" style={{ margin: 0 }}>
                      <div className="stack">
                        <div className="row">
                          <div>
                            <h3 style={{ marginTop: 0 }}>{selectedInvoice.invoice_number}</h3>
                            <div style={{ color: "var(--muted)" }}>
                              Status: {selectedInvoice.status} · Issued:{" "}
                              {selectedInvoice.issue_date || "—"}
                            </div>
                          </div>
                          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                            {selectedInvoice.status === "draft" && (
                              <button className="btn btn-primary" onClick={issueInvoice}>
                                Issue invoice
                              </button>
                            )}
                            {selectedInvoice.status !== "void" && (
                              <button className="btn btn-secondary" onClick={voidInvoice}>
                                Void invoice
                              </button>
                            )}
                          </div>
                        </div>

                        <div className="grid grid-3">
                          <div>
                            <div className="label">Subtotal</div>
                            <div>{formatPence(selectedInvoice.subtotal_pence)}</div>
                          </div>
                          <div>
                            <div className="label">Discount</div>
                            <div>{formatPence(selectedInvoice.discount_pence)}</div>
                          </div>
                          <div>
                            <div className="label">Total</div>
                            <div>{formatPence(selectedInvoice.total_pence)}</div>
                          </div>
                          <div>
                            <div className="label">Paid</div>
                            <div>{formatPence(selectedInvoice.paid_pence)}</div>
                          </div>
                          <div>
                            <div className="label">Balance</div>
                            <div>{formatPence(selectedInvoice.balance_pence)}</div>
                          </div>
                        </div>

                        <div className="stack" style={{ gap: 8 }}>
                          <label className="label">Invoice notes</label>
                          <textarea
                            className="input"
                            rows={3}
                            value={invoiceNotes}
                            onChange={(e) => setInvoiceNotes(e.target.value)}
                          />
                        </div>
                        <div className="stack" style={{ gap: 8 }}>
                          <label className="label">Discount (£)</label>
                          <input
                            className="input"
                            value={invoiceDiscount}
                            onChange={(e) => setInvoiceDiscount(e.target.value)}
                            disabled={selectedInvoice.status !== "draft"}
                          />
                        </div>
                        <button className="btn btn-secondary" type="button" onClick={saveInvoiceMeta}>
                          Save invoice
                        </button>

                        <div className="card" style={{ margin: 0 }}>
                          <div className="stack">
                            <h4 style={{ marginTop: 0 }}>Line items</h4>
                            {selectedInvoice.lines.length === 0 ? (
                              <div className="notice">No line items yet.</div>
                            ) : (
                              <table className="table">
                                <thead>
                                  <tr>
                                    <th>Description</th>
                                    <th>Qty</th>
                                    <th>Unit (£)</th>
                                    <th>Total</th>
                                    <th>Actions</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {selectedInvoice.lines.map((line) => (
                                    <tr key={line.id}>
                                      <td>
                                        <input
                                          className="input"
                                          value={lineDrafts[line.id]?.description || ""}
                                          onChange={(e) =>
                                            setLineDrafts((prev) => ({
                                              ...prev,
                                              [line.id]: {
                                                ...prev[line.id],
                                                description: e.target.value,
                                              },
                                            }))
                                          }
                                          disabled={selectedInvoice.status !== "draft"}
                                        />
                                      </td>
                                      <td>
                                        <input
                                          className="input"
                                          value={lineDrafts[line.id]?.quantity || ""}
                                          onChange={(e) =>
                                            setLineDrafts((prev) => ({
                                              ...prev,
                                              [line.id]: {
                                                ...prev[line.id],
                                                quantity: e.target.value,
                                              },
                                            }))
                                          }
                                          disabled={selectedInvoice.status !== "draft"}
                                        />
                                      </td>
                                      <td>
                                        <input
                                          className="input"
                                          value={lineDrafts[line.id]?.unit_price || ""}
                                          onChange={(e) =>
                                            setLineDrafts((prev) => ({
                                              ...prev,
                                              [line.id]: {
                                                ...prev[line.id],
                                                unit_price: e.target.value,
                                              },
                                            }))
                                          }
                                          disabled={selectedInvoice.status !== "draft"}
                                        />
                                      </td>
                                      <td>{formatPence(line.line_total_pence)}</td>
                                      <td>
                                        <div className="table-actions">
                                          <button
                                            className="btn btn-secondary"
                                            disabled={selectedInvoice.status !== "draft"}
                                            onClick={() => updateInvoiceLine(line.id)}
                                          >
                                            Update
                                          </button>
                                          <button
                                            className="btn btn-secondary"
                                            disabled={selectedInvoice.status !== "draft"}
                                            onClick={() => deleteInvoiceLine(line.id)}
                                          >
                                            Remove
                                          </button>
                                        </div>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}

                            <div className="grid grid-3">
                              <div className="stack" style={{ gap: 8 }}>
                                <label className="label">Description</label>
                                <input
                                  className="input"
                                  value={lineDescription}
                                  onChange={(e) => setLineDescription(e.target.value)}
                                  disabled={selectedInvoice.status !== "draft"}
                                />
                              </div>
                              <div className="stack" style={{ gap: 8 }}>
                                <label className="label">Qty</label>
                                <input
                                  className="input"
                                  value={lineQuantity}
                                  onChange={(e) => setLineQuantity(e.target.value)}
                                  disabled={selectedInvoice.status !== "draft"}
                                />
                              </div>
                              <div className="stack" style={{ gap: 8 }}>
                                <label className="label">Unit price (£)</label>
                                <input
                                  className="input"
                                  value={lineUnitPrice}
                                  onChange={(e) => setLineUnitPrice(e.target.value)}
                                  disabled={selectedInvoice.status !== "draft"}
                                />
                              </div>
                            </div>
                            <button
                              className="btn btn-primary"
                              type="button"
                              onClick={addInvoiceLine}
                              disabled={selectedInvoice.status !== "draft"}
                            >
                              Add line
                            </button>
                          </div>
                        </div>

                        <div className="card" style={{ margin: 0 }}>
                          <div className="stack">
                            <h4 style={{ marginTop: 0 }}>Payments</h4>
                            {selectedInvoice.payments.length === 0 ? (
                              <div className="notice">No payments recorded.</div>
                            ) : (
                              <table className="table">
                                <thead>
                                  <tr>
                                    <th>Date</th>
                                    <th>Method</th>
                                    <th>Amount</th>
                                    <th>Reference</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {selectedInvoice.payments.map((payment) => (
                                    <tr key={payment.id}>
                                      <td>{new Date(payment.paid_at).toLocaleDateString()}</td>
                                      <td>{payment.method}</td>
                                      <td>{formatPence(payment.amount_pence)}</td>
                                      <td>{payment.reference || "—"}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}

                            <div className="grid grid-3">
                              <div className="stack" style={{ gap: 8 }}>
                                <label className="label">Amount (£)</label>
                                <input
                                  className="input"
                                  value={paymentAmount}
                                  onChange={(e) => setPaymentAmount(e.target.value)}
                                  disabled={
                                    selectedInvoice.status === "draft" ||
                                    selectedInvoice.status === "void"
                                  }
                                />
                              </div>
                              <div className="stack" style={{ gap: 8 }}>
                                <label className="label">Method</label>
                                <select
                                  className="input"
                                  value={paymentMethod}
                                  onChange={(e) => setPaymentMethod(e.target.value)}
                                  disabled={
                                    selectedInvoice.status === "draft" ||
                                    selectedInvoice.status === "void"
                                  }
                                >
                                  <option value="card">Card</option>
                                  <option value="cash">Cash</option>
                                  <option value="bank_transfer">Bank transfer</option>
                                  <option value="other">Other</option>
                                </select>
                              </div>
                              <div className="stack" style={{ gap: 8 }}>
                                <label className="label">Paid date</label>
                                <input
                                  className="input"
                                  type="date"
                                  value={paymentDate}
                                  onChange={(e) => setPaymentDate(e.target.value)}
                                  disabled={
                                    selectedInvoice.status === "draft" ||
                                    selectedInvoice.status === "void"
                                  }
                                />
                              </div>
                            </div>
                            <div className="stack" style={{ gap: 8 }}>
                              <label className="label">Reference</label>
                              <input
                                className="input"
                                value={paymentReference}
                                onChange={(e) => setPaymentReference(e.target.value)}
                                disabled={
                                  selectedInvoice.status === "draft" ||
                                  selectedInvoice.status === "void"
                                }
                              />
                            </div>
                            <button
                              className="btn btn-primary"
                              type="button"
                              onClick={addPayment}
                              disabled={
                                recordingPayment ||
                                selectedInvoice.status === "draft" ||
                                selectedInvoice.status === "void"
                              }
                            >
                              {recordingPayment ? "Recording..." : "Record payment"}
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <Timeline items={timeline} title="Recent activity" />
          </div>
        </div>
      ) : (
        <div className="notice">Patient not found.</div>
      )}
    </div>
  );
}
