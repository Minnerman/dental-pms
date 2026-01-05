"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";

type Actor = {
  id: number;
  email: string;
  role: string;
};

type AuditEntry = {
  id: number;
  created_at: string;
  actor?: Actor | null;
  actor_email?: string | null;
  action: string;
  entity_type: string;
  before_json?: Record<string, unknown> | null;
  after_json?: Record<string, unknown> | null;
};

export default function PatientAuditClient({ id }: { id: string }) {
  const router = useRouter();
  const patientId = id;
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  useEffect(() => {
    (async () => {
      try {
        const res = await apiFetch(`/api/patients/${patientId}/audit`);
        if (res.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        if (!res.ok) {
          throw new Error(`Failed to load audit (HTTP ${res.status})`);
        }
        const data = (await res.json()) as AuditEntry[];
        setAudit(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load audit");
      } finally {
        setLoading(false);
      }
    })();
  }, [patientId, router]);

  return (
    <section className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ marginTop: 0 }}>Audit log</h2>
          <p style={{ color: "var(--muted)" }}>
            Immutable record of changes for this patient.
          </p>
        </div>
        <a className="btn btn-secondary" href={`/patients/${patientId}`}>
          Back to patient
        </a>
      </div>

      {error && <div className="notice">{error}</div>}

      {loading ? (
        <div className="badge">Loading audit…</div>
      ) : (
        <div className="card" style={{ margin: 0 }}>
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Who</th>
                <th>Action</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((entry) => (
                <tr key={entry.id}>
                  <td>{new Date(entry.created_at).toLocaleString()}</td>
                  <td>{entry.actor?.email || entry.actor_email || "System"}</td>
                  <td>{entry.action}</td>
                  <td>
                    <button
                      className="btn btn-secondary"
                      onClick={() =>
                        setExpanded((prev) => ({
                          ...prev,
                          [entry.id]: !prev[entry.id],
                        }))
                      }
                    >
                      {expanded[entry.id] ? "Hide" : "View"}
                    </button>
                    {expanded[entry.id] && (
                      <pre style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>
                        {JSON.stringify(
                          { before: entry.before_json, after: entry.after_json },
                          null,
                          2
                        )}
                      </pre>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
