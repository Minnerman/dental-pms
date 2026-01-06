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

type PatientCategory = "CLINIC_PRIVATE" | "DOMICILIARY_PRIVATE" | "DENPLAN";
type CareSetting = "CLINIC" | "HOME" | "CARE_HOME" | "HOSPITAL";

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
  patient_category: PatientCategory;
  denplan_member_no?: string | null;
  denplan_plan_name?: string | null;
  care_setting: CareSetting;
  visit_address_text?: string | null;
  access_notes?: string | null;
  primary_contact_name?: string | null;
  primary_contact_phone?: string | null;
  primary_contact_relationship?: string | null;
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

type EstimateStatus = "DRAFT" | "ISSUED" | "ACCEPTED" | "DECLINED" | "SUPERSEDED";
type EstimateFeeType = "FIXED" | "RANGE";

type EstimateItem = {
  id: number;
  treatment_id?: number | null;
  description: string;
  qty: number;
  fee_type: EstimateFeeType;
  unit_amount_pence?: number | null;
  min_unit_amount_pence?: number | null;
  max_unit_amount_pence?: number | null;
  sort_order: number;
};

type Estimate = {
  id: number;
  patient_id: number;
  appointment_id?: number | null;
  category_snapshot: PatientCategory;
  status: EstimateStatus;
  valid_until?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  items: EstimateItem[];
};

type Treatment = {
  id: number;
  code?: string | null;
  name: string;
  description?: string | null;
  is_active: boolean;
  default_duration_minutes?: number | null;
  is_denplan_included_default: boolean;
};

const categoryLabels: Record<PatientCategory, string> = {
  CLINIC_PRIVATE: "Clinic (Private)",
  DOMICILIARY_PRIVATE: "Domiciliary (Private)",
  DENPLAN: "Denplan",
};

const careSettingLabels: Record<CareSetting, string> = {
  CLINIC: "Clinic",
  HOME: "Home",
  CARE_HOME: "Care home",
  HOSPITAL: "Hospital",
};

