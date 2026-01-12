import { cookies, headers } from "next/headers";
import { notFound } from "next/navigation";

const TOKEN_COOKIE = "dental_pms_token";
const FALLBACK_API_BASE = "http://backend:8000";

function resolveApiBase() {
  const publicBase = process.env.NEXT_PUBLIC_API_BASE ?? "/api";
  if (publicBase.startsWith("http")) {
    return publicBase.replace(/\/$/, "");
  }
  return FALLBACK_API_BASE;
}

export async function requirePatientOrNotFound(patientId: string) {
  if (process.env.NODE_ENV !== "production") {
    return;
  }
  const cookieToken = cookies().get(TOKEN_COOKIE)?.value;
  const headerToken = headers()
    .get("authorization")
    ?.replace(/^Bearer\\s+/i, "");
  const token = cookieToken || headerToken;
  if (!token) {
    return;
  }

  const apiBase = resolveApiBase();
  const res = await fetch(`${apiBase}/patients/${patientId}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (res.status === 404) {
    notFound();
  }
}
