import type { Backend } from './gateway'
import { mockBackend } from './mock'

/**
 * 🔴 **이 사본은 언제나 목업이다** — 포트폴리오로 옮기며 고정했다 (2026-10-06).
 *
 * 원본(`super-sub.cloud/www/src/server/backend/index.ts`)은 환경변수 `USE_MOCK`
 * 으로 목업과 실제 FastAPI 를 골랐다. 여기서는 **고를 수 없게 했다.**
 *
 * 이유는 안전 쪽이다. 환경변수로 두면 **빠뜨렸을 때 실서버를 부르는 쪽으로
 * 떨어진다** — 원본의 기본값이 `fastapiBackend` 다. 이 배포는 포트폴리오라
 * 백엔드 주소도 자격증명도 없으므로 그건 깨진 화면이 되거나, 더 나쁘게는
 * 팀의 실제 운영 데이터를 개인 도메인에서 그리게 된다. 상수로 박아 두면
 * 둘 다 일어날 수 없다.
 *
 * 🔴 **`fastapiBackend` 임포트를 지웠다.** 남겨 두면 다음 사람이 한 줄로
 * 되살릴 수 있고, 그게 위에서 막으려는 바로 그 일이다. 실제 백엔드를 붙이려면
 * 이 파일이 아니라 **배포를 나누는 것**이 맞다.
 */
export function getBackend(): Backend {
  return mockBackend
}

export type { Backend } from './gateway'
export * from './types'
export { BackendError, errorResponseBody, readRetryAfter } from './errors'
