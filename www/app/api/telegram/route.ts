import { NextRequest, NextResponse } from "next/server";
import { requireAdmin } from "@/lib/require-admin";

export async function POST(req: NextRequest) {
  const guard = await requireAdmin(req);
  if (!guard.ok) {
    return NextResponse.json({ detail: guard.detail }, { status: guard.status });
  }

  const body = await req.json();
  const { chatId, message } = body;
  if (!chatId || !message) {
    return NextResponse.json({ detail: "chatId와 message가 필요합니다." }, { status: 400 });
  }
  const res = await fetch(`${process.env.INTERNAL_API_BASE_URL}/api/manager/telegram/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, message }),
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
