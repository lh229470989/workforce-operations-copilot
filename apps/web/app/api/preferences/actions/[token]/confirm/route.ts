import { NextRequest, NextResponse } from "next/server";

const AI_API_URL = process.env.AI_API_INTERNAL_URL ?? "http://localhost:8000";
const VALID_ACTORS = new Set([1, 2, 3]);
const TOKEN_PATTERN = /^[0-9a-f-]{36}$/i;

export async function POST(request: NextRequest, context: { params: Promise<{ token: string }> }) {
  const { token } = await context.params;
  const { actorId, confirm } = await request.json();
  if (!TOKEN_PATTERN.test(token) || !VALID_ACTORS.has(actorId) || confirm !== true) {
    return NextResponse.json({ detail: "Explicit confirmation required." }, { status: 400 });
  }
  const upstream = await fetch(
    `${AI_API_URL}/preferences/actions/${encodeURIComponent(token)}/confirm`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Actor-ID": String(actorId) },
      body: JSON.stringify({ confirm: true }), cache: "no-store",
    },
  );
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
