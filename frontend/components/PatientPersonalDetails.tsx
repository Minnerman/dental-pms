import type { FormEvent, MouseEvent } from "react";

export type PersonalDetailsPatient = {
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  email?: string | null;
  phone?: string | null;
  phone_label?: string | null;
  home_phone?: string | null;
  home_phone_label?: string | null;
  work_phone?: string | null;
  work_phone_label?: string | null;
  mobile_phone?: string | null;
  mobile_phone_label?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  postcode?: string | null;
  patient_category: "CLINIC_PRIVATE" | "DOMICILIARY_PRIVATE" | "DENPLAN";
  denplan_member_no?: string | null;
  denplan_plan_name?: string | null;
  care_setting: "CLINIC" | "HOME" | "CARE_HOME" | "HOSPITAL";
  visit_address_text?: string | null;
  access_notes?: string | null;
  primary_contact_name?: string | null;
  primary_contact_phone?: string | null;
  primary_contact_relationship?: string | null;
  referral_source?: string | null;
  referral_contact_name?: string | null;
  referral_contact_phone?: string | null;
  referral_notes?: string | null;
  allergies?: string | null;
  medical_alerts?: string | null;
  safeguarding_notes?: string | null;
  alerts_financial?: string | null;
  alerts_access?: string | null;
  notes?: string | null;
  deleted_at?: string | null;
};

type TextField = Exclude<keyof PersonalDetailsPatient, "patient_category" | "care_setting" | "deleted_at">;
type Props = {
  patient: PersonalDetailsPatient;
  canWrite: boolean;
  permissionsReady: boolean;
  saving: boolean;
  archiveAction: "archive" | "restore" | null;
  onChange: (patch: Partial<PersonalDetailsPatient>) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onArchive: (event: MouseEvent<HTMLButtonElement>) => void;
};

const phoneRows = [
  { field: "phone", label: "Primary phone", owner: "phone_label" },
  { field: "home_phone", label: "Home landline", owner: "home_phone_label" },
  { field: "work_phone", label: "Work phone", owner: "work_phone_label" },
  { field: "mobile_phone", label: "Mobile phone", owner: "mobile_phone_label" },
] as const;

