import { NextRequest, NextResponse } from "next/server";

const CORE_URL = process.env.DEMO_CORE_API_INTERNAL_URL ?? "http://localhost:8001";

export async function GET(request: NextRequest) {
  const params = new URL(request.url).searchParams;
  const actorId = Number(params.get("actorId"));
  if (actorId !== 1) return NextResponse.json({ detail: "Admin role required" }, { status: 403 });
  const stats = params.get("stats") === "1";
  params.delete("actorId");
  params.delete("stats");
  const upstream = await fetch(`${CORE_URL}/audit-events${stats ? "/stats" : `?${params}`}`, {
    headers: { "X-Actor-ID": String(actorId) }, cache: "no-store",
  });
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
