"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import Icon from "@/components/ui/Icon";
import styles from "./RecallSummary.module.css";

type Summary = {
  as_of_date: string;
  due_this_week: number;
  overdue: number;
  scheduled_this_month: number | null;
  scheduled_availability: "available" | "forbidden";
  conversion_rate: null;
  conversion_availability: "unavailable";
  conversion_reason: string;
};

export default function RecallSummary({ refreshKey }: { refreshKey: unknown }) {
  const router = useRouter();
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setError(false);
    async function load() {
      try {
        const response = await apiFetch("/api/recalls/summary");
        if (response.status === 401) { clearToken(); router.replace("/login"); return; }
        if (!response.ok) throw new Error();
        const payload = await response.json() as Summary;
        if (active) setData(payload);
      } catch {
        if (active) { setError(true); setData(null); }
      }
    }
    void load();
    return () => { active = false; };
  }, [refreshKey, retry, router]);
  const count = (value?: number | null) => error ? "—" : value == null ? "…" : value.toLocaleString("en-GB");
  return (
    <section aria-label="Recall overview" data-testid="recalls-summary" className={styles.section}>
      <div className={styles.grid}>
        <div className={styles.metric} title="Open recalls due Monday–Sunday this week, including earlier days this week."><Icon name="calendar" /><strong data-testid="recalls-summary-due">{count(data?.due_this_week)}</strong><span>Due this week</span></div>
        <div className={`${styles.metric} ${data?.overdue ? styles.overdue : ""}`} title="All open recalls with a due date before today."><Icon name="history" /><strong data-testid="recalls-summary-overdue">{count(data?.overdue)}</strong><span>Overdue</span></div>
        <div className={styles.metric} title={data?.scheduled_availability === "forbidden" ? "Appointment viewing permission is required." : "Linked recall appointments taking place this month; excludes cancelled, no-shows and deleted records. Counts each appointment once."}><Icon name="patients" /><strong data-testid="recalls-summary-scheduled">{data?.scheduled_availability === "forbidden" ? "—" : count(data?.scheduled_this_month)}</strong><span>Scheduled this month</span>{data?.scheduled_availability === "forbidden" && <small>Permission required</small>}</div>
        <div className={styles.metric} title={data?.conversion_reason || "A reliable contacted-to-booked measure is not recorded."}><Icon name="reports" /><strong data-testid="recalls-summary-conversion">—</strong><span>Conversion</span><small>Not recorded yet</small></div>
      </div>
      {error ? <p role="status">Overview unavailable. The call list still works. <button type="button" onClick={() => setRetry((value) => value + 1)}>Retry overview</button></p> : <p>Practice overview · independent of list filters · London dates{data ? ` · ${new Date(`${data.as_of_date}T12:00:00`).toLocaleDateString("en-GB")}` : ""}</p>}
    </section>
  );
}
