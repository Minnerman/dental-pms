"use client";

import { useCallback, useMemo, useState } from "react";
import HeaderBar from "@/components/ui/HeaderBar";
import { apiFetch, clearToken } from "@/lib/auth";
import { useRouter } from "next/navigation";

type TreatmentPlanSummary = {
  id: number;
  legacy_patient_code: number;
  legacy_tp_number: number;
  plan_index: number | null;
  is_master: boolean;
  is_current: boolean;
  is_accepted: boolean;
  creation_date: string | null;
  acceptance_date: string | null;
  completion_date: string | null;
  status_code: number | null;
  reason_id: number | null;
  tp_group: number | null;
  item_count: number;
};

type TreatmentPlanItem = {
  id: number;
  legacy_tp_item: number;
  legacy_tp_item_key: number | null;
  code_id: number | null;
  tooth: number | null;
  surface: number | null;
  appointment_need_id: number | null;
  completed: boolean;
  completed_date: string | null;
  patient_cost: string | number | null;
  dpb_cost: string | number | null;
  discretionary_cost: string | number | null;
  material: string | null;
  arch_code: number | null;
};

type TreatmentPlanDetail = {
  plan: TreatmentPlanSummary & { legacy_source: string };
  items: TreatmentPlanItem[];
  reviews: {
    id: number;
    temporary_note: string | null;
    reviewed: boolean;
    last_edit_user: string | null;
    last_edit_date: string | null;
  }[];
};

