"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";

type PatientCategory = "CLINIC_PRIVATE" | "DOMICILIARY_PRIVATE" | "DENPLAN";

type FeeType = "FIXED" | "RANGE" | "N_A";

type Treatment = {
  id: number;
  code?: string | null;
  name: string;
  description?: string | null;
  is_active: boolean;
  default_duration_minutes?: number | null;
  is_denplan_included_default: boolean;
};

type TreatmentFee = {
  id: number;
  treatment_id: number;
  patient_category: PatientCategory;
  fee_type: FeeType;
  amount_pence?: number | null;
  min_amount_pence?: number | null;
  max_amount_pence?: number | null;
  notes?: string | null;
};

type FeeDraft = {
  fee_type: FeeType;
  amount: string;
  min: string;
  max: string;
  notes: string;
};

const categoryLabels: Record<PatientCategory, string> = {
  CLINIC_PRIVATE: "Clinic (Private)",
  DOMICILIARY_PRIVATE: "Domiciliary (Private)",
  DENPLAN: "Denplan",
};

const emptyDraft: FeeDraft = {
  fee_type: "N_A",
  amount: "",
  min: "",
  max: "",
  notes: "",
};

export default function TreatmentsPage() {
  const router = useRouter();
  const [treatments, setTreatments] = useState<Treatment[]>([]);
  const [selected, setSelected] = useState<Treatment | null>(null);
  const [fees, setFees] = useState<Record<PatientCategory, FeeDraft>>({
    CLINIC_PRIVATE: { ...emptyDraft },
    DOMICILIARY_PRIVATE: { ...emptyDraft },
    DENPLAN: { ...emptyDraft },
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savingFees, setSavingFees] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [newCode, setNewCode] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newDuration, setNewDuration] = useState("");
  const [newActive, setNewActive] = useState(true);
  const [newDenplanIncluded, setNewDenplanIncluded] = useState(false);

  const hasSelection = Boolean(selected);

  const feeRows = useMemo(() => {
    return (Object.keys(categoryLabels) as PatientCategory[]).map((category) => ({
      category,
      label: categoryLabels[category],
      draft: fees[category],
    }));
  }, [fees]);

  function toPence(raw: string) {
    const parsed = Number(raw);
    if (Number.isNaN(parsed)) return null;
    return Math.max(0, Math.round(parsed * 100));
  }

  async function loadTreatments() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/api/treatments?include_inactive=1");
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load treatments (HTTP ${res.status})`);
      }
      const data = (await res.json()) as Treatment[];
      setTreatments(data);
      if (selected) {
        const next = data.find((treatment) => treatment.id === selected.id) || null;
        setSelected(next);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load treatments");
    } finally {
      setLoading(false);
    }
  }

  async function loadFees(treatmentId: number) {
    setError(null);
    try {
      const res = await apiFetch(`/api/treatments/${treatmentId}/fees`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load fees (HTTP ${res.status})`);
      }
      const data = (await res.json()) as TreatmentFee[];
      const nextDrafts: Record<PatientCategory, FeeDraft> = {
        CLINIC_PRIVATE: { ...emptyDraft },
        DOMICILIARY_PRIVATE: { ...emptyDraft },
        DENPLAN: { ...emptyDraft },
      };
      data.forEach((fee) => {
        nextDrafts[fee.patient_category] = {
          fee_type: fee.fee_type,
          amount: fee.amount_pence ? (fee.amount_pence / 100).toFixed(2) : "",
          min: fee.min_amount_pence ? (fee.min_amount_pence / 100).toFixed(2) : "",
          max: fee.max_amount_pence ? (fee.max_amount_pence / 100).toFixed(2) : "",
          notes: fee.notes ?? "",
        };
      });
      setFees(nextDrafts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load fees");
    }
  }

  async function createTreatment() {
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/api/treatments", {
        method: "POST",
        body: JSON.stringify({
          code: newCode || null,
          name: newName,
          description: newDescription || null,
          is_active: newActive,
          default_duration_minutes: newDuration ? Number(newDuration) : null,
          is_denplan_included_default: newDenplanIncluded,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to create treatment (HTTP ${res.status})`);
      }
      setNewName("");
      setNewCode("");
      setNewDescription("");
      setNewDuration("");
      setNewActive(true);
      setNewDenplanIncluded(false);
      await loadTreatments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create treatment");
    } finally {
      setSaving(false);
    }
  }

  async function updateTreatment() {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/treatments/${selected.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          code: selected.code || null,
          name: selected.name,
          description: selected.description || null,
          is_active: selected.is_active,
          default_duration_minutes: selected.default_duration_minutes ?? null,
          is_denplan_included_default: selected.is_denplan_included_default,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to update treatment (HTTP ${res.status})`);
      }
      await loadTreatments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update treatment");
    } finally {
      setSaving(false);
    }
  }

  async function saveFees() {
    if (!selected) return;
    setSavingFees(true);
    setError(null);
    try {
      const payload = feeRows.map(({ category, draft }) => {
        const entry: Record<string, unknown> = {
          patient_category: category,
          fee_type: draft.fee_type,
          notes: draft.notes || null,
        };
        if (draft.fee_type === "FIXED") {
          const amount = toPence(draft.amount);
          if (amount === null) throw new Error(`${categoryLabels[category]} fixed amount is invalid.`);
          entry.amount_pence = amount;
        } else if (draft.fee_type === "RANGE") {
          const min = toPence(draft.min);
          const max = toPence(draft.max);
          if (min === null || max === null) {
            throw new Error(`${categoryLabels[category]} range values are invalid.`);
          }
          entry.min_amount_pence = min;
          entry.max_amount_pence = max;
        }
        return entry;
      });

      const res = await apiFetch(`/api/treatments/${selected.id}/fees`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to save fees (HTTP ${res.status})`);
      }
      await loadFees(selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save fees");
    } finally {
      setSavingFees(false);
    }
  }

  useEffect(() => {
    void loadTreatments();
  }, []);

  useEffect(() => {
    if (selected) {
      void loadFees(selected.id);
    }
  }, [selected]);

  return (
    <div className="app-grid">
      <section className="card" style={{ display: "grid", gap: 12 }}>
        <div>
          <h2 style={{ marginTop: 0 }}>Treatments</h2>
          <p style={{ color: "var(--muted)", marginBottom: 0 }}>
            Maintain the treatment catalogue and category-specific fee schedules.
          </p>
        </div>

        {error && <div className="notice">{error}</div>}
        {loading ? (
          <div className="badge">Loading treatments…</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Active</th>
                <th>Denplan default</th>
                <th>Duration</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {treatments.map((treatment) => (
                <tr key={treatment.id}>
                  <td>{treatment.name}</td>
                  <td>{treatment.is_active ? "Yes" : "No"}</td>
                  <td>{treatment.is_denplan_included_default ? "Included" : "Excluded"}</td>
                  <td>{treatment.default_duration_minutes ?? "-"}</td>
                  <td>
                    <button
                      className="btn btn-secondary"
                      onClick={() => setSelected(treatment)}
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card" style={{ display: "grid", gap: 16 }}>
        <div>
          <h3 style={{ marginTop: 0 }}>New treatment</h3>
        </div>
        <div className="grid grid-2">
          <div className="stack" style={{ gap: 8 }}>
            <label className="label">Name</label>
            <input
              className="input"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
          </div>
          <div className="stack" style={{ gap: 8 }}>
            <label className="label">Code</label>
            <input
              className="input"
              value={newCode}
              onChange={(e) => setNewCode(e.target.value)}
            />
          </div>
        </div>
        <div className="stack" style={{ gap: 8 }}>
          <label className="label">Description</label>
          <textarea
            className="input"
            rows={3}
            value={newDescription}
            onChange={(e) => setNewDescription(e.target.value)}
          />
        </div>
        <div className="grid grid-2">
          <div className="stack" style={{ gap: 8 }}>
            <label className="label">Default duration (minutes)</label>
            <input
              className="input"
              value={newDuration}
              onChange={(e) => setNewDuration(e.target.value)}
            />
          </div>
          <div className="stack" style={{ gap: 8 }}>
            <label className="label">Active</label>
            <select
              className="input"
              value={newActive ? "yes" : "no"}
              onChange={(e) => setNewActive(e.target.value === "yes")}
            >
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </select>
          </div>
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            checked={newDenplanIncluded}
            onChange={(e) => setNewDenplanIncluded(e.target.checked)}
          />
          Denplan included by default
        </label>
        <button className="btn btn-primary" onClick={createTreatment} disabled={saving}>
          {saving ? "Saving..." : "Create treatment"}
        </button>
      </section>

      <section className="card" style={{ display: "grid", gap: 16 }}>
        <div>
          <h3 style={{ marginTop: 0 }}>Edit treatment</h3>
          {!hasSelection && (
            <p style={{ color: "var(--muted)", marginBottom: 0 }}>
              Select a treatment to edit details and fees.
            </p>
          )}
        </div>
        {selected && (
          <div className="stack">
            <div className="grid grid-2">
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Name</label>
                <input
                  className="input"
                  value={selected.name}
                  onChange={(e) =>
                    setSelected((prev) => (prev ? { ...prev, name: e.target.value } : prev))
                  }
                />
              </div>
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Code</label>
                <input
                  className="input"
                  value={selected.code ?? ""}
                  onChange={(e) =>
                    setSelected((prev) => (prev ? { ...prev, code: e.target.value } : prev))
                  }
                />
              </div>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Description</label>
              <textarea
                className="input"
                rows={3}
                value={selected.description ?? ""}
                onChange={(e) =>
                  setSelected((prev) =>
                    prev ? { ...prev, description: e.target.value } : prev
                  )
                }
              />
            </div>
            <div className="grid grid-2">
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Default duration (minutes)</label>
                <input
                  className="input"
                  value={selected.default_duration_minutes ?? ""}
                  onChange={(e) =>
                    setSelected((prev) =>
                      prev
                        ? {
                            ...prev,
                            default_duration_minutes: e.target.value
                              ? Number(e.target.value)
                              : null,
                          }
                        : prev
                    )
                  }
                />
              </div>
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Active</label>
                <select
                  className="input"
                  value={selected.is_active ? "yes" : "no"}
                  onChange={(e) =>
                    setSelected((prev) =>
                      prev ? { ...prev, is_active: e.target.value === "yes" } : prev
                    )
                  }
                >
                  <option value="yes">Yes</option>
                  <option value="no">No</option>
                </select>
              </div>
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={selected.is_denplan_included_default}
                onChange={(e) =>
                  setSelected((prev) =>
                    prev ? { ...prev, is_denplan_included_default: e.target.checked } : prev
                  )
                }
              />
              Denplan included by default
            </label>
            <button className="btn btn-primary" onClick={updateTreatment} disabled={saving}>
              {saving ? "Saving..." : "Save treatment"}
            </button>

            <div className="card" style={{ margin: 0 }}>
              <div className="stack">
                <h4 style={{ marginTop: 0 }}>Fees</h4>
                {feeRows.map(({ category, label, draft }) => (
                  <div
                    key={category}
                    className="card"
                    style={{ margin: 0, background: "var(--card-subtle)" }}
                  >
                    <div className="stack" style={{ gap: 8 }}>
                      <strong>{label}</strong>
                      <div className="grid grid-3">
                        <div className="stack" style={{ gap: 8 }}>
                          <label className="label">Fee type</label>
                          <select
                            className="input"
                            value={draft.fee_type}
                            onChange={(e) =>
                              setFees((prev) => ({
                                ...prev,
                                [category]: { ...prev[category], fee_type: e.target.value as FeeType },
                              }))
                            }
                          >
                            <option value="FIXED">Fixed</option>
                            <option value="RANGE">Range</option>
                            <option value="N_A">N/A</option>
                          </select>
                        </div>
                        {draft.fee_type === "FIXED" ? (
                          <div className="stack" style={{ gap: 8 }}>
                            <label className="label">Amount (£)</label>
                            <input
                              className="input"
                              value={draft.amount}
                              onChange={(e) =>
                                setFees((prev) => ({
                                  ...prev,
                                  [category]: { ...prev[category], amount: e.target.value },
                                }))
                              }
                            />
                          </div>
                        ) : draft.fee_type === "RANGE" ? (
                          <>
                            <div className="stack" style={{ gap: 8 }}>
                              <label className="label">Min (£)</label>
                              <input
                                className="input"
                                value={draft.min}
                                onChange={(e) =>
                                  setFees((prev) => ({
                                    ...prev,
                                    [category]: { ...prev[category], min: e.target.value },
                                  }))
                                }
                              />
                            </div>
                            <div className="stack" style={{ gap: 8 }}>
                              <label className="label">Max (£)</label>
                              <input
                                className="input"
                                value={draft.max}
                                onChange={(e) =>
                                  setFees((prev) => ({
                                    ...prev,
                                    [category]: { ...prev[category], max: e.target.value },
                                  }))
                                }
                              />
                            </div>
                          </>
                        ) : (
                          <div className="stack" style={{ gap: 8 }}>
                            <label className="label">Amount</label>
                            <input className="input" value="-" readOnly />
                          </div>
                        )}
                      </div>
                      <div className="stack" style={{ gap: 8 }}>
                        <label className="label">Notes</label>
                        <input
                          className="input"
                          value={draft.notes}
                          onChange={(e) =>
                            setFees((prev) => ({
                              ...prev,
                              [category]: { ...prev[category], notes: e.target.value },
                            }))
                          }
                          placeholder="Optional notes"
                        />
                      </div>
                    </div>
                  </div>
                ))}
                <button className="btn btn-primary" onClick={saveFees} disabled={savingFees}>
                  {savingFees ? "Saving..." : "Save fees"}
                </button>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
