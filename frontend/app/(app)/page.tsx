"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, getToken } from "@/lib/auth";

type Me = {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
};

export default function Home() {
  const [apiHealth, setApiHealth] = useState("checking");
  const [me, setMe] = useState<Me | null>(null);
  const [meErr, setMeErr] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<"checking" | "signed_out" | "signed_in" | "error">(
    "checking"
  );

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch("/api/health", { cache: "no-store" });
        const j = await r.json();
        setApiHealth(j?.status === "ok" ? "ok" : "bad");
      } catch {
        setApiHealth("unreachable");
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      const token = getToken();
      if (!token) {
        setMe(null);
        setMeErr(null);
        setSessionStatus("signed_out");
        return;
      }
      try {
        const r = await apiFetch("/api/me");
        if (r.status === 401 || r.status === 403) {
          setMe(null);
          setMeErr(null);
          setSessionStatus("signed_out");
          return;
        }
        if (!r.ok) {
          setMe(null);
          setMeErr(`Session check failed (HTTP ${r.status})`);
          setSessionStatus("error");
          return;
        }
        const j = await r.json();
        setMe(j);
        setMeErr(null);
        setSessionStatus("signed_in");
      } catch (err) {
        setMe(null);
        setMeErr(err instanceof Error ? err.message : "Session check failed");
        setSessionStatus("error");
      }
    })();
  }, []);

  return (
    <div className="app-grid">
      <section className="card">
        <h2 style={{ marginTop: 0 }}>Welcome back</h2>
        <p style={{ color: "var(--muted)" }}>
          Your Dental PMS workspace is ready.
        </p>
        <div className="badge">
          API health: <strong>{apiHealth}</strong>
        </div>
      </section>

      <section className="card">
        <h3 style={{ marginTop: 0 }}>Session</h3>
        {sessionStatus === "signed_out" ? (
          <p>
            Not signed in. <Link href="/login">Go to login</Link>
          </p>
        ) : sessionStatus === "signed_in" && me ? (
          <div className="stack" style={{ gap: 6 }}>
            <div>
              <strong>Signed in as:</strong> {me.email}
            </div>
            <div>
              <strong>Role:</strong> {me.role}
            </div>
          </div>
        ) : sessionStatus === "error" ? (
          <div className="notice">{meErr || "Session check failed"}</div>
        ) : (
          <div className="badge">Checking session…</div>
        )}
      </section>
    </div>
  );
}
