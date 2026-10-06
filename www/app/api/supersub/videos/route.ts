import { NextResponse, type NextRequest } from 'next/server'
import { getBackend } from '@/supersub/server/backend'
import { withAuth } from '@/supersub/server/handler'

/** api-contract.md 3-6절 — 클립 업로드 3단계(등록·검사).
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
    const { sport_code, storage_key, duration_ms, width, height } = body
    if (
      typeof sport_code !== 'string' ||
      typeof storage_key !== 'string' ||
      typeof duration_ms !== 'number' ||
      typeof width !== 'number' ||
      typeof height !== 'number'
    ) {
      return NextResponse.json(
        {
          error: {
            code: 'BAD_REQUEST',
            message: 'sport_code·storage_key·duration_ms·width·height가 필요합니다.',
          },
        },
        { status: 400 },
      )
    }
    /* 🔴 201 이다 — **반려(passed: false)도 201**이고, 클라이언트는 status 가
       아니라 body 의 `passed` 로 갈린다(계약 3-6절). */
    const result = await getBackend().registerVideo(token, {
      sport_code,
      storage_key,
      duration_ms,
      width,
      height,
      ...(typeof body.filename === 'string' ? { filename: body.filename } : {}),
      ...(typeof body.side === 'string' ? { side: body.side } : {}),
      ...(body.analyze === false ? { analyze: false } : {}),
      ...(Array.isArray(body.focus) ? { focus: body.focus as string[] } : {}),
    })
    return NextResponse.json(result, { status: 201 })
  })
}
