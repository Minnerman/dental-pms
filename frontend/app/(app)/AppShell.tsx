"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type CSSProperties, type PointerEvent } from "react";
import { apiFetch, clearToken, getToken } from "@/lib/auth";
import Icon, { type IconName } from "@/components/ui/Icon";
import ThemeToggle from "@/components/ui/ThemeToggle";
import styles from "./AppShell.module.css";

type Me = { id: number; email: string; full_name: string; role: string; is_active: boolean; must_change_password: boolean };
type PatientSearchResult = { id: number; first_name: string; last_name: string; date_of_birth?: string | null; phone?: string | null };
type ShellTab = { href: string; label: string; icon: IconName };
const baseTabs: ShellTab[] = [
  { href: "/", label: "Home", icon: "home" },
  { href: "/patients", label: "Patients", icon: "patients" },
  { href: "/appointments", label: "Appointments", icon: "calendar" },
  { href: "/r4-calendar", label: "R4 Calendar", icon: "history" },
  { href: "/recalls", label: "Recalls", icon: "history" },
  { href: "/cashup", label: "Cash-up", icon: "wallet" },
  { href: "/reports", label: "Reports", icon: "reports" },
  { href: "/notes", label: "Notes", icon: "notes" },
];
const sidebarStorageKey = "dental_pms_sidebar_collapsed";
const sidebarWidthStorageKey = "dental_pms_sidebar_width";
const minimumSidebarWidth = 200;
const maximumSidebarWidth = 320;
const defaultSidebarWidth = 232;

function boundedSidebarWidth(value: number) {
  return Math.max(minimumSidebarWidth, Math.min(maximumSidebarWidth, Math.round(value)));
}

