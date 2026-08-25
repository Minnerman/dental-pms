"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";

type PaymentMethod = "cash" | "card" | "bank_transfer" | "other";

type CashupPayment = {
  id: number;
  patient_id: number;
  patient_first_name: string;
  patient_last_name: string;
  method?: PaymentMethod | null;
  amount_pence: number;
  reference?: string | null;
  note?: string | null;
  created_at: string;
};

type CashupReport = {
  date: string;
  totals_by_method: Record<string, number>;
  total_pence: number;
  payments: CashupPayment[];
};

export default function CashupPage() {
  const router = useRouter();
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [report, setReport] = useState<CashupReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [capabilities, setCapabilities] = useState<string[] | null>(null);
  const [capabilityError, setCapabilityError] = useState<string | null>(null);
  const canViewCashup = Boolean(
    capabilities?.includes("billing.view") && capabilities?.includes("billing.cashup")
  );

  function formatCurrency(pence: number) {
    return new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency: "GBP",
    }).format(pence / 100);
  }

  const loadReport = useCallback(async (targetDate: string) => {
    if (!canViewCashup) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("date", targetDate);
      const res = await apiFetch(`/api/reports/cashup?${params.toString()}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(
          res.status === 403
            ? "You do not have permission to view cash-up reports."
            : "Failed to load cash-up."
        );
      }
      const data = (await res.json()) as CashupReport;
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cash-up");
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, [canViewCashup, router]);

  const loadCapabilities = useCallback(async () => {
    setCapabilityError(null);
    try {
      const res = await apiFetch("/api/me/capabilities");
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error("Cash-up permissions could not be verified.");
      }
      setCapabilities((await res.json()) as string[]);
    } catch (caught) {
      setCapabilities([]);
      setCapabilityError(
        caught instanceof Error
          ? caught.message
          : "Cash-up permissions could not be verified."
      );
    }
  }, [router]);

  useEffect(() => {
    void loadCapabilities();
  }, [loadCapabilities]);

  useEffect(() => {
    if (canViewCashup) void loadReport(date);
  }, [canViewCashup, date, loadReport]);

  return (
    <div className="app-grid">
      <div className="card">
        <div className="stack">
          <div className="row">
            <div>
              <h2 style={{ marginTop: 0 }}>Cash-up</h2>
              <div style={{ color: "var(--muted)" }}>
                Daily payment totals by method.
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                className="input"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                disabled={!canViewCashup}
              />
              <button
                className="btn btn-secondary"
                onClick={() => void loadReport(date)}
                disabled={!canViewCashup}
              >
                Refresh
              </button>
            </div>
          </div>

          {capabilities === null && <div className="badge">Checking cash-up permissions…</div>}
          {capabilities !== null && !canViewCashup && (
            <div className="notice">
              {capabilityError || "You do not have permission to view cash-up reports."}
            </div>
          )}
          {loading && <div className="badge">Loading cash-up…</div>}
          {error && <div className="notice">{error}</div>}

          {canViewCashup && report && (
            <>
              <div
                style={{
                  display: "grid",
                  gap: 12,
                  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                }}
              >
                <div className="card" style={{ margin: 0 }}>
                  <div className="label">Total</div>
                  <div style={{ fontSize: 20, fontWeight: 700 }}>
                    {formatCurrency(report.total_pence)}
                  </div>
                </div>
                {["cash", "card", "bank_transfer", "other"].map((method) => (
                  <div key={method} className="card" style={{ margin: 0 }}>
                    <div className="label">{method.replace("_", " ")}</div>
                    <div style={{ fontSize: 20, fontWeight: 700 }}>
                      {formatCurrency(report.totals_by_method[method] || 0)}
                    </div>
                  </div>
                ))}
              </div>

              {report.payments.length === 0 ? (
                <div className="notice">No payments recorded for this date.</div>
              ) : (
                <table className="table table-compact table-hover table-sticky">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Patient</th>
                      <th>Method</th>
                      <th>Amount</th>
                      <th>Reference</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.payments.map((payment) => (
                      <tr key={payment.id}>
                        <td>
                          {new Date(payment.created_at).toLocaleTimeString("en-GB", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </td>
                        <td>
                          <button
                            className="btn btn-secondary"
                            onClick={() => router.push(`/patients/${payment.patient_id}`)}
                          >
                            {payment.patient_last_name.toUpperCase()}, {payment.patient_first_name}
                          </button>
                        </td>
                        <td>{payment.method || "other"}</td>
                        <td>{formatCurrency(payment.amount_pence)}</td>
                        <td>
                          {payment.reference || "—"}
                          {payment.note ? ` · ${payment.note}` : ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
