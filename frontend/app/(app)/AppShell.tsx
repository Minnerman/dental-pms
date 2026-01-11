"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch, clearToken, getToken } from "@/lib/auth";

type Me = {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  must_change_password: boolean;
};

type PatientSearchResult = {
  id: number;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  phone?: string | null;
};

type PatientTab = {
  id: number;
  label: string;
};

const baseTabs = [
  { href: "/", label: "Home" },
  { href: "/patients", label: "Patients" },
  { href: "/appointments", label: "Appointments" },
  { href: "/recalls", label: "Recalls" },
  { href: "/cashup", label: "Cash-up" },
  { href: "/reports", label: "Reports" },
  { href: "/notes", label: "Notes" },
];

const patientTabsStorageKey = "dental_pms_patient_tabs";
const activePatientTabStorageKey = "dental_pms_active_patient_tab";

function formatPatientTabLabel(firstName: string, lastName: string) {
  const safeLast = lastName.trim().toUpperCase();
  const safeFirst = firstName.trim();
  return `${safeLast}, ${safeFirst}`.trim();
}

function ThemeToggle() {
  const [theme, setTheme] = useState("light");

  useEffect(() => {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    setTheme(current);
  }, []);

  function toggle() {
    const next = theme === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("dental_pms_theme", next);
    setTheme(next);
  }

  return (
    <button className="btn btn-secondary" onClick={toggle} aria-label="Toggle theme">
      {theme === "light" ? "🌙 Dark" : "☀️ Light"}
    </button>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checking, setChecking] = useState(true);
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<PatientSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [lastQuery, setLastQuery] = useState("");
  const [patientTabs, setPatientTabs] = useState<PatientTab[]>([]);
  const [activePatientTabId, setActivePatientTabId] = useState<number | null>(null);

  useEffect(() => {
    const storedTabs = localStorage.getItem(patientTabsStorageKey);
    if (storedTabs) {
      try {
        const parsed = JSON.parse(storedTabs) as PatientTab[];
        setPatientTabs(parsed);
      } catch {
        setPatientTabs([]);
      }
    }
    const storedActive = localStorage.getItem(activePatientTabStorageKey);
    if (storedActive) {
      const parsed = Number(storedActive);
      setActivePatientTabId(Number.isNaN(parsed) ? null : parsed);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(patientTabsStorageKey, JSON.stringify(patientTabs));
  }, [patientTabs]);

  useEffect(() => {
    if (activePatientTabId === null) {
      localStorage.removeItem(activePatientTabStorageKey);
    } else {
      localStorage.setItem(activePatientTabStorageKey, String(activePatientTabId));
    }
  }, [activePatientTabId]);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    (async () => {
      try {
        const res = await apiFetch("/api/me");
        if (res.status === 401 || res.status === 403) {
          clearToken();
          router.replace("/login");
          return;
        }
        if (!res.ok) {
          setError(`Session check failed (HTTP ${res.status})`);
          return;
        }
        const data = (await res.json()) as Me;
        if (data.must_change_password) {
          setMe(data);
          setError(null);
          setChecking(false);
          router.replace("/change-password");
          return;
        }
        setMe(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Session check failed");
      } finally {
        setChecking(false);
      }
    })();
  }, [router]);

  useEffect(() => {
    const match = pathname?.match(/^\/patients\/(\d+)/);
    if (!match) return;
    const patientId = Number(match[1]);
    if (Number.isNaN(patientId)) return;
    setActivePatientTabId(patientId);
    if (patientTabs.some((tab) => tab.id === patientId)) return;
    (async () => {
      try {
        const res = await apiFetch(`/api/patients/${patientId}`);
        if (res.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        if (!res.ok) return;
        const data = (await res.json()) as PatientSearchResult;
        setPatientTabs((prev) => [
          ...prev,
          { id: data.id, label: formatPatientTabLabel(data.first_name, data.last_name) },
        ]);
      } catch {
        // Ignore failed lookup; patient tab can be added via search later.
      }
    })();
  }, [pathname, patientTabs, router]);

  const isUsersRoute = pathname?.startsWith("/users");
  const isAdmin = me
    ? [
        "superadmin",
        "senior_admin",
        "dentist",
        "nurse",
        "receptionist",
        "reception",
      ].includes(me.role)
    : false;
  const isSuperadmin = me?.role === "superadmin";

  useEffect(() => {
    if (!checking && isUsersRoute && !isAdmin) {
      router.replace("/");
    }
  }, [checking, isUsersRoute, isAdmin, router]);

  useEffect(() => {
    const trimmed = searchQuery.trim();
    if (trimmed.length < 2) {
      setSearchResults([]);
      setActiveIndex(-1);
      setSearching(false);
      return;
    }
    const handle = setTimeout(async () => {
      if (trimmed === lastQuery) {
        setSearching(false);
        return;
      }
      setSearching(true);
      try {
        const res = await apiFetch(`/api/patients/search?q=${encodeURIComponent(trimmed)}`);
        if (res.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        if (res.ok) {
          const data = (await res.json()) as PatientSearchResult[];
          setSearchResults(data);
          setActiveIndex(data.length ? 0 : -1);
        } else {
          setSearchResults([]);
          setActiveIndex(-1);
        }
      } catch {
        setSearchResults([]);
        setActiveIndex(-1);
      } finally {
        setSearching(false);
        setLastQuery(trimmed);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [searchQuery, router, lastQuery]);

  if (checking) {
    return (
      <main className="page-center">
        <div className="badge">Checking session…</div>
      </main>
    );
  }

  function openPatientTab(patient: PatientSearchResult) {
    const label = formatPatientTabLabel(patient.first_name, patient.last_name);
    setPatientTabs((prev) => {
      if (prev.some((tab) => tab.id === patient.id)) {
        return prev.map((tab) => (tab.id === patient.id ? { ...tab, label } : tab));
      }
      return [...prev, { id: patient.id, label }];
    });
    setActivePatientTabId(patient.id);
    router.push(`/patients/${patient.id}`);
  }

  function closePatientTab(patientId: number) {
    setPatientTabs((prev) => {
      const nextTabs = prev.filter((tab) => tab.id !== patientId);
      if (activePatientTabId === patientId) {
        const next = nextTabs[0]?.id ?? null;
        setActivePatientTabId(next);
        router.push(next ? `/patients/${next}` : "/");
      }
      return nextTabs;
    });
  }

  const tabs = [
    ...baseTabs,
    ...(isSuperadmin ? [{ href: "/treatments", label: "Treatments" }] : []),
    ...(isSuperadmin ? [{ href: "/templates", label: "Templates" }] : []),
    ...(isSuperadmin ? [{ href: "/settings/profile", label: "Practice profile" }] : []),
    ...(isSuperadmin ? [{ href: "/settings/schedule", label: "Schedule" }] : []),
    ...(isAdmin ? [{ href: "/users", label: "Users" }] : []),
  ];
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname?.startsWith(href));
  const showDropdown = searchQuery.trim().length >= 2;
  const showNoResults =
    !searching &&
    showDropdown &&
    searchQuery.trim() === lastQuery &&
    searchResults.length === 0;

  return (
    <div className="app-shell">
      <div className="app-top">
        <div className="app-top-bar">
          <h1 className="app-title">Dental PMS</h1>
          <div style={{ position: "relative", flex: 1, maxWidth: 420 }}>
            <input
              className="input"
              placeholder="Search patients..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (!showDropdown) return;
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  setActiveIndex((prev) =>
                    Math.min(prev + 1, Math.max(searchResults.length - 1, 0))
                  );
                }
                if (e.key === "ArrowUp") {
                  e.preventDefault();
                  setActiveIndex((prev) => Math.max(prev - 1, 0));
                }
                if (e.key === "Enter") {
                  e.preventDefault();
                  const next =
                    searchResults[activeIndex] || searchResults[0] || undefined;
                  if (next) {
                    setSearchQuery("");
                    setSearchResults([]);
                    setActiveIndex(-1);
                    openPatientTab(next);
                  }
                }
                if (e.key === "Escape") {
                  e.preventDefault();
                  setSearchResults([]);
                  setActiveIndex(-1);
                }
              }}
            />
            {searching && (
              <div className="badge" style={{ position: "absolute", right: 8, top: 8 }}>
                Searching
              </div>
            )}
            {showDropdown && (searchResults.length > 0 || showNoResults) && (
              <div
                className="card"
                style={{
                  position: "absolute",
                  top: "calc(100% + 6px)",
                  left: 0,
                  right: 0,
                  zIndex: 10,
                  display: "grid",
                  gap: 6,
                }}
              >
                {showNoResults ? (
                  <div className="notice">No results</div>
                ) : (
                  searchResults.map((patient, idx) => (
                    <button
                      key={patient.id}
                      className={idx === activeIndex ? "btn btn-primary" : "btn btn-secondary"}
                      style={{ justifyContent: "space-between" }}
                      onClick={() => {
                        setSearchQuery("");
                        setSearchResults([]);
                        setActiveIndex(-1);
                        openPatientTab(patient);
                      }}
                    >
                      <span>
                        {patient.first_name} {patient.last_name}
                      </span>
                      <span style={{ color: "var(--muted)" }}>
                        {patient.date_of_birth || "DOB —"} · {patient.phone || "No phone"}
                      </span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <div className="badge">{me ? `${me.email} · ${me.role}` : "Signed in"}</div>
            <ThemeToggle />
            <button
              className="btn btn-secondary"
              onClick={() => {
                clearToken();
                router.replace("/login");
              }}
            >
              Sign out
            </button>
          </div>
        </div>
        <nav className="tab-list workspace-tabs">
          <button
            type="button"
            className={`tab-link${pathname === "/" ? " active" : ""}`}
            onClick={() => router.push("/")}
          >
            Home
          </button>
          {patientTabs.map((tab) => (
            <div
              key={tab.id}
              className={`tab-pill${activePatientTabId === tab.id ? " active" : ""}`}
            >
              <button
                type="button"
                className="tab-pill-label"
                onClick={() => router.push(`/patients/${tab.id}`)}
              >
                {tab.label}
              </button>
              <button
                type="button"
                className="tab-close"
                aria-label={`Close ${tab.label}`}
                onClick={() => closePatientTab(tab.id)}
              >
                ×
              </button>
            </div>
          ))}
        </nav>
        <nav className="tab-list">
          {tabs.map((tab) => (
            <Link
              key={tab.href}
              href={tab.href}
              className={`tab-link${isActive(tab.href) ? " active" : ""}`}
            >
              {tab.label}
            </Link>
          ))}
        </nav>
        {error && <div className="notice">{error}</div>}
      </div>

      <main className="app-main">
        {!isAdmin && isUsersRoute ? (
          <section className="card">
            <h3 style={{ marginTop: 0 }}>Not authorized</h3>
            <p style={{ color: "var(--muted)" }}>
              You do not have permission to access user management.
            </p>
          </section>
        ) : (
          children
        )}
      </main>
    </div>
  );
}