function getPatientSearchUrl(query: string) {
  const params = new URLSearchParams({ limit: "20" });
  params.set(query.includes(" ") ? "query" : "q", query);
  return `${query.includes(" ") ? "/api/patients" : "/api/patients/search"}?${params.toString()}`;
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const buildSha = (process.env.NEXT_PUBLIC_BUILD_SHA || "dev").slice(0, 7);
  const [checking, setChecking] = useState(true);
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessionAttempt, setSessionAttempt] = useState(0);
  const [collapsed, setCollapsed] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(defaultSidebarWidth);
  const [resizing, setResizing] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<PatientSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [lastQuery, setLastQuery] = useState("");
  const sidebarRef = useRef<HTMLElement>(null);
  const mainRef = useRef<HTMLElement>(null);
  const mobileHeaderRef = useRef<HTMLElement>(null);
  const mobileOpenerRef = useRef<HTMLButtonElement>(null);
  const sidebarToggleRef = useRef<HTMLButtonElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const focusSearchAfterExpand = useRef(false);
  const resizeRef = useRef<{ pointerId: number; startX: number; startWidth: number; element: HTMLDivElement } | null>(null);
  const isCollapsed = collapsed && !isMobile;

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(sidebarStorageKey) === "true");
      const savedWidth = localStorage.getItem(sidebarWidthStorageKey);
      if (savedWidth !== null && savedWidth.trim() && Number.isFinite(Number(savedWidth))) {
        setSidebarWidth(boundedSidebarWidth(Number(savedWidth)));
      }
    } catch { /* Layout works without persistence. */ }
    const media = window.matchMedia("(max-width: 760px)");
    const update = () => { setIsMobile(media.matches); if (!media.matches) setDrawerOpen(false); };
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (!isCollapsed && focusSearchAfterExpand.current) {
      searchRef.current?.focus();
      focusSearchAfterExpand.current = false;
    }
  }, [isCollapsed]);

  useEffect(() => {
    let cancelled = false;
    if (!getToken()) { router.replace("/login"); return; }
    setChecking(true);
    setMe(null);
    setError(null);
    (async () => {
      try {
        const res = await apiFetch("/api/me");
        if (cancelled) return;
        if (res.status === 401 || res.status === 403) { clearToken(); router.replace("/login"); return; }
        if (!res.ok) { setError("We could not verify your session. Please retry or sign in again."); return; }
        const data = (await res.json()) as Me;
        if (cancelled) return;
        if (!data.is_active) { clearToken(); router.replace("/login"); return; }
        if (data.must_change_password) { router.replace("/change-password"); return; }
        setMe(data);
      } catch {
        if (!cancelled) setError("We could not verify your session. Please retry or sign in again.");
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();
    return () => { cancelled = true; };
  }, [router, sessionAttempt]);

  const isUsersRoute = pathname?.startsWith("/users");
  const isAdmin = me ? ["superadmin", "senior_admin", "dentist", "nurse", "receptionist", "reception"].includes(me.role) : false;
  const isSuperadmin = me?.role === "superadmin";
  const moreTabs: ShellTab[] = [
    ...(isSuperadmin ? [
      { href: "/treatments", label: "Treatments", icon: "treatment" as const },
      { href: "/templates", label: "Templates", icon: "template" as const },
      { href: "/admin/legacy/unmapped-appointments", label: "Legacy Queue", icon: "history" as const },
      { href: "/admin/r4/treatment-plans", label: "R4 Plans", icon: "treatment" as const },
      { href: "/admin/r4/patient-mappings", label: "R4 Mappings", icon: "patients" as const },
      { href: "/admin/r4/manual-mappings", label: "R4 Manual Mappings", icon: "settings" as const },
      { href: "/settings/profile", label: "Practice profile", icon: "settings" as const },
      { href: "/settings/schedule", label: "Schedule", icon: "calendar" as const },
    ] : []),
    ...(isAdmin ? [{ href: "/users", label: "Users", icon: "users" as const }] : []),
  ];
  const isActive = (href: string) => href === "/" ? pathname === "/" : pathname?.startsWith(href);

  useEffect(() => {
    if (!checking && me && isUsersRoute && !isAdmin) router.replace("/");
  }, [checking, isUsersRoute, isAdmin, me, router]);

  useEffect(() => { setDrawerOpen(false); setSearchOpen(false); }, [pathname]);

  useEffect(() => {
    sidebarRef.current?.toggleAttribute("inert", isMobile && !drawerOpen);
  }, [isMobile, drawerOpen, me]);

  useEffect(() => () => {
    const drag = resizeRef.current;
    resizeRef.current = null;
    if (drag?.element.hasPointerCapture(drag.pointerId)) drag.element.releasePointerCapture(drag.pointerId);
  }, []);

  useEffect(() => {
    if (!isMobile || !drawerOpen || !me) return;
    const sidebar = sidebarRef.current;
    const main = mainRef.current;
    const header = mobileHeaderRef.current;
    const opener = mobileOpenerRef.current;
    const previousOverflow = document.body.style.overflow;
    main?.setAttribute("inert", "");
    header?.setAttribute("inert", "");
    document.body.style.overflow = "hidden";
    // Opening removes inert and changes CSS visibility in the same commit.
    // Wait for the browser's next frame before moving focus into the drawer.
    const focusFrame = window.requestAnimationFrame(() => {
      if (sidebar?.dataset.open === "true" && !sidebar.hasAttribute("inert")) {
        sidebarToggleRef.current?.focus({ preventScroll: true });
      }
    });
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); setDrawerOpen(false); }
      if (event.key !== "Tab" || !sidebar) return;
      const controls = Array.from(sidebar.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), [tabindex="0"]'
      )).filter((element) => element.offsetParent !== null);
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      main?.removeAttribute("inert");
      header?.removeAttribute("inert");
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
      opener?.focus();
    };
  }, [isMobile, drawerOpen, me]);

  useEffect(() => {
    const trimmed = searchQuery.trim();
    if (!me || trimmed.length < 2) { setSearchResults([]); setActiveIndex(-1); setSearching(false); return; }
    let cancelled = false;
    const controller = new AbortController();
    const handle = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await apiFetch(getPatientSearchUrl(trimmed), { signal: controller.signal });
        if (cancelled) return;
        if (res.status === 401) { clearToken(); router.replace("/login"); return; }
        const data = res.ok ? await res.json() as PatientSearchResult[] : [];
        if (!cancelled) { setSearchResults(data); setActiveIndex(data.length ? 0 : -1); }
      } catch {
        if (!cancelled) { setSearchResults([]); setActiveIndex(-1); }
      } finally {
        if (!cancelled) { setSearching(false); setLastQuery(trimmed); }
      }
    }, 250);
    return () => { cancelled = true; clearTimeout(handle); controller.abort(); };
  }, [searchQuery, router, me]);

  function toggleCollapsed() {
    if (isMobile) { setDrawerOpen(false); return; }
    const next = !collapsed;
    setCollapsed(next);
    setSearchOpen(false);
    try { localStorage.setItem(sidebarStorageKey, String(next)); } catch { /* Optional preference. */ }
  }
  function rememberWidth(width: number) {
    const next = boundedSidebarWidth(width);
    setSidebarWidth(next);
    try { localStorage.setItem(sidebarWidthStorageKey, String(next)); } catch { /* Optional layout preference. */ }
  }
  function finishResize(event?: PointerEvent<HTMLDivElement>, cancel = false) {
    const drag = resizeRef.current;
    if (!drag || (event && event.pointerId !== drag.pointerId)) return;
    resizeRef.current = null;
    setResizing(false);
    if (cancel) setSidebarWidth(drag.startWidth);
    else if (event) rememberWidth(drag.startWidth + event.clientX - drag.startX);
    if (drag.element.hasPointerCapture(drag.pointerId)) drag.element.releasePointerCapture(drag.pointerId);
  }
  function expandSearch() {
    focusSearchAfterExpand.current = true;
    setCollapsed(false);
    try { localStorage.setItem(sidebarStorageKey, "false"); } catch { /* Optional preference. */ }
  }
  function openPatient(patient: PatientSearchResult) {
    setSearchQuery(""); setSearchResults([]); setSearchOpen(false); setActiveIndex(-1); setDrawerOpen(false);
    router.push(`/patients/${patient.id}`);
  }
  function signOut() {
    clearToken(); setMe(null); setSearchResults([]); router.replace("/login");
  }

  if (checking) return <main className="page-center"><div className="badge" role="status">Checking session…</div></main>;
  if (!me || error) return (
    <main className="page-center"><section className="card app-session-message">
      <span className="app-mark" aria-hidden="true"><Icon name="treatment" size={22} /></span>
      <h1>Session unavailable</h1><p role="alert">{error || "Please sign in to continue."}</p>
      <div className="header-actions">
        <button className="btn btn-primary" onClick={() => setSessionAttempt((value) => value + 1)}>Retry</button>
        <button className="btn btn-secondary" onClick={signOut}>Sign in again</button>
      </div>
    </section></main>
  );

  const showDropdown = searchOpen && searchQuery.trim().length >= 2;
  const showNoResults = !searching && showDropdown && searchQuery.trim() === lastQuery && searchResults.length === 0;
  const userName = me.full_name || me.email || "Signed in";
  const initials = (me.full_name || me.email).split(/\s+/).slice(0, 2).map((name) => name[0]).join("").toUpperCase();

  return (
    <div className={`app-shell ${styles.shell}`} data-sidebar-collapsed={isCollapsed ? "true" : "false"}
      data-sidebar-resizing={resizing ? "true" : "false"}
      style={{ "--app-sidebar-expanded-width": `${sidebarWidth}px` } as CSSProperties}>
      <a className="app-skip-link" href="#main-content">Skip to main content</a>
      <header className="app-mobile-header" ref={mobileHeaderRef}>
        <button className="app-icon-button" ref={mobileOpenerRef} data-testid="app-mobile-menu-toggle"
          aria-label="Open navigation" aria-controls="app-sidebar" aria-expanded={drawerOpen}
          onClick={() => setDrawerOpen(true)}><Icon name="menu" size={22} /></button>
        <Link href="/" className="app-mobile-brand"><Icon name="treatment" size={22} />Dental PMS</Link>
      </header>
      {isMobile && drawerOpen && <button className="app-sidebar-backdrop" data-testid="app-sidebar-backdrop"
        aria-label="Close navigation" tabIndex={-1} onClick={() => setDrawerOpen(false)} />}
      <aside id="app-sidebar" className="app-sidebar" ref={sidebarRef} data-testid="app-sidebar"
        data-collapsed={isCollapsed ? "true" : "false"} data-open={drawerOpen ? "true" : "false"}
        role={isMobile && drawerOpen ? "dialog" : undefined} aria-modal={isMobile && drawerOpen ? true : undefined}
        aria-hidden={isMobile && !drawerOpen ? true : undefined} aria-label="Practice navigation">
        <div className="app-sidebar-heading">
          <Link href="/" className="app-title" aria-label="Dental PMS home" onClick={() => setDrawerOpen(false)}>
            <span className="app-mark"><Icon name="treatment" size={22} /></span><span className="app-sidebar-label">Dental PMS</span>
          </Link>
          <button className="app-icon-button app-sidebar-toggle" ref={sidebarToggleRef} data-testid="app-sidebar-toggle"
            aria-controls="app-sidebar" aria-expanded={isMobile ? drawerOpen : !isCollapsed}
            aria-label={isMobile ? "Close navigation" : isCollapsed ? "Expand navigation" : "Collapse navigation"}
            title={isMobile ? "Close navigation" : isCollapsed ? "Expand navigation" : "Collapse navigation"}
            onClick={toggleCollapsed}><Icon name="menu" size={18} /></button>
        </div>
        <div className="app-sidebar-scroll">
          {isCollapsed ? <button className="app-sidebar-link app-sidebar-search-toggle" aria-label="Search patients" title="Search patients" onClick={expandSearch}><Icon name="search" size={19} /></button> : (
            <div className="app-search" onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setSearchOpen(false); }}>
              <Icon name="search" className="app-search-icon" />
              <input className="input app-search-input" ref={searchRef} placeholder="Search patients..." aria-label="Search patients"
                role="combobox" aria-autocomplete="list" aria-controls="app-patient-search-results" aria-expanded={showDropdown}
                aria-activedescendant={showDropdown && activeIndex >= 0 && searchResults[activeIndex] ? `app-patient-result-${searchResults[activeIndex].id}` : undefined}
                value={searchQuery} onFocus={() => setSearchOpen(true)}
                onChange={(event) => {
                  setSearchQuery(event.target.value); setSearchOpen(true);
                  // Old results must not remain keyboard-selectable while a
                  // different patient's query is waiting for its response.
                  setSearchResults([]); setActiveIndex(-1);
                  setSearching(event.target.value.trim().length >= 2);
                }}
                onKeyDown={(event) => {
                  if (!showDropdown) return;
                  if (event.key === "ArrowDown") { event.preventDefault(); setActiveIndex((prev) => Math.min(prev + 1, Math.max(searchResults.length - 1, 0))); }
                  if (event.key === "ArrowUp") { event.preventDefault(); setActiveIndex((prev) => Math.max(prev - 1, 0)); }
                  if (event.key === "Enter") { event.preventDefault(); const next = searchResults[activeIndex] || searchResults[0]; if (next) openPatient(next); }
                  if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); setSearchOpen(false); }
                }} />
              {showDropdown && <div className="app-search-results" id="app-patient-search-results" role="listbox" aria-label="Patient search results">
                {searching ? <div className="app-search-status" role="status">Searching…</div> : showNoResults ? <div className="app-search-status">No results</div> : searchResults.map((patient, index) => (
                  <button key={patient.id} id={`app-patient-result-${patient.id}`} role="option" aria-selected={index === activeIndex}
                    className={`app-search-result${index === activeIndex ? " active" : ""}`} tabIndex={-1} onClick={() => openPatient(patient)}>
                    <span>{patient.first_name} {patient.last_name}</span><small>{patient.date_of_birth || "DOB —"} · {patient.phone || "No phone"}</small>
                  </button>
                ))}
              </div>}
            </div>
          )}
          <span className="app-sidebar-section-label">WORKSPACE</span>
          <nav className="app-primary-nav" aria-label="Main navigation">
            {baseTabs.map((tab) => <Link key={tab.href} href={tab.href} className={`app-sidebar-link${isActive(tab.href) ? " active" : ""}`}
              aria-current={isActive(tab.href) ? "page" : undefined} aria-label={tab.label} title={isCollapsed ? tab.label : undefined} onClick={() => setDrawerOpen(false)}>
              <Icon name={tab.icon} size={19} /><span className="app-sidebar-label">{tab.label}</span>
            </Link>)}
          </nav>
          {moreTabs.length > 0 && <div className="app-sidebar-more">
            <button className={`app-sidebar-link${moreTabs.some((tab) => isActive(tab.href)) ? " active" : ""}`} aria-label="More"
              aria-expanded={!isCollapsed && moreOpen} aria-controls="app-more-links" title={isCollapsed ? "More" : undefined}
              onClick={() => {
                if (isCollapsed) {
                  setCollapsed(false); setMoreOpen(true);
                  try { localStorage.setItem(sidebarStorageKey, "false"); } catch { /* Optional layout preference. */ }
                } else setMoreOpen(!moreOpen);
              }}>
              <Icon name="settings" size={19} /><span className="app-sidebar-label">More</span><span className="app-sidebar-chevron app-sidebar-label" aria-hidden="true">{moreOpen ? "−" : "+"}</span>
            </button>
            {!isCollapsed && moreOpen && <nav id="app-more-links" className="app-more-links" aria-label="Administration">
              {moreTabs.map((tab) => <Link key={tab.href} href={tab.href} className={`app-sidebar-link${isActive(tab.href) ? " active" : ""}`}
                aria-current={isActive(tab.href) ? "page" : undefined} onClick={() => setDrawerOpen(false)}>
                <Icon name={tab.icon} size={16} /><span>{tab.label}</span>
              </Link>)}
            </nav>}
          </div>}
        </div>
        <div className="app-sidebar-footer">
          <div className="app-user" title={`${userName} · ${me.role}`}>
            <span className="app-user-avatar" aria-hidden="true">{initials}</span>
            <div className="app-sidebar-label app-user-text"><span className="app-user-name">{userName}</span><span className="app-user-role">{me.role.replace(/_/g, " ")}</span></div>
          </div>
          <ThemeToggle className="app-sidebar-link" compact={isCollapsed} />
          <button className="app-sidebar-link" onClick={signOut} aria-label="Sign out" title={isCollapsed ? "Sign out" : undefined}>
            <Icon name="logout" size={19} /><span className="app-sidebar-label">Sign out</span>
          </button>
          <span className="app-sidebar-build app-sidebar-label">Dental PMS · {buildSha}</span>
        </div>
        {!isMobile && !isCollapsed && <div className="app-sidebar-resize" data-testid="app-sidebar-resize"
          role="separator" tabIndex={0} aria-label="Navigation width" aria-orientation="vertical"
          aria-controls="app-sidebar" aria-valuemin={minimumSidebarWidth} aria-valuemax={maximumSidebarWidth}
          aria-valuenow={sidebarWidth} aria-valuetext={`${sidebarWidth} pixels`}
          title="Drag to resize. Arrow keys adjust width; Home/End set minimum/maximum."
          onPointerDown={(event) => {
            if (event.button !== 0 || !event.isPrimary) return;
            event.preventDefault(); event.stopPropagation(); event.currentTarget.focus();
            resizeRef.current = { pointerId: event.pointerId, startX: event.clientX, startWidth: sidebarWidth, element: event.currentTarget };
            event.currentTarget.setPointerCapture(event.pointerId); setResizing(true);
          }}
          onPointerMove={(event) => {
            const drag = resizeRef.current;
            if (drag && drag.pointerId === event.pointerId) setSidebarWidth(boundedSidebarWidth(drag.startWidth + event.clientX - drag.startX));
          }}
          onPointerUp={(event) => finishResize(event)}
          onPointerCancel={(event) => finishResize(event, true)}
          onLostPointerCapture={() => finishResize(undefined, true)}
          onKeyDown={(event) => {
            if (event.key === "Escape" && resizeRef.current) {
              event.preventDefault(); event.stopPropagation(); finishResize(undefined, true); return;
            }
            if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
            event.preventDefault(); event.stopPropagation();
            finishResize(undefined, true);
            const step = event.shiftKey ? 40 : 10;
            rememberWidth(event.key === "Home" ? minimumSidebarWidth : event.key === "End" ? maximumSidebarWidth :
              sidebarWidth + (event.key === "ArrowRight" ? step : -step));
          }} />}
      </aside>
      <main id="main-content" className="app-main" data-testid="app-main" ref={mainRef} tabIndex={-1}>
        {!isAdmin && isUsersRoute ? <section className="card"><h3>Not authorized</h3><p>You do not have permission to access user management.</p></section> : children}
      </main>
    </div>
  );
}
