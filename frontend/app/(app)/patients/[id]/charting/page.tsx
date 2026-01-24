import PatientDetailClient from "../PatientDetailClient";
import { requireNumericParam } from "@/lib/params";
import { requirePatientOrNotFound } from "../requirePatient";

export const dynamic = "force-dynamic";

export default async function Page({
  params,
}: {
  params: { id?: string | string[] };
}) {
  const id = requireNumericParam("id", params?.id);
  await requirePatientOrNotFound(id);
  return <PatientDetailClient id={id} initialTab="charting" />;
}
