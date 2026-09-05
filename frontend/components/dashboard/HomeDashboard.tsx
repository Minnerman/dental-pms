"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { apiFetch, clearToken } from "@/lib/auth";
import Icon, { type IconName } from "@/components/ui/Icon";
import type { Availability, DashboardHome } from "./types";
import styles from "./dashboard.module.css";

const statusNames: Record<string, string> = {
  booked: "Booked", arrived: "Arrived", in_progress: "In progress",
  completed: "Completed", no_show: "Did not attend", cancelled: "Cancelled",
};
const currency = (pence: number) => new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(pence / 100);
const clockTime = (value: string) => new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
const calendarDate = (value: string, full = false) => new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/London", ...(full ? { weekday: "long" as const } : {}),
  day: "numeric", month: full ? "long" : "short", year: full ? "numeric" : undefined,
}).format(new Date(value.length === 10 ? value + "T12:00:00Z" : value));
const unavailableLabel = (state: Availability) => state === "forbidden" ? "Access restricted" : "Not recorded yet";

function Panel({ title, icon, children, link, state = "available", testId, tone }: {
  title: string; icon: IconName; children: ReactNode; link?: { href: string; label: string };
  state?: Availability; testId: string; tone?: string;
}) {
  return <section className={styles.panel} data-testid={testId} data-state={state}>
    <div className={styles.panelHeader}>
      <h2><span className={styles.panelIcon} data-tone={tone}><Icon name={icon} size={18} /></span>{title}</h2>
      {link && <Link className={styles.textLink} href={link.href}>{link.label}<span aria-hidden="true"> →</span></Link>}
    </div>{children}
  </section>;
}
function Empty({ icon, title, detail }: { icon: IconName; title: string; detail?: string }) {
  return <div className={styles.empty}><Icon name={icon} size={26} /><strong>{title}</strong>{detail && <p>{detail}</p>}</div>;
}
function Metric({ name, label, icon, value, description, state, alert = false }: {
  name: string; label: string; icon: IconName; value: number | null;
  description: ReactNode; state: Availability; alert?: boolean;
}) {
  return <section className={styles.metric} data-testid={`dashboard-card-${name}`} data-state={state} data-alert={alert}>
    <div className={styles.metricLabel}>{label}<Icon name={icon} size={18} /></div>
    {state === "available" && value !== null
      ? <strong className={styles.metricValue} data-testid={`dashboard-value-${name}`}>{value}</strong>
      : <strong className={styles.unavailableValue}>{unavailableLabel(state)}</strong>}
    <div className={styles.metricDescription}>{state === "available" ? description : "Your account cannot view this information."}</div>
  </section>;
}
function Change({ current, previous }: { current: number | null; previous: number | null }) {
  if (current === null || previous === null) return null;
  if (previous === 0) return <span className={styles.change}>{current === 0 ? "No change" : "No previous activity"}</span>;
  const change = Math.round(((current - previous) / previous) * 100);
  return <span className={styles.change} data-direction={change > 0 ? "up" : change < 0 ? "down" : "same"}>
    {change === 0 ? "No change" : `${change > 0 ? "↑ +" : "↓ "}${change}%`}
  </span>;
}

