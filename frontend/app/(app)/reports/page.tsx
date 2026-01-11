"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";

type FinanceCashup = {
  range: { from: string; to: string };
  totals_by_method: Record<string, number>;
  total_pence: number;
  daily: {
    date: string;
    total_pence: number;
    totals_by_method: Record<string, number>;
  }[];
};

type OutstandingReport = {
  as_of: string;
  total_outstanding_pence: number;
  count_patients_with_balance: number;
  top_debtors: { patient_id: number; patient_name: string; balance_pence: number }[];
};

type FinanceTrends = {
  days: number;
  series: { date: string; payments_pence: number; charges_pence: number; net_pence: number }[];
};

type RangePreset = 7 | 30 | 90;

export default function ReportsPage() {
  const router = useRouter();
  const [rangePreset, setRangePreset] = useState<RangePreset>(30);
  const [cashup, setCashup] = useState<FinanceCashup | null>(null);
  const [outstanding, setOutstanding] = useState<OutstandingReport | null>(null);
  const [trends, setTrends] = useState<FinanceTrends | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function formatCurrency(pence: number) {
    return new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency: "GBP",
    }).format(pence / 100);
  }

  function buildRange(days: number) {
    const end = new Date();
    const endDate = new Date(end.getFullYear(), end.getMonth(), end.getDate());
    const start = new Date(endDate);
    start.setDate(start.getDate() - (days - 1));
    return {
      start: start.toISOString().slice(0, 10),
      end: endDate.toISOString().slice(0, 10),
    };
  }

  async function loadReports(days: number) {
    setLoading(true);
    setError(null);
    try {
      const range = buildRange(days);
      const cashupParams = new URLSearchParams({ start: range.start, end: range.end });
      const trendParams = new URLSearchParams({ days: String(days) });
      const [cashupRes, outstandingRes, trendsRes] = await Promise.all([
        apiFetch(`/api/reports/finance/cashup?${cashupParams.toString()}`),
        apiFetch(`/api/reports/finance/outstanding`),
        apiFetch(`/api/reports/finance/trends?${trendParams.toString()}`),
      ]);
      if ([cashupRes, outstandingRes, trendsRes].some((res) => res.status === 401)) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!cashupRes.ok) {
        throw new Error(`Failed to load cash-up (HTTP ${cashupRes.status})`);
      }
      if (!outstandingRes.ok) {
        throw new Error(`Failed to load outstanding balances (HTTP ${outstandingRes.status})`);
      }
      if (!trendsRes.ok) {
        throw new Error(`Failed to load trends (HTTP ${trendsRes.status})`);
      }
      setCashup((await cashupRes.json()) as FinanceCashup);
      setOutstanding((await outstandingRes.json()) as OutstandingReport);
      setTrends((await trendsRes.json()) as FinanceTrends);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reports");
    } finally {
      setLoading(false);
    }
  }

  function downloadCsv(filename: string, rows: string[][]) {
    const content = rows.map((row) => row.map((cell) => `"${cell}"`).join(",")).join("\n");
    const blob = new Blob([content], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  useEffect(() => {
    void loadReports(rangePreset);
  }, [rangePreset]);

  return (
    <div className="app-grid">
      <div className="card">
        <div className="stack">
          <div className="row">
            <div>
              <h2 style={{ marginTop: 0 }}>Financial reports</h2>
              <div style={{ color: "var(--muted)" }}>
                Cash-up summaries, outstanding balances, and trends.
              </div>
            </div>
            <div className="row" style={{ gap: 8 }}>
              {[7, 30, 90].map((days) => (
                <button
                  key={days}
                  className="btn btn-secondary"
                  type="button"
                  onClick={() => setRangePreset(days as RangePreset)}
                >
                  {days}d
                </button>
              ))}
            </div>
          </div>

          {loading && <div className="badge">Loading reports…</div>}
          {error && <div className="notice">{error}</div>}

          {cashup && (
            <div className="card" style={{ margin: 0 }}>
              <div className="stack">
                <div className="row" style={{ alignItems: "center" }}>
                  <h4 style={{ margin: 0 }}>Cash-up summary</h4>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    onClick={() =>
                      downloadCsv(
                        `cashup_${cashup.range.from}_${cashup.range.to}.csv`,
                        [
                          ["Date", "Total", "Cash", "Card", "Bank transfer", "Other"],
                          ...cashup.daily.map((day) => [
                            day.date,
                            formatCurrency(day.total_pence),
                            formatCurrency(day.totals_by_method.cash || 0),
                            formatCurrency(day.totals_by_method.card || 0),
                            formatCurrency(day.totals_by_method.bank_transfer || 0),
                            formatCurrency(day.totals_by_method.other || 0),
                          ]),
                        ]
                      )
                    }
                  >
                    Export CSV
                  </button>
                </div>
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
                      {formatCurrency(cashup.total_pence)}
                    </div>
                  </div>
                  {["cash", "card", "bank_transfer", "other"].map((method) => (
                    <div key={method} className="card" style={{ margin: 0 }}>
                      <div className="label">{method.replace("_", " ")}</div>
                      <div style={{ fontSize: 20, fontWeight: 700 }}>
                        {formatCurrency(cashup.totals_by_method[method] || 0)}
                      </div>
                    </div>
                  ))}
                </div>
                <table className="table table-compact table-hover">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Total</th>
                      <th>Cash</th>
                      <th>Card</th>
                      <th>Bank transfer</th>
                      <th>Other</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cashup.daily.map((day) => (
                      <tr key={day.date}>
                        <td>{day.date}</td>
                        <td>{formatCurrency(day.total_pence)}</td>
                        <td>{formatCurrency(day.totals_by_method.cash || 0)}</td>
                        <td>{formatCurrency(day.totals_by_method.card || 0)}</td>
                        <td>{formatCurrency(day.totals_by_method.bank_transfer || 0)}</td>
                        <td>{formatCurrency(day.totals_by_method.other || 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {outstanding && (
            <div className="card" style={{ margin: 0 }}>
              <div className="stack">
                <div className="row" style={{ alignItems: "center" }}>
                  <h4 style={{ margin: 0 }}>Outstanding balances</h4>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    onClick={() =>
                      downloadCsv(
                        `outstanding_${outstanding.as_of}.csv`,
                        [
                          ["Patient", "Balance"],
                          ...outstanding.top_debtors.map((row) => [
                            row.patient_name,
                            formatCurrency(row.balance_pence),
                          ]),
                        ]
                      )
                    }
                  >
                    Export CSV
                  </button>
                </div>
                <div className="grid grid-3">
                  <div className="card" style={{ margin: 0 }}>
                    <div className="label">Total outstanding</div>
                    <div style={{ fontSize: 20, fontWeight: 700 }}>
                      {formatCurrency(outstanding.total_outstanding_pence)}
                    </div>
                  </div>
                  <div className="card" style={{ margin: 0 }}>
                    <div className="label">Patients with balance</div>
                    <div style={{ fontSize: 20, fontWeight: 700 }}>
                      {outstanding.count_patients_with_balance}
                    </div>
                  </div>
                </div>
                {outstanding.top_debtors.length === 0 ? (
                  <div className="notice">No outstanding balances.</div>
                ) : (
                  <table className="table table-compact table-hover">
                    <thead>
                      <tr>
                        <th>Patient</th>
                        <th>Balance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {outstanding.top_debtors.map((row) => (
                        <tr key={row.patient_id}>
                          <td>
                            <button
                              className="btn btn-secondary"
                              onClick={() => router.push(`/patients/${row.patient_id}`)}
                            >
                              {row.patient_name}
                            </button>
                          </td>
                          <td>{formatCurrency(row.balance_pence)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}

          {trends && (
            <div className="card" style={{ margin: 0 }}>
              <div className="stack">
                <h4 style={{ margin: 0 }}>Trends (payments/charges/net)</h4>
                <table className="table table-compact table-hover">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Payments</th>
                      <th>Charges</th>
                      <th>Net</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trends.series.map((row) => (
                      <tr key={row.date}>
                        <td>{row.date}</td>
                        <td>{formatCurrency(row.payments_pence)}</td>
                        <td>{formatCurrency(row.charges_pence)}</td>
                        <td>{formatCurrency(row.net_pence)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
