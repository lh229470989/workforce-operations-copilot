import { NextRequest, NextResponse } from "next/server";

const CORE_API_URL =
  process.env.DEMO_CORE_API_INTERNAL_URL ?? "http://localhost:8001";
const VALID_ACTORS = new Set([1, 2, 3]);
const TOKEN_PATTERN = /^[0-9a-f-]{36}$/i;

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ token: string }> },
) {
  const { token } = await context.params;
  const body = (await request.json()) as { actorId?: number; confirm?: boolean };

  if (
    !TOKEN_PATTERN.test(token) ||
    !VALID_ACTORS.has(body.actorId ?? 0) ||
    body.confirm !== true
  ) {
    return NextResponse.json(
      { detail: "Explicit confirmation from a valid demo actor is required." },
      { status: 400 },
    );
  }

  try {
    const upstream = await fetch(
      `${CORE_API_URL}/actions/${encodeURIComponent(token)}/confirm`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Actor-ID": String(body.actorId),
        },
        body: JSON.stringify({ confirm: true }),
        cache: "no-store",
      },
    );
    const payload = await upstream.json();
    return NextResponse.json(payload, { status: upstream.status });
  } catch {
    return NextResponse.json(
      { detail: "The Core API is unavailable." },
      { status: 503 },
    );
  }
}
