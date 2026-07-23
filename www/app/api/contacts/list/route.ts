import { NextRequest, NextResponse } from "next/server";
import { requireAdmin } from "@/lib/require-admin";

export async function GET(req: NextRequest) {
  const guard = await requireAdmin(req);
  if (!guard.ok) {
    return NextResponse.json({ detail: guard.detail }, { status: guard.status });
  }

  const res = await fetch(`${process.env.INTERNAL_API_BASE_URL}/api/manager/juso/contacts`, {
    cache: "no-store",
  });
  if (!res.ok) return NextResponse.json([], { status: res.status });
  const data = await res.json();
  return NextResponse.json(data);
}

export async function DELETE(req: NextRequest) {
  const guard = await requireAdmin(req);
  if (!guard.ok) {
    return NextResponse.json({ detail: guard.detail }, { status: guard.status });
  }

  const res = await fetch(`${process.env.INTERNAL_API_BASE_URL}/api/manager/juso/contacts`, {
    method: "DELETE",
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
