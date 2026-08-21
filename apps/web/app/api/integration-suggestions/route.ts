import { NextRequest, NextResponse } from "next/server";

const CORE_API_URL =
  process.env.DEMO_CORE_API_INTERNAL_URL ?? "http://localhost:8001";
const VALID_ACTORS = new Set([1, 2, 3]);

export async function GET(request: NextRequest) {
  const actorId = Number(request.nextUrl.searchParams.get("actorId"));
  if (!VALID_ACTORS.has(actorId)) {
    return NextResponse.json(
      { detail: "A valid demo actor is required." },
      { status: 400 },
    );
  }
  try {
    const upstream = await fetch(`${CORE_API_URL}/integration-suggestions`, {
      headers: { "X-Actor-ID": String(actorId) },
      cache: "no-store",
    });
    return NextResponse.json(await upstream.json(), { status: upstream.status });
  } catch {
    return NextResponse.json(
      { detail: "The Core API is unavailable." },
      { status: 503 },
    );
  }
}
