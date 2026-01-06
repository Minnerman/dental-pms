"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiFetch, clearToken } from "@/lib/auth";

type PatientCategory = "CLINIC_PRIVATE" | "DOMICILIARY_PRIVATE" | "DENPLAN";
type CareSetting = "CLINIC" | "HOME" | "CARE_HOME" | "HOSPITAL";

export default function NewPatientPage() {
  const router = useRouter();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [dob, setDob] = useState("");
  const [patientCategory, setPatientCategory] =
    useState<PatientCategory>("CLINIC_PRIVATE");
  const [denplanPlanName, setDenplanPlanName] = useState("");
  const [denplanMemberNo, setDenplanMemberNo] = useState("");
  const [careSetting, setCareSetting] = useState<CareSetting>("CLINIC");
  const [visitAddressText, setVisitAddressText] = useState("");
  const [accessNotes, setAccessNotes] = useState("");
  const [primaryContactName, setPrimaryContactName] = useState("");
  const [primaryContactPhone, setPrimaryContactPhone] = useState("");
  const [primaryContactRelationship, setPrimaryContactRelationship] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/api/patients", {
        method: "POST",
        body: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          email: email || null,
          phone: phone || null,
          date_of_birth: dob || null,
          patient_category: patientCategory,
          denplan_plan_name: patientCategory === "DENPLAN" ? denplanPlanName || null : null,
          denplan_member_no: patientCategory === "DENPLAN" ? denplanMemberNo || null : null,
          care_setting: careSetting,
          visit_address_text: visitAddressText || null,
          access_notes: accessNotes || null,
          primary_contact_name: primaryContactName || null,
          primary_contact_phone: primaryContactPhone || null,
          primary_contact_relationship: primaryContactRelationship || null,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to create patient (HTTP ${res.status})`);
      }
      const data = await res.json();
      router.push(`/patients/${data.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create patient");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="card" style={{ maxWidth: 720 }}>
      <h2 style={{ marginTop: 0 }}>New patient</h2>
      <p style={{ color: "var(--muted)" }}>
        Enter the basics now; you can add more details later.
      </p>
      {error && <div className="notice">{error}</div>}
      <form onSubmit={onSubmit} className="stack">
        <div className="stack" style={{ gap: 8 }}>
          <label className="label">First name</label>
          <input
            className="input"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            required
          />
        </div>
        <div className="stack" style={{ gap: 8 }}>
          <label className="label">Last name</label>
          <input
            className="input"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            required
          />
        </div>
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr" }}>
          <div className="stack" style={{ gap: 8 }}>
            <label className="label">Email</label>
            <input
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="stack" style={{ gap: 8 }}>
            <label className="label">Phone</label>
            <input
              className="input"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </div>
        </div>
        <div className="stack" style={{ gap: 8 }}>
          <label className="label">Date of birth</label>
          <input
            className="input"
            type="date"
            value={dob}
            onChange={(e) => setDob(e.target.value)}
          />
        </div>
        <div className="stack" style={{ gap: 8 }}>
          <label className="label">Patient category</label>
          <select
            className="input"
            value={patientCategory}
            onChange={(e) => setPatientCategory(e.target.value as PatientCategory)}
          >
            <option value="CLINIC_PRIVATE">Clinic (Private)</option>
            <option value="DOMICILIARY_PRIVATE">Domiciliary (Private)</option>
            <option value="DENPLAN">Denplan</option>
          </select>
          {patientCategory === "DENPLAN" && (
            <p style={{ margin: 0, color: "var(--muted)", fontSize: 12 }}>
              Most care included; excluded items can be added as private charges via estimates.
            </p>
          )}
        </div>
        {patientCategory === "DENPLAN" && (
          <div style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr" }}>
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Denplan plan name</label>
              <input
                className="input"
                value={denplanPlanName}
                onChange={(e) => setDenplanPlanName(e.target.value)}
              />
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Denplan member number</label>
              <input
                className="input"
                value={denplanMemberNo}
                onChange={(e) => setDenplanMemberNo(e.target.value)}
              />
            </div>
          </div>
        )}
        <div className="stack" style={{ gap: 8 }}>
          <label className="label">Care setting</label>
          <select
            className="input"
            value={careSetting}
            onChange={(e) => setCareSetting(e.target.value as CareSetting)}
          >
            <option value="CLINIC">Clinic</option>
            <option value="HOME">Home</option>
            <option value="CARE_HOME">Care home</option>
            <option value="HOSPITAL">Hospital</option>
          </select>
        </div>
        {careSetting !== "CLINIC" && (
          <div className="stack" style={{ gap: 12 }}>
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Visit address</label>
              <textarea
                className="input"
                rows={2}
                value={visitAddressText}
                onChange={(e) => setVisitAddressText(e.target.value)}
              />
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Access notes</label>
              <textarea
                className="input"
                rows={2}
                value={accessNotes}
                onChange={(e) => setAccessNotes(e.target.value)}
              />
            </div>
            <div style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr 1fr" }}>
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Primary contact</label>
                <input
                  className="input"
                  value={primaryContactName}
                  onChange={(e) => setPrimaryContactName(e.target.value)}
                />
              </div>
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Contact phone</label>
                <input
                  className="input"
                  value={primaryContactPhone}
                  onChange={(e) => setPrimaryContactPhone(e.target.value)}
                />
              </div>
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Relationship</label>
                <input
                  className="input"
                  value={primaryContactRelationship}
                  onChange={(e) => setPrimaryContactRelationship(e.target.value)}
                />
              </div>
            </div>
          </div>
        )}
        <button className="btn btn-primary" disabled={saving}>
          {saving ? "Saving..." : "Save patient"}
        </button>
      </form>
    </section>
  );
}
