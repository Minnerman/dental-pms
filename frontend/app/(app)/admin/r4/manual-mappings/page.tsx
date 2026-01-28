"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import HeaderBar from "@/components/ui/HeaderBar";
import { apiFetch, clearToken } from "@/lib/auth";

type ManualMapping = {
  id: string;
  legacy_source: string;
  legacy_patient_code: number;
  target_patient_id: number;
  note?: string | null;
  created_at: string;
};

export default function R4ManualMappingsAdminPage() {
  const router = useRouter();
  const [items, setItems] = useState<ManualMapping[]>([]);
  const [legacyPatientCode, setLegacyPatientCode] = useState("");
  const [limit, setLimit] = useState(100);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [formCode, setFormCode] = useState("");
  const [formTargetId, setFormTargetId] = useState("");
  const [formNote, setFormNote] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const queryString = useMemo(() => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (legacyPatientCode.trim()) {
      params.set("legacy_patient_code", legacyPatientCode.trim());
    }
    return params.toString();
  }, [legacyPatientCode, limit]);

  const loadMappings = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const res = await apiFetch(`/api/admin/r4/manual-mappings?${queryString}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.status === 403) {
        setError("Only admins can access manual mappings.");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load manual mappings (HTTP ${res.status})`);
      }
      const data = (await res.json()) as ManualMapping[];
      setItems(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load manual mappings");
    } finally {
      setLoading(false);
    }
  }, [queryString, router]);

  useEffect(() => {
    void loadMappings();
  }, [loadMappings]);

  const submitMapping = useCallback(async () => {
    const code = formCode.trim();
    const targetId = formTargetId.trim();
    if (!code || !targetId) {
      setFormError("Patient code and target patient ID are required.");
      return;
    }
    setCreating(true);
    setFormError(null);
    try {
      const res = await apiFetch("/api/admin/r4/manual-mappings", {
        method: "POST",
        body: JSON.stringify({
          legacy_patient_code: Number(code),
          target_patient_id: Number(targetId),
          note: formNote.trim() || null,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.status === 403) {
        setFormError("Only admins can create manual mappings.");
        return;
      }
      if (res.status === 409) {
        setFormError("A manual mapping already exists for that patient code.");
        return;
      }
      if (res.status === 404) {
        setFormError("Target patient not found.");
        return;
      }
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Failed to create mapping (HTTP ${res.status})`);
      }
      setNotice("Manual mapping created.");
      setFormCode("");
      setFormTargetId("");
      setFormNote("");
      await loadMappings();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to create mapping");
    } finally {
      setCreating(false);
    }
  }, [formCode, formTargetId, formNote, loadMappings, router]);

  const deleteMapping = useCallback(
    async (id: string) => {
      if (!confirm("Delete this manual mapping?")) return;
      setDeletingId(id);
      setError(null);
      setNotice(null);
      try {
        const res = await apiFetch(`/api/admin/r4/manual-mappings/${id}`, {
          method: "DELETE",
        });
        if (res.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        if (res.status === 403) {
          setError("Only admins can delete manual mappings.");
          return;
        }
        if (res.status === 404) {
          setError("Manual mapping not found.");
          return;
        }
        if (!res.ok) {
          throw new Error(`Failed to delete mapping (HTTP ${res.status})`);
        }
        setNotice("Manual mapping deleted.");
        await loadMappings();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete mapping");
      } finally {
        setDeletingId(null);
      }
    },
    [loadMappings, router]
  );

  return (
    <div className="app-grid">
      <div className="card">
        <div className="stack">
          <HeaderBar
            title="R4 manual mappings"
            subtitle="Admin-only overrides for R4 patient codes."
            actions={
              <div className="row" style={{ gap: 8 }}>
                <input
                  className="input"
                  type="number"
                  inputMode="numeric"
                  placeholder="Legacy patient code"
                  value={legacyPatientCode}
                  onChange={(e) => setLegacyPatientCode(e.target.value)}
                />
                <input
                  className="input"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={500}
                  value={limit}
                  onChange={(e) => setLimit(Number(e.target.value || 0))}
                />
                <button className="button" onClick={loadMappings} disabled={loading}>
                  {loading ? "Loading..." : "Refresh"}
                </button>
              </div>
            }
          />

          {error && <div className="notice error">{error}</div>}
          {notice && <div className="notice success">{notice}</div>}

          <div className="card subtle">
            <div className="stack">
              <h3>Add manual mapping</h3>
              {formError && <div className="notice error">{formError}</div>}
              <div className="row wrap" style={{ gap: 12 }}>
                <input
                  className="input"
                  type="number"
                  inputMode="numeric"
                  placeholder="Legacy patient code"
                  value={formCode}
                  onChange={(e) => setFormCode(e.target.value)}
                />
                <input
                  className="input"
                  type="text"
                  placeholder="Target patient ID"
                  value={formTargetId}
                  onChange={(e) => setFormTargetId(e.target.value)}
                />
                <input
                  className="input"
                  type="text"
                  placeholder="Note (optional)"
                  value={formNote}
                  onChange={(e) => setFormNote(e.target.value)}
                />
                <button className="button" onClick={submitMapping} disabled={creating}>
                  {creating ? "Saving..." : "Create"}
                </button>
              </div>
            </div>
          </div>

          <div className="table-wrap">
            <table className="table compact">
              <thead>
                <tr>
                  <th>Legacy code</th>
                  <th>Target patient ID</th>
                  <th>Note</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {!loading && items.length === 0 ? (
                  <tr>
                    <td colSpan={5}>No manual mappings found.</td>
                  </tr>
                ) : (
                  items.map((row) => (
                    <tr key={row.id}>
                      <td>{row.legacy_patient_code}</td>
                      <td>{row.target_patient_id}</td>
                      <td>{row.note || "—"}</td>
                      <td>{new Date(row.created_at).toLocaleString()}</td>
                      <td>
                        <button
                          className="button ghost"
                          onClick={() => void deleteMapping(row.id)}
                          disabled={deletingId === row.id}
                        >
                          {deletingId === row.id ? "Deleting..." : "Delete"}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
