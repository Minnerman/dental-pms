"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import Timeline from "@/components/timeline/Timeline";
import { apiFetch, clearToken } from "@/lib/auth";
import StatusIcon from "@/components/ui/StatusIcon";
import Panel from "@/components/ui/Panel";
import Table from "@/components/ui/Table";
import PatientDocuments from "./PatientDocuments";
import PatientAttachments from "./PatientAttachments";

type Actor = {
  id: number;
  email: string;
  role: string;
};

type PatientCategory = "CLINIC_PRIVATE" | "DOMICILIARY_PRIVATE" | "DENPLAN";
type CareSetting = "CLINIC" | "HOME" | "CARE_HOME" | "HOSPITAL";
type RecallStatus = "due" | "contacted" | "booked" | "not_required";
type AppointmentStatus =
  | "booked"
  | "arrived"
  | "in_progress"
  | "completed"
  | "cancelled"
  | "no_show";
type LedgerEntryType = "charge" | "payment" | "adjustment";
type PaymentMethod = "cash" | "card" | "bank_transfer" | "other";

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
  referral_source?: string | null;
  referral_contact_name?: string | null;
  referral_contact_phone?: string | null;
  referral_notes?: string | null;
  notes?: string | null;
  allergies?: string | null;
  medical_alerts?: string | null;
  safeguarding_notes?: string | null;
  alerts_financial?: string | null;
  alerts_access?: string | null;
  recall_interval_months?: number | null;
  recall_due_date?: string | null;
  recall_status?: RecallStatus | null;
  recall_last_set_at?: string | null;
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

type AppointmentSummary = {
  id: number;
  starts_at: string;
  ends_at: string;
  status: AppointmentStatus;
  appointment_type?: string | null;
  clinician?: string | null;
  location?: string | null;
  location_type: "clinic" | "visit";
  location_text?: string | null;
  cancel_reason?: string | null;
};

