"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";
import HeaderBar from "@/components/ui/HeaderBar";

type DocumentTemplateKind = "letter" | "prescription";

type DocumentTemplate = {
  id: number;
  name: string;
  kind: DocumentTemplateKind;
  content: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

const kindLabels: Record<DocumentTemplateKind, string> = {
  letter: "Letter",
  prescription: "Prescription",
};

function filenameFromHeader(header: string | null) {
  if (!header) return null;
  const match = /filename="([^"]+)"/.exec(header);
  return match?.[1] ?? null;
}

export default function TemplatesPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<DocumentTemplate[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [kindFilter, setKindFilter] = useState<"all" | DocumentTemplateKind>("all");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [newKind, setNewKind] = useState<DocumentTemplateKind>("letter");
  const [newContent, setNewContent] = useState("");
  const [newActive, setNewActive] = useState(true);

  const [editName, setEditName] = useState("");
  const [editKind, setEditKind] = useState<DocumentTemplateKind>("letter");
  const [editContent, setEditContent] = useState("");
  const [editActive, setEditActive] = useState(true);

  const selected = templates.find((item) => item.id === selectedId) || null;

  async function loadTemplates() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("include_inactive", "1");
      if (kindFilter !== "all") {
        params.set("kind", kindFilter);
      }
      const res = await apiFetch(`/api/document-templates?${params.toString()}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load templates (HTTP ${res.status})`);
      }
      const data = (await res.json()) as DocumentTemplate[];
      setTemplates(data);
      if (selectedId) {
        const next = data.find((item) => item.id === selectedId) || null;
        setSelectedId(next?.id ?? null);
        if (next) {
          setEditName(next.name);
          setEditKind(next.kind);
          setEditContent(next.content);
          setEditActive(next.is_active);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load templates");
    } finally {
      setLoading(false);
    }
  }

  function selectTemplate(template: DocumentTemplate) {
    setSelectedId(template.id);
    setEditName(template.name);
    setEditKind(template.kind);
    setEditContent(template.content);
    setEditActive(template.is_active);
  }

  async function createTemplate() {
    if (!newName.trim() || !newContent.trim()) {
      setError("Name and content are required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/api/document-templates", {
        method: "POST",
        body: JSON.stringify({
          name: newName.trim(),
          kind: newKind,
          content: newContent,
          is_active: newActive,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to create template (HTTP ${res.status})`);
      }
      setNewName("");
      setNewContent("");
      setNewActive(true);
      await loadTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create template");
    } finally {
      setSaving(false);
    }
  }

  async function updateTemplate() {
    if (!selected) return;
    if (!editName.trim() || !editContent.trim()) {
      setError("Name and content are required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/document-templates/${selected.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: editName.trim(),
          kind: editKind,
          content: editContent,
          is_active: editActive,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to update template (HTTP ${res.status})`);
      }
      await loadTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update template");
    } finally {
      setSaving(false);
    }
  }

  async function deleteTemplate(template: DocumentTemplate) {
    if (!confirm(`Delete "${template.name}"?`)) return;
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/document-templates/${template.id}`, {
        method: "DELETE",
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to delete template (HTTP ${res.status})`);
      }
      if (selectedId === template.id) {
        setSelectedId(null);
      }
      await loadTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete template");
    } finally {
      setSaving(false);
    }
  }

  async function downloadTemplate(template: DocumentTemplate) {
    setError(null);
    try {
      const res = await apiFetch(`/api/document-templates/${template.id}/download`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to download template (HTTP ${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const filename =
        filenameFromHeader(res.headers.get("Content-Disposition")) ||
        `${template.name}.txt`;
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download template");
    }
  }

  useEffect(() => {
    void loadTemplates();
  }, [kindFilter]);

  return (
    <div className="app-grid">
      <div className="card">
        <div className="stack">
          <HeaderBar
            title="Document templates"
            subtitle="Manage letter and prescription templates."
            actions={
              <select
                className="input"
                value={kindFilter}
                onChange={(e) => setKindFilter(e.target.value as "all" | DocumentTemplateKind)}
              >
                <option value="all">All kinds</option>
                <option value="letter">Letters</option>
                <option value="prescription">Prescriptions</option>
              </select>
            }
          />

          {loading && <div className="badge">Loading templates…</div>}
          {error && <div className="notice">{error}</div>}

          {templates.length === 0 ? (
            <div className="notice">No templates yet.</div>
          ) : (
            <table className="table table-compact table-hover">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Kind</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {templates.map((template) => (
                  <tr key={template.id}>
                    <td>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        onClick={() => selectTemplate(template)}
                      >
                        {template.name}
                      </button>
                    </td>
                    <td>{kindLabels[template.kind]}</td>
                    <td>{template.is_active ? "Active" : "Inactive"}</td>
                    <td style={{ textAlign: "right" }}>
                      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                        <button
                          className="btn btn-secondary"
                          type="button"
                          onClick={() => downloadTemplate(template)}
                        >
                          Download
                        </button>
                        <button
                          className="btn btn-secondary"
                          type="button"
                          onClick={() => deleteTemplate(template)}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="card" style={{ margin: 0 }}>
            <div className="stack">
              <h4 style={{ marginTop: 0 }}>Create template</h4>
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
                  <label className="label">Kind</label>
                  <select
                    className="input"
                    value={newKind}
                    onChange={(e) => setNewKind(e.target.value as DocumentTemplateKind)}
                  >
                    <option value="letter">Letter</option>
                    <option value="prescription">Prescription</option>
                  </select>
                </div>
              </div>
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Content</label>
                <textarea
                  className="input"
                  rows={8}
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                />
              </div>
              <label className="row" style={{ gap: 8 }}>
                <input
                  type="checkbox"
                  checked={newActive}
                  onChange={(e) => setNewActive(e.target.checked)}
                />
                <span>Active</span>
              </label>
              <button className="btn btn-primary" disabled={saving} onClick={createTemplate}>
                {saving ? "Saving..." : "Create template"}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="stack">
          <HeaderBar
            title="Edit template"
            subtitle={selected ? `Editing ${selected.name}` : "Select a template to edit."}
          />
          {!selected ? (
            <div className="notice">Choose a template from the list to edit.</div>
          ) : (
            <div className="stack">
              <div className="grid grid-2">
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">Name</label>
                  <input
                    className="input"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                  />
                </div>
                <div className="stack" style={{ gap: 8 }}>
                  <label className="label">Kind</label>
                  <select
                    className="input"
                    value={editKind}
                    onChange={(e) => setEditKind(e.target.value as DocumentTemplateKind)}
                  >
                    <option value="letter">Letter</option>
                    <option value="prescription">Prescription</option>
                  </select>
                </div>
              </div>
              <div className="stack" style={{ gap: 8 }}>
                <label className="label">Content</label>
                <textarea
                  className="input"
                  rows={12}
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                />
              </div>
              <label className="row" style={{ gap: 8 }}>
                <input
                  type="checkbox"
                  checked={editActive}
                  onChange={(e) => setEditActive(e.target.checked)}
                />
                <span>Active</span>
              </label>
              <div className="row">
                <button className="btn btn-primary" disabled={saving} onClick={updateTemplate}>
                  {saving ? "Saving..." : "Save changes"}
                </button>
                <button
                  className="btn btn-secondary"
                  type="button"
                  onClick={() => selected && downloadTemplate(selected)}
                >
                  Download
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
