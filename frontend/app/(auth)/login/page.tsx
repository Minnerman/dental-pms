"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { login, setToken } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("ChangeMe123!");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const { accessToken, mustChangePassword } = await login(email, password);
      setToken(accessToken);
      if (mustChangePassword) {
        router.push("/change-password");
      } else {
        router.push("/patients");
      }
    } catch (err) {
      const message =
        err instanceof Error && err.message ? err.message : "Invalid credentials";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-center">
      <section className="card" style={{ width: "min(440px, 100%)" }}>
        <div className="stack">
          <div>
            <div className="badge">Dental PMS</div>
            <h1 style={{ margin: "12px 0 6px" }}>Sign in</h1>
            <p style={{ margin: 0, color: "var(--muted)" }}>
              Use your admin credentials to continue.
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
              />
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Password</label>
              <div className="input-wrap">
                <input
                  className="input"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="input-icon"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword((prev) => !prev)}
                >
                  {showPassword ? (
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                      <path
                        d="M3 3l18 18"
                        stroke="currentColor"
                        strokeWidth="1.6"
                        strokeLinecap="round"
                      />
                      <path
                        d="M10.6 10.7a2.4 2.4 0 003.1 3.1"
                        stroke="currentColor"
                        strokeWidth="1.6"
                        strokeLinecap="round"
                      />
                      <path
                        d="M6.3 6.3C4 7.9 2.7 10 2 12c1.6 4.3 5.4 7 10 7 1.8 0 3.4-.4 4.8-1.1"
                        stroke="currentColor"
                        strokeWidth="1.6"
                        strokeLinecap="round"
                      />
                      <path
                        d="M9.5 4.6A9.8 9.8 0 0112 4c4.6 0 8.4 2.7 10 7-.6 1.5-1.5 2.9-2.6 4"
                        stroke="currentColor"
                        strokeWidth="1.6"
                        strokeLinecap="round"
                      />
                    </svg>
                  ) : (
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                      <path
                        d="M2 12c1.6-4.3 5.4-7 10-7s8.4 2.7 10 7c-1.6 4.3-5.4 7-10 7S3.6 16.3 2 12z"
                        stroke="currentColor"
                        strokeWidth="1.6"
                      />
                      <circle cx="12" cy="12" r="3.2" stroke="currentColor" strokeWidth="1.6" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {error && <div className="notice">{error}</div>}

            <button className="btn btn-primary" disabled={loading} type="submit">
              {loading ? "Signing in..." : "Sign in"}
            </button>
            <p style={{ margin: 0, fontSize: 12, opacity: 0.6 }}>
              API base: {process.env.NEXT_PUBLIC_API_BASE ?? "/api"}
            </p>
          </form>
          <p style={{ margin: 0, color: "var(--muted)", fontSize: 13 }}>
            <Link href="/forgot-password" style={{ textDecoration: "underline" }}>
              Forgot password?
            </Link>
          </p>
          <p style={{ margin: 0, color: "var(--muted)", fontSize: 13 }}>
            Default admin is configured in <code>.env</code>.
          </p>
        </div>
      </section>
    </main>
  );
}
