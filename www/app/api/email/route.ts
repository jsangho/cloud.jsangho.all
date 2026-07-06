import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const { to, subject, body } = await req.json();

  const n8nBase =
    process.env.N8N_WEBHOOK_URL ?? "http://localhost:5678/webhook/";

  const res = await fetch(`${n8nBase}faker-report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ to, subject, body }),
  });

  if (!res.ok) {
    return NextResponse.json({ ok: false }, { status: 502 });
  }

  return NextResponse.json({ ok: true });
}
