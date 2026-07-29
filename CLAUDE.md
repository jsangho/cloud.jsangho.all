# LLM 코딩 행동 지침 (메인)

## 0. 최상위 아키텍처 원칙 (Overrides All)

> 이 섹션은 모든 하위 `.cursorrules` · `CLAUDE.md` 보다 **우선**한다.

### 0-1. 목표: Wiki + LLM PKS (Personal Knowledge System)
- Karpathy 하네스 엔지니어링 원칙을 기반으로 Wiki와 LLM을 결합한 PKS를 구현한다.
- 모든 도메인 지식은 문서화 가능한 단위로 분리하고, LLM이 문맥을 추론할 수 있도록 구조화한다.

### 0-2. 아키텍처 원칙 (SOLID + Hexagonal + Clean + DDD)
- **SOLID** 원칙을 반드시 준수한다. 단일 책임·개방-폐쇄·리스코프 치환·인터페이스 분리·의존성 역전을 모두 지킨다.
- **헥사고날 아키텍처**: 도메인 로직은 인바운드(API/CLI)·아웃바운드(DB/외부 서비스) 어댑터에 의존하지 않는다.
- **클린 아키텍처**: 의존성은 항상 안쪽(도메인)을 향한다. 도메인 레이어가 프레임워크·인프라를 import하면 즉시 거부한다.
- **DDD**: 바운디드 컨텍스트·애그리거트·도메인 이벤트를 명시적으로 모델링한다. 유비쿼터스 언어를 코드에 반영한다.

### 0-3. 경로 규칙 (Path Convention)
- `fastapi/apps/<앱명>/` 내부를 작업할 때, 패키지 경로는 **`jsangho`와 `apps`를 생략**하고 앱명부터 시작한다.
  - 예: `fastapi/apps/titanic/domain/...` → 경로 표기는 `titanic.domain....`
- **core 패키지** 경로는 반드시 `jsangho.core.` 로 시작한다.
  - 예: `fastapi/core/shared/...` → `jsangho.core.shared....`
- 경로 표기가 위 규칙과 어긋나면 코드를 작성하기 전에 멈추고 사용자에게 확인한다.

### 0-4. 문서(MD) 위치 규칙 (Docs Placement)

새 MD 파일을 만들거나 이동할 때 아래 표를 따른다. 범위가 겹치면 더 좁은 쪽을 우선한다.

| 위치 | 대상 |
|------|------|
| `_docs/` | 프로젝트 전체에 걸친 공통 문서 (설정, 운영, 온보딩 등) |
| `fastapi/_docs/` | 백엔드 전용 문서 (API 설계, DB 스키마, 아키텍처 등) |
| `www/_docs/` | 프론트엔드 전용 문서 (컴포넌트, 라우팅, 상태 관리 등) |
| `flutter/_docs/` | Flutter 전용 문서 (위젯, 상태, 플랫폼 설정 등) |

- 특정 스택에 귀속되지 않는 문서는 `_docs/`에 넣는다.
- MD 파일을 루트나 각 앱 루트에 직접 두지 않는다 (`CLAUDE.md` · `agent.md` 같은 LLM 지침 파일 제외).

---

> **본 문서가 메인 규칙이다.** 충돌 시 `CLAUDE.md`가 우선한다.  
> 그래프: `path:www/`(프론트) · `path:fastapi/`(백엔드) 경로로 구분.  
> `.cursorrules`는 보조 참고용이다.

