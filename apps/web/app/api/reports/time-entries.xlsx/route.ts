import { NextRequest, NextResponse } from "next/server";

const CORE_URL = process.env.DEMO_CORE_API_INTERNAL_URL ?? "http://localhost:8001";
const VALID_ACTORS = new Set([1, 2, 3]);

export async function GET(request: NextRequest) {
  const actorId = Number(request.nextUrl.searchParams.get("actorId"));
  if (!VALID_ACTORS.has(actorId)) return NextResponse.json({ detail: "Valid demo actor required." }, { status: 400 });
  const params = new URLSearchParams(request.nextUrl.searchParams);
  params.delete("actorId");
  const upstream = await fetch(`${CORE_URL}/reports/time-entries.xlsx?${params}`, { headers: { "X-Actor-ID": String(actorId) }, cache: "no-store" });
  return new NextResponse(await upstream.arrayBuffer(), { status: upstream.status, headers: {
    "Content-Type": upstream.headers.get("Content-Type") ?? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "Content-Disposition": upstream.headers.get("Content-Disposition") ?? "attachment; filename=acmeworks-time-entries.xlsx",
  }});
}
