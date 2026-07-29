---
name: infra-env-vars
description: Which .env file serves what, the required key list, and that JWT_SECRET_KEY is deprecated dead weight from the HS256 era
metadata:
  type: project
---

| 파일 | 용도 |
|------|------|
| `.env` (루트) | Docker Compose `env_file` — backend·auth·n8n 공용. **git 제외** |
| `.env.example` | 키 목록 템플릿. **새 키를 추가하면 여기에도 반영한다** |
| `www/.env.local` | 프론트 `NEXT_PUBLIC_*`. **git 제외** |

필수 키 (전체 목록은 `.env.example`):

- DB·캐시: `DATABASE_URL` · `PGVECTOR_URL` · `PGVECTOR_PASSWORD` · `REDIS_URL`
- 그래프: `NEO4J_URI` · `NEO4J_USER` · `NEO4J_PASSWORD`
- 인증(RS256): `JWT_PRIVATE_KEY`(auth 컨테이너 전용) · `JWT_PUBLIC_KEY`(전 컨테이너 공용) · `SERVICE_AUD`
- LLM: `GEMINI_API_KEY`
- 프론트: `NEXT_PUBLIC_API_BASE_URL` · `NEXT_PUBLIC_AUTH_BASE_URL`

**`JWT_SECRET_KEY` 는 deprecated** — HS256 시절 값이며 RS256 전환 후 쓰지 않는다.
새 코드에서 참조하지 않는다. 아직 파일에 남아 있어도 살아있는 설정으로 착각하지 말 것.

`NEXT_PUBLIC_API_BASE_URL` 값에 트레일링 슬래시를 넣지 않는다 → [[debug-double-slash-404]].

EC2 쪽 `.env` 는 별개다 (pgAdmin/pgvector 비밀번호 등) → [[server-remote-access-jsangho]].

관련: [[repo-submodules]] (`.env` 커밋 금지)
