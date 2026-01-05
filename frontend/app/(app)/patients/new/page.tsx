"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiFetch, clearToken } from "@/lib/auth";

export default function NewPatientPage() {
  const router = useRouter();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [dob, setDob] = useState("");
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
        <button className="btn btn-primary" disabled={saving}>
          {saving ? "Saving..." : "Save patient"}
        </button>
      </form>
    </section>
  );
}
