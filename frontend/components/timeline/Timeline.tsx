import React from "react";

type TimelineItem = {
  entity_type: string;
  entity_id: string;
  action: string;
  occurred_at: string;
  actor_email?: string | null;
  actor_role?: string | null;
  summary: string;
  link?: string | null;
};

type TimelineProps = {
  items: TimelineItem[];
  title?: string;
  action?: React.ReactNode;
  limit?: number;
  compact?: boolean;
};

const filters = [
  { key: "all", label: "All" },
  { key: "patient", label: "Patient" },
  { key: "appointment", label: "Appointments" },
  { key: "note", label: "Notes" },
];

export default function Timeline({
  items,
  title = "Timeline",
  action,
  limit,
  compact = false,
}: TimelineProps) {
  const [filter, setFilter] = React.useState("all");
  const filtered = items.filter(
    (item) => filter === "all" || item.entity_type === filter
  );
  const visible = limit ? filtered.slice(0, limit) : filtered;

  return (
    <section className="card">
      {(title || action || !compact) && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          {title ? <h3 style={{ marginTop: 0 }}>{title}</h3> : <span />}
          {!compact ? (
            <div className="tab-list">
              {filters.map((f) => (
                <button
                  key={f.key}
                  className={`tab-link${filter === f.key ? " active" : ""}`}
                  onClick={() => setFilter(f.key)}
                >
                  {f.label}
                </button>
              ))}
            </div>
          ) : (
            action || null
          )}
        </div>
      )}
      {visible.length === 0 ? (
        <div className="badge">No activity yet.</div>
      ) : (
        <div className="stack" style={{ marginTop: 12 }}>
          {visible.map((item, index) => (
            <div key={`${item.entity_type}-${item.entity_id}-${index}`} className="card" style={{ margin: 0 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <div>
                  <div className="badge">
                    {item.action} · {item.entity_type}
                  </div>
                  <div style={{ marginTop: 6 }}>{item.summary}</div>
                  <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 6 }}>
                    {item.actor_email || "System"}
                    {item.actor_role ? ` · ${item.actor_role}` : ""}
                  </div>
                </div>
                <div style={{ textAlign: "right", fontSize: 12, color: "var(--muted)" }}>
                  {new Date(item.occurred_at).toLocaleString()}
                  {item.link && (
                    <div style={{ marginTop: 6 }}>
                      <a className="btn btn-secondary" href={item.link}>
                        View audit
                      </a>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
