import { NextResponse, type NextRequest } from 'next/server'

/**
 * 올린 바이트를 **받아서 버린다** — 목업 사본 전용 (2026-10-06).
 *
 * 실제 서비스는 이 자리가 S3 사전 서명 URL 이고, 바이트가 앱 서버를 아예 안
 * 지난다(계약 PER-002). 이 사본에는 S3 가 없다.
 *
 * 🔴 **서버 메모리에 담지 않는다.** 담으면 Vercel 인스턴스가 바뀔 때마다
 * 「될 때도 있고 안 될 때도 있는」 재생이 되는데, 그게 제일 나쁜 결과다.
 * 재생은 지금 창이 들고 있는 파일로 한다(`supersub/lib/localClips.ts`).
 *
 * 🔴 그래도 **진짜로 읽는다.** 안 읽고 200 을 돌려주면 브라우저가 큰 파일을
 * 보내다 끊기는 경우가 생기고, 화면의 진행률도 올라가지 않는다.
 */
export async function PUT(req: NextRequest) {
  await req.arrayBuffer()
  return new NextResponse(null, { status: 200 })
}
