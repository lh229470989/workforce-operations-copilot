import { NextRequest, NextResponse } from "next/server";

const AI_API_URL = process.env.AI_API_INTERNAL_URL ?? "http://localhost:8000";

export async function GET(request: NextRequest) {
  const actorId = Number(request.nextUrl.searchParams.get("actorId"));
  if (actorId !== 1) return NextResponse.json({ detail: "Admin demo actor required." }, { status: 403 });
  const upstream = await fetch(`${AI_API_URL}/agent-audit`, {
    headers: { "X-Actor-ID": String(actorId) }, cache: "no-store",
  });
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
