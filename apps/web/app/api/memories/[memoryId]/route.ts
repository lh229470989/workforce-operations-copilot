import { NextRequest, NextResponse } from "next/server";

const AI_API_URL = process.env.AI_API_INTERNAL_URL ?? "http://localhost:8000";
const VALID_ACTORS = new Set([1, 2, 3]);

export async function DELETE(request: NextRequest, context: { params: Promise<{ memoryId: string }> }) {
  const actorId = Number(request.nextUrl.searchParams.get("actorId"));
  const { memoryId } = await context.params;
  if (!VALID_ACTORS.has(actorId)) return NextResponse.json({ detail: "Valid demo actor required." }, { status: 400 });
  const upstream = await fetch(`${AI_API_URL}/memories/${encodeURIComponent(memoryId)}/dry-run`, {
    method: "DELETE", headers: { "X-Actor-ID": String(actorId) }, cache: "no-store",
  });
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
