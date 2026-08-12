import { NextRequest, NextResponse } from "next/server";

const AI_URL = process.env.AI_API_INTERNAL_URL ?? "http://localhost:8000";

async function forward(request: NextRequest, method: "GET" | "POST") {
  const actorId = Number(new URL(request.url).searchParams.get("actorId"));
  if (actorId !== 1) return NextResponse.json({ detail: "Admin role required" }, { status: 403 });
  const upstream = await fetch(`${AI_URL}/knowledge${method === "POST" ? "/reload" : ""}`, {
    method, headers: { "X-Actor-ID": String(actorId) }, cache: "no-store",
  });
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}

export async function GET(request: NextRequest) { return forward(request, "GET"); }
export async function POST(request: NextRequest) { return forward(request, "POST"); }
