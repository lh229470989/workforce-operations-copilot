import { NextRequest, NextResponse } from "next/server";

const AI_API_URL = process.env.AI_API_INTERNAL_URL ?? "http://localhost:8000";
const VALID_ACTORS = new Set([1, 2, 3]);

export async function GET(request: NextRequest) {
  const actorId = Number(request.nextUrl.searchParams.get("actorId"));
  if (!VALID_ACTORS.has(actorId)) return NextResponse.json({ detail: "Valid demo actor required." }, { status: 400 });
  const upstream = await fetch(`${AI_API_URL}/memories`, {
    headers: { "X-Actor-ID": String(actorId) }, cache: "no-store",
  });
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}

export async function POST(request: NextRequest) {
  const { actorId, ...payload } = await request.json();
  if (!VALID_ACTORS.has(actorId)) return NextResponse.json({ detail: "Valid demo actor required." }, { status: 400 });
  const upstream = await fetch(`${AI_API_URL}/memories/dry-run`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Actor-ID": String(actorId) },
    body: JSON.stringify(payload), cache: "no-store",
  });
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
