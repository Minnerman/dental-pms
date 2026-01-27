"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearToken } from "@/lib/auth";

type PracticeProfile = {
  name?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  postcode?: string | null;
  phone?: string | null;
  website?: string | null;
  email?: string | null;
};

const emptyProfile: PracticeProfile = {
  name: "",
  address_line1: "",
  address_line2: "",
  city: "",
  postcode: "",
  phone: "",
  website: "",
  email: "",
};

export default function PracticeProfileSettingsPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<PracticeProfile>({ ...emptyProfile });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/api/settings/profile");
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load practice profile (HTTP ${res.status})`);
      }
      const data = (await res.json()) as PracticeProfile;
      setProfile({ ...emptyProfile, ...data });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load practice profile");
    } finally {
      setLoading(false);
    }
  }, [router]);

  async function saveProfile() {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const res = await apiFetch("/api/settings/profile", {
        method: "PUT",
        body: JSON.stringify(profile),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to save practice profile (HTTP ${res.status})`);
      }
      setNotice("Practice profile saved.");
      const data = (await res.json()) as PracticeProfile;
      setProfile({ ...emptyProfile, ...data });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save practice profile");
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    void loadProfile();
  }, [loadProfile]);

  return (
    <div className="app-grid">
      <div className="card">
        <div className="stack">
          <div>
            <h2 style={{ marginTop: 0 }}>Practice profile</h2>
            <div style={{ color: "var(--muted)" }}>
              Update letterhead details for PDF documents.
            </div>
          </div>
          {loading && <div className="badge">Loading profile…</div>}
          {error && <div className="notice">{error}</div>}
          {notice && <div className="badge">{notice}</div>}

          <div className="grid grid-2">
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Practice name</label>
              <input
                className="input"
                value={profile.name ?? ""}
                onChange={(e) => setProfile((prev) => ({ ...prev, name: e.target.value }))}
              />
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Phone</label>
              <input
                className="input"
                value={profile.phone ?? ""}
                onChange={(e) => setProfile((prev) => ({ ...prev, phone: e.target.value }))}
              />
            </div>
          </div>

          <div className="grid grid-2">
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Address line 1</label>
              <input
                className="input"
                value={profile.address_line1 ?? ""}
                onChange={(e) =>
                  setProfile((prev) => ({ ...prev, address_line1: e.target.value }))
                }
              />
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Address line 2</label>
              <input
                className="input"
                value={profile.address_line2 ?? ""}
                onChange={(e) =>
                  setProfile((prev) => ({ ...prev, address_line2: e.target.value }))
                }
              />
            </div>
          </div>

          <div className="grid grid-2">
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">City</label>
              <input
                className="input"
                value={profile.city ?? ""}
                onChange={(e) => setProfile((prev) => ({ ...prev, city: e.target.value }))}
              />
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Postcode</label>
              <input
                className="input"
                value={profile.postcode ?? ""}
                onChange={(e) =>
                  setProfile((prev) => ({ ...prev, postcode: e.target.value }))
                }
              />
            </div>
          </div>

          <div className="grid grid-2">
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Website</label>
              <input
                className="input"
                value={profile.website ?? ""}
                onChange={(e) =>
                  setProfile((prev) => ({ ...prev, website: e.target.value }))
                }
              />
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <label className="label">Email</label>
              <input
                className="input"
                value={profile.email ?? ""}
                onChange={(e) => setProfile((prev) => ({ ...prev, email: e.target.value }))}
              />
            </div>
          </div>

          <button className="btn btn-primary" disabled={saving} onClick={saveProfile}>
            {saving ? "Saving..." : "Save profile"}
          </button>
        </div>
      </div>
    </div>
  );
}
