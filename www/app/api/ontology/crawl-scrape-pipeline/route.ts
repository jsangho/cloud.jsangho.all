import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const maxDuration = 60;

function resolveBackendBase(): string {
  return (
    process.env.INTERNAL_API_BASE_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ||
    "http://127.0.0.1:8000"
  );
}

export async function POST(request: NextRequest) {
  const backendBase = resolveBackendBase();
  const body = await request.text();

  let upstream: Response;
  try {
    upstream = await fetch(
      `${backendBase}/api/ontology/crawl-scrape-pipeline/run`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body || undefined,
      },
    );
  } catch {
    return NextResponse.json(
      { detail: "백엔드에 연결하지 못했습니다." },
      { status: 503 },
    );
  }

  const data = await upstream.json().catch(() => null);
  return NextResponse.json(data, { status: upstream.status });
}
