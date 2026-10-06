import { NextResponse, type NextRequest } from 'next/server'
import { getBackend } from '@/supersub/server/backend'
import { withAuth } from '@/supersub/server/handler'

/** api-contract.md 3-6절 — 클립 업로드 1단계(올릴 자리 받기).
 *
 * 🔴 **목업 사본에서는 게이트웨이를 지난다** (2026-10-06). 원본은 이 두 경로만
 * `callFastApi` 로 FastAPI 를 직접 불렀는데, 그 탓에 `USE_MOCK=1` 이어도
 * 올리기가 안 됐다. 지금은 `getBackend()` 를 거치므로 AWS 없이 끝까지 돈다. */
export async function POST(req: NextRequest) {
  return withAuth(req, async (token) => {
    let body: Record<string, unknown>
    try {
      body = (await req.json()) as Record<string, unknown>
    } catch {
      return NextResponse.json(
        { error: { code: 'BAD_REQUEST', message: '요청 형식이 잘못되었습니다.' } },
        { status: 400 },
      )
    }
    if (
      typeof body.content_type !== 'string' ||
      typeof body.size_bytes !== 'number' ||
      typeof body.filename !== 'string'
    ) {
      return NextResponse.json(
        { error: { code: 'BAD_REQUEST', message: 'content_type·size_bytes·filename이 필요합니다.' } },
        { status: 400 },
      )
    }
    const result = await getBackend().createVideoUploadUrl(token, {
      content_type: body.content_type,
      size_bytes: body.size_bytes,
      filename: body.filename,
    })
    return NextResponse.json(result)
  })
}
