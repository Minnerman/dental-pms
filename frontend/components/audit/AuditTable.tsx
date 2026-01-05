type AuditLogRow = {
  id: number | string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor_email: string | null;
  actor_role: string | null;
  created_at: string;
  before_json: Record<string, unknown> | null;
  after_json: Record<string, unknown> | null;
};

type AuditTableProps = {
  title: string;
  rows: AuditLogRow[];
};

function diffKeys(beforeData: Record<string, unknown> | null, afterData: Record<string, unknown> | null) {
  if (!beforeData || !afterData) return [];
  const keys = new Set([...Object.keys(beforeData), ...Object.keys(afterData)]);
  const changed: string[] = [];
  keys.forEach((key) => {
    if (beforeData[key] !== afterData[key]) {
      changed.push(key);
    }
  });
  return changed;
}

export default function AuditTable({ title, rows }: AuditTableProps) {
  return (
    <section className="card">
      <h2 style={{ marginTop: 0 }}>{title}</h2>
      {rows.length === 0 ? (
        <div className="badge">No audit events yet.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Event</th>
              <th>Entity</th>
              <th>Actor</th>
              <th>Time</th>
              <th>Summary</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const changed = diffKeys(row.before_json, row.after_json);
              const preview = changed.slice(0, 6);
              return (
                <tr key={row.id}>
                  <td>{row.action}</td>
                  <td>
                    {row.entity_type} #{row.entity_id}
                  </td>
                  <td>
                    {row.actor_email || "System"}
                    {row.actor_role ? ` · ${row.actor_role}` : ""}
                  </td>
                  <td>{new Date(row.created_at).toLocaleString()}</td>
                  <td>
                    {changed.length === 0 ? (
                      <span style={{ color: "var(--muted)" }}>—</span>
                    ) : (
                      <span>
                        {preview.join(", ")}
                        {changed.length > preview.length
                          ? ` +${changed.length - preview.length} more`
                          : ""}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
