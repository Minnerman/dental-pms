import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const numericId = /^\d+$/;

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const parts = pathname.split("/").filter(Boolean);
  const root = parts[0];

  if (root === "patients") {
    const id = parts[1];
    if (!id || id === "new") return NextResponse.next();
    if (!numericId.test(id)) {
      return NextResponse.rewrite(new URL("/__notfound__", request.url));
    }
    if (process.env.NODE_ENV === "production") {
      const token = request.cookies.get("dental_pms_token")?.value;
      if (token) {
        try {
          const res = await fetch(`http://backend:8000/patients/${id}`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (res.status === 404) {
            return NextResponse.rewrite(new URL("/__notfound__", request.url));
          }
        } catch {
          return NextResponse.next();
        }
      }
    }
    return NextResponse.next();
  }

  if (root === "notes") {
    const id = parts[1];
    const sub = parts[2];
    if (id && sub === "audit" && !numericId.test(id)) {
      return NextResponse.rewrite(new URL("/__notfound__", request.url));
    }
  }

  if (root === "appointments") {
    const id = parts[1];
    const sub = parts[2];
    if (id && sub === "audit" && !numericId.test(id)) {
      return NextResponse.rewrite(new URL("/__notfound__", request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next|api|__notfound__|favicon.ico).*)"],
};