export default function HomeDashboard() {
  const router = useRouter();
  const [data, setData] = useState<DashboardHome | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [name, setName] = useState("");
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const generation = useRef(0);

  const refresh = useCallback(async () => {
    const ticket = ++generation.current;
    setLoading(true);
    setError(false);
    try {
      const response = await apiFetch("/api/dashboard/home", { cache: "no-store" });
      if (response.status === 401) { clearToken(); router.replace("/login"); return; }
      if (!response.ok) throw new Error("dashboard_unavailable");
      const next = await response.json() as DashboardHome;
      if (generation.current === ticket) setData(next);
    } catch {
      if (generation.current === ticket) { setData(null); setError(true); }
    } finally {
      if (generation.current === ticket) setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    let active = true;
    void refresh();
    void Promise.all([apiFetch("/api/me"), apiFetch("/api/me/capabilities")]).then(async ([meResponse, capsResponse]) => {
      const me = meResponse.ok ? await meResponse.json() as { full_name?: string } : null;
      const caps = capsResponse.ok ? await capsResponse.json() as string[] : [];
      if (!active) return;
      setName(me?.full_name?.trim().split(/\s+/)[0] || "");
      setCapabilities(Array.isArray(caps) ? caps : []);
    }).catch(() => { /* Each dashboard section still enforces server-side permissions. */ });
    return () => { active = false; generation.current += 1; };
  }, [refresh]);

  const now = data?.generated_at ?? new Date().toISOString();
  const hour = Number(new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", hour: "2-digit", hourCycle: "h23" }).format(new Date(now)));
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const appts = data?.appointments;
  const payments = data?.payments;
  const recall = data?.recalls;
  const current = appts?.last_7_days;
  const previous = appts?.previous_7_days;

  return <div className={styles.dashboard} data-testid="dashboard-root">
    <header className={styles.heading}>
      <div><h1>{greeting}{name ? `, ${name}` : ""}</h1><p>{calendarDate(data?.date ?? now, true)}</p></div>
      <div className={styles.actions}>
        {capabilities.includes("patients.write") && <Link className="btn btn-secondary" href="/patients/new"><Icon name="patients" />New patient</Link>}
        {capabilities.includes("appointments.write") && <Link className="btn btn-primary" href="/appointments?book=1"><Icon name="calendar" />New appointment</Link>}
        <button className={styles.refresh} type="button" onClick={() => void refresh()} disabled={loading} aria-label="Refresh dashboard" title="Refresh dashboard"><Icon name="history" size={18} /></button>
      </div>
    </header>
    {loading && !data && <div className={styles.loading} data-testid="dashboard-loading" role="status">Loading your practice overview…
      <div className={styles.skeletonGrid} aria-hidden="true"><div /><div /><div /></div>
    </div>}
    {error && <div className={styles.error} role="alert" data-testid="dashboard-error">
      <div><strong>The practice overview is unavailable.</strong><p>No figures are shown because they could not be refreshed.</p></div>
      <button className="btn btn-secondary" onClick={() => void refresh()}>Retry</button>
    </div>}
    {data && appts && payments && recall && <>
      <div className={styles.metrics}>
        <Metric name="today-appointments" label="Appointments today" icon="calendar" state={appts.availability} value={appts.today_count}
          description={appts.today_count === 0 ? "No appointments today" : "On today’s schedule"} />
        <Metric name="in-clinic" label="In clinic now" icon="clinical" state={appts.availability} value={appts.in_clinic_count}
          description={appts.in_clinic_count === 0 ? "No one checked in" : "Arrived or in treatment · clinic only"} />
        <Metric name="overdue-payments" label="Overdue payments" icon="wallet" state={payments.availability} value={payments.overdue_invoice_count}
          alert={(payments.overdue_invoice_count ?? 0) > 0} description={payments.overdue_balance_pence !== null
            ? <span data-testid="dashboard-overdue-amount">{currency(payments.overdue_balance_pence)}<span> · overdue invoices</span></span> : "Invoice balances"} />
      </div>
      <Panel title="Today" icon="history" testId="dashboard-today-schedule" state={appts.schedule_availability}
        link={appts.availability === "available" ? { href: `/appointments?date=${data.date}`, label: "Open schedule" } : undefined}>
        {appts.schedule_availability !== "available" ? <Empty icon="calendar" title="Access restricted" detail="You need appointment and patient access to view the schedule." />
          : appts.schedule.length === 0 ? <Empty icon="calendar" title="No appointments scheduled for today" />
          : <div className={styles.scheduleWrap}><table className={styles.schedule}>
            <caption className={styles.srOnly}>Today’s appointments</caption>
            <thead><tr><th>Time</th><th>Patient</th><th>Appointment</th><th>Clinician</th><th>Status</th></tr></thead>
            <tbody>{appts.schedule.map((item) => <tr key={item.id}>
              <td><span className={styles.time}>{clockTime(item.starts_at)}</span><span className={styles.secondary}>{clockTime(item.ends_at)}</span></td>
              <td><Link href={`/appointments?appointment=${item.id}&date=${data.date}`}>{item.patient_name || "Appointment"}</Link>{item.location_type === "visit" && <span className={styles.secondary}>Home visit</span>}</td>
              <td>{item.appointment_type || "—"}</td><td>{item.clinician || "Unassigned"}</td>
              <td><span className={styles.status} data-status={item.status}>{statusNames[item.status] || item.status}</span></td>
            </tr>)}</tbody>
          </table>{appts.schedule_has_more && <Link className={styles.more} href={`/appointments?date=${data.date}`}>View the full day →</Link>}</div>}
      </Panel>
      <div className={styles.columns}>
        <div className={styles.column}>
          <Panel title="Unconfirmed for tomorrow" icon="calendar" tone="warning" state={appts.unconfirmed_tomorrow.availability} testId="dashboard-card-tomorrow-unconfirmed">
            <Empty icon="calendar" title={unavailableLabel(appts.unconfirmed_tomorrow.availability)}
              detail={appts.unconfirmed_tomorrow.availability === "forbidden" ? "Your account cannot view appointment information." : "Appointment confirmation is not yet tracked in Dental PMS."} />
          </Panel>
          <Panel title="Overdue payments" icon="wallet" tone="danger" testId="dashboard-overdue-list" state={payments.items_availability}>
            {payments.items_availability !== "available" ? <Empty icon="wallet" title="Access restricted" detail="Patient and billing access is required to view overdue invoices." />
              : payments.items.length === 0 ? <Empty icon="wallet" title="No overdue invoices" />
              : <ul className={styles.list}>{payments.items.map((item) => {
                const daysOverdue = Math.max(0, Math.round((Date.parse(data.date) - Date.parse(item.due_date)) / 86400000));
                return <li key={item.invoice_id}><Link className={styles.invoiceRow} href={`/patients/${item.patient_id}?tab=financial`}>
                  <div><span className={styles.invoiceNumber}>{item.invoice_number}</span><strong>{item.patient_name}</strong><span className={styles.overdue}>{daysOverdue} {daysOverdue === 1 ? "day" : "days"} overdue</span></div>
                  <strong className={styles.amount}>{currency(item.balance_pence)}<span aria-hidden="true"> ›</span></strong>
                </Link></li>;
              })}</ul>}
            {payments.items_has_more && <p className={styles.footnote}>Showing the earliest due invoices. Totals above include all overdue invoices.</p>}
          </Panel>
          <Panel title="Recalls" icon="history" testId="dashboard-card-recalls" state={recall.availability}
            link={recall.availability === "available" ? { href: "/recalls", label: "Call list" } : undefined}>
            {recall.availability !== "available" ? <Empty icon="history" title="Access restricted" detail="Your account cannot view recalls." />
              : <div className={styles.recallGrid}>
                <div><strong>{recall.due_this_week}</strong><span>Due this week</span></div>
                <div><strong>{recall.overdue}</strong><span>Overdue</span></div>
                <div><strong>{recall.scheduled_this_month}</strong><span>Scheduled this month</span></div>
                <div><strong className={styles.unavailableSmall}>Not recorded yet</strong><span title="A reliable contacted-to-booked conversion is not yet recorded.">Conversion</span></div>
              </div>}
          </Panel>
        </div>
        <div className={styles.column}>
          <Panel title="Recent patients" icon="patients" testId="dashboard-card-recent-patients" state={data.patients.availability}
            link={data.patients.availability === "available" ? { href: "/patients", label: "View all" } : undefined}>
            {data.patients.availability !== "available" ? <Empty icon="patients" title="Access restricted" detail="Your account cannot view patient records." />
              : data.patients.recent.length === 0 ? <Empty icon="patients" title="No patients added yet" />
              : <><p className={styles.listSubtitle}>Recently added to the practice</p><ul className={styles.list}>{data.patients.recent.map((patient) => <li key={patient.id}>
                <Link className={styles.patientRow} href={`/patients/${patient.id}`}>
                  <span className={styles.avatar} aria-hidden="true">{patient.name.split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0]).join("")}</span>
                  <span className={styles.patientIdentity}><strong>{patient.name}</strong>{patient.phone && <small>{patient.phone}</small>}</span><span className={styles.patientDate}>{calendarDate(patient.created_at)}<span aria-hidden="true"> ›</span></span>
                </Link>
              </li>)}</ul></>}
          </Panel>
          <Panel title="Week at a glance" icon="reports" testId="dashboard-card-week-comparison"
            state={appts.availability === "available" || payments.availability === "available" ? "available" : "forbidden"}>
            <p className={styles.listSubtitle}>Last 7 days vs previous 7 · includes today</p>
            <div className={styles.weekGrid}>
              <div data-testid="dashboard-week-appointments"><span>Appointments</span><strong>{current ? current.appointments : "Restricted"}</strong>
                <Change current={current?.appointments ?? null} previous={previous?.appointments ?? null} /></div>
              <div data-testid="dashboard-week-completed"><span>Completed</span><strong>{current ? <>{current.completed}<small>{current.completion_rate === null ? "No appointments" : `(${Math.round(current.completion_rate)}%)`}</small></> : "Restricted"}</strong>
                <Change current={current?.completed ?? null} previous={previous?.completed ?? null} /></div>
              <div data-testid="dashboard-week-invoiced"><span>Invoiced</span><strong>{payments.last_7_days_invoiced_pence !== null ? currency(payments.last_7_days_invoiced_pence) : "Restricted"}</strong>
                <Change current={payments.last_7_days_invoiced_pence} previous={payments.previous_7_days_invoiced_pence} /></div>
            </div>
          </Panel>
        </div>
      </div>
      <footer className={styles.footer}>
        <span role="status">{loading ? "Refreshing overview…" : `Updated ${clockTime(data.generated_at)} · UK time`}</span>
        <details><summary>About these figures</summary><ul>{Object.entries(data.definitions).map(([key, value]) => <li key={key}>{value}</li>)}</ul></details>
      </footer>
    </>}
  </div>;
}
