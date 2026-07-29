---
name: debug-double-slash-404
description: A trailing slash in NEXT_PUBLIC_API_BASE_URL produced `//weather/seoul` URLs that FastAPI 404s — always normalize env-supplied base URLs (fixed in 64ccb2f)
metadata:
  type: project
---

**증상:** 프론트에서 백엔드 호출이 404. URL에 슬래시가 두 개 (`https://api.../ /weather/seoul`).

**원인:** `NEXT_PUBLIC_API_BASE_URL` / `INTERNAL_API_BASE_URL` 값에 트레일링 슬래시가 있는데
코드에서 `${base}/weather/seoul` 로 붙이면서 `//` 가 됐다. FastAPI는 이 경로를 404로 처리한다.

**해결:** base URL의 트레일링 슬래시를 제거한 뒤 조립한다. `www/lib/api.ts` 에 정리.
커밋 `64ccb2f` — `www/app/api/**/route.ts` 7개 + `www/lib/api.ts` + `page.tsx` + `weather-widget.tsx`.

**교훈 (재발 방지):** 환경변수로 들어오는 base URL은 **항상 정규화한 뒤** 사용한다.
`.env` / `www/.env.local` 값의 형태를 믿지 않는다. 새 API 라우트를 추가할 때
`www/lib/api.ts` 의 헬퍼를 거치지 않고 직접 문자열을 이어붙이면 같은 버그가 재발한다.

관련: [[pattern-error-handling]] (같은 `www/lib/api.ts`)
