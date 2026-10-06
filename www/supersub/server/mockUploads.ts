import { cookies } from 'next/headers'
import type { MyVideo } from './backend/types'

/**
 * 올린 클립을 **쿠키에 실어 나른다** — 목업 사본 전용 (2026-10-06).
 *
 * ## 왜 메모리가 아닌가
 *
 * 처음에는 목업의 다른 것들처럼 모듈 변수에 담았는데, **운영에서 올린 영상이
 * 사라졌다.** 등록은 한 서버리스 인스턴스에서 처리되고 그 다음 요청(리포트·
 * 재생 주소·목록)은 **다른 인스턴스**로 갈 수 있어서, 그쪽 메모리에는 그 행이
 * 없다 — 실측에서 등록 25초 뒤 리포트가 `VIDEO_NOT_FOUND` 로 왔다.
 * `globalThis` 에 둬도 같다. 인스턴스를 넘지 못한다.
 *
 * 🔴 **쿠키는 요청에 실려 모든 인스턴스로 간다.** 그래서 이 사본에서는 올린
 * 클립만 여기 두고, 미리 깔아 둔 셋은 그대로 모듈 상수로 둔다(그쪽은 어느
 * 인스턴스에나 똑같이 있으므로 나를 따라다닐 필요가 없다).
 *
 * ## 담는 것을 최소로 줄였다
 *
 * 쿠키는 4KB 언저리가 상한이고 **요청마다 올라간다.** 그래서 `MyVideo` 를 통째로
 * 넣지 않고 복원에 필요한 일곱 칸만 배열로 담는다 — 나머지는 상수라 되살릴 때
 * 채운다. 이름표가 없어 읽기 어려운 대신 한 행이 100바이트 아래로 떨어진다.
 */

const COOKIE = 'ss_mock_uploads'

/** 최근 몇 개까지 기억할까. 넘치면 오래된 것부터 버린다. */
const MAX_ROWS = 5

/** `[id, 저장키, 길이ms, 종목, 올린시각(초), 통과?, 반려사유]` */
type Packed = [string, string, number, string, number, 0 | 1, string | null]

function pack(v: MyVideo): Packed {
  return [
    v.id,
    v.storage_key,
    v.duration_ms,
    v.sport_code,
    Math.floor(Date.parse(v.created_at) / 1000),
    v.passed ? 1 : 0,
    v.reject_reason,
  ]
}

function unpack([id, key, dur, sport, sec, passed, reject]: Packed): MyVideo {
  return {
    id,
    sport_code: sport,
    storage_key: key,
    duration_ms: dur,
    side: null,
    created_at: new Date(sec * 1000).toISOString(),
    passed: passed === 1,
    reject_reason: reject,
    /* 🔴 **분석 작업은 통과한 것에만 있다.** 반려된 클립에 작업 id 를 주면
       화면이 「분석 중」으로 그리는데, 실제로는 아무것도 안 돈다. */
    analysis_job_id: passed === 1 ? `${id}-job` : null,
    /* 실제 상태는 `mock.ts` 의 `withDerivedStatus` 가 올린 시각에서 계산한다 —
       여기 적힌 값은 그 계산 전의 출발점이다. */
    analysis_status: passed === 1 ? 'queued' : null,
    is_featured: false,
    is_public: false,
    title: null,
    description: null,
  }
}

function decode(raw: string | undefined): MyVideo[] {
  if (!raw) return []
  try {
    const parsed: unknown = JSON.parse(Buffer.from(raw, 'base64url').toString('utf8'))
    if (!Array.isArray(parsed)) return []
    return parsed.map((row) => unpack(row as Packed))
  } catch {
    /* 🔴 **못 읽으면 조용히 빈 목록이다.** 쿠키는 사용자가 고칠 수 있는 값이라
       깨진 것이 들어올 수 있고, 그걸로 화면을 터뜨리지 않는다. 목업이라
       잃을 것도 올린 클립 목록뿐이다. */
    return []
  }
}

/** 이 사람이 올린 클립들 — **최근 것이 앞에 온다**(계약 3-6절의 정렬 그대로). */
export async function readUploads(): Promise<MyVideo[]> {
  const jar = await cookies()
  return decode(jar.get(COOKIE)?.value)
}

/**
 * 올린 클립을 하나 더한다. 🔴 **라우트 핸들러에서만 부를 수 있다** —
 * 서버 컴포넌트에서 쿠키를 쓰면 Next 가 막는다(렌더 중에는 헤더가 이미 나갔다).
 */
export async function appendUpload(v: MyVideo): Promise<void> {
  const jar = await cookies()
  const next = [pack(v), ...decode(jar.get(COOKIE)?.value).map(pack)].slice(0, MAX_ROWS)
  jar.set(COOKIE, Buffer.from(JSON.stringify(next), 'utf8').toString('base64url'), {
    path: '/',
    httpOnly: true,
    sameSite: 'lax',
    secure: true,
    maxAge: 60 * 60 * 24, // 하루. 목업이라 오래 들고 있을 이유가 없다.
  })
}

/** 올린 클립을 뺀다(지우기). 없으면 아무 일도 안 한다. */
export async function removeUpload(videoId: string): Promise<void> {
  const jar = await cookies()
  const rest = decode(jar.get(COOKIE)?.value).filter((v) => v.id !== videoId)
  jar.set(COOKIE, Buffer.from(JSON.stringify(rest.map(pack)), 'utf8').toString('base64url'), {
    path: '/',
    httpOnly: true,
    sameSite: 'lax',
    secure: true,
    maxAge: 60 * 60 * 24,
  })
}
