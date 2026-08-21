import { NextRequest, NextResponse } from "next/server";

const CORE_API_URL =
  process.env.DEMO_CORE_API_INTERNAL_URL ?? "http://localhost:8001";
const VALID_ACTORS = new Set([1, 2, 3]);
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ suggestionId: string }> },
) {
  const { suggestionId } = await context.params;
  const body = (await request.json()) as {
    actorId?: number;
    project_id?: number;
    work_date?: string;
    hours?: string;
    description?: string;
  };
  if (!UUID_PATTERN.test(suggestionId) || !VALID_ACTORS.has(body.actorId ?? 0)) {
    return NextResponse.json(
      { detail: "A valid suggestion and demo actor are required." },
      { status: 400 },
    );
  }
  try {
    const upstream = await fetch(
      `${CORE_API_URL}/integration-suggestions/${encodeURIComponent(suggestionId)}/prepare`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Actor-ID": String(body.actorId),
        },
        body: JSON.stringify({
          project_id: body.project_id,
          work_date: body.work_date,
          hours: body.hours,
          description: body.description,
        }),
        cache: "no-store",
      },
    );
    return NextResponse.json(await upstream.json(), { status: upstream.status });
  } catch {
    return NextResponse.json(
      { detail: "The Core API is unavailable." },
      { status: 503 },
    );
  }
}
