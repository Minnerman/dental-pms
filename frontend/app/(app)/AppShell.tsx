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

const baseTabs = [
  { href: "/", label: "Home" },
  { href: "/patients", label: "Patients" },
  { href: "/appointments", label: "Appointments" },
  { href: "/notes", label: "Notes" },
];

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

  useEffect(() => {
    if (!checking && isUsersRoute && !isAdmin) {
      router.replace("/");
    }
  }, [checking, isUsersRoute, isAdmin, router]);

  useEffect(() => {
    const trimmed = searchQuery.trim();
    if (trimmed.length < 2) {
      setSearchResults([]);
      return;
    }
    const handle = setTimeout(async () => {
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
        } else {
          setSearchResults([]);
        }
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [searchQuery, router]);

  if (checking) {
    return (
      <main className="page-center">
        <div className="badge">Checking session…</div>
      </main>
    );
  }

  const tabs = [...baseTabs, ...(isAdmin ? [{ href: "/users", label: "Users" }] : [])];
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname?.startsWith(href));

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
            />
            {searching && (
              <div className="badge" style={{ position: "absolute", right: 8, top: 8 }}>
                Searching
              </div>
            )}
            {searchResults.length > 0 && (
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
                {searchResults.map((patient) => (
                  <button
                    key={patient.id}
                    className="btn btn-secondary"
                    style={{ justifyContent: "space-between" }}
                    onClick={() => {
                      setSearchQuery("");
                      setSearchResults([]);
                      router.push(`/patients/${patient.id}`);
                    }}
                  >
                    <span>
                      {patient.first_name} {patient.last_name}
                    </span>
                    <span style={{ color: "var(--muted)" }}>
                      {patient.date_of_birth || "DOB —"} · {patient.phone || "No phone"}
                    </span>
                  </button>
                ))}
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
