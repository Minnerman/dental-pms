import { NOTE_BODY_MAX_LENGTH } from "@/lib/noteErrors";

export const journalCategories = ["all", "notes", "diagnosis", "treatment", "medical", "correspondence"] as const;
export type JournalCategory = typeof journalCategories[number];
export const journalLabels: Record<JournalCategory, string> = {
  all: "All", notes: "Notes", diagnosis: "Diagnosis", treatment: "Treatment", medical: "Medical", correspondence: "Correspondence",
};
export const JOURNAL_NOTE_MAX_LENGTH = NOTE_BODY_MAX_LENGTH;
export type JournalAuthor = { name: string | null; user_id: number | null; source_user_code: string | number | null };
export type JournalItem = {
  key: string; source_kind: string; source_id: number | string; category: Exclude<JournalCategory, "all">;
  title: string; body: string | null; occurred_at: string | null; clinical_date: string | null; date_basis: string;
  author: JournalAuthor | null; tooth: string | null; surface: string | null; revision: number | null;
  can_edit: boolean; history_url: string | null; link: string | null;
  provenance: string | Record<string, unknown> | null; details: Record<string, unknown> | null;
};
export type JournalResponse = {
  patient_id: number; items: JournalItem[]; next_cursor: string | null;
  availability: Record<string, string | { status?: string; availability?: string; reason?: string }>;
  coverage_notes?: string[];
};
export type ClinicalNoteTemplate = {
  id: number; title: string; category: string; body: string; codes: string[];
  fields: Array<{ key: string; label: string; options: string[]; required: boolean }>;
  revision: number; is_active: boolean; created_at: string; updated_at: string;
};

export function journalDay(item: Pick<JournalItem, "clinical_date" | "occurred_at">) {
  if (item.clinical_date && /^\d{4}-\d{2}-\d{2}$/.test(item.clinical_date)) return item.clinical_date;
  if (!item.occurred_at || !Number.isFinite(Date.parse(item.occurred_at))) return "undated";
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/London", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(item.occurred_at));
}
export function journalDayLabel(day: string) {
  return day === "undated" ? "Date not recorded" : new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London", day: "numeric", month: "long", year: "numeric",
  }).format(new Date(`${day}T12:00:00Z`));
}
export function groupJournal(items: JournalItem[]) {
  const groups = new Map<string, JournalItem[]>();
  for (const item of items) { const day = journalDay(item); groups.set(day, [...(groups.get(day) ?? []), item]); }
  return [...groups.entries()].sort(([a], [b]) => a === "undated" ? 1 : b === "undated" ? -1 : b.localeCompare(a));
}
export function renderNoteTemplate(template: ClinicalNoteTemplate, answers: Record<string, string>) {
  const missing = template.fields.filter((field) => field.required && !answers[field.key]?.trim()).map((field) => field.label);
  const allowed = new Set(template.fields.map((field) => field.key));
  const body = template.body.replace(/\{\{\s*([A-Za-z][A-Za-z0-9_]*)\s*\}\}/g, (token, key: string) => allowed.has(key) ? answers[key]?.trim() || token : token);
  return { body, missing };
}
export function noteRequestHeaders() {
  return { "Request-Id": crypto.randomUUID?.() ?? `note-${Date.now()}-${Array.from(crypto.getRandomValues(new Uint32Array(3))).join("-")}` };
}
export function safeJournalLink(link: string | null) {
  return link && /^\/(?:api\/)?(?:patients|notes|patient-documents|clinical-note-templates)\//.test(link) && !link.includes("\\") ? link : null;
}
export const noteTeeth = ["UR", "UL", "LL", "LR"].flatMap((quadrant) => Array.from({ length: 8 }, (_, index) => `${quadrant}${index + 1}`));

