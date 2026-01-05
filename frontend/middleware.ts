import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const numericId = /^\d+$/;

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const parts = pathname.split("/").filter(Boolean);
  const root = parts[0];

  if (root === "patients") {
    const id = parts[1];
    if (!id || id === "new") return NextResponse.next();
    if (!numericId.test(id)) {
      return NextResponse.rewrite(new URL("/__notfound__", request.url));
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
