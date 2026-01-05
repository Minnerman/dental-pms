"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AuditTable from "@/components/audit/AuditTable";
import { apiFetch, clearToken } from "@/lib/auth";

type AuditRow = {
  id: number | string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor_email: string | null;
  actor_role: string | null;
  created_at: string;
  before_json: Record<string, unknown> | null;
  after_json: Record<string, unknown> | null;
};

export default function NoteAuditClient({ id }: { id: string }) {
  const router = useRouter();
  const noteId = id;
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<number | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiFetch(`/api/notes/${noteId}/audit`);
        setStatus(res.status);
        if (res.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        if (res.status === 403) {
          setError("Not authorised.");
          return;
        }
        if (res.status === 404) {
          setError("Note not found.");
          return;
        }
        if (!res.ok) {
          throw new Error(`Failed to load audit (HTTP ${res.status})`);
        }
        const data = (await res.json()) as any[];
        const mapped = data.map((row) => ({
          id: row.id,
          entity_type: row.entity_type,
          entity_id: row.entity_id,
          action: row.action,
          actor_email: row.actor?.email ?? row.actor_email ?? null,
          actor_role: row.actor?.role ?? null,
          created_at: row.created_at,
          before_json: row.before_json ?? null,
          after_json: row.after_json ?? null,
        }));
        setRows(mapped);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load audit");
      } finally {
        setLoading(false);
      }
    })();
  }, [noteId, router]);

  return (
    <div className="app-grid">
      <a className="btn btn-secondary" href="/notes">
        ← Back to Notes
      </a>
      {loading ? (
        <div className="badge">Loading audit…</div>
      ) : error ? (
        <div className="notice">{error}</div>
      ) : (
        <AuditTable title="Note audit" rows={rows} />
      )}
      {status && status >= 500 && (
        <div className="notice">Server error (HTTP {status})</div>
      )}
    </div>
  );
}
