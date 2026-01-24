import { notFound } from "next/navigation";

import PatientDetailClient from "../PatientDetailClient";
import { requireNumericParam } from "@/lib/params";
import { requirePatientOrNotFound } from "../requirePatient";

export const dynamic = "force-dynamic";

function resolveApiBase() {
  const publicBase = process.env.NEXT_PUBLIC_API_BASE ?? "/api";
  if (publicBase.startsWith("http")) {
    return publicBase.replace(/\/$/, "");
  }
  return "http://backend:8000";
}

export default async function Page({
  params,
}: {
  params: { id?: string | string[] };
}) {
  let chartingEnabled = process.env.NEXT_PUBLIC_FEATURE_CHARTING_VIEWER === "1";
  try {
    const res = await fetch(`${resolveApiBase()}/config`, { cache: "no-store" });
    if (res.ok) {
      const data = (await res.json()) as {
        feature_flags?: { charting_viewer?: boolean };
      };
      if (typeof data?.feature_flags?.charting_viewer === "boolean") {
        chartingEnabled = data.feature_flags.charting_viewer;
      }
    }
  } catch {
    // Keep env fallback on fetch failure.
  }
  if (!chartingEnabled) {
    notFound();
  }

  const id = requireNumericParam("id", params?.id);
  await requirePatientOrNotFound(id);
  return <PatientDetailClient id={id} initialTab="charting" />;
}
