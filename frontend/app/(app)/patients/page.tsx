"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import Icon from "@/components/ui/Icon";
import styles from "./PatientsDirectory.module.css";

type Category = "CLINIC_PRIVATE" | "DOMICILIARY_PRIVATE" | "DENPLAN";
type Sort = "last_name" | "first_name" | "last_visit" | "joined" | "recently_edited";
type Filters = { query: string; email: string; dob: string; category: Category | ""; status: "active" | "archived" | "all"; sort: Sort; direction: "asc" | "desc"; withDebt: boolean; offset: number };
type Patient = {
  id: number; first_name: string; last_name: string; phone: string | null;
  date_of_birth: string | null; patient_category: Category; created_at: string;
  updated_at: string; deleted_at: string | null; balance_pence: number | null; last_visit_at: string | null;
};
type Directory = {
  items: Patient[]; total: number; limit: number; offset: number;
  metadata: { finance: "available" | "forbidden"; last_visit: "available" | "forbidden"; do_not_contact: "unavailable" };
  definitions: Record<string, string>;
};
const initialFilters: Filters = { query: "", email: "", dob: "", category: "", status: "active", sort: "last_name", direction: "asc", withDebt: false, offset: 0 };
const categoryLabels: Record<Category, string> = { CLINIC_PRIVATE: "Clinic (Private)", DOMICILIARY_PRIVATE: "Home visit (Private)", DENPLAN: "Denplan" };
const money = (pence: number) => new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(Math.abs(pence) / 100);
const dateLabel = (value: string) => new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", day: "numeric", month: "short", year: "numeric" }).format(new Date(value.length === 10 ? `${value}T12:00:00Z` : value));

