import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const file = formData.get("file") as File | null;

  if (!file) {
    return NextResponse.json({ detail: "파일이 없습니다." }, { status: 400 });
  }

  const upstream = new FormData();
  upstream.append("file", file);

  const res = await fetch(
    `${process.env.INTERNAL_API_BASE_URL}/api/manager/juso/fileupload`,
    {
      method: "POST",
      body: upstream,
    },
  );
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