export default function PatientDetailClient({ id }: { id: string }) {
  const router = useRouter();
  const patientId = id;
  const [patient, setPatient] = useState<Patient | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [tab, setTab] = useState<"summary" | "notes" | "invoices" | "estimates">(
    "summary"
  );
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
  const [estimates, setEstimates] = useState<Estimate[]>([]);
  const [loadingEstimates, setLoadingEstimates] = useState(false);
  const [estimateError, setEstimateError] = useState<string | null>(null);
  const [selectedEstimate, setSelectedEstimate] = useState<Estimate | null>(null);
  const [creatingEstimate, setCreatingEstimate] = useState(false);
  const [estimateNotes, setEstimateNotes] = useState("");
  const [estimateValidUntil, setEstimateValidUntil] = useState("");
  const [estimateItemTreatmentId, setEstimateItemTreatmentId] = useState("");
  const [estimateItemDescription, setEstimateItemDescription] = useState("");
  const [estimateItemQty, setEstimateItemQty] = useState("1");
  const [estimateItemFeeType, setEstimateItemFeeType] = useState<EstimateFeeType>("FIXED");
  const [estimateItemAmount, setEstimateItemAmount] = useState("");
  const [estimateItemMinAmount, setEstimateItemMinAmount] = useState("");
  const [estimateItemMaxAmount, setEstimateItemMaxAmount] = useState("");
  const [treatments, setTreatments] = useState<Treatment[]>([]);

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

  async function loadTreatments() {
    try {
      const res = await apiFetch("/api/treatments?include_inactive=1");
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.ok) {
        const data = (await res.json()) as Treatment[];
        setTreatments(data);
      }
    } catch {
      setTreatments([]);
    }
  }

  async function loadEstimates() {
    setLoadingEstimates(true);
    setEstimateError(null);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/estimates`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load estimates (HTTP ${res.status})`);
      }
      const data = (await res.json()) as Estimate[];
      setEstimates(data);
      if (selectedEstimate) {
        const next = data.find((estimate) => estimate.id === selectedEstimate.id) || null;
        setSelectedEstimate(next);
      }
    } catch (err) {
      setEstimateError(err instanceof Error ? err.message : "Failed to load estimates");
    } finally {
      setLoadingEstimates(false);
    }
  }

  async function loadEstimateDetail(estimateId: number) {
    setEstimateError(null);
    try {
      const res = await apiFetch(`/api/estimates/${estimateId}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load estimate (HTTP ${res.status})`);
      }
      const data = (await res.json()) as Estimate;
      setSelectedEstimate(data);
    } catch (err) {
      setEstimateError(err instanceof Error ? err.message : "Failed to load estimate");
    }
  }

  async function createEstimate() {
    if (creatingEstimate) return;
    setCreatingEstimate(true);
    setEstimateError(null);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/estimates`, {
        method: "POST",
        body: JSON.stringify({
          notes: estimateNotes || null,
          valid_until: estimateValidUntil || null,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to create estimate (HTTP ${res.status})`);
      }
      const data = (await res.json()) as Estimate;
      setEstimateNotes("");
      setEstimateValidUntil("");
      await loadEstimates();
      setSelectedEstimate(data);
    } catch (err) {
      setEstimateError(err instanceof Error ? err.message : "Failed to create estimate");
    } finally {
      setCreatingEstimate(false);
    }
  }

  async function addEstimateItem() {
    if (!selectedEstimate) return;
    setEstimateError(null);
    const qty = Number(estimateItemQty);
    if (!Number.isFinite(qty) || qty <= 0) {
      setEstimateError("Quantity must be a positive number.");
      return;
    }
    const payload: Record<string, unknown> = {
      treatment_id: estimateItemTreatmentId ? Number(estimateItemTreatmentId) : null,
      description: estimateItemDescription || null,
      qty,
      fee_type: estimateItemFeeType,
    };

    if (estimateItemFeeType === "FIXED") {
      const amount = toPence(estimateItemAmount);
      if (amount === null) {
        setEstimateError("Enter a valid fixed amount.");
        return;
      }
      payload.unit_amount_pence = amount;
    } else {
      const min = toPence(estimateItemMinAmount);
      const max = toPence(estimateItemMaxAmount);
      if (min === null || max === null) {
        setEstimateError("Enter valid min/max values for a range.");
        return;
      }
      payload.min_unit_amount_pence = min;
      payload.max_unit_amount_pence = max;
    }

    try {
      const res = await apiFetch(`/api/estimates/${selectedEstimate.id}/items`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to add estimate item (HTTP ${res.status})`);
      }
      setEstimateItemTreatmentId("");
      setEstimateItemDescription("");
      setEstimateItemQty("1");
      setEstimateItemFeeType("FIXED");
      setEstimateItemAmount("");
      setEstimateItemMinAmount("");
      setEstimateItemMaxAmount("");
      await loadEstimateDetail(selectedEstimate.id);
      await loadEstimates();
    } catch (err) {
      setEstimateError(err instanceof Error ? err.message : "Failed to add estimate item");
    }
  }

  async function deleteEstimateItem(itemId: number) {
    if (!selectedEstimate) return;
    setEstimateError(null);
    try {
      const res = await apiFetch(`/api/estimates/${selectedEstimate.id}/items/${itemId}`, {
        method: "DELETE",
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to delete estimate item (HTTP ${res.status})`);
      }
      await loadEstimateDetail(selectedEstimate.id);
      await loadEstimates();
    } catch (err) {
      setEstimateError(err instanceof Error ? err.message : "Failed to delete estimate item");
    }
  }

  async function updateEstimateStatus(nextStatus: EstimateStatus) {
    if (!selectedEstimate) return;
    setEstimateError(null);
    try {
      const res = await apiFetch(`/api/estimates/${selectedEstimate.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: nextStatus }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to update estimate (HTTP ${res.status})`);
      }
      const data = (await res.json()) as Estimate;
      setSelectedEstimate(data);
      await loadEstimates();
    } catch (err) {
      setEstimateError(err instanceof Error ? err.message : "Failed to update estimate");
    }
  }

  useEffect(() => {
    void loadPatient();
    void loadNotes();
    void loadTimeline();
    void loadInvoices();
    void loadTreatments();
    void loadEstimates();
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

  function formatEstimateTotal(items: EstimateItem[]) {
    if (!items.length) return "—";
    let minTotal = 0;
    let maxTotal = 0;
    let hasRange = false;
    items.forEach((item) => {
      const qty = Math.max(item.qty || 1, 1);
      if (item.fee_type === "RANGE") {
        hasRange = true;
        minTotal += (item.min_unit_amount_pence ?? 0) * qty;
        maxTotal += (item.max_unit_amount_pence ?? 0) * qty;
      } else {
        const value = (item.unit_amount_pence ?? 0) * qty;
        minTotal += value;
        maxTotal += value;
      }
    });
    if (hasRange) {
      return `${formatPence(minTotal)} - ${formatPence(maxTotal)}`;
    }
    return formatPence(minTotal);
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
          patient_category: patient.patient_category,
          denplan_plan_name:
            patient.patient_category === "DENPLAN" ? patient.denplan_plan_name : null,
          denplan_member_no:
            patient.patient_category === "DENPLAN" ? patient.denplan_member_no : null,
          care_setting: patient.care_setting,
          visit_address_text:
            patient.care_setting === "CLINIC" ? null : patient.visit_address_text,
          access_notes: patient.care_setting === "CLINIC" ? null : patient.access_notes,
          primary_contact_name:
            patient.care_setting === "CLINIC" ? null : patient.primary_contact_name,
          primary_contact_phone:
            patient.care_setting === "CLINIC" ? null : patient.primary_contact_phone,
          primary_contact_relationship:
            patient.care_setting === "CLINIC" ? null : patient.primary_contact_relationship,
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

  async function downloadPdf(path: string, filename: string) {
    setInvoiceError(null);
    try {
      const res = await apiFetch(path);
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
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setInvoiceError(err instanceof Error ? err.message : "Failed to download PDF");
    }
  }

  function buildEstimateFilename() {
    const date = new Date().toISOString().slice(0, 10);
    if (!patient) return `Estimate_${patientId}_${date}.pdf`;
    const rawName = `${patient.first_name}_${patient.last_name}`;
    const safeName = rawName.replace(/[^a-zA-Z0-9-_]+/g, "_");
    return `Estimate_${safeName}_${date}.pdf`;
  }

  async function downloadEstimatePdf(estimateId: number) {
    setEstimateError(null);
    try {
      const res = await apiFetch(`/api/estimates/${estimateId}/pdf`);
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
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = buildEstimateFilename();
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setEstimateError(err instanceof Error ? err.message : "Failed to download PDF");
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
                  <div className="label">Category</div>
                  <div>
                    <span className="badge">{categoryLabels[patient.patient_category]}</span>
                  </div>
                </div>
                <div>
                  <div className="label">Care setting</div>
                  <div>
                    <span className="badge">{careSettingLabels[patient.care_setting]}</span>
                  </div>
                </div>
                <div>
                  <div className="label">Address</div>
                  <div>{buildAddress(patient) || "—"}</div>
                </div>
                <div>
                  <div className="label">Denplan plan</div>
                  <div>
                    {patient.patient_category === "DENPLAN" && patient.denplan_plan_name
                      ? patient.denplan_plan_name
                      : "—"}
                  </div>
                </div>
                <div>
                  <div className="label">Denplan member</div>
                  <div>
                    {patient.patient_category === "DENPLAN" && patient.denplan_member_no
                      ? patient.denplan_member_no
                      : "—"}
                  </div>
                </div>
              </div>

              {patient.care_setting !== "CLINIC" && (
                <div className="card" style={{ margin: 0 }}>
                  <div className="stack" style={{ gap: 6 }}>
                    <div className="label">Visit summary</div>
                    <div>
                      <strong>Visit address:</strong>{" "}
                      {patient.visit_address_text || "—"}
                    </div>
                    <div>
                      <strong>Access notes:</strong> {patient.access_notes || "—"}
                    </div>
                    <div>
                      <strong>Primary contact:</strong>{" "}
                      {patient.primary_contact_name || "—"}{" "}
                      {patient.primary_contact_relationship
                        ? `(${patient.primary_contact_relationship})`
                        : ""}
                      {patient.primary_contact_phone ? ` · ${patient.primary_contact_phone}` : ""}
                    </div>
                  </div>
                </div>
              )}

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
                <button
                  className={`tab ${tab === "estimates" ? "active" : ""}`}
                  onClick={() => setTab("estimates")}
                >
                  Estimates ({estimates.length})
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
                      <label className="label">Patient category</label>
                      <select
                        className="input"
                        value={patient.patient_category}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev
                              ? {
                                  ...prev,
                                  patient_category: e.target.value as PatientCategory,
                                }
                              : prev
                          )
                        }
                      >
                        <option value="CLINIC_PRIVATE">Clinic (Private)</option>
                        <option value="DOMICILIARY_PRIVATE">Domiciliary (Private)</option>
                        <option value="DENPLAN">Denplan</option>
                      </select>
                      {patient.patient_category === "DENPLAN" && (
                        <p style={{ margin: 0, color: "var(--muted)", fontSize: 12 }}>
                          Most care included; excluded items can be added as private charges via
                          estimates.
                        </p>
                      )}
                    </div>
                    {patient.patient_category === "DENPLAN" ? (
                      <div className="stack" style={{ gap: 8 }}>
                        <label className="label">Denplan plan name</label>
                        <input
                          className="input"
                          value={patient.denplan_plan_name ?? ""}
                          onChange={(e) =>
                            setPatient((prev) =>
                              prev ? { ...prev, denplan_plan_name: e.target.value } : prev
                            )
                          }
                        />
                        <label className="label">Denplan member number</label>
                        <input
                          className="input"
                          value={patient.denplan_member_no ?? ""}
                          onChange={(e) =>
                            setPatient((prev) =>
                              prev ? { ...prev, denplan_member_no: e.target.value } : prev
                            )
                          }
                        />
                      </div>
                    ) : (
                      <div className="stack" style={{ gap: 8 }}>
                        <label className="label">Denplan plan name</label>
                        <input className="input" value="—" readOnly />
                        <label className="label">Denplan member number</label>
                        <input className="input" value="—" readOnly />
                      </div>
                    )}
                  </div>

                  <div className="grid grid-2">
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Care setting</label>
                      <select
                        className="input"
                        value={patient.care_setting}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, care_setting: e.target.value as CareSetting } : prev
                          )
                        }
                      >
                        <option value="CLINIC">Clinic</option>
                        <option value="HOME">Home</option>
                        <option value="CARE_HOME">Care home</option>
                        <option value="HOSPITAL">Hospital</option>
                      </select>
                    </div>
                    {patient.care_setting !== "CLINIC" ? (
                      <div className="stack" style={{ gap: 8 }}>
                        <label className="label">Visit address</label>
                        <textarea
                          className="input"
                          rows={2}
                          value={patient.visit_address_text ?? ""}
                          onChange={(e) =>
                            setPatient((prev) =>
                              prev ? { ...prev, visit_address_text: e.target.value } : prev
                            )
                          }
                        />
                      </div>
                    ) : (
                      <div className="stack" style={{ gap: 8 }}>
                        <label className="label">Visit address</label>
                        <input className="input" value="—" readOnly />
                      </div>
                    )}
                  </div>

                  {patient.care_setting !== "CLINIC" && (
                    <div className="stack" style={{ gap: 12 }}>
                      <div className="stack" style={{ gap: 8 }}>
                        <label className="label">Access notes</label>
                        <textarea
                          className="input"
                          rows={2}
                          value={patient.access_notes ?? ""}
                          onChange={(e) =>
                            setPatient((prev) =>
                              prev ? { ...prev, access_notes: e.target.value } : prev
                            )
                          }
                        />
                      </div>
                      <div style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr 1fr" }}>
                        <div className="stack" style={{ gap: 8 }}>
                          <label className="label">Primary contact</label>
                          <input
                            className="input"
                            value={patient.primary_contact_name ?? ""}
                            onChange={(e) =>
                              setPatient((prev) =>
                                prev ? { ...prev, primary_contact_name: e.target.value } : prev
                              )
                            }
                          />
                        </div>
                        <div className="stack" style={{ gap: 8 }}>
                          <label className="label">Contact phone</label>
                          <input
                            className="input"
                            value={patient.primary_contact_phone ?? ""}
                            onChange={(e) =>
                              setPatient((prev) =>
                                prev ? { ...prev, primary_contact_phone: e.target.value } : prev
                              )
                            }
                          />
                        </div>
                        <div className="stack" style={{ gap: 8 }}>
                          <label className="label">Relationship</label>
                          <input
                            className="input"
                            value={patient.primary_contact_relationship ?? ""}
                            onChange={(e) =>
                              setPatient((prev) =>
                                prev
                                  ? { ...prev, primary_contact_relationship: e.target.value }
                                  : prev
                              )
                            }
                          />
                        </div>
                      </div>
                    </div>
                  )}

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
              ) : tab === "estimates" ? (
                <div className="stack">
                  <div className="row">
                    <button className="btn btn-secondary" type="button" onClick={loadEstimates}>
                      Refresh
                    </button>
                  </div>

                  {estimateError && <div className="notice">{estimateError}</div>}
                  {loadingEstimates ? (
                    <div className="badge">Loading estimates…</div>
                  ) : estimates.length === 0 ? (
                    <div className="notice">No estimates yet.</div>
                  ) : (
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Estimate</th>
                          <th>Status</th>
                          <th>Created</th>
                          <th>Total</th>
                          <th>Appointment</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {estimates.map((estimate) => (
                          <tr key={estimate.id}>
                            <td>EST-{estimate.id}</td>
                            <td>{estimate.status}</td>
                            <td>{new Date(estimate.created_at).toLocaleString()}</td>
                            <td>{formatEstimateTotal(estimate.items)}</td>
                            <td>{estimate.appointment_id ?? "—"}</td>
                            <td>
                              <div className="table-actions">
                                <button
                                  className="btn btn-secondary"
                                  onClick={() => loadEstimateDetail(estimate.id)}
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
                      <h4 style={{ marginTop: 0 }}>New estimate</h4>
                      <div className="grid grid-2">
                        <div className="stack" style={{ gap: 8 }}>
                          <label className="label">Valid until</label>
                          <input
                            className="input"
                            type="date"
                            value={estimateValidUntil}
                            onChange={(e) => setEstimateValidUntil(e.target.value)}
                          />
                        </div>
                        <div className="stack" style={{ gap: 8 }}>
                          <label className="label">Notes</label>
                          <input
                            className="input"
                            value={estimateNotes}
                            onChange={(e) => setEstimateNotes(e.target.value)}
                            placeholder="Optional estimate notes"
                          />
                        </div>
                      </div>
                      <button
                        className="btn btn-primary"
                        type="button"
                        onClick={createEstimate}
                        disabled={creatingEstimate}
                      >
                        {creatingEstimate ? "Creating..." : "Create estimate"}
                      </button>
                    </div>
                  </div>

                  {selectedEstimate && (
                    <div className="card" style={{ margin: 0 }}>
                      <div className="stack">
                        <div className="row">
                          <div>
                            <h3 style={{ marginTop: 0 }}>EST-{selectedEstimate.id}</h3>
                            <div style={{ color: "var(--muted)" }}>
                              Status: {selectedEstimate.status} · Category:{" "}
                              {categoryLabels[selectedEstimate.category_snapshot]}
                            </div>
                          </div>
                          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                            <button
                              className="btn btn-secondary"
                              onClick={() => downloadEstimatePdf(selectedEstimate.id)}
                            >
                              Download PDF
                            </button>
                            <button
                              className="btn btn-secondary"
                              onClick={() => updateEstimateStatus("ISSUED")}
                            >
                              Mark issued
                            </button>
                            <button
                              className="btn btn-secondary"
                              onClick={() => updateEstimateStatus("ACCEPTED")}
                            >
                              Mark accepted
                            </button>
                            <button
                              className="btn btn-secondary"
                              onClick={() => updateEstimateStatus("DECLINED")}
                            >
                              Mark declined
                            </button>
                          </div>
                        </div>

                        <div className="stack" style={{ gap: 8 }}>
                          <label className="label">Add line item</label>
                          <div className="grid grid-3">
                            <div className="stack" style={{ gap: 8 }}>
                              <label className="label">Treatment</label>
                              <select
                                className="input"
                                value={estimateItemTreatmentId}
                                onChange={(e) => {
                                  const next = e.target.value;
                                  setEstimateItemTreatmentId(next);
                                  if (!estimateItemDescription && next) {
                                    const treatment = treatments.find(
                                      (item) => String(item.id) === next
                                    );
                                    if (treatment) {
                                      setEstimateItemDescription(treatment.name);
                                    }
                                  }
                                }}
                              >
                                <option value="">Free text</option>
                                {treatments.map((treatment) => (
                                  <option key={treatment.id} value={treatment.id}>
                                    {treatment.name}
                                  </option>
                                ))}
                              </select>
                            </div>
                            <div className="stack" style={{ gap: 8 }}>
                              <label className="label">Description</label>
                              <input
                                className="input"
                                value={estimateItemDescription}
                                onChange={(e) => setEstimateItemDescription(e.target.value)}
                                placeholder="e.g. Composite filling"
                              />
                            </div>
                            <div className="stack" style={{ gap: 8 }}>
                              <label className="label">Qty</label>
                              <input
                                className="input"
                                value={estimateItemQty}
                                onChange={(e) => setEstimateItemQty(e.target.value)}
                              />
                            </div>
                          </div>
                          <div className="grid grid-3">
                            <div className="stack" style={{ gap: 8 }}>
                              <label className="label">Fee type</label>
                              <select
                                className="input"
                                value={estimateItemFeeType}
                                onChange={(e) =>
                                  setEstimateItemFeeType(e.target.value as EstimateFeeType)
                                }
                              >
                                <option value="FIXED">Fixed</option>
                                <option value="RANGE">Range</option>
                              </select>
                            </div>
                            {estimateItemFeeType === "FIXED" ? (
                              <div className="stack" style={{ gap: 8 }}>
                                <label className="label">Amount (£)</label>
                                <input
                                  className="input"
                                  value={estimateItemAmount}
                                  onChange={(e) => setEstimateItemAmount(e.target.value)}
                                />
                              </div>
                            ) : (
                              <>
                                <div className="stack" style={{ gap: 8 }}>
                                  <label className="label">Min (£)</label>
                                  <input
                                    className="input"
                                    value={estimateItemMinAmount}
                                    onChange={(e) => setEstimateItemMinAmount(e.target.value)}
                                  />
                                </div>
                                <div className="stack" style={{ gap: 8 }}>
                                  <label className="label">Max (£)</label>
                                  <input
                                    className="input"
                                    value={estimateItemMaxAmount}
                                    onChange={(e) => setEstimateItemMaxAmount(e.target.value)}
                                  />
                                </div>
                              </>
                            )}
                          </div>
                          <button className="btn btn-primary" type="button" onClick={addEstimateItem}>
                            Add item
                          </button>
                        </div>

                        {selectedEstimate.items.length === 0 ? (
                          <div className="notice">No items yet.</div>
                        ) : (
                          <table className="table">
                            <thead>
                              <tr>
                                <th>Description</th>
                                <th>Qty</th>
                                <th>Fee</th>
                                <th>Actions</th>
                              </tr>
                            </thead>
                            <tbody>
                              {selectedEstimate.items.map((item) => (
                                <tr key={item.id}>
                                  <td>{item.description}</td>
                                  <td>{item.qty}</td>
                                  <td>
                                    {item.fee_type === "RANGE"
                                      ? `${formatPence(item.min_unit_amount_pence ?? 0)} - ${formatPence(
                                          item.max_unit_amount_pence ?? 0
                                        )}`
                                      : formatPence(item.unit_amount_pence ?? 0)}
                                  </td>
                                  <td>
                                    <button
                                      className="btn btn-secondary"
                                      type="button"
                                      onClick={() => deleteEstimateItem(item.id)}
                                    >
                                      Remove
                                    </button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    </div>
                  )}
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
                            <button
                              className="btn btn-secondary"
                              onClick={() =>
                                downloadPdf(
                                  `/api/invoices/${selectedInvoice.id}/pdf`,
                                  `${selectedInvoice.invoice_number}.pdf`
                                )
                              }
                            >
                              Download PDF
                            </button>
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
                                    <th>Receipt</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {selectedInvoice.payments.map((payment) => (
                                    <tr key={payment.id}>
                                      <td>{new Date(payment.paid_at).toLocaleDateString()}</td>
                                      <td>{payment.method}</td>
                                      <td>{formatPence(payment.amount_pence)}</td>
                                      <td>{payment.reference || "—"}</td>
                                      <td>
                                        <button
                                          className="btn btn-secondary"
                                          onClick={() =>
                                            downloadPdf(
                                              `/api/payments/${payment.id}/receipt.pdf`,
                                              `receipt-${selectedInvoice.invoice_number}-${payment.id}.pdf`
                                            )
                                          }
                                        >
                                          Receipt
                                        </button>
                                      </td>
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
