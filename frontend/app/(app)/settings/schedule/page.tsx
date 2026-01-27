"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";

type PracticeHour = {
  day_of_week: number;
  start_time: string | null;
  end_time: string | null;
  is_closed: boolean;
};

type PracticeClosure = {
  start_date: string;
  end_date: string;
  reason: string | null;
};

type PracticeOverride = {
  date: string;
  start_time: string | null;
  end_time: string | null;
  is_closed: boolean;
  reason: string | null;
};

type SchedulePayload = {
  hours: PracticeHour[];
  closures: PracticeClosure[];
  overrides: PracticeOverride[];
};

const dayLabels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function toTimeInput(value: string | null) {
  if (!value) return "";
  return value.slice(0, 5);
}

function fromTimeInput(value: string) {
  return value ? value : null;
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export default function ScheduleSettingsPage() {
  const router = useRouter();
  const [hours, setHours] = useState<PracticeHour[]>([]);
  const [closures, setClosures] = useState<PracticeClosure[]>([]);
  const [overrides, setOverrides] = useState<PracticeOverride[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const hoursByDay = useMemo(() => {
    const byDay: Record<number, PracticeHour> = {};
    hours.forEach((entry) => {
      byDay[entry.day_of_week] = entry;
    });
    return byDay;
  }, [hours]);

  const loadSchedule = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/api/settings/schedule");
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load schedule (HTTP ${res.status})`);
      }
      const data = (await res.json()) as SchedulePayload;
      setHours(
        data.hours.map((entry) => ({
          ...entry,
          start_time: toTimeInput(entry.start_time),
          end_time: toTimeInput(entry.end_time),
        }))
      );
      setClosures(data.closures);
      setOverrides(
        data.overrides.map((entry) => ({
          ...entry,
          start_time: toTimeInput(entry.start_time),
          end_time: toTimeInput(entry.end_time),
        }))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load schedule");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void loadSchedule();
  }, [loadSchedule]);

  function updateHour(dayIndex: number, patch: Partial<PracticeHour>) {
    setHours((prev) =>
      prev.map((entry) =>
        entry.day_of_week === dayIndex ? { ...entry, ...patch } : entry
      )
    );
  }

  function addClosure() {
    setClosures((prev) => [
      ...prev,
      { start_date: todayIso(), end_date: todayIso(), reason: null },
    ]);
  }

  function addOverride() {
    setOverrides((prev) => [
      ...prev,
      {
        date: todayIso(),
        start_time: "09:00",
        end_time: "13:00",
        is_closed: false,
        reason: null,
      },
    ]);
  }

  async function saveSchedule() {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const payload: SchedulePayload = {
        hours: hours.map((entry) => ({
          ...entry,
          start_time: entry.is_closed ? null : fromTimeInput(entry.start_time || ""),
          end_time: entry.is_closed ? null : fromTimeInput(entry.end_time || ""),
        })),
        closures,
        overrides: overrides.map((entry) => ({
          ...entry,
          start_time: entry.is_closed ? null : fromTimeInput(entry.start_time || ""),
          end_time: entry.is_closed ? null : fromTimeInput(entry.end_time || ""),
        })),
      };
      const res = await apiFetch("/api/settings/schedule", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const message = await res.text();
        throw new Error(message || `Failed to save schedule (HTTP ${res.status})`);
      }
      setNotice("Schedule saved.");
      await loadSchedule();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save schedule");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="card" style={{ display: "grid", gap: 16 }}>
      <div>
        <h2 style={{ marginTop: 0 }}>Practice schedule</h2>
        <p style={{ color: "var(--muted)", marginBottom: 0 }}>
          Set weekly hours, closures, and one-off overrides for domiciliary runs.
        </p>
      </div>

      {error && <div className="notice">{error}</div>}
      {notice && <div className="notice">{notice}</div>}

      {loading ? (
        <div className="badge">Loading schedule…</div>
      ) : (
        <>
          <div className="card" style={{ margin: 0 }}>
            <h3 style={{ marginTop: 0 }}>Weekly hours</h3>
            <div className="stack">
              {dayLabels.map((label, idx) => {
                const entry = hoursByDay[idx];
                return (
                  <div
                    key={label}
                    style={{ display: "grid", gap: 12, gridTemplateColumns: "1.2fr 1fr 1fr 1fr" }}
                  >
                    <div style={{ fontWeight: 600 }}>{label}</div>
                    <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <input
                        type="checkbox"
                        checked={entry?.is_closed ?? false}
                        onChange={(e) =>
                          updateHour(idx, {
                            day_of_week: idx,
                            is_closed: e.target.checked,
                          })
                        }
                      />
                      Closed
                    </label>
                    <input
                      className="input"
                      type="time"
                      value={entry?.start_time ?? ""}
                      disabled={entry?.is_closed}
                      onChange={(e) =>
                        updateHour(idx, {
                          day_of_week: idx,
                          start_time: e.target.value,
                        })
                      }
                    />
                    <input
                      className="input"
                      type="time"
                      value={entry?.end_time ?? ""}
                      disabled={entry?.is_closed}
                      onChange={(e) =>
                        updateHour(idx, {
                          day_of_week: idx,
                          end_time: e.target.value,
                        })
                      }
                    />
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card" style={{ margin: 0 }}>
            <div className="row">
              <h3 style={{ marginTop: 0 }}>Closures</h3>
              <button className="btn btn-secondary" onClick={addClosure}>
                Add closure
              </button>
            </div>
            <div className="stack">
              {closures.length === 0 && <div className="notice">No closures set.</div>}
              {closures.map((entry, idx) => (
                <div
                  key={`${entry.start_date}-${idx}`}
                  style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr 1.5fr auto" }}
                >
                  <input
                    className="input"
                    type="date"
                    value={entry.start_date}
                    onChange={(e) =>
                      setClosures((prev) =>
                        prev.map((item, i) =>
                          i === idx ? { ...item, start_date: e.target.value } : item
                        )
                      )
                    }
                  />
                  <input
                    className="input"
                    type="date"
                    value={entry.end_date}
                    onChange={(e) =>
                      setClosures((prev) =>
                        prev.map((item, i) =>
                          i === idx ? { ...item, end_date: e.target.value } : item
                        )
                      )
                    }
                  />
                  <input
                    className="input"
                    placeholder="Reason"
                    value={entry.reason ?? ""}
                    onChange={(e) =>
                      setClosures((prev) =>
                        prev.map((item, i) =>
                          i === idx ? { ...item, reason: e.target.value || null } : item
                        )
                      )
                    }
                  />
                  <button
                    className="btn btn-secondary"
                    onClick={() =>
                      setClosures((prev) => prev.filter((_, i) => i !== idx))
                    }
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="card" style={{ margin: 0 }}>
            <div className="row">
              <h3 style={{ marginTop: 0 }}>Overrides</h3>
              <button className="btn btn-secondary" onClick={addOverride}>
                Add override
              </button>
            </div>
            <div className="stack">
              {overrides.length === 0 && <div className="notice">No overrides set.</div>}
              {overrides.map((entry, idx) => (
                <div
                  key={`${entry.date}-${idx}`}
                  style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr 1fr 1.5fr auto" }}
                >
                  <input
                    className="input"
                    type="date"
                    value={entry.date}
                    onChange={(e) =>
                      setOverrides((prev) =>
                        prev.map((item, i) => (i === idx ? { ...item, date: e.target.value } : item))
                      )
                    }
                  />
                  <input
                    className="input"
                    type="time"
                    value={entry.start_time ?? ""}
                    disabled={entry.is_closed}
                    onChange={(e) =>
                      setOverrides((prev) =>
                        prev.map((item, i) =>
                          i === idx ? { ...item, start_time: e.target.value || null } : item
                        )
                      )
                    }
                  />
                  <input
                    className="input"
                    type="time"
                    value={entry.end_time ?? ""}
                    disabled={entry.is_closed}
                    onChange={(e) =>
                      setOverrides((prev) =>
                        prev.map((item, i) =>
                          i === idx ? { ...item, end_time: e.target.value || null } : item
                        )
                      )
                    }
                  />
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <input
                        type="checkbox"
                        checked={entry.is_closed}
                        onChange={(e) =>
                          setOverrides((prev) =>
                            prev.map((item, i) =>
                              i === idx ? { ...item, is_closed: e.target.checked } : item
                            )
                          )
                        }
                      />
                      Closed
                    </label>
                    <input
                      className="input"
                      placeholder="Reason"
                      value={entry.reason ?? ""}
                      onChange={(e) =>
                        setOverrides((prev) =>
                          prev.map((item, i) =>
                            i === idx ? { ...item, reason: e.target.value || null } : item
                          )
                        )
                      }
                    />
                  </div>
                  <button
                    className="btn btn-secondary"
                    onClick={() =>
                      setOverrides((prev) => prev.filter((_, i) => i !== idx))
                    }
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </div>

          <button className="btn btn-primary" disabled={saving} onClick={saveSchedule}>
            {saving ? "Saving..." : "Save schedule"}
          </button>
        </>
      )}
    </section>
  );
}
