"use client";

import Link from "next/link";
import { useState } from "react";
import { apiFetch } from "@/lib/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [resetToken, setResetToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMessage(null);
    setResetToken(null);
    try {
      const res = await apiFetch("/api/auth/password-reset/request", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || `Request failed (${res.status})`);
      }
      setMessage(data.message || "If the account exists, a reset link has been generated.");
      if (data.reset_token) {
        setResetToken(data.reset_token);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  const resetLink = resetToken ? `/reset-password?token=${encodeURIComponent(resetToken)}` : null;

  return (
    <main className="page-center">
      <section className="card" style={{ width: "min(460px, 100%)" }}>
        <div className="stack">
          <div>
            <div className="badge">Dental PMS</div>
            <h1 style={{ margin: "12px 0 6px" }}>Reset your password</h1>
            <p style={{ margin: 0, color: "var(--muted)" }}>
              Enter your email to request a reset link.
            </p>
          </div>

          <form onSubmit={onSubmit} className="stack">
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Email</label>
              <input
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                placeholder="name@practice.com"
              />
            </div>

            {error && <div className="notice">{error}</div>}
            {message && <div className="notice">{message}</div>}

            <button className="btn btn-primary" disabled={loading} type="submit">
              {loading ? "Requesting..." : "Send reset link"}
            </button>
          </form>

          {resetLink && (
            <div className="stack" style={{ gap: 8 }}>
              <span className="label">Reset link (debug)</span>
              <Link href={resetLink} style={{ textDecoration: "underline" }}>
                Open reset form
              </Link>
            </div>
          )}

          <p style={{ margin: 0, color: "var(--muted)", fontSize: 13 }}>
            <Link href="/login" style={{ textDecoration: "underline" }}>
              Back to sign in
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