function readableObservation(value: unknown, depth = 0): string {
  if (value === null) return "not specified";
  if (typeof value === "string") return value.replaceAll("_", " ");
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "number") return String(value);
  if (Array.isArray(value)) return value.map((item) => readableObservation(item, depth + 1)).join(", ") || "none recorded";
  if (value && typeof value === "object" && depth < 5) return Object.entries(value).filter(([key]) => !["revision", "updated_at", "updated_by", "bridge_group_id"].includes(key)).map(([key, item]) => `${key.replaceAll("_", " ")}: ${readableObservation(item, depth + 1)}`).join("; ") || "none recorded";
  return "";
}
export function journalDiagnosisLines(item: JournalItem): string[] {
  if (item.source_kind !== "diagnosis") return [];
  const details = item.details ?? {};
  const fields: Record<string, readonly string[]> = {
    "clinical.tooth_conditions.recorded": ["condition", "dentition", "movement", "rotation"],
    "clinical.root_conditions.recorded": ["root_observations"],
    "clinical.crown_conditions.recorded": ["crown_observation"],
    "clinical.surface_conditions.recorded": ["surface_observations"],
    "clinical.bridge.created": ["bridge_role", "crown_observation"],
    "clinical.bridge.reset": ["bridge_role", "crown_observation"],
  };
  const keys = typeof details.action === "string" && Object.hasOwn(fields, details.action) ? fields[details.action] : undefined;
  const observations = details.observations;
  if (!keys || !observations || typeof observations !== "object" || Array.isArray(observations)) return [];
  const changed = Array.isArray(details.changed_teeth) ? details.changed_teeth.filter((tooth): tooth is string => typeof tooth === "string") : Object.keys(observations);
  const lines: string[] = [];
  for (const tooth of changed) {
    const row = (observations as Record<string, unknown>)[tooth];
    if (!row || typeof row !== "object" || Array.isArray(row)) continue;
    for (const key of keys) {
      if (!Object.hasOwn(row, key)) continue;
      const value = (row as Record<string, unknown>)[key];
      if (["root_observations", "surface_observations"].includes(key) && value && typeof value === "object" && !Array.isArray(value) && Object.keys(value).length) {
        const label = key === "root_observations" ? "Root" : "Surface";
        for (const [area, finding] of Object.entries(value)) lines.push(`${tooth} · ${label} ${area}: ${readableObservation(finding)}`);
      } else {
        const label = ({ root_observations: "Roots", crown_observation: "Crown", surface_observations: "Surfaces" } as Record<string, string>)[key] ?? key.replaceAll("_", " ");
        lines.push(`${tooth} · ${label}: ${readableObservation(value)}`);
      }
    }
  }
  return lines;
}
export function journalDetailLines(item: JournalItem) {
  const details = item.details ?? {};
  const lines: string[] = [];
  const text = (key: string, label: string) => { const value = details[key]; if (typeof value === "string" || typeof value === "number") lines.push(`${label}: ${String(value).replaceAll("_", " ")}`); };
  if (["procedure", "treatment_plan"].includes(item.source_kind)) { text("procedure_code", "Code"); text("status", "Status"); }
  if (item.source_kind === "recall_communication") { lines.push("Manual contact log · delivery not verified"); for (const [key, label] of [["channel", "Channel"], ["direction", "Direction"], ["status", "Logged status"], ["outcome", "Outcome"], ["other_detail", "Detail"]]) text(key, label); }
  if (item.source_kind === "document") lines.push("Generated document · delivery not recorded");
  if (["note", "tooth_note"].includes(item.source_kind)) {
    text("note_category", "Category");
    if (Array.isArray(details.codes) && details.codes.length) lines.push(`Code labels: ${details.codes.filter((code) => typeof code === "string").join(", ")}`);
    if (details.template_id != null) lines.push(`Template ${details.template_id} · version ${details.template_revision ?? "not recorded"}`);
    if ((item.revision ?? 0) > 1 && details.latest_revision && typeof details.latest_revision === "object") {
      const latest = details.latest_revision as Record<string, unknown>;
      const at = typeof latest.recorded_at === "string" && Number.isFinite(Date.parse(latest.recorded_at)) ? new Date(latest.recorded_at).toLocaleString("en-GB", { timeZone: "Europe/London" }) : "time not recorded";
      lines.push(`${latest.baseline ? "Baseline captured; earlier edits unavailable" : "Latest version"}: ${typeof latest.actor_name === "string" ? latest.actor_name : "author not recorded"} · ${at}`);
    }
  }
  if (item.source_kind.startsWith("r4_")) { text("source_tooth", "Original tooth code (unmapped)"); text("source_surface", "Original surface code"); }
  return lines;
}
