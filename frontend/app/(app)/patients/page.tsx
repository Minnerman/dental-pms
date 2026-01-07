"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import HeaderBar from "@/components/ui/HeaderBar";
import Panel from "@/components/ui/Panel";
import Table from "@/components/ui/Table";

type Actor = {
  id: number;
  email: string;
  role: string;
};

type PatientCategory = "CLINIC_PRIVATE" | "DOMICILIARY_PRIVATE" | "DENPLAN";

type Patient = {
  id: number;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  phone?: string | null;
  updated_at: string;
  patient_category: PatientCategory;
  created_by?: Actor | null;
  updated_by?: Actor | null;
  deleted_at?: string | null;
};

const categoryLabels: Record<PatientCategory, string> = {
  CLINIC_PRIVATE: "Clinic (Private)",
  DOMICILIARY_PRIVATE: "Domiciliary (Private)",
  DENPLAN: "Denplan",
};

export default function PatientsPage() {
  const router = useRouter();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [query, setQuery] = useState("");
  const [emailFilter, setEmailFilter] = useState("");
  const [dobFilter, setDobFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<PatientCategory | "">("");
  const [showArchived, setShowArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openFirst, setOpenFirst] = useState(false);
  const searchRef = useRef<HTMLInputElement | null>(null);

  async function loadPatients(filters?: {
    query?: string;
    email?: string;
    dob?: string;
    category?: PatientCategory | "";
    includeDeleted?: boolean;
    openFirst?: boolean;
  }) {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (filters?.query) params.set("query", filters.query);
    if (filters?.email) params.set("email", filters.email);
    if (filters?.dob) params.set("dob", filters.dob);
    if (filters?.category) params.set("category", filters.category);
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
      if (filters?.openFirst && data.length > 0) {
        router.push(`/patients/${data[0].id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load patients");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadPatients();
  }, []);

  useEffect(() => {
    searchRef.current?.focus();
  }, []);

  return (
    <div className="app-grid">
      <Panel>
        <HeaderBar
          title="Patients"
          subtitle="Search, create, and view patient records."
          actions={
            <Link className="btn btn-primary" href="/patients/new">
              New patient
            </Link>
          }
        />

        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <input
            ref={searchRef}
            className="input"
            placeholder="Search name, email, phone"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                void loadPatients({
                  query,
                  email: emailFilter,
                  dob: dobFilter,
                  category: categoryFilter,
                  openFirst: true,
                });
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
                void loadPatients({
                  query,
                  email: emailFilter,
                  dob: dobFilter,
                  category: categoryFilter,
                });
              }
            }}
          />
          <input
            className="input"
            type="date"
            value={dobFilter}
            onChange={(e) => setDobFilter(e.target.value)}
          />
          <select
            className="input"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value as PatientCategory | "")}
          >
            <option value="">All categories</option>
            <option value="CLINIC_PRIVATE">Clinic (Private)</option>
            <option value="DOMICILIARY_PRIVATE">Domiciliary (Private)</option>
            <option value="DENPLAN">Denplan</option>
          </select>
          <button
            className="btn btn-secondary"
            onClick={() =>
              loadPatients({
                query,
                email: emailFilter,
                dob: dobFilter,
                category: categoryFilter,
              })
            }
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
                void loadPatients({
                  query,
                  email: emailFilter,
                  dob: dobFilter,
                  category: categoryFilter,
                  includeDeleted: next,
                });
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
            <Table className="table-compact table-hover table-sticky">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>DOB</th>
                  <th>Phone</th>
                  <th>Category</th>
                  <th>Balance</th>
                  <th>Recall</th>
                  <th>Last visit</th>
                  <th>Last edited</th>
                  <th>Last edited by</th>
                </tr>
              </thead>
              <tbody>
                {patients.map((patient) => (
                  <tr
                    key={patient.id}
                    onDoubleClick={() => router.push(`/patients/${patient.id}`)}
                    style={{ cursor: "pointer" }}
                  >
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
                    <td>
                      <span className="badge">{categoryLabels[patient.patient_category]}</span>
                    </td>
                    <td>
                      <span className="badge">£—</span>
                    </td>
                    <td>
                      <span className="badge">—</span>
                    </td>
                    <td>
                      <span className="badge">—</span>
                    </td>
                    <td>{new Date(patient.updated_at).toLocaleString()}</td>
                    <td>{patient.updated_by?.email || patient.created_by?.email || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </div>
      </Panel>
    </div>
  );
}
