import AppointmentAuditClient from "./AppointmentAuditClient";
import { requireNumericParam } from "@/lib/params";

export default function Page({
  params,
}: {
  params: { id?: string | string[] };
}) {
  const id = requireNumericParam("id", params?.id);
  return <AppointmentAuditClient id={id} />;
}