export default function PatientPersonalDetails({ patient, canWrite, permissionsReady, saving, archiveAction, onChange, onSubmit, onArchive }: Props) {
  const input = (field: TextField, label: string, options: { type?: string; maxLength?: number; placeholder?: string } = {}) => (
    <div className="patient-personal-field" key={field}>
      <label htmlFor={`personal-${field}`}>{label}</label>
      <input id={`personal-${field}`} data-testid={`patient-personal-${field}`} className="input"
        type={options.type ?? "text"} maxLength={options.maxLength} placeholder={options.placeholder}
        value={patient[field] ?? ""} onChange={(event) => onChange({ [field]: event.target.value })} />
    </div>
  );
  const textarea = (field: TextField, label: string, rows = 2) => (
    <div className="patient-personal-field" key={field}>
      <label htmlFor={`personal-${field}`}>{label}</label>
      <textarea id={`personal-${field}`} data-testid={field === "notes" ? "patient-notes-field" : `patient-personal-${field}`}
        className="input" rows={rows} value={patient[field] ?? ""}
        onChange={(event) => onChange({ [field]: event.target.value })} />
    </div>
  );

  return <section className="card patient-personal-details" data-testid="patient-personal-details" aria-labelledby="patient-personal-details-heading">
    <h3 id="patient-personal-details-heading">Personal details</h3>
    <form onSubmit={onSubmit} className="patient-personal-form">
      {patient.deleted_at ? <div className="notice">Archived patient details are read-only until restored.</div>
        : permissionsReady && !canWrite ? <div className="notice">You can view this patient, but you cannot change it.</div> : null}
      <fieldset data-testid="patient-details-fields" disabled={!canWrite || Boolean(patient.deleted_at) || saving || archiveAction !== null}>
        <div className="patient-personal-pair">
          {input("first_name", "First name")}
          {input("last_name", "Last name")}
        </div>
        <div className="patient-personal-pair">
          {input("date_of_birth", "Date of birth", { type: "date" })}
          <div className="patient-personal-field">
            <label htmlFor="personal-patient_category">Patient category</label>
            <select id="personal-patient_category" className="input" value={patient.patient_category}
              onChange={(event) => onChange({ patient_category: event.target.value as PersonalDetailsPatient["patient_category"] })}>
              <option value="CLINIC_PRIVATE">Clinic (Private)</option>
              <option value="DOMICILIARY_PRIVATE">Domiciliary (Private)</option>
              <option value="DENPLAN">Denplan</option>
            </select>
          </div>
        </div>
        {patient.patient_category === "DENPLAN" && <div className="patient-personal-pair">
          {input("denplan_plan_name", "Denplan plan name")}
          {input("denplan_member_no", "Denplan member number")}
        </div>}
        {input("email", "Email", { type: "email" })}
        <div className="patient-personal-phones" aria-label="Phone numbers">
          {phoneRows.map(({ field, label, owner }) => <div className="patient-personal-phone-row" key={field}>
            {input(field, label, { type: "tel", maxLength: field === "phone" ? undefined : 50 })}
            <div className="patient-personal-field patient-phone-owner">
              <label htmlFor={`personal-${owner}`}>Whose number?</label>
              <input id={`personal-${owner}`} data-testid={`patient-personal-${owner}`} className="input" maxLength={120}
                aria-label={`${label} — whose number?`} placeholder="e.g. Daughter"
                value={patient[owner] ?? ""} onChange={(event) => onChange({ [owner]: event.target.value })} />
            </div>
          </div>)}
          <small>Primary phone is kept as recorded. Number labels do not grant messaging consent.</small>
        </div>
        <div className="patient-personal-address">
          <div className="patient-personal-pair">
            {input("address_line1", "Address line 1")}
            {input("address_line2", "Address line 2")}
          </div>
          <div className="patient-personal-pair">
            {input("city", "City")}
            {input("postcode", "Postcode")}
          </div>
        </div>
        <details className="patient-personal-extra">
          <summary>Care and referral</summary>
          <div className="patient-personal-extra-fields">
            <div className="patient-personal-field">
              <label htmlFor="personal-care_setting">Care setting</label>
              <select id="personal-care_setting" className="input" value={patient.care_setting}
                onChange={(event) => onChange({ care_setting: event.target.value as PersonalDetailsPatient["care_setting"] })}>
                <option value="CLINIC">Clinic</option><option value="HOME">Home</option>
                <option value="CARE_HOME">Care home</option><option value="HOSPITAL">Hospital</option>
              </select>
            </div>
            {patient.care_setting !== "CLINIC" && <>
              {textarea("visit_address_text", "Visit address")}
              {textarea("access_notes", "Access notes")}
              <div className="patient-personal-pair">
                {input("primary_contact_name", "Primary contact")}
                {input("primary_contact_phone", "Contact phone", { type: "tel" })}
              </div>
              {input("primary_contact_relationship", "Relationship")}
            </>}
            <div className="patient-personal-pair">
              {input("referral_source", "Referral source")}
              {input("referral_contact_name", "Referral contact")}
            </div>
            {input("referral_contact_phone", "Referral phone", { type: "tel" })}
            {textarea("referral_notes", "Referral notes")}
          </div>
        </details>
        <details className="patient-personal-extra">
          <summary>Alerts and access needs</summary>
          <div className="patient-personal-extra-fields">
            {textarea("allergies", "Allergies")}
            {textarea("medical_alerts", "Medical alerts")}
            {textarea("safeguarding_notes", "Safeguarding notes")}
            {textarea("alerts_financial", "Financial alerts")}
            {textarea("alerts_access", "Access needs")}
          </div>
        </details>
        <details className="patient-personal-extra" data-testid="patient-personal-notes">
          <summary>Notes</summary>
          <div className="patient-personal-extra-fields">{textarea("notes", "Notes", 3)}</div>
        </details>
      </fieldset>
      <div className="patient-personal-save-row">
        {canWrite && !patient.deleted_at && <button className="btn btn-primary" data-testid="patient-save-changes" disabled={saving || archiveAction !== null}>
          {saving ? "Saving..." : "Save changes"}
        </button>}
        {canWrite && <button className="btn btn-secondary" type="button" onClick={onArchive}
          disabled={saving || archiveAction !== null} data-testid="patient-archive-toggle">
          {archiveAction === "archive" ? "Archiving..." : archiveAction === "restore" ? "Restoring..." : patient.deleted_at ? "Restore patient" : "Archive patient"}
        </button>}
      </div>
    </form>
  </section>;
}
