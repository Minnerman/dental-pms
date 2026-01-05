"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { apiFetch } from "@/lib/auth";

export default function ResetPasswordClient() {
  const params = useSearchParams();
  const tokenFromQuery = useMemo(() => params?.get("token") ?? "", [params]);
  const [token, setToken] = useState(tokenFromQuery);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    if (!token || token.length < 20) {
      setError("Enter a valid reset token.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      const res = await apiFetch("/api/auth/password-reset/confirm", {
        method: "POST",
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || `Reset failed (${res.status})`);
      }
      setMessage(data.message || "Password updated. You can now sign in.");
      setPassword("");
      setConfirm("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-center">
      <section className="card" style={{ width: "min(460px, 100%)" }}>
        <div className="stack">
          <div>
            <div className="badge">Dental PMS</div>
            <h1 style={{ margin: "12px 0 6px" }}>Set a new password</h1>
            <p style={{ margin: 0, color: "var(--muted)" }}>
              Paste your reset token and choose a new password.
            </p>
          </div>

          <form onSubmit={onSubmit} className="stack">
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Reset token</label>
              <input
                className="input"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste token"
              />
            </div>

            <div className="stack" style={{ gap: 8 }}>
              <label className="label">New password</label>
              <div className="input-wrap">
                <input
                  className="input"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  className="input-icon"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword((prev) => !prev)}
                >
                  {showPassword ? "🙈" : "👁️"}
                </button>
              </div>
            </div>

            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Confirm password</label>
              <input
                className="input"
                type={showPassword ? "text" : "password"}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                autoComplete="new-password"
              />
            </div>

            {error && <div className="notice">{error}</div>}
            {message && <div className="notice">{message}</div>}

            <button className="btn btn-primary" disabled={loading} type="submit">
              {loading ? "Updating..." : "Update password"}
            </button>
          </form>

          <p style={{ margin: 0, color: "var(--muted)", fontSize: 13 }}>
            <Link href="/login" style={{ textDecoration: "underline" }}>
              Return to sign in
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
