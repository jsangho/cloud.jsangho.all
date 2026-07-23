import { NextRequest, NextResponse } from "next/server";
import { requireAdmin } from "@/lib/require-admin";

export async function PATCH(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const guard = await requireAdmin(req);
  if (!guard.ok) {
    return NextResponse.json({ detail: guard.detail }, { status: guard.status });
  }

  const { id } = await params;
  const res = await fetch(`${process.env.INTERNAL_API_BASE_URL}/api/manager/receiver/${id}/read`, {
    method: "PATCH",
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
