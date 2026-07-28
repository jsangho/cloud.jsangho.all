import { NextRequest, NextResponse } from "next/server";

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
    upstream = await fetch(`${backendBase}/api/langchain/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
  } catch {
    return NextResponse.json({ detail: "백엔드에 연결하지 못했습니다." }, { status: 503 });
  }

  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}
