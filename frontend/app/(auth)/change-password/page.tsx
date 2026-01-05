"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";

type Me = {
  id: number;
  email: string;
  must_change_password: boolean;
};

export default function ChangePasswordPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiFetch("/api/me");
        if (res.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        if (!res.ok) {
          throw new Error(`Failed to load profile (HTTP ${res.status})`);
        }
        const data = (await res.json()) as Me;
        setMe(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load profile");
      }
    })();
  }, [router]);

  const requiresOldPassword = me ? !me.must_change_password : false;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    if (requiresOldPassword && !oldPassword) {
      setError("Enter your current password.");
      return;
    }
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      const res = await apiFetch("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          new_password: newPassword,
          old_password: oldPassword || undefined,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || `Password update failed (${res.status})`);
      }
      setMessage(data.message || "Password updated.");
      setOldPassword("");
      setNewPassword("");
      setConfirm("");
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password update failed");
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
            <h1 style={{ margin: "12px 0 6px" }}>Change password</h1>
            <p style={{ margin: 0, color: "var(--muted)" }}>
              {me?.must_change_password
                ? "You must update your password before continuing."
                : "Update your account password."}
            </p>
          </div>

          <form onSubmit={onSubmit} className="stack">
            {requiresOldPassword && (
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Current password</label>
                <input
                  className="input"
                  type={showPassword ? "text" : "password"}
                  value={oldPassword}
                  onChange={(e) => setOldPassword(e.target.value)}
                  autoComplete="current-password"
                />
              </div>
            )}

            <div className="stack" style={{ gap: 8 }}>
              <label className="label">New password</label>
              <div className="input-wrap">
                <input
                  className="input"
                  type={showPassword ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
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
        </div>
      </section>
    </main>
  );
}
