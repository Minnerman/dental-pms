import PatientDetailClient from "../PatientDetailClient";
import { requireNumericParam } from "@/lib/params";

export default function Page({
  params,
}: {
  params: { id?: string | string[] };
}) {
  const id = requireNumericParam("id", params?.id);
  return <PatientDetailClient id={id} initialTab="attachments" />;
}