[Andrej Karpathy의 LLM 코딩 관찰](https://x.com/karpathy/status/2015883857489522876)을 바탕으로, LLM이 자주 내는 코딩 실수를 줄이기 위한 행동 지침이다.

**트레이드오프:** 속도보다 신중함에 우선한다. 사소한 작업은 상황에 맞게 판단한다.

---

## 규칙 파일 링크

| 경로 | 메인 |
|------|------|
| 백엔드 | [[fastapi/CLAUDE\|fastapi/CLAUDE.md]] |
| 프론트 | [[www/CLAUDE\|www/CLAUDE.md]] |

---

## 1. 구현 전 사고 (Think Before Coding)

**가정하지 않는다. 혼란을 숨기지 않는다. 트레이드오프를 드러낸다.**

- 자신의 가정을 명시적으로 말한다. 불확실하면 질문한다.
- 해석이 여러 개면 조용히 하나를 고르지 말고, 대안을 나열한다.
- 더 단순한 방법이 있으면 말한다. 타당하면 사용자 요청에도 반대 의견을 낸다.
- 불분명하면 멈춘다. 무엇이 헷갈리는지 구체적으로 짚고 질문한다.

스택별 적용 → 각 경로 **`CLAUDE.md` 먼저**, 보조로 `.cursorrules` 참고

---

## 2. 단순성 우선 (Simplicity First)

- 요청받지 않은 기능·추상화·설정 가능성·비현실적 예외 처리를 넣지 않는다.
- “시니어 엔지니어가 과하게 복잡하다고 할까?”에 스스로 답한다.

---

## 3. 정밀한 수정 (Surgical Changes)

- 인접 코드·포맷·무관 데드 코드 정리 금지(언급만).
- **내 변경**으로 불필요해진 import·변수·함수만 제거한다.
- 바뀐 모든 줄이 사용자 요청과 직접 연결되어야 한다.

---

## 4. 목표 중심 실행 (Goal-Driven Execution)

- 모호한 일을 검증 가능한 목표로 바꾼다.
- 다단계 작업이면 단계별 검증 지점을 적는다.
- “작동하게 만들기”는 완료 기준이 아니다.

---

## 5. 하네스 강제 실행 (Harness Gates)

> 코드 작성 후 반드시 실행한다. 에러는 무시하지 않고 수정 후 완료 보고한다.

### Flutter 작업 후

```bash
dart analyze          # 린트 (avoid_print 위반 시 에러)
dart format .         # 포매팅
```

### Python 작업 후

```bash
uv run ruff check fastapi/ --config pyproject.toml --fix
uv run ruff format fastapi/ --config pyproject.toml
cd fastapi && PYTHONUTF8=1 PYTHONPATH=apps uv run lint-imports   # 스타 토폴로지 계약 검증
```

> `uv run` 없이 `ruff`/`lint-imports`를 그냥 실행하면 PATH상 다른 Python(예: Anaconda)의 전역 설치가 먼저 잡혀 잘못된 버전이 돌거나 `ontology` 패키지를 못 찾을 수 있다. 항상 `uv run`으로 프로젝트 venv를 명시한다.

### Next.js 작업 후

```bash
cd www && pnpm lint        # ESLint (no-console, no-explicit-any 위반 시 에러)
cd www && pnpm type-check  # TypeScript strict 검사
cd www && pnpm format      # Prettier
```

### 전체 게이트 (pre-commit)

```bash
# 최초 1회만
pip install pre-commit
pre-commit install

# 이후 커밋 시 자동 실행 — 수동 전체 실행:
pre-commit run --all-files
```

---

## 관련 문서

| 문서 | 역할 |
|------|------|
| `CLAUDE.md` | **메인** — 아키텍처·코딩 행동 규칙 |
| `.cursorrules` | **보조** — 하네스·vault |
| `agent.md` | useState 객체 압축 등 |

## Docker 개발 워크플로우 (중요)

### 원칙

1. **코드 변경은 빌드 불필요** — 볼륨 마운트(`.:/app`, 저장소 루트 전체)로 즉시 반영된다.

2. **새 패키지는 exec로 먼저 테스트** — `pyproject.toml`을 바로 수정하지 말고, 실행 중인 컨테이너에 직접 설치해서 확인한다.
   ```bash
   docker compose exec <service> uv pip install <package>
   ```

3. **빌드는 명시적 요청 시에만** — `docker build` / `docker compose build` / `--build` 옵션은 사용자가 **"빌드해줘"** 라고 직접 말했을 때만 실행한다. 패키지가 추가됐거나 `pyproject.toml`/`uv.lock`이 바뀌었다는 이유로 AI가 임의로 빌드를 실행하거나 제안하지 않는다.

4. **`pyproject.toml`/`uv.lock` 수정은 가능, 빌드는 금지** — 파일에 패키지를 반영하는 작업(`uv add` 등)은 해도 되지만, 그 직후 자동으로 빌드까지 이어가지 않는다. 빌드 시점은 사용자가 결정한다.

5. **임시 설치 소멸 안내** — 컨테이너를 내렸다 올리면 exec로 설치한 패키지는 사라진다. 필요할 때 한 번 알려줘도 되지만, 그것을 이유로 먼저 빌드하지 않는다.

---

## 프로젝트 개요

Wiki + LLM PKS(§0-1)를 구현하는 **멀티스택 모노레포**.

| 스택 | 경로 | 내용 |
|------|------|------|
| 백엔드 | `fastapi/` | FastAPI · Python 3.13 · SQLAlchemy 2.0 async · SQLModel · Alembic. 모듈러 모놀리식(`apps/<앱>`) + 스타 토폴로지 |
| 프론트 | `www/` | Next.js App Router · React · TypeScript · Tailwind · Radix |
| 앱 | `flutter/` | Flutter |
| 인프라 | `docker-compose.yaml` | pgvector(PostgreSQL 16) · Neo4j 5 · Redis 7 · n8n · pgAdmin · cloudflared |

- 백엔드 엔트리포인트는 둘이다: `main.py`(포트 8000) · `auth_main.py`(인증 게이트웨이, 포트 9000·미노출).
- 앱 목록·API prefix·허브(`ontology`)/스포크 관계는 [`fastapi/CLAUDE.md`](fastapi/CLAUDE.md) §6 참조.

---

## 명령어

린트·포매팅은 §5 하네스에 있다. 아래는 실행·테스트·빌드.

```bash
# 개발 서버 — 프론트
cd www && pnpm dev                    # http://localhost:3000

# 개발 서버 — 백엔드 (Docker 권장)
docker compose up -d backend          # http://127.0.0.1:8000/docs

# 인프라만 기동
docker compose up -d pgvector redis neo4j

# 테스트 (백엔드)
uv run pytest fastapi/apps/titanic/tests

# 빌드 — 프론트
cd www && pnpm build

# DB 마이그레이션
cd fastapi && uv run alembic revision --autogenerate -m "..."
cd fastapi && uv run alembic upgrade head
```

> Python 명령은 항상 `uv run`을 붙인다(§5 주석 참조). 컨테이너 빌드는 사용자가 "빌드해줘"라고 말했을 때만 실행한다(Docker 워크플로우 §3).

---

## 코딩 컨벤션

| 스택 | 규칙 |
|------|------|
| Python | 들여쓰기 4칸(PEP8). ruff `line-length = 88`, `target-version = py313`, 룰셋 `E,F,I,N,UP,B,C4`. 포매터는 `ruff format` |
| TS/TSX | 들여쓰기 2칸, `printWidth 100`, LF, **세미콜론 사용**(Prettier 기본값). `any` 금지·`type` 별칭 우선 등 상세는 [`.claude/rules/typescript.md`](.claude/rules/typescript.md) |
| Dart | `dart format` 결과가 정답. `avoid_print` 위반은 에러 |
| JSON/YAML | 들여쓰기 2칸 |

- **비동기**: Python에서 `async def` / `def` 선택 기준은 [`fastapi/CLAUDE.md`](fastapi/CLAUDE.md) §9. `await`할 대상이 없으면 `async`를 붙이지 않는다.
- **에러 처리**: 전용 `AppError` 계층은 없다. 백엔드는 FastAPI `HTTPException`을 쓰고, 프론트는 `lib/api.ts`의 `parseApiError` 계열을 거쳐 사용자 문구로 변환한다.
- **네이밍**: 백엔드 레이어별 파일·클래스 명명 규칙은 [`fastapi/CLAUDE.md`](fastapi/CLAUDE.md) §4 표를 따른다.

---

## 테스트

- **프레임워크**: pytest + pytest-asyncio (`[dependency-groups] dev`). www에는 테스트 러너가 없고 `pnpm lint` · `pnpm type-check`가 그 자리를 대신한다.
- **위치·패턴**: `fastapi/apps/<앱>/tests/` 아래 `test_*.py`. 헥사고날 레이어를 그대로 미러링한다 (`tests/domain/`, `tests/app/use_cases/`, `tests/adapter/outbound/mappers/`).
- **sys.path**: 앱별 `tests/conftest.py`가 `apps/`를 `sys.path`에 넣어 `titanic.*` 임포트를 활성화한다. 새 앱에 테스트를 추가할 때 이 conftest 패턴을 복사한다.
- **마커**: `ollama` — 로컬 Ollama가 필요한 통합 테스트. 기본 실행에서 빠뜨릴 수 있게 표시한다.
- Flutter는 `flutter/test/`(현재 `widget_test.dart` 하나).
- 참고 구현: `fastapi/apps/titanic/tests/` — 구조 템플릿으로 삼는다.

---

## 브랜치 전략

| 브랜치 | 역할 |
|--------|------|
| `ho` | **작업 브랜치.** 기본으로 여기서 커밋한다 |
| `main` | 기본 브랜치 (`origin/HEAD`) |
| `messi` | `ho`와 동기화하는 미러 브랜치 |
| `aws` | AWS 배포 관련 |

- 커밋·푸시 요청 시: `ho`에 커밋·푸시한 뒤 `main`·`messi`를 fast-forward로 맞춘다.
- 커밋·푸시는 사용자가 요청했을 때만 한다.

---

## 환경 변수

| 파일 | 용도 |
|------|------|
| `.env` (루트) | Docker Compose `env_file` — 백엔드·auth·n8n 공용. **git 제외** |
| `.env.example` | 키 목록 템플릿. 새 키를 추가하면 여기에도 반영한다 |
| `www/.env.local` | 프론트 `NEXT_PUBLIC_*`. **git 제외** |

필수 키 (전체 목록은 `.env.example`):

- DB·캐시: `DATABASE_URL` · `PGVECTOR_URL` · `PGVECTOR_PASSWORD` · `REDIS_URL`
- 그래프: `NEO4J_URI` · `NEO4J_USER` · `NEO4J_PASSWORD`
- 인증(RS256): `JWT_PRIVATE_KEY`(auth 컨테이너 전용) · `JWT_PUBLIC_KEY`(전 컨테이너 공용) · `SERVICE_AUD`
- LLM: `GEMINI_API_KEY`
- 프론트: `NEXT_PUBLIC_API_BASE_URL` · `NEXT_PUBLIC_AUTH_BASE_URL`

---

## 주의사항

- **`fastapi/` · `www/` · `_docs/` 는 git 서브모듈이다** (각각 별도 저장소). 이 디렉터리 안의 변경은 해당 서브모듈에서 커밋한 뒤, 루트에서 포인터를 커밋해야 반영된다.
- **커밋 금지 대상**: `.env` · `*.pem` · `data/` · `.venv/` · `pytorch_env/` (`.gitignore` 기준). 키·비밀번호를 코드나 문서에 하드코딩하지 않는다.
- **`JWT_SECRET_KEY`는 deprecated** — HS256 시절 값이며 RS256 전환 후 쓰지 않는다. 새 코드에서 참조하지 않는다.
- **스포크 ↔ 스포크 직접 import 금지** — 앱 간 의존은 허브(`ontology`)를 통한다. 위반은 `lint-imports`가 차단한다 (§5).
- **`alembic/` 은 ruff 검사 제외 대상**이다. 자동 생성 파일을 임의로 손보지 않는다.
- **`fastapi/core/` 의 import 경로는 `jsangho.core.`** 로 시작한다 (§0-3). 경로 표기가 어긋나면 코드를 쓰기 전에 멈추고 확인한다.

## 커밋 메시지 규칙
- Conventional Commits 형식 사용 (feat:, fix:, docs:, refactor:)
- 제목은 50자 이내
- 한국어로 작성
- 예시: feat: 사용자 로그인 기능 추가