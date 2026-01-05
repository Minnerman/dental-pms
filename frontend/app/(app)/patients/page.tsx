"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
  updated_at: string;
  created_by?: Actor | null;
  updated_by?: Actor | null;
  deleted_at?: string | null;
};

export default function PatientsPage() {
  const router = useRouter();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [query, setQuery] = useState("");
  const [emailFilter, setEmailFilter] = useState("");
  const [dobFilter, setDobFilter] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadPatients(filters?: {
    query?: string;
    email?: string;
    dob?: string;
    includeDeleted?: boolean;
  }) {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (filters?.query) params.set("query", filters.query);
    if (filters?.email) params.set("email", filters.email);
    if (filters?.dob) params.set("dob", filters.dob);
    if (filters?.includeDeleted ?? showArchived) params.set("include_deleted", "1");
    try {
      const res = await apiFetch(`/api/patients?${params.toString()}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load patients (HTTP ${res.status})`);
      }
      const data = (await res.json()) as Patient[];
      setPatients(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load patients");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadPatients();
  }, []);

  return (
    <div className="app-grid">
      <section className="card" style={{ display: "grid", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
          <div>
            <h2 style={{ marginTop: 0 }}>Patients</h2>
            <p style={{ color: "var(--muted)", marginBottom: 0 }}>
              Search, create, and view patient records.
            </p>
          </div>
          <Link className="btn btn-primary" href="/patients/new">
            New patient
          </Link>
        </div>

        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <input
            className="input"
            placeholder="Search name, email, phone"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                void loadPatients({ query, email: emailFilter, dob: dobFilter });
              }
            }}
          />
          <input
            className="input"
            placeholder="Filter by email"
            value={emailFilter}
            onChange={(e) => setEmailFilter(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                void loadPatients({ query, email: emailFilter, dob: dobFilter });
              }
            }}
          />
          <input
            className="input"
            type="date"
            value={dobFilter}
            onChange={(e) => setDobFilter(e.target.value)}
          />
          <button
            className="btn btn-secondary"
            onClick={() => loadPatients({ query, email: emailFilter, dob: dobFilter })}
          >
            Search
          </button>
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: "auto" }}>
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => {
                const next = e.target.checked;
                setShowArchived(next);
                void loadPatients({ query, email: emailFilter, dob: dobFilter, includeDeleted: next });
              }}
            />
            Show archived
          </label>
        </div>

        {error && <div className="notice">{error}</div>}

        <div className="card" style={{ margin: 0 }}>
          {loading ? (
            <div className="badge">Loading patients…</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>DOB</th>
                  <th>Phone</th>
                  <th>Last edited</th>
                  <th>Last edited by</th>
                </tr>
              </thead>
              <tbody>
                {patients.map((patient) => (
                  <tr key={patient.id}>
                    <td>
                      <Link href={`/patients/${patient.id}`}>
                        {patient.first_name} {patient.last_name}
                      </Link>
                      {patient.deleted_at && (
                        <span className="badge" style={{ marginLeft: 8 }}>
                          Archived
                        </span>
                      )}
                    </td>
                    <td>{patient.date_of_birth || "—"}</td>
                    <td>{patient.phone || "—"}</td>
                    <td>{new Date(patient.updated_at).toLocaleString()}</td>
                    <td>{patient.updated_by?.email || patient.created_by?.email || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}
