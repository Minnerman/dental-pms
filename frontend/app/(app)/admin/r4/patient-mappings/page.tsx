"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import HeaderBar from "@/components/ui/HeaderBar";
import { apiFetch, clearToken } from "@/lib/auth";

type UnmappedPlanPatientCode = {
  legacy_patient_code: number;
  plan_count: number;
};

type PatientSearch = {
  id: number;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  phone?: string | null;
};

type BackfillResponse = {
  processed: number;
  updated: number;
  remaining_estimate: number | null;
  dry_run: boolean;
};

function formatPatientLabel(patient: PatientSearch) {
  const dob = patient.date_of_birth ? ` (${patient.date_of_birth})` : "";
  return `${patient.last_name}, ${patient.first_name}${dob}`;
}

export default function R4PatientMappingsAdminPage() {
  const router = useRouter();
  const [items, setItems] = useState<UnmappedPlanPatientCode[]>([]);
  const [legacyPatientCode, setLegacyPatientCode] = useState("");
  const [limit, setLimit] = useState(50);
  const [selectedCode, setSelectedCode] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [patientQuery, setPatientQuery] = useState("");
  const [patientOptions, setPatientOptions] = useState<PatientSearch[]>([]);
  const [patientLoading, setPatientLoading] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState<PatientSearch | null>(null);
  const [mappingNotes, setMappingNotes] = useState("");
  const [mappingError, setMappingError] = useState<string | null>(null);
  const [backfillLimit, setBackfillLimit] = useState(500);
  const [backfillResult, setBackfillResult] = useState<BackfillResponse | null>(null);
  const [backfillError, setBackfillError] = useState<string | null>(null);
  const [backfillLoading, setBackfillLoading] = useState(false);
  const [showBackfillCommand, setShowBackfillCommand] = useState(false);
  const [backfillNotice, setBackfillNotice] = useState<string | null>(null);

  const queryString = useMemo(() => {
    const params = new URLSearchParams({
      limit: String(limit),
    });
    if (legacyPatientCode.trim()) {
      params.set("legacy_patient_code", legacyPatientCode.trim());
    }
    return params.toString();
  }, [legacyPatientCode, limit]);

  const loadUnmapped = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const res = await apiFetch(`/api/admin/r4/patient-mappings/unmapped-plans?${queryString}`);
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.status === 403) {
        setError("Only admins can access R4 patient mappings.");
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load unmapped codes (HTTP ${res.status})`);
      }
      const data = (await res.json()) as UnmappedPlanPatientCode[];
      setItems(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load unmapped codes");
    } finally {
      setLoading(false);
    }
  }, [queryString, router]);

  useEffect(() => {
    void loadUnmapped();
  }, [loadUnmapped]);

  useEffect(() => {
    const trimmed = patientQuery.trim();
    if (!selectedCode) return;
    if (selectedPatient && trimmed === formatPatientLabel(selectedPatient)) return;
    if (trimmed.length < 2) {
      setPatientOptions([]);
      setSelectedPatient(null);
      return;
    }
    const timeout = window.setTimeout(async () => {
      setPatientLoading(true);
      setMappingError(null);
      try {
        const params = new URLSearchParams({ q: trimmed, limit: "10" });
        const res = await apiFetch(`/api/patients/search?${params.toString()}`);
        if (res.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        if (!res.ok) {
          throw new Error(`Patient search failed (HTTP ${res.status})`);
        }
        const data = (await res.json()) as PatientSearch[];
        setPatientOptions(data);
      } catch (err) {
        setMappingError(err instanceof Error ? err.message : "Patient search failed");
      } finally {
        setPatientLoading(false);
      }
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [patientQuery, selectedCode, selectedPatient, router]);

  const startMapping = useCallback((code: number) => {
    setSelectedCode(code);
    setPatientQuery("");
    setPatientOptions([]);
    setSelectedPatient(null);
    setMappingNotes("");
    setMappingError(null);
  }, []);

  const cancelMapping = useCallback(() => {
    setSelectedCode(null);
    setPatientQuery("");
    setPatientOptions([]);
    setSelectedPatient(null);
    setMappingNotes("");
    setMappingError(null);
  }, []);

  const submitMapping = useCallback(async () => {
    if (!selectedCode) return;
    if (!selectedPatient) {
      setMappingError("Select a patient to link.");
      return;
    }
    setCreating(true);
    setMappingError(null);
    try {
      const res = await apiFetch("/api/admin/r4/patient-mappings", {
        method: "POST",
        body: JSON.stringify({
          legacy_patient_code: selectedCode,
          patient_id: selectedPatient.id,
          notes: mappingNotes.trim() || null,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.status === 403) {
        setMappingError("Only admins can create R4 patient mappings.");
        return;
      }
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Failed to create mapping (HTTP ${res.status})`);
      }
      setNotice("Mapping created.");
      cancelMapping();
      await loadUnmapped();
    } catch (err) {
      setMappingError(err instanceof Error ? err.message : "Failed to create mapping");
    } finally {
      setCreating(false);
    }
  }, [selectedCode, selectedPatient, mappingNotes, loadUnmapped, cancelMapping, router]);

  const backfillCommand =
    "docker compose exec -T backend python -m app.scripts.r4_import --entity treatment_plans_backfill_patient_ids --apply --confirm APPLY";

  const handleBackfill = useCallback(async () => {
    const apply = backfillResult?.dry_run === true && backfillResult.processed > 0;
    setBackfillLoading(true);
    setBackfillError(null);
    setBackfillNotice(null);
    try {
      const res = await apiFetch("/api/admin/r4/patient-mappings/backfill-patient-ids", {
        method: "POST",
        body: JSON.stringify({
          limit: backfillLimit,
          dry_run: !apply,
          only_unmapped: true,
        }),
      });
      if (res.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (res.status === 403) {
        setBackfillError("Only admins can run R4 backfill.");
        return;
      }
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Backfill failed (HTTP ${res.status})`);
      }
      const data = (await res.json()) as BackfillResponse;
      setBackfillResult(data);
    } catch (err) {
      setBackfillError(err instanceof Error ? err.message : "Backfill failed");
    } finally {
      setBackfillLoading(false);
    }
  }, [backfillLimit, backfillResult, router]);

  const handleBackfillCommand = useCallback(() => {
    setShowBackfillCommand(true);
    setBackfillNotice(null);
    if (navigator.clipboard?.writeText) {
      navigator.clipboard
        .writeText(backfillCommand)
        .then(() => setBackfillNotice("Backfill command copied to clipboard."))
        .catch(() => setBackfillNotice("Backfill command ready to copy below."));
    } else {
      setBackfillNotice("Backfill command ready to copy below.");
    }
  }, [backfillCommand]);

  return (
    <div className="app-grid">
      <div className="card">
        <div className="stack">
          <HeaderBar
            title="R4 patient mappings"
            subtitle="Link legacy patient codes to active patients."
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
                  value={limit}
                  min={1}
                  max={500}
                  onChange={(e) => setLimit(Number(e.target.value))}
                  style={{ width: 120 }}
                />
                <button className="btn btn-secondary" type="button" onClick={loadUnmapped}>
                  Refresh
                </button>
              </div>
            }
          />

          {loading && <div className="badge">Loading unmapped codes…</div>}
          {notice && <div className="notice">{notice}</div>}
          {error && <div className="notice">{error}</div>}

          {!loading && items.length === 0 ? (
            <div className="notice">No unmapped legacy patient codes.</div>
          ) : (
            <table className="table table-compact table-hover">
              <thead>
                <tr>
                  <th>Legacy patient code</th>
                  <th>Unmapped plans</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.legacy_patient_code}>
                    <td>{item.legacy_patient_code}</td>
                    <td>{item.plan_count}</td>
                    <td style={{ textAlign: "right" }}>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        onClick={() => startMapping(item.legacy_patient_code)}
                      >
                        Map
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="card">
        <div className="stack">
          <HeaderBar
            title="Create mapping"
            subtitle={
              selectedCode
                ? `Legacy patient code ${selectedCode}`
                : "Select a legacy patient code to link."
            }
          />

          {selectedCode ? (
            <>
              <label className="stack">
                <span>Search patient</span>
                <input
                  className="input"
                  placeholder="Search by name, phone, or DOB..."
                  value={patientQuery}
                  onChange={(e) => setPatientQuery(e.target.value)}
                />
              </label>
              {patientLoading && <div className="badge">Searching patients…</div>}
              {patientOptions.length > 0 && (
                <div className="card" style={{ margin: 0 }}>
                  <div className="stack">
                    {patientOptions.map((patient) => (
                      <button
                        key={patient.id}
                        className={
                          selectedPatient?.id === patient.id
                            ? "btn btn-primary"
                            : "btn btn-secondary"
                        }
                        type="button"
                        onClick={() => {
                          setSelectedPatient(patient);
                          setPatientQuery(formatPatientLabel(patient));
                          setPatientOptions([]);
                        }}
                      >
                        {formatPatientLabel(patient)}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {selectedPatient && (
                <div className="notice">Linking to: {formatPatientLabel(selectedPatient)}</div>
              )}

              <label className="stack">
                <span>Notes (optional)</span>
                <textarea
                  className="input"
                  rows={3}
                  value={mappingNotes}
                  onChange={(e) => setMappingNotes(e.target.value)}
                />
              </label>

              {mappingError && <div className="notice">{mappingError}</div>}

              <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
                <button className="btn btn-secondary" type="button" onClick={cancelMapping}>
                  Cancel
                </button>
                <button
                  className="btn btn-primary"
                  type="button"
                  onClick={submitMapping}
                  disabled={creating || !selectedPatient}
                >
                  {creating ? "Creating..." : "Create mapping"}
                </button>
              </div>
            </>
          ) : (
            <div className="notice">Pick a code from the table to start mapping.</div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="stack">
          <HeaderBar
            title="Backfill treatment plans"
            subtitle="Apply mappings to existing R4 treatment plans."
          />
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <input
              className="input"
              type="number"
              min={1}
              max={5000}
              value={backfillLimit}
              onChange={(e) => setBackfillLimit(Number(e.target.value))}
              style={{ width: 140 }}
            />
            <button
              className="btn btn-primary"
              type="button"
              onClick={handleBackfill}
              disabled={backfillLoading}
            >
              {backfillLoading
                ? "Running..."
                : backfillResult?.dry_run && backfillResult.processed > 0
                  ? "Apply backfill"
                  : "Run backfill (dry run)"}
            </button>
            <button
              className="btn btn-secondary"
              type="button"
              onClick={handleBackfillCommand}
            >
              Copy CLI command
            </button>
          </div>
          {backfillResult && (
            <div className="notice">
              {backfillResult.dry_run
                ? `Dry run: would update ${backfillResult.processed} plans.`
                : `Updated ${backfillResult.updated} plans.`}{" "}
              {backfillResult.remaining_estimate !== null
                ? `Remaining estimate: ${backfillResult.remaining_estimate}.`
                : null}
            </div>
          )}
          {backfillError && <div className="notice">{backfillError}</div>}
          {backfillNotice && <div className="notice">{backfillNotice}</div>}
          {showBackfillCommand && (
            <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{backfillCommand}</pre>
          )}
          <div style={{ color: "var(--muted)", fontSize: 13 }}>
            Backfill runs in chunks (default 500). Repeat until remaining estimate is 0.
          </div>
        </div>
      </div>
    </div>
  );
}
