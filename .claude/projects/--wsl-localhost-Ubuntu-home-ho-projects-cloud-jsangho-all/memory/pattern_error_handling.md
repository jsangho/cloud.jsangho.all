---
name: pattern-error-handling
description: There is NO custom AppError hierarchy — backend raises FastAPI HTTPException, frontend converts via parseApiError in www/lib/api.ts
metadata:
  type: project
---

이 저장소에는 **전용 `AppError` 계층이 없다.** 새로 만들지 않는다.

- **백엔드**: FastAPI `HTTPException` 을 그대로 쓴다.
- **프론트**: `www/lib/api.ts` 의 `parseApiError` 계열을 거쳐 사용자 문구로 변환한다.

에러 처리 추상화를 새로 도입하고 싶어지면, 요청받지 않은 추상화를 넣지 않는다는 원칙
(`CLAUDE.md` §2 단순성 우선)과 충돌하는지 먼저 따진다.

관련: [[debug-double-slash-404]] (같은 `www/lib/api.ts` 파일)
