import { NextRequest, NextResponse } from "next/server";
import { requireAdmin } from "@/lib/require-admin";

export async function GET(req: NextRequest) {
  const guard = await requireAdmin(req);
  if (!guard.ok) {
    return NextResponse.json({ detail: guard.detail }, { status: guard.status });
  }

  const res = await fetch(`${process.env.INTERNAL_API_BASE_URL}/api/manager/receiver/list`, {
    cache: "no-store",
  });
  if (!res.ok) return NextResponse.json([], { status: res.status });
  return NextResponse.json(await res.json());
}
