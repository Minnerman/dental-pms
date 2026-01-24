import { notFound } from "next/navigation";

import PatientDetailClient from "../PatientDetailClient";
import { requireNumericParam } from "@/lib/params";
import { requirePatientOrNotFound } from "../requirePatient";

export const dynamic = "force-dynamic";

export default async function Page({
  params,
}: {
  params: { id?: string | string[] };
}) {
  if (process.env.NEXT_PUBLIC_FEATURE_CHARTING_VIEWER !== "1") {
    notFound();
  }

  const id = requireNumericParam("id", params?.id);
  await requirePatientOrNotFound(id);
  return <PatientDetailClient id={id} initialTab="charting" />;
}