export default function PatientsPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const [data, setData] = useState<Directory | null>(null);
  const [capabilities, setCapabilities] = useState<string[] | null>(null);
  const [capabilityError, setCapabilityError] = useState(false);
  const [permissionAttempt, setPermissionAttempt] = useState(0);
  const [requestAttempt, setRequestAttempt] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const filtersRef = useRef<HTMLDivElement>(null);
  const filterButtonRef = useRef<HTMLButtonElement>(null);
  const firstRowRef = useRef<HTMLAnchorElement>(null);
  const emptyRef = useRef<HTMLDivElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const pageFocusPending = useRef(false);
  const canRead = capabilities?.includes("patients.view") ?? false;
  const canWrite = capabilities?.includes("patients.write") ?? false;
  const canFinance = capabilities?.includes("billing.view") ?? false;
  const canVisits = capabilities?.includes("appointments.view") ?? false;

  useEffect(() => {
    const controller = new AbortController();
    setCapabilities(null);
    setCapabilityError(false);
    void apiFetch("/api/me/capabilities", { signal: controller.signal, cache: "no-store" }).then(async (response) => {
      if (response.status === 401) { clearToken(); router.replace("/login"); return; }
      if (!response.ok) throw new Error();
      const value: unknown = await response.json();
      if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) throw new Error();
      if (!controller.signal.aborted) setCapabilities(value as string[]);
    }).catch(() => {
      if (!controller.signal.aborted) { setCapabilityError(true); setCapabilities([]); }
    });
    return () => controller.abort();
  }, [router, permissionAttempt]);

  useEffect(() => {
    const timer = window.setTimeout(() => setFilters((previous) => previous.query === query.trim() ? previous : { ...previous, query: query.trim(), offset: 0 }), 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    if (!canRead) { setData(null); setLoading(capabilities === null); return; }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setData(null);
    const params = new URLSearchParams({ status: filters.status, sort: filters.sort, direction: filters.direction, limit: "50", offset: String(filters.offset) });
    if (filters.query) params.set("query", filters.query);
    if (filters.email.trim()) params.set("email", filters.email.trim());
    if (filters.dob) params.set("dob", filters.dob);
    if (filters.category) params.set("category", filters.category);
    if (filters.withDebt) params.set("with_debt", "true");
    void apiFetch(`/api/patients/directory?${params}`, { signal: controller.signal, cache: "no-store" }).then(async (response) => {
      if (response.status === 401) { clearToken(); router.replace("/login"); return; }
      if (response.status === 403) throw new Error("Your account cannot use the selected patient filters.");
      if (!response.ok) throw new Error("The patient list could not be loaded. Please retry.");
      const value = await response.json() as Directory;
      if (controller.signal.aborted) return;
      if (value.total > 0 && filters.offset >= value.total) {
        setFilters((previous) => ({ ...previous, offset: Math.floor((value.total - 1) / value.limit) * value.limit }));
      } else setData(value);
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "The patient list could not be loaded. Please retry.");
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [canRead, capabilities, filters, requestAttempt, router]);

  useEffect(() => { if (canRead) searchRef.current?.focus(); }, [canRead]);
  useEffect(() => {
    if (!pageFocusPending.current || loading || (!data && !error)) return;
    pageFocusPending.current = false;
    (error ? errorRef.current : firstRowRef.current ?? emptyRef.current)?.focus();
  }, [data, loading, error]);
  useEffect(() => {
    if (!filtersOpen) return;
    const dismiss = (event: PointerEvent) => { if (!filtersRef.current?.contains(event.target as Node)) setFiltersOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { setFiltersOpen(false); filterButtonRef.current?.focus(); } };
    document.addEventListener("pointerdown", dismiss);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", dismiss); document.removeEventListener("keydown", escape); };
  }, [filtersOpen]);

  function updateFilter(change: Partial<Filters>) { setFilters((previous) => ({ ...previous, ...change, offset: 0 })); }
  function resetFilters() { setQuery(""); setFilters(initialFilters); }
  const activeFilters = Number(filters.status !== "active") + Number(Boolean(filters.category)) + Number(Boolean(filters.email)) + Number(Boolean(filters.dob));
  const hasFilters = activeFilters > 0 || filters.withDebt || Boolean(query);

  return <div className={styles.directory} data-testid="patients-directory">
    <header className={styles.header}><h1>Patients</h1>{canWrite && <Link href="/patients/new" className={`btn btn-primary ${styles.newPatient}`}><span aria-hidden="true">＋</span>New patient</Link>}</header>
    {canRead && <>
      <div className={styles.toolbar}>
        <form className={styles.search} role="search" onSubmit={(event) => { event.preventDefault(); updateFilter({ query: query.trim() }); setRequestAttempt((value) => value + 1); }}>
          <Icon name="search" size={18} /><input ref={searchRef} placeholder="Search name, email, phone" aria-label="Search name, email, phone" maxLength={320} value={query} onChange={(event) => setQuery(event.target.value)} />
          {query && <button type="button" aria-label="Clear search" title="Clear search" onClick={() => { setQuery(""); searchRef.current?.focus(); }}>×</button>}
          <button type="submit" aria-label="Search" title="Search"><span aria-hidden="true">↵</span></button>
        </form>
        <div className={styles.filterAnchor} ref={filtersRef}>
          <button className={styles.control} type="button" ref={filterButtonRef} onClick={() => setFiltersOpen((value) => !value)} aria-expanded={filtersOpen} aria-controls="patient-directory-filters"><Icon name="settings" />Filters{activeFilters > 0 && <span className={styles.filterCount}>{activeFilters}</span>}<span aria-hidden="true">⌄</span></button>
          {filtersOpen && <div id="patient-directory-filters" className={styles.filterPopover} role="group" aria-label="Patient filters">
            <label>Patient status<select aria-label="Patient status" value={filters.status} onChange={(event) => updateFilter({ status: event.target.value as Filters["status"] })}><option value="active">Active</option><option value="archived">Archived</option><option value="all">Active and archived</option></select></label>
            <label>Category<select value={filters.category} onChange={(event) => updateFilter({ category: event.target.value as Filters["category"] })}><option value="">All categories</option>{Object.entries(categoryLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label>Date of birth<input type="date" value={filters.dob} onChange={(event) => updateFilter({ dob: event.target.value })} /></label>
            <label>Email<input type="email" maxLength={320} placeholder="Filter by email" value={filters.email} onChange={(event) => updateFilter({ email: event.target.value })} /></label>
            <div className={styles.filterActions}><button type="button" onClick={resetFilters}>Reset filters</button><button type="button" onClick={() => { setFiltersOpen(false); filterButtonRef.current?.focus(); }}>Done</button></div>
          </div>}
        </div>
        <button type="button" className={styles.control} disabled title="Contact preferences are not recorded yet." aria-describedby="contact-filter-help"><Icon name="phone" />Do not contact</button>
        <button type="button" className={styles.control} disabled={!canFinance} aria-pressed={filters.withDebt} title={canFinance ? "Show patients with a positive ledger balance" : "Billing access required"} onClick={() => updateFilter({ withDebt: !filters.withDebt })}><Icon name="wallet" />With debt</button>
        <div className={styles.sortControls}>
          <label className={styles.srOnly} htmlFor="patient-directory-sort">Sort patients</label>
          <select id="patient-directory-sort" className={styles.control} value={filters.sort} onChange={(event) => { const sort = event.target.value as Sort; updateFilter({ sort, direction: sort === "last_name" || sort === "first_name" ? "asc" : "desc" }); }}>
            <option value="last_name">Last name</option><option value="first_name">First name</option><option value="last_visit" disabled={!canVisits}>Last visit{!canVisits ? " (restricted)" : ""}</option><option value="joined">Joined</option><option value="recently_edited">Recently edited</option>
          </select>
          <button type="button" className={styles.direction} aria-label={filters.direction === "asc" ? "Sort descending" : "Sort ascending"} title={filters.direction === "asc" ? "Ascending order — switch to descending" : "Descending order — switch to ascending"} onClick={() => updateFilter({ direction: filters.direction === "asc" ? "desc" : "asc" })}>{filters.direction === "asc" ? "↑" : "↓"}</button>
        </div>
      </div>
      <div className={styles.filterHint}><span id="contact-filter-help">Contact preferences are not recorded yet.</span>{hasFilters && <button type="button" onClick={resetFilters}>Clear filters</button>}</div>
    </>}
    {capabilityError ? <div role="alert" className={styles.message} data-testid="patients-directory-error"><strong>Patient permissions could not be verified.</strong><button className="btn btn-secondary" onClick={() => setPermissionAttempt((value) => value + 1)}>Retry</button></div>
      : capabilities !== null && !canRead ? <div role="alert" className={styles.message} data-testid="patients-directory-error">You do not have permission to view patients.</div>
      : loading ? <div className={styles.loading} role="status">Loading patients…<div aria-hidden="true" className={styles.skeleton}><div /><div /><div /><div /><div /></div></div>
      : error ? <div ref={errorRef} tabIndex={-1} role="alert" className={styles.message} data-testid="patients-directory-error"><strong>{error}</strong><button className="btn btn-secondary" onClick={() => setRequestAttempt((value) => value + 1)}>Retry</button></div>
      : data && <>
        {data.items.length === 0 ? <div ref={emptyRef} tabIndex={-1} className={styles.empty} data-testid="patients-directory-empty"><Icon name="patients" size={32} /><h2>No patients found</h2><p>{hasFilters ? "Try another search or clear your filters." : filters.status === "archived" ? "There are no archived patient records." : "New patient records will appear here."}</p>{hasFilters && <button className="btn btn-secondary" onClick={resetFilters}>Reset filters</button>}</div>
          : <ul className={styles.list} aria-label="Patient records" data-testid="patients-directory-list">{data.items.map((patient, index) => {
            const balance = data.metadata.finance === "available" ? patient.balance_pence : null;
            const visit = data.metadata.last_visit === "available";
            return <li key={patient.id} data-testid={`patient-directory-row-${patient.id}`}><Link ref={index === 0 ? firstRowRef : undefined} className={styles.row} href={`/patients/${patient.id}`} aria-label={`${patient.first_name} ${patient.last_name}`} aria-describedby={`directory-identity-${patient.id}`}>
              <span className={styles.avatar} aria-hidden="true">{patient.first_name[0]}{patient.last_name[0]}</span>
              <span className={styles.identity}><strong>{patient.last_name}, {patient.first_name}</strong><span>{patient.phone || "No phone recorded"}</span><span className={styles.compactIdentity}>{patient.date_of_birth ? `DOB ${dateLabel(patient.date_of_birth)}` : `Patient #${patient.id}`}</span><span className={styles.srOnly} id={`directory-identity-${patient.id}`}>Patient #{patient.id}. {patient.date_of_birth ? `Date of birth ${dateLabel(patient.date_of_birth)}.` : "Date of birth not recorded."} {patient.phone ? `Phone ${patient.phone}.` : "No phone recorded."}</span></span>
              <span className={styles.demographics}>{patient.date_of_birth && <span>DOB {dateLabel(patient.date_of_birth)}</span>}<span>{categoryLabels[patient.patient_category]}</span></span>
              <span className={styles.rowDetails}>
                {balance !== null && balance !== 0 && <span className={styles.balance} data-kind={balance > 0 ? "debt" : "credit"} title="Patient ledger balance"><Icon name="wallet" size={15} />{balance > 0 ? "Due" : "Credit"} {money(balance)}</span>}
                {visit && <span className={styles.lastVisit}>{patient.last_visit_at ? `Last visit ${dateLabel(patient.last_visit_at)}` : "No recorded visit"}</span>}
              </span>
              <span className={styles.status} data-archived={Boolean(patient.deleted_at)}>{patient.deleted_at ? "Archived" : "Active"}</span><span className={styles.chevron} aria-hidden="true">›</span>
            </Link></li>;
          })}</ul>}
        <footer className={styles.footer}>
          <span role="status">{data.items.length ? `${data.offset + 1}–${data.offset + data.items.length} of ${data.total}` : "0"} {data.total === 1 ? "patient" : "patients"}</span>
          <div className={styles.pagination}><button type="button" disabled={filters.offset === 0} aria-label="Previous page" onClick={() => { pageFocusPending.current = true; setFilters((previous) => ({ ...previous, offset: Math.max(0, previous.offset - data.limit) })); }}>← Previous</button><button type="button" disabled={data.offset + data.limit >= data.total} aria-label="Next page" onClick={() => { pageFocusPending.current = true; setFilters((previous) => ({ ...previous, offset: previous.offset + data.limit })); }}>Next →</button></div>
        </footer>
        <details className={styles.about}><summary>About this list</summary><ul>{Object.entries(data.definitions).map(([key, value]) => <li key={key}>{value}</li>)}{data.metadata.finance !== "available" && <li>Balances require billing access.</li>}{data.metadata.last_visit !== "available" && <li>Last visits require appointment access.</li>}</ul></details>
      </>}
  </div>;
}
