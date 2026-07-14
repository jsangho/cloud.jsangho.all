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
  const body = await request.arrayBuffer();

  let upstream: Response;
  try {
    upstream = await fetch(`${backendBase}/api/wwe-chat/chat`, {
      method: "POST",
      headers: {
        "Content-Type":
          request.headers.get("content-type") || "application/json",
      },
      body,
    });
  } catch {
    return NextResponse.json(
      { detail: "백엔드에 연결하지 못했습니다." },
      { status: 503 },
    );
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type":
        upstream.headers.get("content-type") || "text/plain; charset=utf-8",
    },
  });
}
