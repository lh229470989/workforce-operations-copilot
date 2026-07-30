import { NextRequest, NextResponse } from "next/server";

const AI_API_URL = process.env.AI_API_INTERNAL_URL ?? "http://localhost:8000";
const VALID_ACTORS = new Set([1, 2, 3]);

export async function POST(request: NextRequest) {
  const body = (await request.json()) as {
    actorId?: number;
    message?: string;
    sessionId?: string;
  };

  if (
    !VALID_ACTORS.has(body.actorId ?? 0) ||
    typeof body.message !== "string" ||
    body.message.trim().length === 0
  ) {
    return NextResponse.json(
      { detail: "A valid demo actor and message are required." },
      { status: 400 },
    );
  }

  try {
    const upstream = await fetch(`${AI_API_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Actor-ID": String(body.actorId),
      },
      body: JSON.stringify({
        message: body.message.trim(),
        session_id: body.sessionId,
      }),
      cache: "no-store",
    });
    const payload = await upstream.json();
    return NextResponse.json(payload, { status: upstream.status });
  } catch {
    return NextResponse.json(
      { detail: "The AI API is unavailable." },
      { status: 503 },
    );
  }
}
