"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Timeline from "@/components/timeline/Timeline";
import { apiFetch, clearToken } from "@/lib/auth";

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

export default function PatientTimelineClient({ id }: { id: string }) {
  const router = useRouter();
  const patientId = id;
  const [items, setItems] = useState<TimelineItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await apiFetch(`/api/patients/${patientId}/timeline`);
        if (res.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        if (res.status === 403) {
          setError("Not authorised to view this timeline.");
          return;
        }
        if (res.status === 404) {
          setError("Patient not found.");
          return;
        }
        if (!res.ok) {
          throw new Error(`Failed to load timeline (HTTP ${res.status})`);
        }
        const data = (await res.json()) as TimelineItem[];
        setItems(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load timeline");
      } finally {
        setLoading(false);
      }
    })();
  }, [patientId, router]);

  return (
    <div className="app-grid">
      <div>
        <Link className="btn btn-secondary" href={`/patients/${patientId}`}>
          ← Back to patient
        </Link>
      </div>

      {error && <div className="notice">{error}</div>}
      {loading ? (
        <div className="badge">Loading timeline…</div>
      ) : (
        <Timeline items={items} title="Patient timeline" />
      )}
    </div>
  );
}
