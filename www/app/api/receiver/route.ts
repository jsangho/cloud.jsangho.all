import { NextResponse } from "next/server";

export async function GET() {
  const res = await fetch(
    `${process.env.INTERNAL_API_BASE_URL}/api/manager/receiver/list`,
    {
      cache: "no-store",
    },
  );
  if (!res.ok) return NextResponse.json([], { status: res.status });
  return NextResponse.json(await res.json());
}
