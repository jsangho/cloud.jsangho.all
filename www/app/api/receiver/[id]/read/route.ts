import { NextRequest, NextResponse } from "next/server";

export async function PATCH(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const res = await fetch(
    `${process.env.INTERNAL_API_BASE_URL}/api/manager/receiver/${id}/read`,
    {
      method: "PATCH",
    },
  );
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
