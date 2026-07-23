import { NextRequest, NextResponse } from "next/server";
import { requireAdmin } from "@/lib/require-admin";

type ContactItem = {
  id: number;
  name: string;
  email: string;
  phone: string;
  org_name: string;
};

export async function GET(req: NextRequest) {
  const guard = await requireAdmin(req);
  if (!guard.ok) {
    return NextResponse.json({ detail: guard.detail }, { status: guard.status });
  }

  const q = (req.nextUrl.searchParams.get("q") ?? "").toLowerCase().trim();
  if (!q) return NextResponse.json([]);

  const res = await fetch(`${process.env.INTERNAL_API_BASE_URL}/api/manager/juso/contacts`, {
    cache: "no-store",
  });
  if (!res.ok) return NextResponse.json([]);

  const all: ContactItem[] = await res.json();
  const matched = all
    .filter((c) => c.name.toLowerCase().includes(q) || c.email.toLowerCase().includes(q))
    .slice(0, 5)
    .map((c) => ({ name: c.name, email: c.email }));

  return NextResponse.json(matched);
}
