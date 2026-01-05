import { NextResponse } from "next/server";

export async function GET() {
  try {
    const r = await fetch("http://backend:8000/health", { cache: "no-store" });
    const text = await r.text();

    return new NextResponse(text, {
      status: r.status,
      headers: {
        "content-type": r.headers.get("content-type") || "application/json",
        "cache-control": "no-store",
      },
    });
  } catch (e: any) {
    return NextResponse.json(
      { status: "error", message: "backend unreachable", detail: String(e?.message || e) },
      { status: 502, headers: { "cache-control": "no-store" } }
    );
  }
}
