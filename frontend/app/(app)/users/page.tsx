"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";

type User = {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
};

const fallbackRoles = [
  "superadmin",
  "dentist",
  "senior_admin",
  "reception",
  "receptionist",
  "nurse",
  "external",
];

export default function UsersPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<string[]>(fallbackRoles);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [resetUser, setResetUser] = useState<User | null>(null);
  const [resetResult, setResetResult] = useState<string | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [resetConfirm, setResetConfirm] = useState("");
  const [resetLoading, setResetLoading] = useState(false);
  const [statusTarget, setStatusTarget] = useState<User | null>(null);

  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [role, setRole] = useState("receptionist");
  const [isActive, setIsActive] = useState(true);

  const createRoles = useMemo(() => {
    const allowed = roles.filter((r) => ["dentist", "nurse", "receptionist"].includes(r));
    return allowed.length ? allowed : ["dentist", "nurse", "receptionist"];
  }, [roles]);

  const isFormValid = useMemo(
    () =>
      email.trim().length > 3 &&
      password.trim().length >= 12 &&
      password === passwordConfirm,
    [email, password, passwordConfirm]
  );

  async function loadUsers() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/api/users");
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.status === 403) {
        setError("Not authorized to view users.");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load users (HTTP ${res.status})`);
      }
      const data = (await res.json()) as User[];
      setUsers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }

  async function loadRoles() {
    try {
      const res = await apiFetch("/api/users/roles");
      if (res.ok) {
        const data = (await res.json()) as string[];
        if (Array.isArray(data) && data.length > 0) {
          setRoles(data);
        }
      }
    } catch {
      setRoles(fallbackRoles);
    }
  }

  useEffect(() => {
    void loadUsers();
    void loadRoles();
  }, []);

  async function onCreateUser(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    if (password.trim().length < 12) {
      setError("Temporary password must be at least 12 characters.");
      setSaving(false);
      return;
    }
    if (password !== passwordConfirm) {
      setError("Passwords do not match.");
      setSaving(false);
      return;
    }
    try {
      const res = await apiFetch("/api/users", {
        method: "POST",
        body: JSON.stringify({
          email: email.trim(),
          full_name: fullName.trim(),
          role,
          temp_password: password,
          is_active: isActive,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.status === 403) {
        setError("Not authorized to create users.");
        return;
      }
      const contentType = res.headers.get("content-type") || "";
      const text = await res.text();
      let data: { detail?: string } | null = null;
      if (contentType.includes("application/json") && text) {
        try {
          data = JSON.parse(text);
        } catch {
          data = null;
        }
      }
      if (!res.ok) {
        throw new Error(data?.detail || text || `Failed to create user (HTTP ${res.status})`);
      }
      setEmail("");
      setFullName("");
      setPassword("");
      setPasswordConfirm("");
      setRole("receptionist");
      setIsActive(true);
      setShowForm(false);
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setSaving(false);
    }
  }

  async function disableUser(userId: number) {
    setError(null);
    try {
      const res = await apiFetch(`/api/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: false }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.status === 403) {
        setError("Not authorized to update users.");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to update user (HTTP ${res.status})`);
      }
      setNotice("User disabled.");
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update user");
    }
  }

  async function enableUser(userId: number) {
    setError(null);
    try {
      const res = await apiFetch(`/api/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: true }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.status === 403) {
        setError("Not authorized to update users.");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to update user (HTTP ${res.status})`);
      }
      setNotice("User enabled.");
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update user");
    }
  }

  async function submitPasswordReset(e: React.FormEvent) {
    e.preventDefault();
    if (!resetUser) return;
    if (resetPassword.trim().length < 12) {
      setError("Temporary password must be at least 12 characters.");
      return;
    }
    if (resetPassword !== resetConfirm) {
      setError("Temporary passwords do not match.");
      return;
    }
    setResetLoading(true);
    setError(null);
    setNotice(null);
    try {
      const res = await apiFetch(`/api/users/${resetUser.id}/reset-password`, {
        method: "POST",
        body: JSON.stringify({
          temp_password: resetPassword.trim(),
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.status === 403) {
        setError("Not authorized to reset passwords.");
        return;
      }
      const contentType = res.headers.get("content-type") || "";
      const text = await res.text();
      let data: { detail?: string; message?: string } | null = null;
      if (contentType.includes("application/json") && text) {
        try {
          data = JSON.parse(text);
        } catch {
          data = null;
        }
      }
      if (!res.ok) {
        throw new Error(data?.detail || text || `Failed to reset password (HTTP ${res.status})`);
      }
      setNotice(data?.message || "Temporary password set. User will be forced to change it.");
      setResetPassword("");
      setResetConfirm("");
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset password");
    } finally {
      setResetLoading(false);
    }
  }

  function closeResetModal() {
    setResetUser(null);
    setResetPassword("");
    setResetConfirm("");
  }

  function closeStatusModal() {
    setStatusTarget(null);
  }

  return (
    <div className="app-grid">
      <section className="card" style={{ display: "grid", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
          <div>
            <h2 style={{ marginTop: 0 }}>Users</h2>
            <p style={{ color: "var(--muted)", marginBottom: 0 }}>
              Manage access and roles for the practice team.
            </p>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <button className="btn btn-secondary" onClick={loadUsers}>
              Refresh
            </button>
            <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
              {showForm ? "Close" : "Create user"}
            </button>
          </div>
        </div>

        {error && <div className="notice">{error}</div>}
        {notice && <div className="notice">{notice}</div>}

        {showForm && (
          <form onSubmit={onCreateUser} className="card" style={{ margin: 0 }}>
            <div className="stack">
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Email</label>
                <input
                  className="input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  type="email"
                />
              </div>
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Full name</label>
                <input
                  className="input"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
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
                    required
                    minLength={12}
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
                        <circle
                          cx="12"
                          cy="12"
                          r="3.2"
                          stroke="currentColor"
                          strokeWidth="1.6"
                        />
                      </svg>
                    )}
                  </button>
                </div>
                <span style={{ color: "var(--muted)", fontSize: 12 }}>
                  Use at least 12 characters.
                </span>
              </div>
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Confirm password</label>
                <input
                  className="input"
                  type={showPassword ? "text" : "password"}
                  value={passwordConfirm}
                  onChange={(e) => setPasswordConfirm(e.target.value)}
                  required
                  minLength={12}
                />
              </div>
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Role</label>
                <select
                  className="input"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                >
                  {createRoles.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </div>
              <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                />
                Active user
              </label>
              <div>
                <button className="btn btn-primary" disabled={!isFormValid || saving}>
                  {saving ? "Creating..." : "Create user"}
                </button>
              </div>
            </div>
          </form>
        )}

        {resetUser && (
          <div className="card" style={{ margin: 0 }}>
            <div className="stack">
              <div className="row">
                <div>
                  <h3 style={{ marginTop: 0 }}>Reset password</h3>
                  <p style={{ color: "var(--muted)" }}>
                    Set a temporary password for {resetUser.email}. They will be forced to change
                    it on next login.
                  </p>
                </div>
                <button className="btn btn-secondary" type="button" onClick={closeResetModal}>
                  Close
                </button>
              </div>

              <form onSubmit={submitPasswordReset} className="stack">
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">Temporary password</label>
                  <div className="input-wrap">
                    <input
                      className="input"
                      type={showPassword ? "text" : "password"}
                      value={resetPassword}
                      onChange={(e) => setResetPassword(e.target.value)}
                      placeholder="At least 12 characters"
                      minLength={12}
                      required
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
                  <label className="label">Confirm temporary password</label>
                  <input
                    className="input"
                    type={showPassword ? "text" : "password"}
                    value={resetConfirm}
                    onChange={(e) => setResetConfirm(e.target.value)}
                    minLength={12}
                    required
                  />
                </div>
                <button className="btn btn-primary" disabled={resetLoading}>
                  {resetLoading ? "Resetting..." : "Reset password"}
                </button>
              </form>
            </div>
          </div>
        )}

        {statusTarget && (
          <div className="card" style={{ margin: 0 }}>
            <div className="stack">
              <div className="row">
                <div>
                  <h3 style={{ marginTop: 0 }}>Disable user</h3>
                  <p style={{ color: "var(--muted)" }}>
                    Disable access for {statusTarget.email}? They will not be able to sign in.
                  </p>
                </div>
                <button className="btn btn-secondary" type="button" onClick={closeStatusModal}>
                  Cancel
                </button>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className="btn btn-primary"
                  onClick={() => {
                    const id = statusTarget.id;
                    closeStatusModal();
                    void disableUser(id);
                  }}
                >
                  Confirm disable
                </button>
                <button className="btn btn-secondary" onClick={closeStatusModal}>
                  Keep active
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="card" style={{ margin: 0 }}>
          {loading ? (
            <div className="badge">Loading users…</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.full_name || "—"}</td>
                    <td>{user.email}</td>
                    <td>{user.role}</td>
                    <td>
                      <span className="badge">
                        {user.is_active ? "Active" : "Disabled"}
                      </span>
                    </td>
                    <td>
                      <div className="table-actions">
                        {user.is_active ? (
                          <button
                            className="btn btn-secondary"
                            onClick={() => setStatusTarget(user)}
                          >
                            Disable
                          </button>
                        ) : (
                          <button
                            className="btn btn-secondary"
                            onClick={() => enableUser(user.id)}
                          >
                            Enable
                          </button>
                        )}
                        <button
                          className="btn btn-secondary"
                          onClick={() => {
                            setResetUser(user);
                            setResetResult(null);
                            setResetPassword("");
                          }}
                        >
                          Reset password
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}