type UserOption = {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
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

type FinanceSummaryItem = {
  id: number;
  kind: "invoice" | "payment";
  date: string;
  amount_pence: number;
  status: string;
  invoice_id?: number | null;
  payment_id?: number | null;
  invoice_number?: string | null;
};

type FinanceSummary = {
  patient_id: number;
  outstanding_balance_pence: number;
  items: FinanceSummaryItem[];
};

type RecallKind = "exam" | "hygiene" | "perio" | "implant" | "custom";
type RecallItemStatus = "upcoming" | "due" | "overdue" | "completed" | "cancelled";
type RecallOutcome = "attended" | "dna" | "cancelled" | "rebooked";
type RecallCommChannel = "letter" | "phone" | "email" | "sms" | "other";
type RecallCommDirection = "outbound";
type RecallCommStatus = "draft" | "sent" | "failed";

type PatientRecallItem = {
  id: number;
  patient_id: number;
  kind: RecallKind;
  due_date: string;
  status: RecallItemStatus;
  notes?: string | null;
  completed_at?: string | null;
  outcome?: RecallOutcome | null;
  linked_appointment_id?: number | null;
  created_at: string;
  updated_at: string;
};

type RecallCommunication = {
  id: number;
  patient_id: number;
  recall_id: number;
  channel: RecallCommChannel;
  direction: RecallCommDirection;
  status: RecallCommStatus;
  notes?: string | null;
  created_at: string;
  created_by_user_id?: number | null;
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

type LedgerEntry = {
  id: number;
  patient_id: number;
  entry_type: LedgerEntryType;
  amount_pence: number;
  method?: PaymentMethod | null;
  reference?: string | null;
  note?: string | null;
  related_invoice_id?: number | null;
  created_at: string;
  created_by: Actor;
};

type ClinicalToothNote = {
  id: number;
  patient_id: number;
  tooth: string;
  surface?: string | null;
  note: string;
  created_at: string;
  created_by: Actor;
};

type ProcedureStatus = "completed";

type Procedure = {
  id: number;
  patient_id: number;
  appointment_id?: number | null;
  tooth?: string | null;
  surface?: string | null;
  procedure_code: string;
  description: string;
  fee_pence?: number | null;
  status: ProcedureStatus;
  performed_at: string;
  created_by: Actor;
};

type TreatmentPlanStatus =
  | "proposed"
  | "accepted"
  | "declined"
  | "completed"
  | "cancelled";

type TreatmentPlanItem = {
  id: number;
  patient_id: number;
  appointment_id?: number | null;
  tooth?: string | null;
  surface?: string | null;
  procedure_code: string;
  description: string;
  fee_pence?: number | null;
  status: TreatmentPlanStatus;
  created_at: string;
  updated_at: string;
  created_by: Actor;
  updated_by?: Actor | null;
};

type ClinicalSummary = {
  recent_tooth_notes: ClinicalToothNote[];
  recent_procedures: Procedure[];
  treatment_plan_items: TreatmentPlanItem[];
  bpe_scores?: string[] | null;
  bpe_recorded_at?: string | null;
};

type ToothHistory = {
  notes: ClinicalToothNote[];
  procedures: Procedure[];
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

const appointmentStatusLabels: Record<AppointmentStatus, string> = {
  booked: "Booked",
  arrived: "Arrived",
  in_progress: "In progress",
  completed: "Completed",
  cancelled: "Cancelled",
  no_show: "No show",
};

const recallStatusLabels: Record<RecallStatus, string> = {
  due: "Due",
  contacted: "Contacted",
  booked: "Booked",
  not_required: "Not required",
};

const recallItemStatusLabels: Record<RecallItemStatus, string> = {
  upcoming: "Upcoming",
  due: "Due",
  overdue: "Overdue",
  completed: "Completed",
  cancelled: "Cancelled",
};

const recallKindLabels: Record<RecallKind, string> = {
  exam: "Exam",
  hygiene: "Hygiene",
  perio: "Perio",
  implant: "Implant",
  custom: "Custom",
};

const recallOutcomeLabels: Record<RecallOutcome, string> = {
  attended: "Attended",
  dna: "DNA",
  cancelled: "Cancelled",
  rebooked: "Rebooked",
};

const recallCommChannelLabels: Record<RecallCommChannel, string> = {
  letter: "Letter",
  phone: "Phone",
  email: "Email",
  sms: "SMS",
  other: "Other",
};

const recallCommStatusLabels: Record<RecallCommStatus, string> = {
  draft: "Draft",
  sent: "Sent",
  failed: "Failed",
};

const treatmentStatusLabels: Record<TreatmentPlanStatus, string> = {
  proposed: "Proposed",
  accepted: "Accepted",
  declined: "Declined",
  completed: "Completed",
  cancelled: "Cancelled",
};

const procedureCatalog = [
  { code: "EXAM", label: "Examination" },
  { code: "SCAL", label: "Scale & polish" },
  { code: "FILL", label: "Filling" },
  { code: "EXTR", label: "Extraction" },
  { code: "RCT", label: "Root canal" },
  { code: "CROWN", label: "Crown" },
  { code: "XRAY", label: "X-ray" },
];

const upperTeeth = [
  "UR8",
  "UR7",
  "UR6",
  "UR5",
  "UR4",
  "UR3",
  "UR2",
  "UR1",
  "UL1",
  "UL2",
  "UL3",
  "UL4",
  "UL5",
  "UL6",
  "UL7",
  "UL8",
];

const lowerTeeth = [
  "LR8",
  "LR7",
  "LR6",
  "LR5",
  "LR4",
  "LR3",
  "LR2",
  "LR1",
  "LL1",
  "LL2",
  "LL3",
  "LL4",
  "LL5",
  "LL6",
  "LL7",
  "LL8",
];

const allTeeth = [...upperTeeth, ...lowerTeeth];
const bpeSextants = ["UR", "UA", "UL", "LL", "LA", "LR"];


type PatientTab =
  | "summary"
  | "clinical"
  | "notes"
  | "invoices"
  | "estimates"
  | "ledger"
  | "recalls"
  | "documents"
  | "attachments";

export default function PatientDetailClient({
  id,
  initialTab,
}: {
  id: string;
  initialTab?: PatientTab;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const patientId = id;
  const patientIdNum = Number(patientId);
  const isValidPatientId = Number.isFinite(patientIdNum);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [pastAppointments, setPastAppointments] = useState<AppointmentSummary[]>([]);
  const [futureAppointments, setFutureAppointments] = useState<AppointmentSummary[]>([]);
  const [loadingAppointments, setLoadingAppointments] = useState(false);
  const [appointmentsError, setAppointmentsError] = useState<string | null>(null);
  const [tab, setTab] = useState<PatientTab>(initialTab ?? "summary");
  const [clinicalTab, setClinicalTab] = useState<"chart" | "treatment" | "notes">(
    "chart"
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
  const [users, setUsers] = useState<UserOption[]>([]);
  const [showBookingModal, setShowBookingModal] = useState(false);
  const [bookingDate, setBookingDate] = useState("");
  const [bookingTime, setBookingTime] = useState("");
  const [bookingDuration, setBookingDuration] = useState("30");
  const [bookingClinicianUserId, setBookingClinicianUserId] = useState("");
  const [bookingAppointmentType, setBookingAppointmentType] = useState("");
  const [bookingLocation, setBookingLocation] = useState("");
  const [bookingLocationType, setBookingLocationType] = useState<
    "clinic" | "visit"
  >("clinic");
  const [bookingLocationText, setBookingLocationText] = useState("");
  const [bookingSaving, setBookingSaving] = useState(false);
  const [bookingMarkRecall, setBookingMarkRecall] = useState(false);
  const [recallInterval, setRecallInterval] = useState("6");
  const [recallDueDate, setRecallDueDate] = useState("");
  const [recallStatus, setRecallStatus] = useState<RecallStatus>("due");
  const [recallSaving, setRecallSaving] = useState(false);
  const [recallError, setRecallError] = useState<string | null>(null);
  const [handledBookParam, setHandledBookParam] = useState(false);
  const [pendingScrollTarget, setPendingScrollTarget] = useState<string | null>(null);
  const [ledgerEntries, setLedgerEntries] = useState<LedgerEntry[]>([]);
  const [ledgerLoading, setLedgerLoading] = useState(false);
  const [ledgerError, setLedgerError] = useState<string | null>(null);
  const [ledgerBalance, setLedgerBalance] = useState<number>(0);
  const [financeSummary, setFinanceSummary] = useState<FinanceSummary | null>(null);
  const [financeSummaryLoading, setFinanceSummaryLoading] = useState(false);
  const [financeSummaryError, setFinanceSummaryError] = useState<string | null>(null);
  const [recalls, setRecalls] = useState<PatientRecallItem[]>([]);
  const [recallsLoading, setRecallsLoading] = useState(false);
  const [recallsError, setRecallsError] = useState<string | null>(null);
  const [showRecallForm, setShowRecallForm] = useState(false);
  const [editingRecallId, setEditingRecallId] = useState<number | null>(null);
  const [recallEntryKind, setRecallEntryKind] = useState<RecallKind>("exam");
  const [recallEntryDueDate, setRecallEntryDueDate] = useState("");
  const [recallEntryNotes, setRecallEntryNotes] = useState("");
  const [recallEntrySaving, setRecallEntrySaving] = useState(false);
  const [recallActionId, setRecallActionId] = useState<number | null>(null);
  const [recallDownloadId, setRecallDownloadId] = useState<number | null>(null);
  const [recallCommMap, setRecallCommMap] = useState<Record<number, RecallCommunication[]>>(
    {}
  );
  const [recallCommLoadingId, setRecallCommLoadingId] = useState<number | null>(null);
  const [recallCommError, setRecallCommError] = useState<string | null>(null);
  const [expandedRecallId, setExpandedRecallId] = useState<number | null>(null);
  const [showRecallCommModal, setShowRecallCommModal] = useState(false);
  const [recallCommRecallId, setRecallCommRecallId] = useState<number | null>(null);
  const [recallCommChannel, setRecallCommChannel] = useState<RecallCommChannel>("letter");
  const [recallCommNotes, setRecallCommNotes] = useState("");
  const [recallCommSaving, setRecallCommSaving] = useState(false);
  const [showLedgerModal, setShowLedgerModal] = useState(false);
  const [ledgerMode, setLedgerMode] = useState<LedgerEntryType>("payment");
  const [ledgerAmount, setLedgerAmount] = useState("");
  const [ledgerMethod, setLedgerMethod] = useState<PaymentMethod>("card");
  const [ledgerReference, setLedgerReference] = useState("");
  const [ledgerNote, setLedgerNote] = useState("");
  const [ledgerSaving, setLedgerSaving] = useState(false);
  const [clinicalNotes, setClinicalNotes] = useState<ClinicalToothNote[]>([]);
  const [clinicalProcedures, setClinicalProcedures] = useState<Procedure[]>([]);
  const [treatmentPlanItems, setTreatmentPlanItems] = useState<TreatmentPlanItem[]>([]);
  const [clinicalLoading, setClinicalLoading] = useState(false);
  const [clinicalError, setClinicalError] = useState<string | null>(null);
  const [clinicalLastUpdated, setClinicalLastUpdated] = useState<string | null>(null);
  const [selectedTooth, setSelectedTooth] = useState<string | null>(null);
  const [toothHistory, setToothHistory] = useState<ToothHistory>({
    notes: [],
    procedures: [],
  });
  const [toothHistoryLoading, setToothHistoryLoading] = useState(false);
  const [chartNoteSurface, setChartNoteSurface] = useState("");
  const [chartNoteBody, setChartNoteBody] = useState("");
  const [procedureCode, setProcedureCode] = useState("");
  const [procedureDescription, setProcedureDescription] = useState("");
  const [procedureFee, setProcedureFee] = useState("");
  const [savingProcedure, setSavingProcedure] = useState(false);
  const [savingToothNote, setSavingToothNote] = useState(false);
  const [chartNoteNotice, setChartNoteNotice] = useState<string | null>(null);
  const [notesTooth, setNotesTooth] = useState("");
  const [notesSurface, setNotesSurface] = useState("");
  const [notesBody, setNotesBody] = useState("");
  const [savingClinicalNote, setSavingClinicalNote] = useState(false);
  const [clinicalNoteNotice, setClinicalNoteNotice] = useState<string | null>(null);
  const [showPlanModal, setShowPlanModal] = useState(false);
  const [planTooth, setPlanTooth] = useState("");
  const [planSurface, setPlanSurface] = useState("");
  const [planCode, setPlanCode] = useState("");
  const [planDescription, setPlanDescription] = useState("");
  const [planFee, setPlanFee] = useState("");
  const [planSaving, setPlanSaving] = useState(false);
  const [bpeScores, setBpeScores] = useState<string[]>(Array(6).fill(""));
  const [bpeRecordedAt, setBpeRecordedAt] = useState<string | null>(null);
  const [bpeSaving, setBpeSaving] = useState(false);
  const [bpeNotice, setBpeNotice] = useState<string | null>(null);
  const [clinicalViewMode, setClinicalViewMode] = useState<
    "current" | "planned" | "history"
  >("current");

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
      if (res.status === 404) {
        router.replace("/__notfound__");
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

  async function loadAppointments() {
    setLoadingAppointments(true);
    setAppointmentsError(null);
    try {
      const now = new Date();
      const nowIso = now.toISOString();
      const pastStart = new Date(now);
      pastStart.setFullYear(pastStart.getFullYear() - 1);
      const futureEnd = new Date(now);
      futureEnd.setFullYear(futureEnd.getFullYear() + 1);
      const pastParams = new URLSearchParams();
      pastParams.set("patient_id", patientId);
      pastParams.set("from", pastStart.toISOString());
      pastParams.set("to", nowIso);
      const futureParams = new URLSearchParams();
      futureParams.set("patient_id", patientId);
      futureParams.set("from", nowIso);
      futureParams.set("to", futureEnd.toISOString());

      const [pastRes, futureRes] = await Promise.all([
        apiFetch(`/api/appointments?${pastParams.toString()}`),
        apiFetch(`/api/appointments?${futureParams.toString()}`),
      ]);
      if (pastRes.status === 401 || futureRes.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!pastRes.ok || !futureRes.ok) {
        throw new Error("Failed to load appointments");
      }
      const pastData = (await pastRes.json()) as AppointmentSummary[];
      const futureData = (await futureRes.json()) as AppointmentSummary[];
      setPastAppointments(
        pastData.sort(
          (a, b) => new Date(b.starts_at).getTime() - new Date(a.starts_at).getTime()
        )
      );
      setFutureAppointments(
        futureData.sort(
          (a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()
        )
      );
    } catch (err) {
      setAppointmentsError(err instanceof Error ? err.message : "Failed to load appointments");
    } finally {
      setLoadingAppointments(false);
    }
  }

  async function loadLedger() {
    setLedgerLoading(true);
    setLedgerError(null);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/ledger?limit=200`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to load ledger (HTTP ${res.status})`);
      }
      const data = (await res.json()) as LedgerEntry[];
      setLedgerEntries(data);
    } catch (err) {
      setLedgerError(err instanceof Error ? err.message : "Failed to load ledger");
      setLedgerEntries([]);
    } finally {
      setLedgerLoading(false);
    }
  }

  async function loadLedgerBalance() {
    try {
      const res = await apiFetch(`/api/patients/${patientId}/balance`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to load balance (HTTP ${res.status})`);
      }
      const data = (await res.json()) as { balance_pence: number };
      setLedgerBalance(data.balance_pence ?? 0);
    } catch {
      setLedgerBalance(0);
    }
  }

  async function loadFinanceSummary() {
    setFinanceSummaryLoading(true);
    setFinanceSummaryError(null);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/finance-summary?limit=10`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to load finance summary (HTTP ${res.status})`);
      }
      const data = (await res.json()) as FinanceSummary;
      setFinanceSummary(data);
    } catch (err) {
      setFinanceSummaryError(
        err instanceof Error ? err.message : "Failed to load finance summary"
      );
      setFinanceSummary(null);
    } finally {
      setFinanceSummaryLoading(false);
    }
  }

  async function loadRecalls() {
    setRecallsLoading(true);
    setRecallsError(null);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/recalls`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to load recalls (HTTP ${res.status})`);
      }
      const data = (await res.json()) as PatientRecallItem[];
      setRecalls(data);
    } catch (err) {
      setRecallsError(err instanceof Error ? err.message : "Failed to load recalls");
    } finally {
      setRecallsLoading(false);
    }
  }

  async function loadRecallCommunications(recallId: number) {
    setRecallCommLoadingId(recallId);
    setRecallCommError(null);
    try {
      const res = await apiFetch(
        `/api/patients/${patientId}/recalls/${recallId}/communications?limit=3`
      );
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to load recall communications (HTTP ${res.status})`);
      }
      const data = (await res.json()) as RecallCommunication[];
      setRecallCommMap((prev) => ({ ...prev, [recallId]: data }));
    } catch (err) {
      setRecallCommError(
        err instanceof Error ? err.message : "Failed to load recall communications"
      );
    } finally {
      setRecallCommLoadingId(null);
    }
  }

  function openRecallCommModal(recall: PatientRecallItem) {
    setRecallCommRecallId(recall.id);
    setRecallCommChannel("letter");
    setRecallCommNotes("");
    setRecallCommError(null);
    setShowRecallCommModal(true);
  }

  async function saveRecallCommunication() {
    if (!recallCommRecallId) return;
    setRecallCommSaving(true);
    setRecallCommError(null);
    try {
      const res = await apiFetch(
        `/api/patients/${patientId}/recalls/${recallCommRecallId}/communications`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            channel: recallCommChannel,
            notes: recallCommNotes.trim() || null,
          }),
        }
      );
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to log communication (HTTP ${res.status})`);
      }
      setShowRecallCommModal(false);
      setRecallCommNotes("");
      await loadRecallCommunications(recallCommRecallId);
    } catch (err) {
      setRecallCommError(
        err instanceof Error ? err.message : "Failed to log communication"
      );
    } finally {
      setRecallCommSaving(false);
    }
  }

  function toggleRecallCommunications(recallId: number) {
    if (expandedRecallId === recallId) {
      setExpandedRecallId(null);
      return;
    }
    setExpandedRecallId(recallId);
    if (!recallCommMap[recallId]) {
      void loadRecallCommunications(recallId);
    }
  }

  async function loadUsers() {
    try {
      const res = await apiFetch("/api/users");
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.ok) {
        const data = (await res.json()) as UserOption[];
        setUsers(data.filter((user) => user.is_active));
      }
    } catch {
      setUsers([]);
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

  async function loadClinicalSummary() {
    setClinicalLoading(true);
    setClinicalError(null);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/clinical/summary`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load clinical summary (HTTP ${res.status})`);
      }
      const data = (await res.json()) as ClinicalSummary;
      setClinicalNotes(data.recent_tooth_notes ?? []);
      setClinicalProcedures(data.recent_procedures ?? []);
      setTreatmentPlanItems(data.treatment_plan_items ?? []);
      setBpeScores(normalizeBpeScores(data.bpe_scores));
      setBpeRecordedAt(data.bpe_recorded_at ?? null);
      setClinicalLastUpdated(new Date().toISOString());
    } catch (err) {
      setClinicalError(err instanceof Error ? err.message : "Failed to load clinical summary");
    } finally {
      setClinicalLoading(false);
    }
  }

  async function loadToothHistory(tooth: string) {
    setToothHistoryLoading(true);
    try {
      const res = await apiFetch(
        `/api/patients/${patientId}/tooth-history?tooth=${encodeURIComponent(tooth)}`
      );
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load tooth history (HTTP ${res.status})`);
      }
      const data = (await res.json()) as ToothHistory;
      setToothHistory({
        notes: data.notes ?? [],
        procedures: data.procedures ?? [],
      });
    } catch {
      setToothHistory({ notes: [], procedures: [] });
    } finally {
      setToothHistoryLoading(false);
    }
  }

  async function submitChartNote() {
    if (!selectedTooth || !chartNoteBody.trim()) return;
    setSavingToothNote(true);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/tooth-notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tooth: selectedTooth,
          surface: chartNoteSurface || null,
          note: chartNoteBody.trim(),
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to save note (HTTP ${res.status})`);
      }
      setChartNoteBody("");
      setChartNoteSurface("");
      setChartNoteNotice("Note saved.");
      await loadClinicalSummary();
      await loadToothHistory(selectedTooth);
    } catch (err) {
      setClinicalError(err instanceof Error ? err.message : "Failed to save note");
    } finally {
      setSavingToothNote(false);
    }
  }

  async function submitProcedure() {
    if (!selectedTooth || !procedureCode || !procedureDescription.trim()) return;
    setSavingProcedure(true);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/procedures`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tooth: selectedTooth,
          surface: chartNoteSurface || null,
          procedure_code: procedureCode,
          description: procedureDescription.trim(),
          fee_pence: parseCurrencyToPence(procedureFee),
          performed_at: new Date().toISOString(),
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to save procedure (HTTP ${res.status})`);
      }
      setProcedureCode("");
      setProcedureDescription("");
      setProcedureFee("");
      await loadClinicalSummary();
      await loadToothHistory(selectedTooth);
    } catch (err) {
      setClinicalError(err instanceof Error ? err.message : "Failed to save procedure");
    } finally {
      setSavingProcedure(false);
    }
  }

  function openPlanFromChart() {
    if (!selectedTooth || !procedureCode || !procedureDescription.trim()) return;
    setPlanTooth(selectedTooth);
    setPlanSurface(chartNoteSurface);
    setPlanCode(procedureCode);
    setPlanDescription(procedureDescription.trim());
    setPlanFee(procedureFee);
    setShowPlanModal(true);
  }

  async function submitBpe() {
    setBpeSaving(true);
    setBpeNotice(null);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/clinical/bpe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scores: bpeScores }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to save BPE (HTTP ${res.status})`);
      }
      const data = (await res.json()) as {
        bpe_scores?: string[] | null;
        bpe_recorded_at?: string | null;
      };
      setBpeScores(normalizeBpeScores(data.bpe_scores));
      setBpeRecordedAt(data.bpe_recorded_at ?? null);
      setBpeNotice(data.bpe_scores ? "BPE saved." : "BPE cleared.");
      await loadClinicalSummary();
    } catch (err) {
      setClinicalError(err instanceof Error ? err.message : "Failed to save BPE");
    } finally {
      setBpeSaving(false);
    }
  }

  async function submitClinicalNote() {
    if (!notesTooth.trim() || !notesBody.trim()) return;
    setSavingClinicalNote(true);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/tooth-notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tooth: notesTooth.trim(),
          surface: notesSurface || null,
          note: notesBody.trim(),
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to save clinical note (HTTP ${res.status})`);
      }
      setNotesBody("");
      setNotesSurface("");
      setClinicalNoteNotice("Note saved.");
      await loadClinicalSummary();
    } catch (err) {
      setClinicalError(err instanceof Error ? err.message : "Failed to save clinical note");
    } finally {
      setSavingClinicalNote(false);
    }
  }

  async function submitTreatmentPlanItem() {
    if (!planCode.trim() || !planDescription.trim()) return;
    setPlanSaving(true);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/treatment-plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tooth: planTooth.trim() || null,
          surface: planSurface || null,
          procedure_code: planCode.trim(),
          description: planDescription.trim(),
          fee_pence: parseCurrencyToPence(planFee),
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to save treatment plan item (HTTP ${res.status})`);
      }
      setShowPlanModal(false);
      setPlanTooth("");
      setPlanSurface("");
      setPlanCode("");
      setPlanDescription("");
      setPlanFee("");
      await loadClinicalSummary();
    } catch (err) {
      setClinicalError(err instanceof Error ? err.message : "Failed to save treatment plan item");
    } finally {
      setPlanSaving(false);
    }
  }

  async function updateTreatmentPlanStatus(item: TreatmentPlanItem, status: TreatmentPlanStatus) {
    try {
      const res = await apiFetch(`/api/treatment-plan/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to update treatment plan (HTTP ${res.status})`);
      }
      if (status === "completed") {
        const shouldCreate = window.confirm(
          "Create a completed procedure record for this item?"
        );
        if (shouldCreate) {
          await apiFetch(`/api/patients/${patientId}/procedures`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              tooth: item.tooth,
              surface: item.surface,
              procedure_code: item.procedure_code,
              description: item.description,
              fee_pence: item.fee_pence ?? null,
              performed_at: new Date().toISOString(),
              appointment_id: item.appointment_id ?? null,
            }),
          });
        }
      }
      await loadClinicalSummary();
    } catch (err) {
      setClinicalError(
        err instanceof Error ? err.message : "Failed to update treatment plan"
      );
    }
  }

  function parseCurrencyToPence(value: string) {
    if (!value) return null;
    const parsed = Number.parseFloat(value);
    if (Number.isNaN(parsed)) return null;
    return Math.round(parsed * 100);
  }

  function formatDateInput(value: Date) {
    return value.toISOString().slice(0, 10);
  }

  function addMonthsToDate(base: Date, months: number) {
    const year = base.getFullYear();
    const month = base.getMonth();
    const day = base.getDate();
    const next = new Date(year, month + months, 1);
    const lastDay = new Date(next.getFullYear(), next.getMonth() + 1, 0).getDate();
    next.setDate(Math.min(day, lastDay));
    return next;
  }

  function resetRecallForm() {
    setEditingRecallId(null);
    setRecallEntryKind("exam");
    setRecallEntryDueDate("");
    setRecallEntryNotes("");
    setShowRecallForm(false);
  }

  function startEditRecall(recall: PatientRecallItem) {
    setEditingRecallId(recall.id);
    setRecallEntryKind(recall.kind);
    setRecallEntryDueDate(recall.due_date || "");
    setRecallEntryNotes(recall.notes || "");
    setShowRecallForm(true);
  }

  async function saveRecallEntry() {
    if (!recallEntryDueDate) {
      setRecallsError("Select a due date.");
      return;
    }
    setRecallEntrySaving(true);
    setRecallsError(null);
    try {
      const payload = {
        kind: recallEntryKind,
        due_date: recallEntryDueDate,
        notes: recallEntryNotes.trim() || null,
      };
      const url = editingRecallId
        ? `/api/patients/${patientId}/recalls/${editingRecallId}`
        : `/api/patients/${patientId}/recalls`;
      const method = editingRecallId ? "PATCH" : "POST";
      const res = await apiFetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to save recall (HTTP ${res.status})`);
      }
      resetRecallForm();
      await loadRecalls();
    } catch (err) {
      setRecallsError(err instanceof Error ? err.message : "Failed to save recall");
    } finally {
      setRecallEntrySaving(false);
    }
  }

  async function createNextRecall(recall: PatientRecallItem, months: number) {
    const baseDate = recall.due_date ? new Date(recall.due_date) : new Date();
    const dueDate = formatDateInput(addMonthsToDate(baseDate, months));
    const res = await apiFetch(`/api/patients/${patientId}/recalls`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: recall.kind,
        due_date: dueDate,
        notes: recall.notes || null,
      }),
    });
    if (res.status === 401) {
      clearToken();
      router.replace("/login");
      return false;
    }
    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || `Failed to create next recall (HTTP ${res.status})`);
    }
    return true;
  }

  async function markRecallCompleted(recall: PatientRecallItem, nextMonths?: number) {
    setRecallActionId(recall.id);
    setRecallsError(null);
    try {
      const res = await apiFetch(`/api/patients/${patientId}/recalls/${recall.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: "completed",
          completed_at: new Date().toISOString(),
          outcome: "attended",
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to complete recall (HTTP ${res.status})`);
      }
      if (nextMonths) {
        await createNextRecall(recall, nextMonths);
      }
      await loadRecalls();
    } catch (err) {
      setRecallsError(err instanceof Error ? err.message : "Failed to update recall");
    } finally {
      setRecallActionId(null);
    }
  }

  function buildRecallLetterFilename(recall: PatientRecallItem) {
    const date = recall.due_date?.slice(0, 10) || new Date().toISOString().slice(0, 10);
    const rawName = patient
      ? `${patient.first_name}_${patient.last_name}`
      : `patient_${patientId}`;
    const safeName = rawName.replace(/[^a-zA-Z0-9-_]+/g, "_");
    return `Recall_${safeName}_${date}.pdf`;
  }

  async function downloadRecallLetter(recall: PatientRecallItem) {
    setRecallsError(null);
    setRecallDownloadId(recall.id);
    try {
      const res = await apiFetch(
        `/api/patients/${patientId}/recalls/${recall.id}/letter.pdf`
      );
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to download letter (HTTP ${res.status})`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = buildRecallLetterFilename(recall);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setRecallsError(
        err instanceof Error ? err.message : "Failed to download recall letter"
      );
    } finally {
      setRecallDownloadId(null);
    }
  }

  useEffect(() => {
    if (!isValidPatientId) return;
    void loadPatient();
    void loadNotes();
    void loadTimeline();
    void loadInvoices();
    void loadTreatments();
    void loadEstimates();
    void loadAppointments();
    void loadUsers();
    void loadLedger();
    void loadLedgerBalance();
    void loadFinanceSummary();
    void loadRecalls();
  }, [isValidPatientId, patientId]);

  useEffect(() => {
    if (!initialTab) return;
    setTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    if (tab !== "clinical") return;
    void loadClinicalSummary();
    if (!selectedTooth) {
      setSelectedTooth(upperTeeth[0]);
      setNotesTooth(upperTeeth[0]);
    }
  }, [tab, patientId]);

  useEffect(() => {
    if (tab !== "clinical" || !selectedTooth) return;
    void loadToothHistory(selectedTooth);
  }, [tab, selectedTooth, patientId]);

  useEffect(() => {
    if (!patient) return;
    setRecallInterval(String(patient.recall_interval_months ?? 6));
    setRecallDueDate(patient.recall_due_date ?? "");
    if (patient.recall_status) {
      setRecallStatus(patient.recall_status);
    } else {
      setRecallStatus("due");
    }
    setBookingMarkRecall(Boolean(patient.recall_due_date));
  }, [patient?.id]);

  useEffect(() => {
    if (!patient || handledBookParam) return;
    if (searchParams?.get("book") === "1") {
      setTab("summary");
      openBookingModal();
      setPendingScrollTarget("patient-book-appointment");
      setHandledBookParam(true);
    }
  }, [patient, handledBookParam, searchParams]);

  useEffect(() => {
    if (!pendingScrollTarget) return;
    if (tab !== "summary") return;
    if (pendingScrollTarget === "patient-book-appointment" && !showBookingModal) return;
    scrollToAnchor(pendingScrollTarget);
    setPendingScrollTarget(null);
  }, [pendingScrollTarget, tab, showBookingModal]);

  const alerts = [
    patient?.allergies ? { label: "Allergies", tone: "danger" } : null,
    patient?.medical_alerts ? { label: "Medical alert", tone: "warning" } : null,
    patient?.safeguarding_notes ? { label: "Safeguarding", tone: "warning" } : null,
    patient?.alerts_financial ? { label: "Financial", tone: "warning" } : null,
    patient?.alerts_access ? { label: "Access", tone: "warning" } : null,
  ].filter(Boolean) as { label: string; tone: "danger" | "warning" }[];

  function normalizeToothCode(code?: string | null) {
    return code ? code.trim().toUpperCase() : null;
  }

  useEffect(() => {
    const fromUrl = searchParams?.get("clinicalView");
    if (fromUrl === "current" || fromUrl === "planned" || fromUrl === "history") {
      if (fromUrl !== clinicalViewMode) setClinicalViewMode(fromUrl);
      return;
    }
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem("clinicalViewMode");
    if (stored === "current" || stored === "planned" || stored === "history") {
      if (stored !== clinicalViewMode) setClinicalViewMode(stored);
    }
  }, [searchParams]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem("clinicalViewMode", clinicalViewMode);
    }
    if (!pathname) return;
    const params = new URLSearchParams(searchParams?.toString() ?? "");
    if (clinicalViewMode === "current") {
      params.delete("clinicalView");
    } else {
      params.set("clinicalView", clinicalViewMode);
    }
    const current = searchParams?.get("clinicalView") ?? "";
    const next = params.get("clinicalView") ?? "";
    if (current === next) return;
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [clinicalViewMode, pathname, router, searchParams]);

  const plannedTeeth = useMemo(() => {
    const activeStatuses = new Set(["proposed", "accepted"]);
    return new Set(
      treatmentPlanItems
        .filter((item) => item.tooth && activeStatuses.has(item.status))
        .map((item) => normalizeToothCode(item.tooth))
        .filter((tooth): tooth is string => Boolean(tooth))
    );
  }, [treatmentPlanItems]);

  const historyTeeth = useMemo(() => {
    return new Set(
      clinicalProcedures
        .filter((procedure) => procedure.tooth)
        .map((procedure) => normalizeToothCode(procedure.tooth))
        .filter((tooth): tooth is string => Boolean(tooth))
    );
  }, [clinicalProcedures]);

  const plannedItemsForTooth = useMemo(() => {
    if (!selectedTooth) return [];
    return treatmentPlanItems.filter((item) => item.tooth === selectedTooth);
  }, [selectedTooth, treatmentPlanItems]);

  const sortedClinicalNotes = useMemo(() => {
    return [...clinicalNotes].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  }, [clinicalNotes]);

  const sortedClinicalProcedures = useMemo(() => {
    return [...clinicalProcedures].sort(
      (a, b) => new Date(b.performed_at).getTime() - new Date(a.performed_at).getTime()
    );
  }, [clinicalProcedures]);

  function getToothBadges(tooth: string) {
    const badges: { label: string; title: string }[] = [];
    const normalized = normalizeToothCode(tooth);
    if (normalized && clinicalViewMode !== "history" && plannedTeeth.has(normalized)) {
      badges.push({ label: "P", title: "Planned treatment" });
    }
    if (normalized && clinicalViewMode !== "planned" && historyTeeth.has(normalized)) {
      badges.push({ label: "H", title: "History" });
    }
    // TODO: add missing/extracted/deciduous/gap-closed tooth badges once stored.
    return badges;
  }

  const ledgerWithBalance = useMemo(() => {
    let running = 0;
    return ledgerEntries.map((entry) => {
      running += entry.amount_pence;
      return { ...entry, running_balance: running };
    });
  }, [ledgerEntries]);

  const financeItems = financeSummary?.items ?? [];
  const financeBalance =
    financeSummary?.outstanding_balance_pence ?? ledgerBalance ?? 0;

  const toothHistoryEntries = useMemo(() => {
    const entries = [
      ...toothHistory.notes.map((note) => ({
        type: "note" as const,
        date: note.created_at,
        label: note.surface ? `${note.tooth} · ${note.surface}` : note.tooth,
        detail: note.note,
        actor: note.created_by?.email,
      })),
      ...toothHistory.procedures.map((procedure) => ({
        type: "procedure" as const,
        date: procedure.performed_at,
        label: procedure.procedure_code,
        detail: procedure.description,
        actor: procedure.created_by?.email,
      })),
    ];
    return entries.sort(
      (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
    );
  }, [toothHistory]);

  const recallCommTarget = useMemo(() => {
    if (!recallCommRecallId) return null;
    return recalls.find((recall) => recall.id === recallCommRecallId) || null;
  }, [recallCommRecallId, recalls]);

  function buildAddress(p: Patient | null) {
    if (!p) return "";
    return [p.address_line1, p.address_line2, p.city, p.postcode]
      .filter(Boolean)
      .join(", ");
  }

  function formatAge(dateOfBirth?: string | null) {
    if (!dateOfBirth) return "—";
    const dob = new Date(dateOfBirth);
    if (Number.isNaN(dob.getTime())) return "—";
    const now = new Date();
    let age = now.getFullYear() - dob.getFullYear();
    const monthDiff = now.getMonth() - dob.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && now.getDate() < dob.getDate())) {
      age -= 1;
    }
    return `${age}`;
  }

  function formatDurationMinutes(start: string, end: string) {
    const startDate = new Date(start);
    const endDate = new Date(end);
    if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return "—";
    const diffMinutes = Math.round((endDate.getTime() - startDate.getTime()) / 60000);
    return `${diffMinutes} min`;
  }

  function formatCurrency(pence: number) {
    return new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency: "GBP",
      minimumFractionDigits: 2,
    }).format(pence / 100);
  }

  function formatSignedCurrency(pence: number) {
    const formatted = formatCurrency(Math.abs(pence));
    return pence < 0 ? `-${formatted}` : formatted;
  }

  function formatShortDate(value?: string | null) {
    if (!value) return "—";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "—";
    return parsed.toLocaleDateString("en-GB");
  }

  function formatDateTime(value?: string | null) {
    if (!value) return "—";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "—";
    return parsed.toLocaleString("en-GB");
  }

  function normalizeBpeScores(scores?: string[] | null) {
    const entries = Array.isArray(scores) ? scores : [];
    const filled = [...entries, "", "", "", "", "", ""].slice(0, 6);
    return filled.map((value) => value || "");
  }

  function tabStyle(active: boolean, compact = false) {
    return {
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      padding: compact ? "4px 8px" : "6px 12px",
      borderRadius: 999,
      border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
      background: active ? "var(--tab-active-bg)" : "transparent",
      fontSize: compact ? 12 : 14,
      fontWeight: active ? 600 : 500,
      color: "inherit",
      cursor: "pointer",
      textDecoration: "none",
    } as const;
  }

  const tabRowStyle = {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
    alignItems: "center",
  } as const;

  function scrollToAnchor(id: string, attempts = 8) {
    const target = document.getElementById(id);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      const focusable = target.querySelector("input, select, textarea") as
        | HTMLElement
        | null;
      focusable?.focus();
      return;
    }
    if (attempts <= 0) return;
    requestAnimationFrame(() => scrollToAnchor(id, attempts - 1));
  }

  function getDefaultBookingSlot() {
    const next = new Date();
    const minutes = Math.ceil(next.getMinutes() / 10) * 10;
    next.setMinutes(minutes, 0, 0);
    const date = next.toLocaleDateString("en-CA");
    const time = next.toTimeString().slice(0, 5);
    return { date, time };
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
          referral_source: patient.referral_source,
          referral_contact_name: patient.referral_contact_name,
          referral_contact_phone: patient.referral_contact_phone,
          referral_notes: patient.referral_notes,
          allergies: patient.allergies,
          medical_alerts: patient.medical_alerts,
          safeguarding_notes: patient.safeguarding_notes,
          alerts_financial: patient.alerts_financial,
          alerts_access: patient.alerts_access,
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

  async function updateRecall(payload: {
    interval_months?: number | null;
    due_date?: string | null;
    status?: RecallStatus | null;
  }) {
    if (!patient) return;
    setRecallSaving(true);
    setRecallError(null);
    try {
      const res = await apiFetch(`/api/patients/${patient.id}/recall`, {
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
        throw new Error(msg || `Failed to update recall (HTTP ${res.status})`);
      }
      const data = (await res.json()) as Patient;
      setPatient(data);
    } catch (err) {
      setRecallError(err instanceof Error ? err.message : "Failed to update recall");
    } finally {
      setRecallSaving(false);
    }
  }

  async function submitLedgerEntry() {
    if (!patient) return;
    const parsed = Number(ledgerAmount);
    if (Number.isNaN(parsed) || parsed <= 0) {
      setLedgerError("Amount must be greater than 0.");
      return;
    }
    setLedgerSaving(true);
    setLedgerError(null);
    try {
      const endpoint =
        ledgerMode === "payment"
          ? `/api/patients/${patient.id}/payments`
          : `/api/patients/${patient.id}/charges`;
      const payload =
        ledgerMode === "payment"
          ? {
              amount_pence: Math.round(parsed * 100),
              method: ledgerMethod,
              reference: ledgerReference.trim() || undefined,
              note: ledgerNote.trim() || undefined,
            }
          : {
              amount_pence: Math.round(parsed * 100),
              entry_type: ledgerMode,
              reference: ledgerReference.trim() || undefined,
              note: ledgerNote.trim() || undefined,
            };
      const res = await apiFetch(endpoint, {
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
        throw new Error(msg || `Failed to save entry (HTTP ${res.status})`);
      }
      setShowLedgerModal(false);
      setLedgerAmount("");
      setLedgerReference("");
      setLedgerNote("");
      await loadLedger();
      await loadLedgerBalance();
      await loadFinanceSummary();
    } catch (err) {
      setLedgerError(err instanceof Error ? err.message : "Failed to save entry");
    } finally {
      setLedgerSaving(false);
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
      await loadFinanceSummary();
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
      await loadFinanceSummary();
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

  function openBookingModal() {
    const slot = getDefaultBookingSlot();
    setBookingDate(slot.date);
    setBookingTime(slot.time);
    setBookingDuration("30");
    setBookingClinicianUserId("");
    setBookingAppointmentType("");
    setBookingLocation("");
    if (patient?.care_setting && patient.care_setting !== "CLINIC") {
      setBookingLocationType("visit");
      setBookingLocationText(patient.visit_address_text || "");
    } else {
      setBookingLocationType("clinic");
      setBookingLocationText("");
    }
    setShowBookingModal(true);
  }

  async function createBooking(e: React.FormEvent) {
    e.preventDefault();
    if (!bookingDate || !bookingTime) return;
    const start = new Date(`${bookingDate}T${bookingTime}`);
    if (Number.isNaN(start.getTime())) return;
    const duration = Number(bookingDuration || "30");
    const end = new Date(start);
    end.setMinutes(end.getMinutes() + duration);
    if (bookingLocationType === "visit" && !bookingLocationText.trim()) {
      setError("Visit address is required for domiciliary visits.");
      return;
    }
    setBookingSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/api/appointments", {
        method: "POST",
        body: JSON.stringify({
          patient_id: Number(patientId),
          clinician_user_id: bookingClinicianUserId
            ? Number(bookingClinicianUserId)
            : undefined,
          starts_at: start.toISOString(),
          ends_at: end.toISOString(),
          status: "booked",
          appointment_type: bookingAppointmentType.trim() || undefined,
          location: bookingLocation.trim() || undefined,
          location_type: bookingLocationType,
          location_text: bookingLocationText.trim() || undefined,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to create appointment (HTTP ${res.status})`);
      }
      const created = (await res.json()) as AppointmentSummary;
      setShowBookingModal(false);
      if (bookingMarkRecall) {
        await updateRecall({ status: "booked" });
      }
      await loadAppointments();
      router.push(`/appointments?date=${bookingDate}&appointment=${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create appointment");
  } finally {
    setBookingSaving(false);
  }
}

  if (!isValidPatientId) {
    return <div className="notice">Invalid patient ID.</div>;
  }

  return (
    <div className="app-grid">
      <div style={{ maxWidth: 1200, margin: "0 auto", width: "100%" }}>
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
                  {patient.recall_due_date ? (
                    <span className="badge">
                      Recall {recallStatusLabels[patient.recall_status || "due"]} ·{" "}
                      {formatShortDate(patient.recall_due_date)}
                    </span>
                  ) : (
                    <span className="badge">Recall not set</span>
                  )}
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
                  <div className="label">Recall due</div>
                  <div>{formatShortDate(patient.recall_due_date)}</div>
                </div>
                <div>
                  <div className="label">Recall status</div>
                  <div>
                    <span className="badge">
                      {recallStatusLabels[patient.recall_status || "due"]}
                    </span>
                  </div>
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

              {(patient.referral_source ||
                patient.referral_contact_name ||
                patient.referral_contact_phone ||
                patient.referral_notes) && (
                <div className="card" style={{ margin: 0 }}>
                  <div className="stack" style={{ gap: 6 }}>
                    <div className="label">Referral</div>
                    <div>
                      <strong>Source:</strong> {patient.referral_source || "—"}
                    </div>
                    <div>
                      <strong>Contact:</strong> {patient.referral_contact_name || "—"}
                      {patient.referral_contact_phone
                        ? ` · ${patient.referral_contact_phone}`
                        : ""}
                    </div>
                    <div>
                      <strong>Notes:</strong> {patient.referral_notes || "—"}
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
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                <div className="label">Quick links</div>
                <div style={tabRowStyle}>
                  <Link
                    style={tabStyle(tab === "summary", true)}
                    href={`/patients/${patientId}`}
                    aria-current={tab === "summary" ? "page" : undefined}
                  >
                    Summary
                  </Link>
                  <Link
                    style={tabStyle(tab === "clinical", true)}
                    href={`/patients/${patientId}/clinical`}
                    aria-current={tab === "clinical" ? "page" : undefined}
                  >
                    Clinical
                  </Link>
                  <Link
                    style={tabStyle(tab === "documents", true)}
                    href={`/patients/${patientId}/documents`}
                    aria-current={tab === "documents" ? "page" : undefined}
                  >
                    Documents
                  </Link>
                  <Link
                    style={tabStyle(tab === "attachments", true)}
                    href={`/patients/${patientId}/attachments`}
                    aria-current={tab === "attachments" ? "page" : undefined}
                  >
                    Attachments
                  </Link>
                  <Link style={tabStyle(false, true)} href={`/patients/${patientId}/timeline`}>
                    Timeline
                  </Link>
                </div>
              </div>

              {(patient.allergies ||
                patient.medical_alerts ||
                patient.safeguarding_notes ||
                patient.alerts_financial ||
                patient.alerts_access) && (
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
                  <div className="stack" style={{ gap: 6 }}>
                    <div className="label">Financial</div>
                    <div>{patient.alerts_financial || "—"}</div>
                  </div>
                  <div className="stack" style={{ gap: 6 }}>
                    <div className="label">Access needs</div>
                    <div>{patient.alerts_access || "—"}</div>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <div className="stack">
              <div style={tabRowStyle}>
                <button
                  style={tabStyle(tab === "summary")}
                  onClick={() => setTab("summary")}
                  type="button"
                  aria-current={tab === "summary" ? "page" : undefined}
                >
                  Summary
                </button>
                <Link
                  style={tabStyle(tab === "clinical")}
                  href={`/patients/${patientId}/clinical`}
                  aria-current={tab === "clinical" ? "page" : undefined}
                >
                  Clinical
                </Link>
                <Link
                  style={tabStyle(tab === "documents")}
                  href={`/patients/${patientId}/documents`}
                  aria-current={tab === "documents" ? "page" : undefined}
                >
                  Documents
                </Link>
                <Link
                  style={tabStyle(tab === "attachments")}
                  href={`/patients/${patientId}/attachments`}
                  aria-current={tab === "attachments" ? "page" : undefined}
                >
                  Attachments
                </Link>
                <button
                  style={tabStyle(tab === "notes")}
                  onClick={() => setTab("notes")}
                  type="button"
                  aria-current={tab === "notes" ? "page" : undefined}
                >
                  Notes ({notes.length})
                </button>
                <button
                  style={tabStyle(tab === "invoices")}
                  onClick={() => setTab("invoices")}
                  type="button"
                  aria-current={tab === "invoices" ? "page" : undefined}
                >
                  Invoices ({invoices.length})
                </button>
                <button
                  style={tabStyle(tab === "ledger")}
                  onClick={() => setTab("ledger")}
                  type="button"
                  aria-current={tab === "ledger" ? "page" : undefined}
                >
                  Ledger ({ledgerEntries.length})
                </button>
                <button
                  style={tabStyle(tab === "recalls")}
                  onClick={() => setTab("recalls")}
                  type="button"
                  aria-current={tab === "recalls" ? "page" : undefined}
                >
                  Recalls ({recalls.length})
                </button>
                <button
                  style={tabStyle(tab === "estimates")}
                  onClick={() => setTab("estimates")}
                  type="button"
                  aria-current={tab === "estimates" ? "page" : undefined}
                >
                  Estimates ({estimates.length})
                </button>
                <Link style={tabStyle(false)} href={`/patients/${patientId}/timeline`}>
                  Timeline
                </Link>
                <Link style={tabStyle(false)} href={`/patients/${patientId}/audit`}>
                  Audit
                </Link>
              </div>

              {tab === "summary" ? (
                <div className="stack summary-stack">
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 12,
                      flexWrap: "wrap",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <div className="label">Patient home</div>
                      <div style={{ fontSize: 22, fontWeight: 700 }}>
                        {patient.first_name} {patient.last_name}
                      </div>
                      <div style={{ color: "var(--muted)" }}>
                        DOB {patient.date_of_birth || "—"} · Age{" "}
                        {formatAge(patient.date_of_birth)} · Phone{" "}
                        {patient.phone || "—"}
                      </div>
                      <div style={{ color: "var(--muted)" }}>
                        Address {buildAddress(patient) || "—"}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <div className="badge">
                        Recall{" "}
                        {patient.recall_due_date
                          ? `${recallStatusLabels[patient.recall_status || "due"]} · ${formatShortDate(
                              patient.recall_due_date
                            )}`
                          : "not set"}
                      </div>
                      <div className="badge">
                        Balance: {formatCurrency(financeBalance)}
                      </div>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => {
                          openBookingModal();
                          setPendingScrollTarget("patient-book-appointment");
                        }}
                      >
                        Book appointment
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => {
                          setTab("summary");
                          setPendingScrollTarget("patient-appointments");
                        }}
                      >
                        Jump to appointments
                      </button>
                    </div>
                  </div>

                  <div className="summary-grid">
                    <div className="stack">
                      <div className="card" style={{ margin: 0 }}>
                        <div className="stack">
                          <div className="row">
                            <div>
                              <h4 style={{ marginTop: 0 }}>Recall</h4>
                              <div style={{ color: "var(--muted)" }}>
                                Due {formatShortDate(patient.recall_due_date)} ·{" "}
                                {recallStatusLabels[patient.recall_status || "due"]}
                              </div>
                            </div>
                            {recallError && <span className="badge">{recallError}</span>}
                          </div>
                          <div className="grid grid-3">
                            <div className="stack" style={{ gap: 8 }}>
                              <label className="label">Interval (months)</label>
                              <input
                                className="input"
                                value={recallInterval}
                                onChange={(e) => setRecallInterval(e.target.value)}
                              />
                            </div>
                            <div className="stack" style={{ gap: 8 }}>
                              <label className="label">Due date</label>
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
                                onChange={(e) =>
                                  setRecallStatus(e.target.value as RecallStatus)
                                }
                              >
                                <option value="due">Due</option>
                                <option value="contacted">Contacted</option>
                                <option value="booked">Booked</option>
                                <option value="not_required">Not required</option>
                              </select>
                            </div>
                          </div>
                          <div className="row">
                            <button
                              className="btn btn-primary"
                              type="button"
                              disabled={recallSaving}
                              onClick={() => {
                                const parsed = Number(recallInterval);
                                const interval = Number.isNaN(parsed) ? null : parsed;
                                void updateRecall({
                                  interval_months: interval,
                                  due_date: recallDueDate || null,
                                  status: recallStatus || null,
                                });
                              }}
                            >
                              {recallSaving ? "Saving..." : "Save recall"}
                            </button>
                            <button
                              className="btn btn-secondary"
                              type="button"
                              onClick={() => void updateRecall({ status: "contacted" })}
                            >
                              Mark contacted
                            </button>
                            <button
                              className="btn btn-secondary"
                              type="button"
                              onClick={() => void updateRecall({ status: "not_required" })}
                            >
                              Not required
                            </button>
                          </div>
                        </div>
                      </div>

                      <div className="card" style={{ margin: 0 }}>
                        <div className="stack">
                          <div className="row">
                            <div>
                              <h4 style={{ marginTop: 0 }}>Finance summary</h4>
                              <div style={{ color: "var(--muted)" }}>
                                Outstanding {formatCurrency(financeBalance)}
                              </div>
                            </div>
                            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                              <button
                                className="btn btn-primary"
                                type="button"
                                onClick={() => {
                                  setTab("invoices");
                                }}
                              >
                                Create invoice
                              </button>
                              <button
                                className="btn btn-secondary"
                                type="button"
                                onClick={() => {
                                  setLedgerMode("payment");
                                  setShowLedgerModal(true);
                                }}
                              >
                                Add payment
                              </button>
                              <button
                                className="btn btn-secondary"
                                type="button"
                                onClick={() => {
                                  setLedgerMode("adjustment");
                                  setShowLedgerModal(true);
                                }}
                              >
                                Add adjustment
                              </button>
                            </div>
                          </div>
                          {financeSummaryError && (
                            <div className="notice">{financeSummaryError}</div>
                          )}
                          {financeSummaryLoading ? (
                            <div className="badge">Loading finance…</div>
                          ) : financeItems.length === 0 ? (
                            <div className="notice">No finance activity yet.</div>
                          ) : (
                            <div className="stack" style={{ gap: 8 }}>
                              {financeItems.map((item) => {
                                const amountPence =
                                  item.kind === "payment" ? -item.amount_pence : item.amount_pence;
                                const title =
                                  item.kind === "invoice"
                                    ? `Invoice${item.invoice_number ? ` · ${item.invoice_number}` : ""}`
                                    : "Payment";
                                return (
                                  <div
                                    key={`${item.kind}-${item.id}`}
                                    style={{
                                      display: "flex",
                                      justifyContent: "space-between",
                                      gap: 12,
                                      flexWrap: "wrap",
                                      alignItems: "center",
                                    }}
                                  >
                                    <div>
                                      <div style={{ fontWeight: 600 }}>{title}</div>
                                      <div style={{ color: "var(--muted)" }}>
                                        {formatShortDate(item.date)} · {item.status}
                                      </div>
                                    </div>
                                    <div
                                      style={{
                                        display: "flex",
                                        alignItems: "center",
                                        gap: 8,
                                        flexWrap: "wrap",
                                      }}
                                    >
                                      <div style={{ fontWeight: 600 }}>
                                        {formatSignedCurrency(amountPence)}
                                      </div>
                                      {item.kind === "invoice" && item.invoice_id && (
                                        <button
                                          className="btn btn-secondary"
                                          style={{ padding: "4px 8px", fontSize: 12 }}
                                          type="button"
                                          onClick={() =>
                                            downloadPdf(
                                              `/api/invoices/${item.invoice_id}/pdf`,
                                              `${item.invoice_number || `invoice-${item.invoice_id}`}.pdf`
                                            )
                                          }
                                        >
                                          Invoice PDF
                                        </button>
                                      )}
                                      {item.kind === "payment" && item.payment_id && (
                                        <button
                                          className="btn btn-secondary"
                                          style={{ padding: "4px 8px", fontSize: 12 }}
                                          type="button"
                                          onClick={() =>
                                            downloadPdf(
                                              `/api/payments/${item.payment_id}/receipt.pdf`,
                                              `receipt-${item.invoice_number || item.payment_id}.pdf`
                                            )
                                          }
                                        >
                                          Receipt PDF
                                        </button>
                                      )}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="stack">
                      <div
                        className="card"
                        id="patient-appointments"
                        style={{ margin: 0, scrollMarginTop: 96 }}
                      >
                        <div className="stack">
                          <div className="row">
                            <div>
                              <h4 style={{ marginTop: 0 }}>Appointments</h4>
                              <p style={{ color: "var(--muted)" }}>
                                Upcoming and recent visits for this patient.
                              </p>
                            </div>
                          </div>
                          {loadingAppointments ? (
                            <div className="badge">Loading appointments…</div>
                          ) : appointmentsError ? (
                            <div className="notice">{appointmentsError}</div>
                          ) : (
                            <div className="stack">
                              <div>
                                <div className="label">Future</div>
                                {futureAppointments.length === 0 ? (
                                  <div className="notice">No upcoming appointments.</div>
                                ) : (
                                  futureAppointments.slice(0, 6).map((appt) => (
                                    <button
                                      key={appt.id}
                                      type="button"
                                      className="card"
                                      style={{
                                        margin: "8px 0 0",
                                        textAlign: "left",
                                        cursor: "pointer",
                                      }}
                                      onClick={() => {
                                        const date = appt.starts_at.slice(0, 10);
                                        router.push(
                                          `/appointments?date=${date}&appointment=${appt.id}`
                                        );
                                      }}
                                    >
                                      <div
                                        style={{
                                          display: "grid",
                                          gap: 6,
                                          gridTemplateColumns: "200px 1fr 1fr",
                                          alignItems: "center",
                                        }}
                                      >
                                        <div style={{ fontWeight: 600 }}>
                                          <StatusIcon status={appt.status} />{" "}
                                          {new Date(appt.starts_at).toLocaleDateString("en-GB", {
                                            weekday: "short",
                                            day: "2-digit",
                                            month: "short",
                                          })}{" "}
                                          ·{" "}
                                          {new Date(appt.starts_at).toLocaleTimeString("en-GB", {
                                            hour: "2-digit",
                                            minute: "2-digit",
                                          })}{" "}
                                          ({formatDurationMinutes(appt.starts_at, appt.ends_at)})
                                        </div>
                                        <div style={{ color: "var(--muted)" }}>
                                          {appt.clinician || "Unassigned"} ·{" "}
                                          {appt.location || appt.location_text || "—"}
                                        </div>
                                        <div style={{ color: "var(--muted)" }}>
                                          {appointmentStatusLabels[appt.status]} ·{" "}
                                          {appt.appointment_type || "General"}
                                        </div>
                                      </div>
                                      {appt.status !== "booked" &&
                                        (appt.status === "cancelled" ||
                                          appt.status === "no_show") &&
                                        appt.cancel_reason && (
                                          <div
                                            style={{
                                              color: "var(--muted)",
                                              fontSize: 12,
                                              marginTop: 8,
                                            }}
                                            title={appt.cancel_reason}
                                          >
                                            Reason: {appt.cancel_reason}
                                          </div>
                                        )}
                                    </button>
                                  ))
                                )}
                              </div>
                              <div>
                                <div className="label">Past</div>
                                {pastAppointments.length === 0 ? (
                                  <div className="notice">No past appointments.</div>
                                ) : (
                                  pastAppointments.slice(0, 6).map((appt) => (
                                    <button
                                      key={appt.id}
                                      type="button"
                                      className="card"
                                      style={{
                                        margin: "8px 0 0",
                                        textAlign: "left",
                                        cursor: "pointer",
                                      }}
                                      onClick={() => {
                                        const date = appt.starts_at.slice(0, 10);
                                        router.push(
                                          `/appointments?date=${date}&appointment=${appt.id}`
                                        );
                                      }}
                                    >
                                      <div
                                        style={{
                                          display: "grid",
                                          gap: 6,
                                          gridTemplateColumns: "200px 1fr 1fr",
                                          alignItems: "center",
                                        }}
                                      >
                                        <div style={{ fontWeight: 600 }}>
                                          <StatusIcon status={appt.status} />{" "}
                                          {new Date(appt.starts_at).toLocaleDateString("en-GB", {
                                            weekday: "short",
                                            day: "2-digit",
                                            month: "short",
                                          })}{" "}
                                          ·{" "}
                                          {new Date(appt.starts_at).toLocaleTimeString("en-GB", {
                                            hour: "2-digit",
                                            minute: "2-digit",
                                          })}{" "}
                                          ({formatDurationMinutes(appt.starts_at, appt.ends_at)})
                                        </div>
                                        <div style={{ color: "var(--muted)" }}>
                                          {appt.clinician || "Unassigned"} ·{" "}
                                          {appt.location || appt.location_text || "—"}
                                        </div>
                                        <div style={{ color: "var(--muted)" }}>
                                          {appointmentStatusLabels[appt.status]} ·{" "}
                                          {appt.appointment_type || "General"}
                                        </div>
                                      </div>
                                      {appt.status !== "booked" &&
                                        (appt.status === "cancelled" ||
                                          appt.status === "no_show") &&
                                        appt.cancel_reason && (
                                          <div
                                            style={{
                                              color: "var(--muted)",
                                              fontSize: 12,
                                              marginTop: 8,
                                            }}
                                            title={appt.cancel_reason}
                                          >
                                            Reason: {appt.cancel_reason}
                                          </div>
                                        )}
                                    </button>
                                  ))
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      <details className="card" style={{ margin: 0 }}>
                        <summary className="label">Documents</summary>
                        <div className="stack" style={{ marginTop: 12 }}>
                          <PatientDocuments patientId={patientId} embedded />
                        </div>
                      </details>
                      <details className="card" style={{ margin: 0 }}>
                        <summary className="label">Attachments</summary>
                        <div className="stack" style={{ marginTop: 12 }}>
                          <PatientAttachments patientId={patientIdNum} embedded />
                        </div>
                      </details>
                    </div>
                  </div>

                  <details className="card" style={{ margin: 0 }}>
                    <summary className="label">Patient details</summary>
                    <div className="stack" style={{ marginTop: 12 }}>
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
                      <label className="label">Referral source</label>
                      <input
                        className="input"
                        value={patient.referral_source ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, referral_source: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Referral contact</label>
                      <input
                        className="input"
                        value={patient.referral_contact_name ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, referral_contact_name: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="grid grid-2">
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Referral phone</label>
                      <input
                        className="input"
                        value={patient.referral_contact_phone ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, referral_contact_phone: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Referral notes</label>
                      <textarea
                        className="input"
                        rows={2}
                        value={patient.referral_notes ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, referral_notes: e.target.value } : prev
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
                  <div className="grid grid-2">
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Financial alerts</label>
                      <textarea
                        className="input"
                        rows={3}
                        value={patient.alerts_financial ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, alerts_financial: e.target.value } : prev
                          )
                        }
                      />
                    </div>
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Access needs</label>
                      <textarea
                        className="input"
                        rows={3}
                        value={patient.alerts_access ?? ""}
                        onChange={(e) =>
                          setPatient((prev) =>
                            prev ? { ...prev, alerts_access: e.target.value } : prev
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
                </div>
              </details>
                </div>
              ) : tab === "clinical" ? (
                <div className="stack">
                  <div className="tabs">
                    <button
                      className={`tab ${clinicalTab === "chart" ? "active" : ""}`}
                      onClick={() => setClinicalTab("chart")}
                    >
                      Chart
                    </button>
                    <button
                      className={`tab ${clinicalTab === "treatment" ? "active" : ""}`}
                      onClick={() => setClinicalTab("treatment")}
                    >
                      Treatment plan ({treatmentPlanItems.length})
                    </button>
                    <button
                      className={`tab ${clinicalTab === "notes" ? "active" : ""}`}
                      onClick={() => setClinicalTab("notes")}
                    >
                      Notes ({clinicalNotes.length})
                    </button>
                  </div>

                  <div
                    className="row"
                    style={{
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 12,
                      flexWrap: "wrap",
                    }}
                  >
                    <div style={{ color: "var(--muted)" }}>
                      Last updated: {formatDateTime(clinicalLastUpdated)}
                    </div>
                    <button
                      className="btn btn-secondary"
                      type="button"
                      onClick={loadClinicalSummary}
                      disabled={clinicalLoading}
                    >
                      {clinicalLoading ? "Refreshing..." : "Refresh"}
                    </button>
                  </div>

                  {clinicalError && (
                    <div className="notice">
                      <div
                        className="row"
                        style={{ justifyContent: "space-between", alignItems: "center", gap: 12 }}
                      >
                        <span>{clinicalError}</span>
                        <button
                          className="btn btn-secondary"
                          type="button"
                          onClick={loadClinicalSummary}
                          disabled={clinicalLoading}
                        >
                          Retry
                        </button>
                      </div>
                    </div>
                  )}
                  {clinicalLoading ? (
                    <div className="badge">Loading clinical…</div>
                  ) : clinicalTab === "chart" ? (
                <div className="stack">
                  <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
                    <div className="label">View mode</div>
                    <div style={tabRowStyle} data-testid="clinical-chart-toggle">
                      <button
                        type="button"
                        style={tabStyle(clinicalViewMode === "current", true)}
                        onClick={() => setClinicalViewMode("current")}
                        data-testid="clinical-chart-view-current"
                        data-active={clinicalViewMode === "current"}
                        aria-pressed={clinicalViewMode === "current"}
                      >
                        Current
                      </button>
                      <button
                        type="button"
                        style={tabStyle(clinicalViewMode === "planned", true)}
                        onClick={() => setClinicalViewMode("planned")}
                        data-testid="clinical-chart-view-planned"
                        data-active={clinicalViewMode === "planned"}
                        aria-pressed={clinicalViewMode === "planned"}
                      >
                        Planned
                      </button>
                      <button
                        type="button"
                        style={tabStyle(clinicalViewMode === "history", true)}
                        onClick={() => setClinicalViewMode("history")}
                        data-testid="clinical-chart-view-history"
                        data-active={clinicalViewMode === "history"}
                        aria-pressed={clinicalViewMode === "history"}
                      >
                        History
                      </button>
                    </div>
                  </div>
                  <div style={tabRowStyle}>
                    <span className="badge">P Planned</span>
                    <span className="badge">H History</span>
                    <span className="badge">M Missing</span>
                    <span className="badge">X Extracted</span>
                    <span className="badge">D Deciduous</span>
                    <span className="badge">GC Gap closed</span>
                  </div>
                  <div
                    style={{
                      display: "grid",
                          gap: 16,
                          gridTemplateColumns: "minmax(0, 1.1fr) minmax(0, 0.9fr)",
                        }}
                      >
                        <div className="stack" style={{ gap: 16 }}>
                          <Panel title="Odontogram">
                            <div className="stack" style={{ gap: 16 }} data-testid="clinical-chart">
                              <div className="stack" style={{ gap: 8 }}>
                                <div className="label">Upper</div>
                                <div
                                  style={{
                                    display: "grid",
                                    gap: 6,
                                    gridTemplateColumns: "repeat(16, minmax(34px, 1fr))",
                                  }}
                                >
                                  {upperTeeth.map((tooth) => {
                                    const isActive = selectedTooth === tooth;
                                    return (
                                      <button
                                        key={tooth}
                                        className="btn btn-secondary"
                                        type="button"
                                        onClick={() => {
                                          setSelectedTooth(tooth);
                                          setNotesTooth(tooth);
                                        }}
                                        data-testid={`tooth-button-${tooth}`}
                                        style={{
                                          padding: "6px 0",
                                          fontWeight: 600,
                                          background: isActive
                                            ? "rgba(51, 255, 180, 0.18)"
                                            : undefined,
                                          borderColor: isActive ? "var(--accent)" : undefined,
                                        }}
                                    >
                                      <div
                                        style={{
                                          display: "flex",
                                          flexDirection: "column",
                                          alignItems: "center",
                                          gap: 2,
                                        }}
                                      >
                                        <span>{tooth}</span>
                                        {getToothBadges(tooth).length > 0 && (
                                          <div
                                            style={{
                                              display: "flex",
                                              gap: 4,
                                              fontSize: 10,
                                              lineHeight: 1,
                                              flexWrap: "wrap",
                                              justifyContent: "center",
                                            }}
                                            data-testid={`tooth-badge-${tooth}`}
                                          >
                                            {getToothBadges(tooth).map((badge) => (
                                              <span
                                                key={`${tooth}-${badge.label}`}
                                                title={badge.title}
                                              >
                                                {badge.label}
                                              </span>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </button>
                                  );
                                })}
                                </div>
                              </div>
                              <div className="stack" style={{ gap: 8 }}>
                                <div className="label">Lower</div>
                                <div
                                  style={{
                                    display: "grid",
                                    gap: 6,
                                    gridTemplateColumns: "repeat(16, minmax(34px, 1fr))",
                                  }}
                                >
                                  {lowerTeeth.map((tooth) => {
                                    const isActive = selectedTooth === tooth;
                                    return (
                                      <button
                                        key={tooth}
                                        className="btn btn-secondary"
                                        type="button"
                                        onClick={() => {
                                          setSelectedTooth(tooth);
                                          setNotesTooth(tooth);
                                        }}
                                        data-testid={`tooth-button-${tooth}`}
                                        style={{
                                          padding: "6px 0",
                                          fontWeight: 600,
                                          background: isActive
                                            ? "rgba(51, 255, 180, 0.18)"
                                            : undefined,
                                          borderColor: isActive ? "var(--accent)" : undefined,
                                        }}
                                    >
                                      <div
                                        style={{
                                          display: "flex",
                                          flexDirection: "column",
                                          alignItems: "center",
                                          gap: 2,
                                        }}
                                      >
                                        <span>{tooth}</span>
                                        {getToothBadges(tooth).length > 0 && (
                                          <div
                                            style={{
                                              display: "flex",
                                              gap: 4,
                                              fontSize: 10,
                                              lineHeight: 1,
                                              flexWrap: "wrap",
                                              justifyContent: "center",
                                            }}
                                            data-testid={`tooth-badge-${tooth}`}
                                          >
                                            {getToothBadges(tooth).map((badge) => (
                                              <span
                                                key={`${tooth}-${badge.label}`}
                                                title={badge.title}
                                              >
                                                {badge.label}
                                              </span>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </button>
                                  );
                                })}
                                </div>
                              </div>
                            </div>
                          </Panel>

                          <Panel title="BPE">
                            <div className="stack" style={{ gap: 12 }}>
                              <div
                                style={{
                                  display: "grid",
                                  gap: 8,
                                  gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
                                }}
                              >
                                {bpeSextants.map((label, index) => (
                                  <div className="stack" style={{ gap: 6 }} key={label}>
                                    <label className="label">{label}</label>
                                    <input
                                      className="input"
                                      value={bpeScores[index] ?? ""}
                                      onChange={(e) => {
                                        const next = [...bpeScores];
                                        next[index] = e.target.value;
                                        setBpeScores(next);
                                        setBpeNotice(null);
                                      }}
                                      placeholder="0-4 / *"
                                    />
                                  </div>
                                ))}
                              </div>
                              <div style={{ color: "var(--muted)" }}>
                                Last recorded: {formatShortDate(bpeRecordedAt)}
                              </div>
                              <div className="row">
                                <button
                                  className="btn btn-secondary"
                                  type="button"
                                  onClick={submitBpe}
                                  disabled={bpeSaving}
                                >
                                  {bpeSaving ? "Saving..." : "Save BPE"}
                                </button>
                                {bpeNotice && <span className="badge">{bpeNotice}</span>}
                              </div>
                            </div>
                          </Panel>
                        </div>

                        <Panel title={selectedTooth ? `Tooth ${selectedTooth}` : "Select a tooth"}>
                          {!selectedTooth ? (
                            <div className="notice">Select a tooth to add notes and procedures.</div>
                          ) : (
                            <div className="stack" style={{ gap: 16 }}>
                              <div className="stack" style={{ gap: 10 }}>
                                <div className="label">Add tooth note</div>
                                <div
                                  style={{
                                    display: "grid",
                                    gap: 10,
                                    gridTemplateColumns: "1fr 1fr",
                                  }}
                                >
                                  <div className="stack" style={{ gap: 8 }}>
                                    <label className="label">Surface (optional)</label>
                                    <input
                                      className="input"
                                      value={chartNoteSurface}
                                      onChange={(e) => setChartNoteSurface(e.target.value)}
                                      placeholder="O / M / D / B / L"
                                    />
                                  </div>
                                </div>
                                <div className="stack" style={{ gap: 8 }}>
                                  <label className="label">Note</label>
                                  <textarea
                                    className="input"
                                    rows={3}
                                    value={chartNoteBody}
                                    onChange={(e) => {
                                      setChartNoteBody(e.target.value);
                                      setChartNoteNotice(null);
                                    }}
                                    placeholder="Clinical observation or note"
                                  />
                                </div>
                                <button
                                  className="btn btn-primary"
                                  type="button"
                                  onClick={submitChartNote}
                                  disabled={savingToothNote || !chartNoteBody.trim()}
                                >
                                  {savingToothNote ? "Saving..." : "Add note"}
                                </button>
                                {chartNoteNotice && <span className="badge">{chartNoteNotice}</span>}
                              </div>

                              <div className="stack" style={{ gap: 10 }}>
                                <div className="label">Quick add procedure</div>
                                <div className="stack" style={{ gap: 8 }}>
                                  <label className="label">Procedure code</label>
                                  <select
                                    className="input"
                                    value={procedureCode}
                                    onChange={(e) => {
                                      const code = e.target.value;
                                      setProcedureCode(code);
                                      const match = procedureCatalog.find(
                                        (item) => item.code === code
                                      );
                                      setProcedureDescription(match ? match.label : "");
                                    }}
                                  >
                                    <option value="">Select code</option>
                                    {procedureCatalog.map((item) => (
                                      <option key={item.code} value={item.code}>
                                        {item.code} · {item.label}
                                      </option>
                                    ))}
                                  </select>
                                </div>
                                <div className="stack" style={{ gap: 8 }}>
                                  <label className="label">Description</label>
                                  <input
                                    className="input"
                                    value={procedureDescription}
                                    onChange={(e) => setProcedureDescription(e.target.value)}
                                    placeholder="Procedure description"
                                  />
                                </div>
                                <div className="stack" style={{ gap: 8 }}>
                                  <label className="label">Fee (optional)</label>
                                  <input
                                    className="input"
                                    value={procedureFee}
                                    onChange={(e) => setProcedureFee(e.target.value)}
                                    placeholder="0.00"
                                  />
                                </div>
                                <button
                                  className="btn btn-secondary"
                                  type="button"
                                  onClick={submitProcedure}
                                  disabled={
                                    savingProcedure ||
                                    !procedureCode ||
                                    !procedureDescription.trim()
                                  }
                                >
                                  {savingProcedure ? "Saving..." : "Add procedure"}
                                </button>
                                <button
                                  className="btn btn-secondary"
                                  type="button"
                                  onClick={openPlanFromChart}
                                  disabled={!procedureCode || !procedureDescription.trim()}
                                >
                                  Add to plan
                                </button>
                              </div>

                              <div className="stack" style={{ gap: 10 }}>
                                <div className="label">Tooth timeline</div>
                                {clinicalViewMode !== "planned" && (
                                  <div className="stack" style={{ gap: 8 }}>
                                    <div className="label">History</div>
                                    {toothHistoryLoading ? (
                                      <div className="badge">Loading history…</div>
                                    ) : toothHistoryEntries.length === 0 ? (
                                      <div className="notice">No history yet.</div>
                                    ) : (
                                      <div className="stack">
                                        {toothHistoryEntries.map((entry, index) => (
                                          <div className="card" style={{ margin: 0 }} key={index}>
                                            <div className="row">
                                              <div>
                                                <strong>
                                                  {entry.type === "note" ? "Note" : "Procedure"}
                                                </strong>
                                                <div style={{ color: "var(--muted)" }}>
                                                  {formatShortDate(entry.date)} ·{" "}
                                                  {entry.actor || "—"}
                                                </div>
                                              </div>
                                              <span className="badge">{entry.label}</span>
                                            </div>
                                            <div title={entry.detail}>{entry.detail}</div>
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                )}
                                {clinicalViewMode !== "history" && (
                                  <div className="stack" style={{ gap: 8 }}>
                                    <div className="label">Planned</div>
                                    {plannedItemsForTooth.length === 0 ? (
                                      <div className="notice">No planned items yet.</div>
                                    ) : (
                                      <div className="stack">
                                        {plannedItemsForTooth.map((item) => (
                                          <div className="card" style={{ margin: 0 }} key={item.id}>
                                            <div className="row">
                                              <div>
                                                <strong>{item.procedure_code}</strong>
                                                <div style={{ color: "var(--muted)" }}>
                                                  {item.description}
                                                </div>
                                              </div>
                                              <span className="badge">
                                                {treatmentStatusLabels[item.status]}
                                              </span>
                                            </div>
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </Panel>
                      </div>
                    </div>
                  ) : clinicalTab === "treatment" ? (
                    <div className="stack">
                      <div className="row">
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          <button
                            className="btn btn-primary"
                            type="button"
                            onClick={() => setShowPlanModal(true)}
                          >
                            Add item
                          </button>
                          <button
                            className="btn btn-secondary"
                            type="button"
                            onClick={loadClinicalSummary}
                          >
                            Refresh
                          </button>
                        </div>
                      </div>

                      {treatmentPlanItems.length === 0 ? (
                        <div className="notice">
                          No treatment plan items yet. Add an item to start planning.
                        </div>
                      ) : (
                        <Table>
                          <thead>
                            <tr>
                              <th>Status</th>
                              <th>Tooth</th>
                              <th>Code</th>
                              <th>Description</th>
                              <th>Fee</th>
                              <th>Created</th>
                              <th>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {treatmentPlanItems.map((item) => {
                              const isFinal = ["completed", "declined", "cancelled"].includes(
                                item.status
                              );
                              return (
                                <tr key={item.id}>
                                  <td>
                                    <div
                                      style={{
                                        display: "inline-flex",
                                        gap: 6,
                                        alignItems: "center",
                                      }}
                                    >
                                      <span
                                        className="status-icon"
                                        data-status={item.status}
                                        aria-hidden="true"
                                      />
                                      {treatmentStatusLabels[item.status]}
                                    </div>
                                  </td>
                                  <td>{item.tooth || "—"}</td>
                                  <td>{item.procedure_code}</td>
                                  <td title={item.description}>
                                    <span
                                      style={{
                                        display: "inline-block",
                                        maxWidth: 220,
                                        overflow: "hidden",
                                        textOverflow: "ellipsis",
                                        whiteSpace: "nowrap",
                                      }}
                                    >
                                      {item.description}
                                    </span>
                                  </td>
                                  <td>
                                    {item.fee_pence != null
                                      ? formatCurrency(item.fee_pence)
                                      : "—"}
                                  </td>
                                  <td>{formatShortDate(item.created_at)}</td>
                                  <td>
                                    <div className="table-actions">
                                      <button
                                        className="btn btn-secondary"
                                        type="button"
                                        onClick={() => updateTreatmentPlanStatus(item, "accepted")}
                                        disabled={isFinal || item.status !== "proposed"}
                                      >
                                        Accept
                                      </button>
                                      <button
                                        className="btn btn-secondary"
                                        type="button"
                                        onClick={() => updateTreatmentPlanStatus(item, "declined")}
                                        disabled={isFinal || item.status !== "proposed"}
                                      >
                                        Decline
                                      </button>
                                      <button
                                        className="btn btn-secondary"
                                        type="button"
                                        onClick={() => updateTreatmentPlanStatus(item, "completed")}
                                        disabled={isFinal || item.status === "declined"}
                                      >
                                        Complete
                                      </button>
                                      <button
                                        className="btn btn-secondary"
                                        type="button"
                                        onClick={() => updateTreatmentPlanStatus(item, "cancelled")}
                                        disabled={isFinal}
                                      >
                                        Cancel
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </Table>
                      )}
                    </div>
                  ) : (
                    <div className="stack">
                      <Panel title="Add clinical note">
                        <div className="stack" style={{ gap: 10 }}>
                          <div
                            style={{
                              display: "grid",
                              gap: 10,
                              gridTemplateColumns: "1fr 1fr",
                            }}
                          >
                            <div className="stack" style={{ gap: 8 }}>
                              <label className="label">Tooth</label>
                              <select
                                className="input"
                                value={notesTooth}
                                onChange={(e) => setNotesTooth(e.target.value)}
                              >
                                <option value="">Select tooth</option>
                                {allTeeth.map((tooth) => (
                                  <option key={tooth} value={tooth}>
                                    {tooth}
                                  </option>
                                ))}
                              </select>
                            </div>
                            <div className="stack" style={{ gap: 8 }}>
                              <label className="label">Surface</label>
                              <input
                                className="input"
                                value={notesSurface}
                                onChange={(e) => setNotesSurface(e.target.value)}
                                placeholder="O / M / D / B / L"
                              />
                            </div>
                          </div>
                          <div className="stack" style={{ gap: 8 }}>
                            <label className="label">Note</label>
                            <textarea
                              className="input"
                              rows={3}
                              value={notesBody}
                              onChange={(e) => {
                                setNotesBody(e.target.value);
                                setClinicalNoteNotice(null);
                              }}
                              placeholder="Date-stamped clinical note"
                            />
                          </div>
                          <button
                            className="btn btn-primary"
                            type="button"
                            onClick={submitClinicalNote}
                            disabled={savingClinicalNote || !notesTooth || !notesBody.trim()}
                          >
                            {savingClinicalNote ? "Saving..." : "Add note"}
                          </button>
                          {clinicalNoteNotice && (
                            <span className="badge">{clinicalNoteNotice}</span>
                          )}
                        </div>
                      </Panel>

                      {sortedClinicalNotes.length === 0 ? (
                        <div className="notice">
                          No clinical notes recorded yet. Add notes from the Clinical entry area.
                        </div>
                      ) : (
                        <div className="stack">
                          {sortedClinicalNotes.map((note) => (
                            <div className="card" key={note.id}>
                              <div className="row">
                                <div>
                                  <strong>
                                    {note.tooth}
                                    {note.surface ? ` · ${note.surface}` : ""}
                                  </strong>
                                  <div style={{ color: "var(--muted)" }}>
                                  {formatDateTime(note.created_at)} · {note.created_by.email}
                                </div>
                                </div>
                                <span className="badge">Tooth note</span>
                              </div>
                              <p style={{ marginBottom: 0 }} title={note.note}>
                                {note.note}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}

                      <Panel title="Recent procedures">
                        {sortedClinicalProcedures.length === 0 ? (
                          <div className="notice">
                            No procedures recorded yet. Add from the chart or treatment plan.
                          </div>
                        ) : (
                          <div className="stack">
                            {sortedClinicalProcedures.map((procedure) => (
                              <div className="card" style={{ margin: 0 }} key={procedure.id}>
                                <div className="row">
                                  <div>
                                    <strong>{procedure.procedure_code}</strong>
                                    <div style={{ color: "var(--muted)" }}>
                                      {formatShortDate(procedure.performed_at)} ·{" "}
                                      {procedure.created_by.email}
                                    </div>
                                  </div>
                                  <span className="badge">{procedure.tooth || "—"}</span>
                                </div>
                                <div title={procedure.description}>{procedure.description}</div>
                              </div>
                            ))}
                          </div>
                        )}
                      </Panel>
                    </div>
                  )}
                </div>
              ) : tab === "documents" ? (
                <div className="stack">
                  <PatientDocuments patientId={patientId} />
                </div>
              ) : tab === "attachments" ? (
                <div className="stack">
                  <PatientAttachments patientId={patientIdNum} />
                </div>
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
                                {formatDateTime(note.created_at)} • {note.created_by.email}
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
              ) : tab === "ledger" ? (
                <div className="stack">
                  <div className="row">
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <button
                        className="btn btn-primary"
                        type="button"
                        onClick={() => {
                          setLedgerMode("payment");
                          setShowLedgerModal(true);
                        }}
                      >
                        Add payment
                      </button>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        onClick={() => {
                          setLedgerMode("adjustment");
                          setShowLedgerModal(true);
                        }}
                      >
                        Add adjustment
                      </button>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        onClick={() => {
                          void loadLedger();
                          void loadLedgerBalance();
                        }}
                      >
                        Refresh
                      </button>
                    </div>
                    <div className="badge">Balance {formatCurrency(ledgerBalance)}</div>
                  </div>
                  {ledgerError && <div className="notice">{ledgerError}</div>}
                  {ledgerLoading ? (
                    <div className="badge">Loading ledger…</div>
                  ) : ledgerEntries.length === 0 ? (
                    <div className="notice">No ledger entries yet.</div>
                  ) : (
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Type</th>
                          <th>Reference</th>
                          <th>Charge</th>
                          <th>Payment</th>
                          <th>Balance</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ledgerWithBalance.map((entry) => (
                          <tr key={entry.id}>
                            <td>{new Date(entry.created_at).toLocaleDateString("en-GB")}</td>
                            <td>
                              {entry.entry_type === "payment"
                                ? "Payment"
                                : entry.entry_type === "charge"
                                ? "Charge"
                                : "Adjustment"}
                            </td>
                            <td>
                              {entry.reference || "—"}
                              {entry.note ? ` · ${entry.note}` : ""}
                            </td>
                            <td>
                              {entry.amount_pence > 0
                                ? formatCurrency(entry.amount_pence)
                                : "—"}
                            </td>
                            <td>
                              {entry.amount_pence < 0
                                ? formatCurrency(Math.abs(entry.amount_pence))
                                : "—"}
                            </td>
                            <td>{formatSignedCurrency(entry.running_balance)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              ) : tab === "recalls" ? (
                <div className="stack">
                  <div className="row">
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <button
                        className="btn btn-primary"
                        type="button"
                        onClick={() => {
                          if (showRecallForm) {
                            resetRecallForm();
                          } else {
                            setShowRecallForm(true);
                          }
                        }}
                      >
                        {showRecallForm ? "Close form" : "Add recall"}
                      </button>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        onClick={() => void loadRecalls()}
                      >
                        Refresh
                      </button>
                    </div>
                  </div>

                  {showRecallForm && (
                    <div className="card" style={{ margin: 0 }}>
                      <div className="stack">
                        <div className="row">
                          <h4 style={{ margin: 0 }}>
                            {editingRecallId ? "Edit recall" : "Add recall"}
                          </h4>
                          {editingRecallId && <span className="badge">Editing</span>}
                        </div>
                        <div className="grid grid-3">
                          <div className="stack" style={{ gap: 8 }}>
                            <label className="label">Type</label>
                            <select
                              className="input"
                              value={recallEntryKind}
                              onChange={(e) => setRecallEntryKind(e.target.value as RecallKind)}
                            >
                              {Object.entries(recallKindLabels).map(([value, label]) => (
                                <option key={value} value={value}>
                                  {label}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="stack" style={{ gap: 8 }}>
                            <label className="label">Due date</label>
                            <input
                              className="input"
                              type="date"
                              value={recallEntryDueDate}
                              onChange={(e) => setRecallEntryDueDate(e.target.value)}
                            />
                          </div>
                          <div className="stack" style={{ gap: 8 }}>
                            <label className="label">Quick set</label>
                            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                              {[3, 6, 12].map((months) => (
                                <button
                                  key={months}
                                  type="button"
                                  className="btn btn-secondary"
                                  onClick={() =>
                                    setRecallEntryDueDate(
                                      formatDateInput(addMonthsToDate(new Date(), months))
                                    )
                                  }
                                >
                                  {months} months
                                </button>
                              ))}
                            </div>
                          </div>
                        </div>
                        <div className="stack" style={{ gap: 8 }}>
                          <label className="label">Notes</label>
                          <textarea
                            className="input"
                            rows={3}
                            value={recallEntryNotes}
                            onChange={(e) => setRecallEntryNotes(e.target.value)}
                            placeholder="Optional notes for this recall"
                          />
                        </div>
                        <div className="row">
                          <button
                            className="btn btn-primary"
                            type="button"
                            disabled={recallEntrySaving || !recallEntryDueDate}
                            onClick={saveRecallEntry}
                          >
                            {recallEntrySaving
                              ? "Saving..."
                              : editingRecallId
                              ? "Save recall"
                              : "Add recall"}
                          </button>
                          {editingRecallId && (
                            <button
                              className="btn btn-secondary"
                              type="button"
                              onClick={resetRecallForm}
                            >
                              Cancel edit
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {recallsError && <div className="notice">{recallsError}</div>}
                  {recallsLoading ? (
                    <div className="badge">Loading recalls…</div>
                  ) : recalls.length === 0 ? (
                    <div className="notice">No recalls yet.</div>
                  ) : (
                    <>
                      <Table className="recall-table">
                        <thead>
                          <tr>
                            <th>Type</th>
                            <th>Due</th>
                            <th>Status</th>
                            <th>Outcome</th>
                            <th>Notes</th>
                            <th>Completed</th>
                            <th>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {recalls.map((recall) => {
                            const isFinal = ["completed", "cancelled"].includes(recall.status);
                            const isExpanded = expandedRecallId === recall.id;
                            const comms = recallCommMap[recall.id] || [];
                            return (
                              <Fragment key={recall.id}>
                                <tr>
                                  <td>{recallKindLabels[recall.kind]}</td>
                                  <td>{formatShortDate(recall.due_date)}</td>
                                  <td>
                                    <span className="badge">
                                      {recallItemStatusLabels[recall.status]}
                                    </span>
                                  </td>
                                  <td>
                                    {recall.outcome ? recallOutcomeLabels[recall.outcome] : "—"}
                                  </td>
                                  <td>{recall.notes || "—"}</td>
                                  <td>
                                    {recall.completed_at
                                      ? formatShortDate(recall.completed_at)
                                      : "—"}
                                  </td>
                                  <td>
                                    <div className="table-actions">
                                      <button
                                        className="btn btn-secondary"
                                        type="button"
                                        onClick={() => startEditRecall(recall)}
                                        disabled={recallEntrySaving}
                                      >
                                        Edit
                                      </button>
                                      <button
                                        className="btn btn-secondary"
                                        type="button"
                                        onClick={() => void downloadRecallLetter(recall)}
                                        disabled={recallDownloadId === recall.id}
                                      >
                                        {recallDownloadId === recall.id
                                          ? "Generating..."
                                          : "Generate letter"}
                                      </button>
                                      <button
                                        className="btn btn-secondary"
                                        type="button"
                                        onClick={() => openRecallCommModal(recall)}
                                      >
                                        Log contact
                                      </button>
                                      <button
                                        className="btn btn-secondary"
                                        type="button"
                                        onClick={() => toggleRecallCommunications(recall.id)}
                                      >
                                        {isExpanded ? "Hide log" : "Show log"}
                                      </button>
                                      <button
                                        className="btn btn-secondary"
                                        type="button"
                                        onClick={() => void markRecallCompleted(recall)}
                                        disabled={isFinal || recallActionId === recall.id}
                                      >
                                        {recallActionId === recall.id
                                          ? "Updating..."
                                          : "Mark completed"}
                                      </button>
                                      <button
                                        className="btn btn-secondary"
                                        type="button"
                                        onClick={() => void markRecallCompleted(recall, 6)}
                                        disabled={isFinal || recallActionId === recall.id}
                                      >
                                        Complete +6m
                                      </button>
                                      <button
                                        className="btn btn-secondary"
                                        type="button"
                                        onClick={() => void markRecallCompleted(recall, 12)}
                                        disabled={isFinal || recallActionId === recall.id}
                                      >
                                        Complete +12m
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                                {isExpanded && (
                                  <tr>
                                    <td colSpan={7}>
                                      <div className="stack" style={{ gap: 8 }}>
                                        <strong>Recent communications</strong>
                                        {recallCommError && (
                                          <div className="notice">{recallCommError}</div>
                                        )}
                                        {recallCommLoadingId === recall.id ? (
                                          <div className="badge">Loading communications…</div>
                                        ) : comms.length === 0 ? (
                                          <div className="badge">No communications yet.</div>
                                        ) : (
                                          <div className="stack" style={{ gap: 6 }}>
                                            {comms.map((entry) => (
                                              <div
                                                key={entry.id}
                                                className="row"
                                                style={{ alignItems: "center" }}
                                              >
                                                <span className="badge">
                                                  {recallCommChannelLabels[entry.channel]}
                                                </span>
                                                <span className="badge">
                                                  {recallCommStatusLabels[entry.status]}
                                                </span>
                                                <span style={{ color: "var(--muted)" }}>
                                                  {formatDateTime(entry.created_at)}
                                                </span>
                                                <span>{entry.notes || "—"}</span>
                                              </div>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </td>
                                  </tr>
                                )}
                              </Fragment>
                            );
                          })}
                        </tbody>
                      </Table>
                      <div className="recall-cards">
                        {recalls.map((recall) => {
                          const isFinal = ["completed", "cancelled"].includes(recall.status);
                          const isExpanded = expandedRecallId === recall.id;
                          const comms = recallCommMap[recall.id] || [];
                          return (
                            <div className="card recall-card" key={recall.id}>
                              <div className="row">
                                <div>
                                  <strong>{recallKindLabels[recall.kind]}</strong>
                                  <div style={{ color: "var(--muted)" }}>
                                    Due {formatShortDate(recall.due_date)}
                                  </div>
                                </div>
                                <span className="badge">
                                  {recallItemStatusLabels[recall.status]}
                                </span>
                              </div>
                              <div style={{ color: "var(--muted)" }}>
                                Completed{" "}
                                {recall.completed_at
                                  ? formatShortDate(recall.completed_at)
                                  : "—"}
                              </div>
                              <div style={{ color: "var(--muted)" }}>
                                Outcome{" "}
                                {recall.outcome ? recallOutcomeLabels[recall.outcome] : "—"}
                              </div>
                              {recall.notes && <div>{recall.notes}</div>}
                              <div className="row">
                                <button
                                  className="btn btn-secondary"
                                  type="button"
                                  onClick={() => startEditRecall(recall)}
                                  disabled={recallEntrySaving}
                                >
                                  Edit
                                </button>
                                <button
                                  className="btn btn-secondary"
                                  type="button"
                                  onClick={() => void downloadRecallLetter(recall)}
                                  disabled={recallDownloadId === recall.id}
                                >
                                  {recallDownloadId === recall.id
                                    ? "Generating..."
                                    : "Generate letter"}
                                </button>
                                <button
                                  className="btn btn-secondary"
                                  type="button"
                                  onClick={() => openRecallCommModal(recall)}
                                >
                                  Log contact
                                </button>
                                <button
                                  className="btn btn-secondary"
                                  type="button"
                                  onClick={() => toggleRecallCommunications(recall.id)}
                                >
                                  {isExpanded ? "Hide log" : "Show log"}
                                </button>
                                <button
                                  className="btn btn-secondary"
                                  type="button"
                                  onClick={() => void markRecallCompleted(recall)}
                                  disabled={isFinal || recallActionId === recall.id}
                                >
                                  {recallActionId === recall.id
                                    ? "Updating..."
                                    : "Mark completed"}
                                </button>
                                <button
                                  className="btn btn-secondary"
                                  type="button"
                                  onClick={() => void markRecallCompleted(recall, 6)}
                                  disabled={isFinal || recallActionId === recall.id}
                                >
                                  Complete +6m
                                </button>
                                <button
                                  className="btn btn-secondary"
                                  type="button"
                                  onClick={() => void markRecallCompleted(recall, 12)}
                                  disabled={isFinal || recallActionId === recall.id}
                                >
                                  Complete +12m
                                </button>
                              </div>
                              {isExpanded && (
                                <div className="stack" style={{ gap: 6 }}>
                                  <strong>Recent communications</strong>
                                  {recallCommError && (
                                    <div className="notice">{recallCommError}</div>
                                  )}
                                  {recallCommLoadingId === recall.id ? (
                                    <div className="badge">Loading communications…</div>
                                  ) : comms.length === 0 ? (
                                    <div className="badge">No communications yet.</div>
                                  ) : (
                                    <div className="stack" style={{ gap: 6 }}>
                                      {comms.map((entry) => (
                                        <div
                                          key={entry.id}
                                          className="row"
                                          style={{ alignItems: "center" }}
                                        >
                                          <span className="badge">
                                            {recallCommChannelLabels[entry.channel]}
                                          </span>
                                          <span className="badge">
                                            {recallCommStatusLabels[entry.status]}
                                          </span>
                                          <span style={{ color: "var(--muted)" }}>
                                            {formatDateTime(entry.created_at)}
                                          </span>
                                          <span>{entry.notes || "—"}</span>
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}
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

          {showPlanModal && (
            <div className="card" style={{ margin: 0 }}>
              <div className="stack">
                <div className="row">
                  <div>
                    <h3 style={{ marginTop: 0 }}>Add treatment plan item</h3>
                    <p style={{ color: "var(--muted)" }}>
                      Proposed treatment for {patient.first_name} {patient.last_name}.
                    </p>
                  </div>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    onClick={() => setShowPlanModal(false)}
                  >
                    Close
                  </button>
                </div>
                <div className="stack" style={{ gap: 10 }}>
                  <div
                    style={{
                      display: "grid",
                      gap: 10,
                      gridTemplateColumns: "1fr 1fr",
                    }}
                  >
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Tooth (optional)</label>
                      <select
                        className="input"
                        value={planTooth}
                        onChange={(e) => setPlanTooth(e.target.value)}
                      >
                        <option value="">Select tooth</option>
                        {allTeeth.map((tooth) => (
                          <option key={tooth} value={tooth}>
                            {tooth}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Surface</label>
                      <input
                        className="input"
                        value={planSurface}
                        onChange={(e) => setPlanSurface(e.target.value)}
                        placeholder="O / M / D / B / L"
                      />
                    </div>
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Procedure code</label>
                    <input
                      className="input"
                      list="procedure-codes"
                      value={planCode}
                      onChange={(e) => {
                        const code = e.target.value;
                        setPlanCode(code);
                        const match = procedureCatalog.find((item) => item.code === code);
                        if (match && !planDescription) {
                          setPlanDescription(match.label);
                        }
                      }}
                      placeholder="Code"
                    />
                    <datalist id="procedure-codes">
                      {procedureCatalog.map((item) => (
                        <option key={item.code} value={item.code}>
                          {item.label}
                        </option>
                      ))}
                    </datalist>
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Description</label>
                    <textarea
                      className="input"
                      rows={3}
                      value={planDescription}
                      onChange={(e) => setPlanDescription(e.target.value)}
                    />
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Fee (optional)</label>
                    <input
                      className="input"
                      value={planFee}
                      onChange={(e) => setPlanFee(e.target.value)}
                      placeholder="0.00"
                    />
                  </div>
                  <button
                    className="btn btn-primary"
                    type="button"
                    onClick={submitTreatmentPlanItem}
                    disabled={planSaving || !planCode.trim() || !planDescription.trim()}
                  >
                    {planSaving ? "Saving..." : "Add item"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {showRecallCommModal && (
            <div className="card" style={{ margin: 0 }}>
              <div className="stack">
                <div className="row">
                  <div>
                    <h3 style={{ marginTop: 0 }}>Log recall communication</h3>
                    <p style={{ color: "var(--muted)" }}>
                      {recallCommTarget
                        ? `${recallKindLabels[recallCommTarget.kind]} due ${formatShortDate(
                            recallCommTarget.due_date
                          )}`
                        : "Recall contact log"}
                    </p>
                  </div>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    onClick={() => setShowRecallCommModal(false)}
                  >
                    Close
                  </button>
                </div>
                {recallCommError && <div className="notice">{recallCommError}</div>}
                <div
                  style={{
                    display: "grid",
                    gap: 12,
                    gridTemplateColumns: "1fr 1fr",
                  }}
                >
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Channel</label>
                    <select
                      className="input"
                      value={recallCommChannel}
                      onChange={(e) =>
                        setRecallCommChannel(e.target.value as RecallCommChannel)
                      }
                    >
                      {Object.entries(recallCommChannelLabels).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Notes</label>
                    <textarea
                      className="input"
                      rows={3}
                      value={recallCommNotes}
                      onChange={(e) => setRecallCommNotes(e.target.value)}
                      placeholder="Optional notes"
                    />
                  </div>
                </div>
                <button
                  className="btn btn-primary"
                  type="button"
                  onClick={saveRecallCommunication}
                  disabled={recallCommSaving || !recallCommRecallId}
                >
                  {recallCommSaving ? "Saving..." : "Save log"}
                </button>
              </div>
            </div>
          )}

          {showBookingModal && (
            <div
              className="card"
              id="patient-book-appointment"
              style={{ margin: 0, scrollMarginTop: 96 }}
            >
              <div className="stack">
                <div className="row">
                  <div>
                    <h3 style={{ marginTop: 0 }}>Book appointment</h3>
                    <p style={{ color: "var(--muted)" }}>
                      Appointment for {patient.first_name} {patient.last_name}.
                    </p>
                  </div>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    onClick={() => setShowBookingModal(false)}
                  >
                    Close
                  </button>
                </div>
                <form onSubmit={createBooking} className="stack">
                  <div style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr" }}>
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Date</label>
                      <input
                        className="input"
                        type="date"
                        value={bookingDate}
                        onChange={(e) => setBookingDate(e.target.value)}
                        required
                      />
                    </div>
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Start time</label>
                      <input
                        className="input"
                        type="time"
                        value={bookingTime}
                        onChange={(e) => setBookingTime(e.target.value)}
                        required
                      />
                    </div>
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Duration</label>
                    <select
                      className="input"
                      value={bookingDuration}
                      onChange={(e) => setBookingDuration(e.target.value)}
                    >
                      {[10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120].map(
                        (minutes) => (
                          <option key={minutes} value={String(minutes)}>
                            {minutes} minutes
                          </option>
                        )
                      )}
                    </select>
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Treatment type</label>
                    <input
                      className="input"
                      value={bookingAppointmentType}
                      onChange={(e) => setBookingAppointmentType(e.target.value)}
                      placeholder="Exam, cleaning, emergency"
                    />
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Clinician (optional)</label>
                    <select
                      className="input"
                      value={bookingClinicianUserId}
                      onChange={(e) => setBookingClinicianUserId(e.target.value)}
                    >
                      <option value="">Unassigned</option>
                      {users.map((user) => (
                        <option key={user.id} value={user.id}>
                          {user.full_name || user.email} ({user.role})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Location / room</label>
                    <input
                      className="input"
                      value={bookingLocation}
                      onChange={(e) => setBookingLocation(e.target.value)}
                      placeholder="Room 1"
                    />
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Location type</label>
                    <select
                      className="input"
                      value={bookingLocationType}
                      onChange={(e) => {
                        const next = e.target.value as "clinic" | "visit";
                        setBookingLocationType(next);
                        if (next === "clinic") setBookingLocationText("");
                      }}
                    >
                      <option value="clinic">Clinic</option>
                      <option value="visit">Visit</option>
                    </select>
                  </div>
                  {bookingLocationType === "visit" && (
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Visit address</label>
                      <textarea
                        className="input"
                        rows={3}
                        value={bookingLocationText}
                        onChange={(e) => setBookingLocationText(e.target.value)}
                      />
                    </div>
                  )}
                  <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <input
                      type="checkbox"
                      checked={bookingMarkRecall}
                      onChange={(e) => setBookingMarkRecall(e.target.checked)}
                    />
                    Mark recall as booked
                  </label>
                  <button className="btn btn-primary" disabled={bookingSaving}>
                    {bookingSaving ? "Saving..." : "Create appointment"}
                  </button>
                </form>
              </div>
            </div>
          )}

          {showLedgerModal && (
            <div className="card" style={{ margin: 0 }}>
              <div className="stack">
                <div className="row">
                  <div>
                    <h3 style={{ marginTop: 0 }}>
                      {ledgerMode === "payment" ? "Add payment" : "Add adjustment"}
                    </h3>
                    <p style={{ color: "var(--muted)" }}>
                      Entry for {patient.first_name} {patient.last_name}.
                    </p>
                  </div>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    onClick={() => setShowLedgerModal(false)}
                  >
                    Close
                  </button>
                </div>
                {ledgerError && <div className="notice">{ledgerError}</div>}
                <div className="stack">
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Amount (£)</label>
                    <input
                      className="input"
                      value={ledgerAmount}
                      onChange={(e) => setLedgerAmount(e.target.value)}
                      placeholder="0.00"
                    />
                  </div>
                  {ledgerMode === "payment" && (
                    <div className="stack" style={{ gap: 8 }}>
                      <label className="label">Method</label>
                      <select
                        className="input"
                        value={ledgerMethod}
                        onChange={(e) => setLedgerMethod(e.target.value as PaymentMethod)}
                      >
                        <option value="card">Card</option>
                        <option value="cash">Cash</option>
                        <option value="bank_transfer">Bank transfer</option>
                        <option value="other">Other</option>
                      </select>
                    </div>
                  )}
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Reference</label>
                    <input
                      className="input"
                      value={ledgerReference}
                      onChange={(e) => setLedgerReference(e.target.value)}
                      placeholder="Optional reference"
                    />
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <label className="label">Note</label>
                    <textarea
                      className="input"
                      rows={3}
                      value={ledgerNote}
                      onChange={(e) => setLedgerNote(e.target.value)}
                      placeholder="Optional note"
                    />
                  </div>
                  <button
                    className="btn btn-primary"
                    type="button"
                    onClick={submitLedgerEntry}
                    disabled={ledgerSaving}
                  >
                    {ledgerSaving ? "Saving..." : "Save entry"}
                  </button>
                </div>
              </div>
            </div>
          )}

          <div className="card">
            <Timeline items={timeline} title="Recent activity" />
          </div>
        </div>
      ) : (
        <div className="notice">Patient not found.</div>
      )}
      </div>
    </div>
  );
}
