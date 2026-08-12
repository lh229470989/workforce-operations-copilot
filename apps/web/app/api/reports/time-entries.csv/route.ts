import { NextRequest, NextResponse } from "next/server";

const CORE_URL = process.env.DEMO_CORE_API_INTERNAL_URL ?? "http://localhost:8001";

export async function GET(request: NextRequest) {
  const params = new URL(request.url).searchParams;
  const actorId = Number(params.get("actorId"));
  if (![1, 2, 3].includes(actorId)) return NextResponse.json({ detail: "Invalid actor" }, { status: 400 });
  params.delete("actorId");
  const upstream = await fetch(`${CORE_URL}/reports/time-entries.csv?${params}`, {
    headers: { "X-Actor-ID": String(actorId) }, cache: "no-store",
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") ?? "text/csv; charset=utf-8",
      "Content-Disposition": upstream.headers.get("Content-Disposition") ?? "attachment; filename=acmeworks-time-entries.csv",
    },
  });
}