function formatDateTime(value: string | null) {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString("en-GB", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatMoney(value: string | number | null) {
  if (!value) return "—";
  const num = Number(value);
  if (Number.isNaN(num)) return value;
  return `£${num.toFixed(2)}`;
}

export default function R4TreatmentPlansAdminPage() {
  const router = useRouter();
  const [legacyPatientCode, setLegacyPatientCode] = useState("");
  const [limit, setLimit] = useState(50);
  const [plans, setPlans] = useState<TreatmentPlanSummary[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null);
  const [detail, setDetail] = useState<TreatmentPlanDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSearch = legacyPatientCode.trim().length > 0;

  const queryString = useMemo(() => {
    if (!canSearch) return "";
    const params = new URLSearchParams({
      legacy_patient_code: legacyPatientCode.trim(),
      limit: String(limit),
    });
    return params.toString();
  }, [legacyPatientCode, limit, canSearch]);

  const loadPlans = useCallback(async () => {
    if (!canSearch) return;
    setLoading(true);
    setError(null);
    setPlans([]);
    setSelectedPlanId(null);
    setDetail(null);
    try {
      const res = await apiFetch(`/api/admin/r4/treatment-plans?${queryString}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.status === 403) {
        setError("Only admins can access R4 treatment plans.");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load plans (HTTP ${res.status})`);
      }
      const data = (await res.json()) as TreatmentPlanSummary[];
      setPlans(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load plans");
    } finally {
      setLoading(false);
    }
  }, [canSearch, queryString, router]);

  const loadDetail = useCallback(
    async (planId: number) => {
      setSelectedPlanId(planId);
      setDetailLoading(true);
      setError(null);
      try {
        const res = await apiFetch(`/api/admin/r4/treatment-plans/${planId}`);
        if (res.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        if (res.status === 403) {
          setError("Only admins can access R4 treatment plans.");
          return;
        }
        if (!res.ok) {
          throw new Error(`Failed to load plan detail (HTTP ${res.status})`);
        }
        const data = (await res.json()) as TreatmentPlanDetail;
        setDetail(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load plan detail");
      } finally {
        setDetailLoading(false);
      }
    },
    [router]
  );

  return (
    <div className="app-grid">
      <div className="card">
        <div className="stack">
          <HeaderBar
            title="R4 treatment plans"
            subtitle="Read-only view of imported treatment plans and items."
          />
          <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
            <input
              className="input"
              type="number"
              inputMode="numeric"
              placeholder="Legacy patient code"
              value={legacyPatientCode}
              onChange={(e) => setLegacyPatientCode(e.target.value)}
              style={{ minWidth: 220 }}
            />
            <input
              className="input"
              type="number"
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              min={1}
              max={200}
              style={{ width: 120 }}
            />
            <button
              className="btn btn-primary"
              onClick={loadPlans}
              disabled={!canSearch || loading}
            >
              {loading ? "Loading..." : "Search"}
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => {
                setLegacyPatientCode("");
                setPlans([]);
                setDetail(null);
                setSelectedPlanId(null);
                setError(null);
              }}
            >
              Clear
            </button>
          </div>
          {error && <div className="notice">{error}</div>}
          {!loading && canSearch && plans.length === 0 && !error && (
            <div style={{ color: "var(--muted)", fontSize: 14 }}>
              No treatment plans found for that legacy patient code.
            </div>
          )}
          {plans.length > 0 && (
            <div style={{ overflowX: "auto" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Plan ID</th>
                    <th>Legacy patient</th>
                    <th>TP #</th>
                    <th>Created</th>
                    <th>Accepted</th>
                    <th>Current</th>
                    <th>Items</th>
                  </tr>
                </thead>
                <tbody>
                  {plans.map((plan) => (
                    <tr
                      key={plan.id}
                      onClick={() => loadDetail(plan.id)}
                      style={{
                        cursor: "pointer",
                        background:
                          selectedPlanId === plan.id ? "rgba(59, 130, 246, 0.08)" : undefined,
                      }}
                    >
                      <td>{plan.id}</td>
                      <td>{plan.legacy_patient_code}</td>
                      <td>{plan.legacy_tp_number}</td>
                      <td>{formatDateTime(plan.creation_date)}</td>
                      <td>{plan.is_accepted ? "Yes" : "No"}</td>
                      <td>{plan.is_current ? "Yes" : "No"}</td>
                      <td>{plan.item_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="stack">
          <HeaderBar
            title="Plan detail"
            subtitle={detail ? `Plan ${detail.plan.id}` : "Select a plan to inspect items."}
          />
          {detailLoading && (
            <div style={{ color: "var(--muted)", fontSize: 14 }}>Loading plan detail...</div>
          )}
          {!detailLoading && detail && (
            <>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                  gap: 12,
                }}
              >
                <div className="card" style={{ padding: 16 }}>
                  <div className="stack">
                    <div className="label">Legacy patient code</div>
                    <div style={{ fontSize: 16 }}>{detail.plan.legacy_patient_code}</div>
                  </div>
                </div>
                <div className="card" style={{ padding: 16 }}>
                  <div className="stack">
                    <div className="label">TP number</div>
                    <div style={{ fontSize: 16 }}>{detail.plan.legacy_tp_number}</div>
                  </div>
                </div>
                <div className="card" style={{ padding: 16 }}>
                  <div className="stack">
                    <div className="label">Created</div>
                    <div style={{ fontSize: 16 }}>
                      {formatDateTime(detail.plan.creation_date)}
                    </div>
                  </div>
                </div>
                <div className="card" style={{ padding: 16 }}>
                  <div className="stack">
                    <div className="label">Accepted</div>
                    <div style={{ fontSize: 16 }}>{detail.plan.is_accepted ? "Yes" : "No"}</div>
                  </div>
                </div>
              </div>

              <div style={{ overflowX: "auto" }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>Code</th>
                      <th>Tooth</th>
                      <th>Surface</th>
                      <th>Completed</th>
                      <th>Completed date</th>
                      <th>Patient cost</th>
                      <th>DPB cost</th>
                      <th>Disc. cost</th>
                      <th>Material</th>
                      <th>Arch</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.items.map((item) => (
                      <tr key={item.id}>
                        <td>{item.legacy_tp_item}</td>
                        <td>{item.code_id ?? "—"}</td>
                        <td>{item.tooth ?? "—"}</td>
                        <td>{item.surface ?? "—"}</td>
                        <td>{item.completed ? "Yes" : "No"}</td>
                        <td>{formatDateTime(item.completed_date)}</td>
                        <td>{formatMoney(item.patient_cost)}</td>
                        <td>{formatMoney(item.dpb_cost)}</td>
                        <td>{formatMoney(item.discretionary_cost)}</td>
                        <td>{item.material ?? "—"}</td>
                        <td>{item.arch_code ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {detail.reviews.length > 0 && (
                <div className="card" style={{ padding: 16 }}>
                  <div className="stack">
                    <div className="label">Review notes</div>
                    {detail.reviews.map((review) => (
                      <div key={review.id} style={{ color: "var(--muted)", fontSize: 14 }}>
                        {review.temporary_note || "No note"} (reviewed:{" "}
                        {review.reviewed ? "Yes" : "No"})
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
