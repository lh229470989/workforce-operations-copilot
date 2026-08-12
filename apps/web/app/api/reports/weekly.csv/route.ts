import { NextRequest, NextResponse } from "next/server";

const CORE_API_URL =
  process.env.DEMO_CORE_API_INTERNAL_URL ?? "http://localhost:8001";
const VALID_ACTORS = new Set([1, 2, 3]);
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

export async function GET(request: NextRequest) {
  const actorId = Number(request.nextUrl.searchParams.get("actorId"));
  const weekStart = request.nextUrl.searchParams.get("week_start");
  if (!VALID_ACTORS.has(actorId) || !weekStart || !DATE_PATTERN.test(weekStart)) {
    return NextResponse.json(
      { detail: "A valid demo actor and week_start are required." },
      { status: 400 },
    );
  }
  try {
    const upstream = await fetch(
      `${CORE_API_URL}/reports/weekly.csv?week_start=${encodeURIComponent(weekStart)}`,
      { headers: { "X-Actor-ID": String(actorId) }, cache: "no-store" },
    );
    if (!upstream.ok || !upstream.body) {
      return NextResponse.json(
        { detail: "Weekly export failed." },
        { status: upstream.status },
      );
    }
    return new Response(upstream.body, {
      status: 200,
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition":
          upstream.headers.get("content-disposition") ??
          'attachment; filename="acmeworks-week.csv"',
      },
    });
  } catch {
    return NextResponse.json(
      { detail: "The Core API is unavailable." },
      { status: 503 },
    );
  }
}
