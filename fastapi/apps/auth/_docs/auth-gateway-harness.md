# AUTH-GATEWAY-HARNESS.md

Claude Code 작업 지시서 — `superstar` 내장 인증을 `apps/auth`로 분리 + RS256 전환

**대상 저장소:** `fastapi/` 모노레포 (모듈러 모놀리식, `ontology` 허브 + 스포크 스타 토폴로지)
**원칙:** 발급(개인키 접근)은 `apps/auth`에만, 그 외 모든 컨테이너·앱은 검증(공개키)만.

> 이 문서는 원본 지시서(`ragtailor.com` / 영화 앱 / RS256 신규 도입 전제)를 이 프로젝트의 실제 상태에 맞춰 다시 쓴 것이다. 아래 "0. 컨텍스트"는 추측이 아니라 실제 코드를 읽고 확인한 내용이다.

---

## 구현 현황 (2026-07-22 기준, 2026-07-23 재검증)

> **먼저 읽을 것:** 이 절은 원본 지시서(2.1~2.9) 실행 당시 기록이다. 같은 날 이후 별도 세션에서 범위가 더 확장됐고(회원가입/프로필 재이관, `auth.jsangho.cloud` 실 라우팅) 그 내용은 이 절 끝의 **"0-1. 범위 확장"**에 있다 — 최종 상태를 알고 싶으면 그쪽을 우선 참고.

2.1(auth 골격+이관) · 2.2(core/security) · 2.3(UserModel core 이동) · 2.9(.importlinter)를 **한 커밋으로 묶어 완료**했다 — HS256→RS256은 하드 컷오버라 로그인이 RS256을 발급하는 순간 기존 HS256 검증부(`bearer_auth`, `nick_fury_router`)가 전부 깨지기 때문에, 발급·검증·엔티티 이동을 분리 커밋할 수 없었다. `docs_gate_router`(구 `nick_fury_router`) 이동도 같은 이유로 이번 커밋에 포함됐다 — 로그인이 `pamela_cook_router`(auth로 이동)의 `get_pamela_cook` 팩토리를 직접 import하고 있어서 분리 불가능했다.

**계획과 달라진 점(모두 실행 중 발견한 의존성 문제 때문):**
- `Role`(RBAC)·`password.py`(해시)·`UserModel`을 `apps/auth`가 아니라 **`core`**로 옮겼다. `superstar`에 남는 회원가입(`jason_mask`)이 이 셋을 그대로 써야 하는데, `auth`를 import하면 절대 규칙(1절) 위반이라 공유 커널(`core`)로 내렸다. 위치: `core/entities/user_model.py`, `core/security/{role,password,token_verifier,dependencies,cookie}.py`.
- Google/Kakao/Naver의 프로필 값 객체·포트·유스케이스가 필드 하나 안 다르고 완전히 동일한 모양이어서, 원본 문서가 암시한 provider별 3벌 대신 **`OAuthProfile`/`OAuthIdentityProvider`/`OAuthLoginUseCase`/`OAuthLoginInteractor` 1벌 + provider 파라미터**로 합쳤다.
- `kayfabe`가 FK 때문에 `superstar.domain.entities.user_model`을 직접 import하던 **기존 스타 토폴로지 위반**을 `UserModel`의 core 이동으로 함께 해소했다(`ple_match_pick_pg_repository.py`, `ple_events_pg_repository.py` 수정).
- `core/matrix/grid_oracle_database_manager.py`의 `init_db()`에 있던 죽은 참조(`import user.domain.entities.user_model` — 존재한 적 없는 `user` 패키지, try/except로 항상 무시됨)를 `core.entities.user_model`로 고쳤다. `users` 테이블이 `Base.metadata`에 실제로 등록되는 건 이번이 처음이다.
- 로그인/OAuth 콜백 응답에 `refreshToken` 필드가 새로 추가됐다(리프레시 로테이션, 2.6). 프런트(`www/`)는 아직 이 필드를 안 쓴다 — 이번 범위 밖.

**검증 완료:** `ruff check`/`ruff format` 통과, `lint-imports`(신규 `auth_isolation` 계약 포함 4개 계약 전부 KEPT — kayfabe 위반도 사라짐), 실제 RSA 키페어로 발급→검증 왕복·`aud` 불일치 거부·서명 변조 거부·`alg=none` 위조 거부·JWKS n/e 계산까지 스모크 테스트 통과. 이후 `uv add cryptography`로 `uv.lock`도 잠갔고, 운영 컨테이너(`cloudjsanghoall-backend-1`)에서 `cryptography`/`pyjwt` import 확인 완료. 실제 `.env`에 `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY`/`SERVICE_AUD`도 채워 넣고(로컬 `.env`만 — 서버 `.env`는 아직) 그 키로 발급→검증 왕복까지 재확인.

**2.5 완료:** `fastapi/auth_main.py` 생성 — `login`/`logout`/`refresh`/`oauth_callback`(prefix `/auth`)·`jwks`(prefix 없음)·`/healthz`만 mount하는 단독 엔트리포인트. `heyman`/`ontology` 등 무거운 앱을 안 거치니 로컬에서 바로 뜬다.
- 로컬에서 `python auth_main.py`로 실제 기동해 확인: `/healthz` 200, `/.well-known/jwks.json`이 실제 `.env`의 공개키와 일치하는 JWK 반환, `GET /auth/auth/google/login`이 `.env`의 실제 `GOOGLE_CLIENT_ID`/`GOOGLE_OAUTH_REDIRECT_URI`로 정확한 Google authorize URL을 307 리다이렉트. `POST /auth/login`/`POST /auth/refresh`는 로컬에 DB/Redis가 없어(`pgvector`/`redis`는 도커 네트워크 내부 호스트명, 이 PC엔 도커 자체가 없음) DB/Redis 연결 시도까지는 도달하고 그 지점에서 실패 — 라우팅·DI·리포지토리 배선은 이렇게 확인됨.
- **버그 발견 및 수정:** `auth_main.py`에 `main.py`가 갖고 있던 Windows `WindowsSelectorEventLoopPolicy` 설정이 빠져 있어서 psycopg 비동기 연결이 항상 실패했다(`ProactorEventLoop`는 psycopg async와 호환 안 됨). `main.py`와 똑같은 이유로 `python -m uvicorn auth_main:app`이 아니라 `python auth_main.py`로 직접 실행해야 정책이 적용된다(CLI로 띄우면 uvicorn이 앱을 import하기 전에 이미 이벤트 루프를 만들어서 정책 설정이 늦는다). `pyproject.toml` per-file-ignores에 `auth_main.py`도 `main.py`와 같은 이유로 `E402` 추가.

**2.8 1단계 완료:** `docker-compose.yaml`에 `auth` 서비스 등록 — `backend`와 같은 이미지(`fastapi/Dockerfile`)·같은 `./.env`(사용자 확인: 지금은 분리하지 않고 공유, 원본 문서의 `.env.auth`/`.env.backend` 완전 분리는 보류), `command: uvicorn auth_main:app --host 0.0.0.0 --port 9000`, **`ports:` 매핑 없음**. `redis`/`pgvector` `depends_on` 추가(`neo4j`는 auth에 불필요해서 제외). YAML 문법은 로컬에서 `yaml.safe_load`로 확인(이 PC에 도커가 없어 `docker compose config`로는 검증 못 함). **아직 빌드·기동은 안 함** — 리포의 Docker 워크플로 규칙대로 빌드는 사용자가 명시적으로 요청할 때만.
- 다음 단계: 서버(`DESKTOP-9E3A4EC`)에 이 커밋 배포 → 서버 `.env`에 `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` 추가 → `docker compose up --build -d auth`로 기동 확인 → 그 다음에야 2.8 2단계(cloudflared 라우팅) 진행.

**2.7 완료:** `scripts/generate_jwt_keys.sh` 작성 — 원본 지시서 스니펫(`openssl genrsa`/`openssl rsa -pubout`)에 더해, 실제 `token_issuer.py`/`token_verifier.py`가 `.env`에서 읽는 형식(PEM 개행을 문자 그대로의 `\n`으로 이스케이프한 한 줄)까지 바로 출력하도록 확장했다 — 원본 스니펫은 PEM 파일만 만들고 이 변환은 안 했음. 기존 키 파일이 있으면 덮어쓰지 않고 에러로 중단하는 가드 추가. 스크래치 디렉터리에서 실행 → 이스케이프된 값을 `\n`으로 되돌려 `cryptography.load_pem_private_key`로 로드 → 실제로 `jwt.encode(algorithm="RS256")`까지 왕복 검증 완료(원본 PEM과 바이트 단위 일치 확인). PEM 파일은 루트/`fastapi` 양쪽 `.gitignore`에 이미 `*.pem`으로 걸려있어 커밋 걱정 없음.

**서버 `.env` 키 교체 완료 (2026-07-22):** 서버(`DESKTOP-9E3A4EC`, `ssh messi@ssh.jsangho.cloud:/home/messi/project/cloud.jsangho.all`) `.env`에 이미 `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` 값이 들어있던 것을 발견(문서 기록과 불일치 — 이전 세션에서 채운 것으로 추정, 원인 불명). 사용자 확인 후 로컬 키 재사용 대신 **서버 전용으로 새로 발급해서 덮어씀** — `scripts/generate_jwt_keys.sh`를 서버로 복사해 `/tmp` 임시 디렉터리에서 직접 실행(개인키가 dev PC로 나가지 않게), `.env`의 기존 두 줄만 안전하게 치환(다른 값은 건드리지 않음), 임시 PEM·헬퍼 스크립트는 즉시 삭제. 현재 서버에 배포된 `main` 브랜치는 아직 RS256 마이그레이션 커밋을 포함하지 않아(이번 세션 커밋들은 로컬 `ho`에만 있음) 이 값을 읽는 코드가 서버에 없다 — 지금 당장 컨테이너 재시작 등은 불필요.

**2.8 1단계 실배포 완료 (2026-07-22):** `ho`→`main`/`messi` 커밋·푸시(`1b0eb11`) 후 서버에서 `git pull`, `docker compose up --build -d auth`로 실제 기동. 빌드는 `fastapi/Dockerfile`이 백엔드와 동일 이미지라 torch/CUDA 등 무거운 의존성까지 전부 새로 받음(직전에 빌드 캐시를 전량 정리했던 여파, 약 5분 소요, 디스크는 101GB/1007GB로 여유 있게 완료). 컨테이너 내부(`docker compose exec auth python -c ...`, 이미지에 `curl` 없음)에서 확인:
- `GET /healthz` → `{"ok":true}`
- `GET /.well-known/jwks.json` → 새로 발급한 키의 JWK(`kid: jsangho-auth-1`) 정상 반환
- `GET /auth/auth/google/login` → 307, 실제 `GOOGLE_CLIENT_ID`/`redirect_uri=https://api.jsangho.cloud/api/auth/google/callback`로 정확히 리다이렉트
- `POST /auth/login`(존재하지 않는 `userId`) → `401 "ID 또는 비밀번호가 올바르지 않습니다."` — DB(pgvector) 조회까지 실제로 도달함을 확인(로컬에서는 DB가 없어 여기까지 못 봤던 부분). 완료 기준 §3 첫 항목(`/healthz` 200) 및 로그인 경로 DB 연동을 운영 컨테이너에서 처음으로 실증.

**아직 안 한 것:**
- pytest 테스트 코드는 작성하지 않았다(스모크 테스트 스크립트 + 실제 프로덕션 왕복 확인으로만 검증). 완료 기준의 pytest 항목은 미완.
- `superstar → auth` docs 게이트 쿠키 이름이 여전히 `kayfabe_docs_session`이다(원본 그대로 유지 — 이름 자체를 바꾸는 건 이번 범위 밖).
- `kayfabe.adapter.outbound.pg.ple_events_pg_repository`를 단독 import하면 `kayfabe.adapter.outbound.mappers` 패키지의 순환 참조로 `ImportError`가 난다(기존부터 있던 구조적 문제, 이번 변경과 무관 — `main.py` 정상 로드 순서에서는 안 터지는 것으로 보이나 확인 필요).
- `auth_main.py` 상단 docstring이 "아직 docker-compose 서비스로는 등록하지 않았다 — 로컬 검증용"이라고 남아 있는데, 아래 2.8 2단계 이후로는 사실이 아니다(실제로 등록·배포·라우팅까지 끝남). 코드 주석 정리는 이번 문서 업데이트 범위 밖으로 남겨둔다.

---

## 0-1. 범위 확장 (2026-07-22, 같은 날 후속 커밋 5개)

> 아래는 위 "구현 현황" 작성 시점 이후 **별도 세션에서 사용자 확인을 거쳐 진행된 후속 작업**이다. 원본 지시서(2.0/2.4)가 "회원가입·프로필은 superstar 잔존, 2.8 2단계는 별도 확인 후 진행"이라고 못박은 것과 방향이 다르므로, 이 섹션에서 무엇이 원안과 달라졌는지 명시한다.

**2.8 2단계 완료 — `auth.jsangho.cloud` 실제 라우팅 (`6de929f`):** `docker-compose.yaml`의 `auth` 서비스에 전용 브리지 네트워크 `auth_net`(172.28.0.2:9000 고정 IP)를 추가했다. 호스트 포트를 노출하지 않으면서(절대 규칙 준수) cloudflared가 컨테이너 재생성으로 IP가 흔들리지 않고 라우팅할 수 있게 하기 위함. 서버 `/etc/cloudflared/config.yml`에 `auth.jsangho.cloud` 호스트명이 등록되어 현재 실제로 서비스 중이다(2.8 원안의 "별도 커밋/작업으로 진행, 그때 다시 사용자 확인" 절차를 이 커밋에서 수행).

**www 로그인 연동 (`881728e`):** `auth_main.py`에 CORS 미들웨어 추가(`main.py`와 달리 원래 없었음, `jsangho.cloud`/`www.jsangho.cloud`/로컬 오리진 허용). `www/lib/api.ts`에 `authBaseUrl` 상수 신설, 이메일/비밀번호 로그인 호출을 `auth.jsangho.cloud/auth/login`으로 전환. 이 시점엔 회원가입·프로필은 아직 `api.jsangho.cloud`(구 경로) 유지 — 실제 브라우저 로그인으로 프로덕션 왕복 확인.

**SNS(Google/Kakao/Naver) 로그인 연동 (`2219cbb`):** `auth_main.py`의 이중 prefix 버그 수정 — `oauth_callback_router` 자체 경로가 이미 `/auth/{provider}/...`로 시작하는데 `prefix="/auth"`를 추가로 주면 `/auth/auth/...`가 되던 문제. `oauth_callback_router`는 prefix 없이 mount하도록 변경. `www`의 SNS 로그인 버튼도 `authBaseUrl`로 전환. OAuth 콜백 redirect_uri를 `api.jsangho.cloud`→`auth.jsangho.cloud`로 바꾼 `.env`/각 provider 콘솔 설정은 서버에서 직접 했고 이 리포에는 추적되지 않는다(`.env`는 gitignore). 3개 provider 모두 프로덕션에서 실제 로그인 왕복 확인 완료.

**회원가입·프로필 조회를 `auth`로 재이관 (`696cbfa`) — 원안(2.0/2.4)을 뒤집는 결정:** 원본 지시서는 `jason_mask`(회원가입)/`murder_list`(프로필 조회)를 "인증이 아니라 유저 도메인 로직"으로 보고 `superstar`에 잔존시켰다. 이 커밋에서 그 결정을 재검토해 뒤집었다 — www가 인증 관련 모든 것을 `auth.jsangho.cloud` 한 곳에서만 접근하게 하려는 목적. 구체적으로:
- `auth`의 `UserRepository`/`UserPgRepository`에 `create_user` 추가(기존 `create_oauth_user`와 나란히).
- `SignupUseCase`/`SignupInteractor`, `ProfileUseCase`/`ProfileInteractor` 신설(`auth`의 기존 DI 팩토리 컨벤션 `dependencies/auth_provider.py` 그대로 따름).
- `auth_main.py`에만 `/auth/signup`, `/auth/users/{id}`로 mount(`main.py`의 공용 `auth_router` 집계에는 포함하지 않음 — `main.py`/`api.jsangho.cloud` 쪽 회원가입·프로필 경로는 제거됨).
- `superstar`에서 `jason_mask`/`murder_list` 관련 코드 전부 삭제(라우터·리포지토리·유스케이스·포트 전부) — **더 이상 "잔존"이 아니라 완전히 없어짐.** 아래 2.0 매핑표·2.4 절의 해당 서술은 이 커밋 이후 사실과 다르다.
- `www`의 회원가입(`login-form.tsx`)·프로필 조회(`lib/auth-api.ts`)도 `authBaseUrl`로 전환.
- 프로덕션에서 회원가입→로그인→프로필 조회, 중복 가입 거부, 구 `api.jsangho.cloud` 경로 404 확인까지 실제 검증됨.
- `.importlinter` 변경 불필요(`auth`가 이미 등록된 root package이고 토폴로지 위반 없음) — 커밋 메시지에도 명시.

> **결과적으로 2.0 매핑표의 `jason_mask_router.py`/`murder_list_router.py` 행("superstar에 잔존")과 2.4의 관련 서술, §3 완료 기준의 "superstar에 남은 jason_mask/murder_list 라우터가 core.security.dependencies를 통해서만 인증 검증을 받음" 항목은 이 후속 결정으로 대상 자체가 사라져 더 이상 유효하지 않다. 표는 원본 지시서 기록 보존 차원에서 그대로 두고, 실제 최종 상태는 이 섹션을 우선한다.**

---

## 0. 컨텍스트 (실제 상태)

- 앱 목록(`.importlinter` `root_packages` 기준, 허브 `ontology` + 스포크): `ontology`(허브), `titanic`, `kayfabe`, `superstar`, `admin`, `heyman`, `soccer`. 도메인 이름은 영화 제목이 아니라 WWE/코믹스 코드네임이다.
- **인증은 이미 구현되어 있다.** 전부 `superstar` 앱 안에 있다:
  - `superstar/domain/services/jwt_token.py` — HS256, `JWT_SECRET_KEY` 대칭키, 7일 만료. 리프레시 토큰 없음.
  - `superstar/domain/services/password.py` — PBKDF2-HMAC-SHA256(솔트+10만 회).
  - `superstar/domain/entities/user_model.py` — `UserModel` ORM 엔티티(`users` 테이블).
  - `superstar/domain/value_objects/role.py` — `UserRole(user, admin)`.
  - `superstar/adapter/outbound/{google,kakao,naver}_oauth_client.py` — OAuth 3사 클라이언트.
  - `superstar/adapter/inbound/api/bearer_auth.py` — `require_auth`, `require_self_or_admin` (검증부 Depends).
  - `superstar/adapter/inbound/api/v1/*_router.py` — 실제 엔드포인트 매핑:

    | 파일 | 실제 역할 |
    |---|---|
    | `pamela_cook_router.py` | `POST` 로그인 (`login_id`+`password`) |
    | `jason_mask_router.py` | `POST` 회원가입 |
    | `clark_kent_router.py` | Google OAuth 콜백 |
    | `bruce_wayne_router.py` | Kakao OAuth 콜백 |
    | `peter_parker_router.py` | Naver OAuth 콜백 |
    | `murder_list_router.py` | `GET` 유저 프로필 조회 (`require_auth` 사용) |
    | `nick_fury_router.py` | **FastAPI `/docs` 게이트** — Swagger/Redoc 접근을 관리자 로그인 쿠키(`kayfabe_docs_session`, 15분 만료)로 보호. 원본 문서가 말한 "기존 `login_gate.py`"에 해당하는 실제 코드가 이것이다(별도 파일이 아니라 `superstar` 안의 라우터). `main.py`에 `prefix` 없이 직접 mount됨.

- **기존 스타 토폴로지 위반이 이미 존재한다.** `kayfabe`(스포크)가 `superstar.domain.entities.user_model`을 FK 참조 때문에 직접 import 중이다(`ple_match_pick_pg_repository.py`, `ple_events_pg_repository.py`). `.importlinter`의 `no_spoke_to_spoke` 계약을 위반하고 있다.
- `core/`는 `root_packages`/토폴로지 계약 밖에 있는 사실상의 shared kernel이다(`core.matrix.grid_oracle_database_manager`, `core.matrix.vault_keymaker_secret_manager` 등, `main.py`와 모든 스포크가 자유롭게 import). 비밀은 `Keymaker.get_secret(name, default)` (`core/matrix/vault_keymaker_secret_manager.py`)로 `.env`에서 읽는다.
- 실제 import 경로는 `core.matrix....`다. `fastapi/CLAUDE.md`는 `jsangho.core.` 접두어를 요구하지만 코드베이스 어디에도 그렇게 쓰인 곳이 없다 — 문서가 실제 구현과 어긋난 상태다. 이 작업에서는 **실제로 동작하는 관례(`core.matrix...`)를 따른다.**
- 도메인은 `ragtailor.com`이 아니라 `jsangho.cloud`(`.env.example`의 `NEXTAUTH_URL=https://jsangho.cloud`, `main.py` CORS 오리진 기준). `api.jsangho.cloud`는 **이미 존재한다** — 리포 밖 서버(`DESKTOP-9E3A4EC`)의 named Cloudflare Tunnel(`jsangho.cloud`, `/etc/cloudflared/config.yml`, systemd `cloudflared`)이 `ssh.jsangho.cloud`/`api.jsangho.cloud`(/`n8n.jsangho.cloud`)를 라우팅 중이다. `auth.jsangho.cloud`는 같은 터널에 호스트명 하나를 추가하는 방식으로 확장 가능 — 다만 뒤에서 응답할 `auth` 서비스가 실제로 떠 있어야 의미가 있으므로, 이 문서의 코드 이관(2.1~2.9)이 끝난 뒤 진행한다(2.8 참고).
- `docker-compose.yaml`(이 리포 안): 모든 서비스가 호스트 포트를 **직접 매핑**하고 있다(`8000:8000`, `5432:5432` 등). `dreamscape` 네트워크, `cloudflared` 서비스는 compose 어디에도 없다(직전 커밋 `afb0f58`에서 죽은 cloudflared 서비스를 제거함). 실제 터널은 리포 밖 서버 호스트에서 systemd로 별도 관리된다(위 항목 참고) — 이 리포의 compose를 건드려도 서버의 `/etc/cloudflared/config.yml`은 자동으로 바뀌지 않는다.
- Redis는 이미 스택에 있고(`redis:7-alpine`), `ontology` 앱이 `redis.asyncio`로 직접 연결하는 선례가 있다(`ontology/adapter/outbound/repositories/redis_crawl_job_queue_repository.py`, `REDIS_HOST`/`REDIS_PORT` 환경변수, `decode_responses=True`).
- 사용자 확인 사항(이번 세션에서 결정됨):
  1. **범위: 이관(Migrate).** `superstar`의 인증 코드를 `apps/auth`로 실제로 옮긴다. 중복 병행 구현은 하지 않는다.
  2. **서명 알고리즘: RS256 전환.** 현재 운영 중인 HS256(`JWT_SECRET_KEY`)을 RS256 키페어로 교체한다.
  3. **배포 분리 범위: 코드 경계 우선.** `auth_main.py`·`.importlinter` 계약·검증 로직까지만 이번 범위. 실제 별도 컨테이너/서브도메인(`auth.jsangho.cloud`) 분리는 `docker-compose.yaml`/cloudflared 라우팅이 준비된 뒤 **별도로** 진행한다(아래 2.8 참고, 지금은 건드리지 않는다).

---

## 1. 절대 규칙 (위반 시 작업 중단 후 보고)

- `apps/auth` 밖의 스포크(`titanic`, `kayfabe`, `superstar`, `admin`, `heyman`, `soccer`)와 허브(`ontology`) **어디에서도** `auth.*`를 import하지 않는다. 검증이 필요하면 `core`의 공유 검증 함수만 쓴다.
- 어떤 서비스에도 `docker-compose.yaml`에 새 `ports:` 매핑을 추가하지 않는다.
- JWT 검증부의 허용 알고리즘은 `algorithms=["RS256"]` 리터럴로 하드코딩한다. 환경변수·설정으로 빼지 않는다.
- 개인키(`JWT_PRIVATE_KEY`)를 읽는 코드는 `apps/auth`의 발급 함수(`token_issuer.py`)에만 존재한다. `core`(모든 컨테이너 공용) 쪽에서 개인키 참조가 발견되면 즉시 수정한다.
- 비밀키·개인키를 저장소에 커밋하지 않는다. PEM 파일, `.env.*`는 `.gitignore`에 있는지 확인한다.
- `superstar`에 남는 라우터(`jason_mask`=회원가입, `murder_list`=프로필)가 이번 작업으로 `auth` 스포크를 import하게 되면 절대 규칙 위반이다 — 검증은 `core`를 통해서만 받는다.

---

## 2. 작업 목록

### 2.0 마이그레이션 매핑표 (무엇을 옮기고, 무엇을 남기는가)

| 기존 위치(`superstar`) | 이동 후(`auth`) | 비고 |
|---|---|---|
| `domain/services/jwt_token.py` | `domain/services/token_issuer.py`(발급, RS256) + `domain/services/token_verifier.py`(검증) | 검증 함수는 이후 2.2에서 다시 `core`로 얇게 재노출 |
| `domain/services/password.py` | `domain/services/password.py` | **알고리즘은 그대로 이관**(PBKDF2 유지). bcrypt/argon2 교체는 이번 범위 밖 — 필요하면 별도 요청으로 진행 |
| `domain/value_objects/role.py` | `domain/value_objects/role.py` | `Permission`, role→permission 매핑 추가(RBAC 신규) |
| `domain/value_objects/{google,kakao,naver}_profile.py` | 동일 파일명 이동 | 변경 없음 |
| `domain/entities/user_model.py` | **`core`로 이동** (아래 2.3 참고) | `auth`·`superstar`(잔존 `jason_mask`/`murder_list`)·`kayfabe` 세 곳 모두 FK/조회로 필요 — `auth` 전용으로 옮기면 기존 `kayfabe` 위반을 못 고치고 새 위반만 하나 더 생긴다 |
| `adapter/outbound/{google,kakao,naver}_oauth_client.py` | 동일 파일명 이동 | 변경 없음 |
| `adapter/outbound/pg/clark_kent_pg_repository.py` | `adapter/outbound/pg/user_pg_repository.py`로 통합 | `bruce_wayne`/`peter_parker`도 같은 레포를 재사용 중이었음 — 이관하면서 3개 provider가 공유하는 구조를 그대로 유지 |
| `adapter/inbound/api/v1/pamela_cook_router.py` | `adapter/inbound/api/login_router.py` (`POST /login`) | |
| `adapter/inbound/api/v1/clark_kent_router.py` | `adapter/inbound/api/oauth_callback_router.py` (`GET /callback/google`) | bruce_wayne·peter_parker와 함께 provider별 핸들러로 통합 |
| `adapter/inbound/api/v1/bruce_wayne_router.py` | 〃 (`GET /callback/kakao`) | |
| `adapter/inbound/api/v1/peter_parker_router.py` | 〃 (`GET /callback/naver`) | |
| `adapter/inbound/api/bearer_auth.py` | **삭제(이관 후)** — 로직은 `core`의 `get_current_user`/`RoleChecker`로 대체 | `murder_list_router.py`(잔존)는 `core` 쪽 의존성으로 갈아탐 |
| `adapter/inbound/api/v1/nick_fury_router.py` | `adapter/inbound/api/docs_gate_router.py`로 이동 | 관리자 전용 docs 게이트도 토큰 발급/검증을 쓰므로 `auth`로 옮기는 게 맞다. **단, `main.py` mount 방식(무prefix)을 그대로 유지해야 하므로 이동 전 사용자 확인 1회 필요(2.4 참고)** |
| `adapter/inbound/api/v1/jason_mask_router.py`(회원가입) | **`superstar`에 잔존** | 원본 지시서도 회원가입은 범위 밖으로 명시. `password.hash_password`만 `auth`에서 import |
| `adapter/inbound/api/v1/murder_list_router.py`(프로필 조회) | **`superstar`에 잔존** | 순수 프로필 읽기 — 인증이 아니라 유저 도메인 로직. `require_auth` 대신 `core`의 `get_current_user`로 갈아탐 |

### 2.1 `apps/auth/` 구조 (헥사고날 — `fastapi/CLAUDE.md` §2 레이어 규칙 그대로 적용)

```
apps/auth/
├── __init__.py
├── domain/
│   ├── services/
│   │   ├── token_issuer.py     # RS256 발급 — JWT_PRIVATE_KEY 유일한 사용처
│   │   ├── token_verifier.py   # RS256 검증 — core에서 재노출할 원본
│   │   └── password.py         # PBKDF2 그대로 이관
│   └── value_objects/
│       ├── role.py             # UserRole + Permission + role→permission 매핑(RBAC)
│       ├── google_profile.py
│       ├── kakao_profile.py
│       └── naver_profile.py
├── app/
│   ├── ports/{input,output}/   # LoginUseCase, RefreshUseCase, OAuthCallbackUseCase 등
│   └── use_cases/              # *_interactor.py
├── adapter/
│   ├── inbound/api/
│   │   ├── login_router.py         # POST /login
│   │   ├── logout_router.py        # POST /logout
│   │   ├── refresh_router.py       # POST /refresh
│   │   ├── oauth_callback_router.py# GET /callback/{provider}
│   │   ├── jwks_router.py          # GET /.well-known/jwks.json (prefix 없이 mount)
│   │   └── docs_gate_router.py     # 기존 nick_fury_router — 사용자 확인 후 이동
│   └── outbound/
│       ├── {google,kakao,naver}_oauth_client.py
│       ├── pg/user_pg_repository.py
│       └── redis/refresh_token_repository.py   # 로테이션 저장소
└── dependencies/
    └── auth_provider.py        # get_{x}_use_case() 팩토리
```

- `UserModel`은 여기 없다(2.3 참고) — `core`에서 import한다.
- `.well-known/jwks.json`은 공개키를 JWK 형식(`kid` 포함)으로 반환한다. `/api` prefix 없이 mount(기존 `nick_fury_router`가 무prefix로 mount되는 선례와 동일한 방식).
- 리프레시 토큰: Redis에 저장, 로테이션 방식. 재사용 감지 시 해당 유저의 모든 세션(jti) 폐기.

### 2.2 `core` 쪽 신규 — 발급은 `auth` 내부, 검증은 `core` 공용

원본 문서는 `core/security.py` 단일 파일에 발급+검증을 같이 두자고 했지만, 그러면 검증부를 import하는 모든 스포크가 발급 함수와 같은 모듈을 로드하게 되어 "개인키 접근 코드는 발급 함수에만" 원칙과 부딪힌다. 그래서 물리적으로 분리한다.

```
core/security/
├── __init__.py
├── token_verifier.py   # 공개키만 사용. auth.domain.services.token_verifier를 그대로 재노출하거나 얇게 래핑
├── dependencies.py      # get_current_user, RoleChecker — 모든 앱이 Depends로 사용
└── cookie.py            # COOKIE_KWARGS
```

```python
# core/security/token_verifier.py — 모든 컨테이너 공용, JWT_PUBLIC_KEY만 필요
def verify_token(token: str, aud: str) -> TokenPayload: ...
    # jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"], audience=aud)

# core/security/dependencies.py
async def get_current_user(request: Request) -> TokenPayload: ...
    # 쿠키 또는 Authorization 헤더에서 토큰 추출 → verify_token(aud=SERVICE_AUD)
    # Redis 블랙리스트 조회(jti 기준) 포함 — 즉시 차단 계정 처리용

class RoleChecker:
    def __init__(self, *allowed: Role): ...
    def __call__(self, user: TokenPayload = Depends(get_current_user)): ...
        # roles 클레임 검사, 미충족 시 403

# core/security/cookie.py
COOKIE_KWARGS = dict(domain=".jsangho.cloud", secure=True, httponly=True, samesite="lax")
```

- `core/security/token_verifier.py`는 `JWT_PUBLIC_KEY`만 `get_keymaker().get_secret(...)`로 읽는다. 개인키는 여기서 절대 참조하지 않는다.
- access token 클레임: `sub`, `roles`, `aud`, `exp`, `iat`, `jti`, 헤더에 `kid`.
- `aud`: 현재 실제 배포 컨테이너가 `main.py` 하나뿐이므로 기본값은 `SERVICE_AUD=jsangho-api` 하나로 시작한다(원본 문서의 `ragtailor-api`/`ragtaylor-api`/`acoder-api`처럼 서비스별로 나눌 대상이 지금은 없다). `docs_gate_router`(관리자 docs 게이트)는 같은 프로세스 안에서 발급/검증하므로 별도 `aud`(예: `jsangho-docs-gate`)를 쓸지, 같은 `aud`를 공유할지는 2.1의 이동 여부와 함께 확인한다.

### 2.3 `UserModel` 소속 — 기존 위반 해소 + 신규 위반 예방

`UserModel`을 `apps/auth`로 옮기면 `kayfabe`가 FK 때문에 `auth`를 import해야 해서 "아무도 `auth`를 import하지 않는다" 절대 규칙을 즉시 깬다. 지금도 `kayfabe`가 `superstar.domain.entities.user_model`을 직접 import하는 기존 위반이 있다(0. 컨텍스트 참고).

**해결안:** `UserModel`(ORM 엔티티, 테이블 정의)만 `core`로 옮긴다. 예: `core/matrix/grid_oracle_database_manager.py`가 있는 자리에 `core/entities/user_model.py` 신설, 또는 기존 파일 옆에 배치. 정확한 위치는 리포의 `core/matrix` 네이밍(Matrix 테마)을 따를지 평범한 이름으로 둘지 다음 단계에서 확인한다. `password_hash` 컬럼은 이미 해시된 문자열이라 엔티티 자체를 공유해도 개인키 격리 원칙과 충돌하지 않는다.

- `auth`, `superstar`(잔존 `jason_mask`/`murder_list`), `kayfabe` 모두 `core`에서 import하도록 통일 → 기존 위반과 신규 위반을 동시에 제거.
- 이 변경은 원본 지시서에 없던 항목이다. 실행 전 한 번 더 확인 없이 진행하되, PR/커밋 설명에 "기존 kayfabe→superstar 위반을 core 이동으로 함께 해소" 라고 명시한다.

### 2.4 `superstar`·`main.py` 리와이어링

- `superstar`에 남는 `jason_mask_router.py`(회원가입), `murder_list_router.py`(프로필)는 `require_auth` 대신 `core.security.dependencies.get_current_user`/`RoleChecker`를 사용하도록 import만 교체한다. 비즈니스 로직은 건드리지 않는다.
- `main.py`의 `from superstar.adapter.inbound.api.v1.nick_fury_router import nick_fury_router` / `app.include_router(nick_fury_router)`를 `auth.adapter.inbound.api.docs_gate_router`로 바꿀지는 **사용자에게 먼저 확인**한다(문서 게이트가 `main.py` 최상위에 prefix 없이 붙어 있어 실수하면 `/docs` 보호가 순간적으로 풀릴 수 있는 민감 지점).
- `main.py`에 `apps.auth` 관련 라우터(`login`, `logout`, `refresh`, `jwks`, `callback/*`)를 새로 include한다(지금까지 `user_router` prefix `/api`에 있던 `pamela_cook`/`clark_kent`/`bruce_wayne`/`peter_parker` 대신).

### 2.5 `auth_main.py` (신규, 루트, `main.py` 옆) — 지금은 코드만, 기동은 검증용

```python
from fastapi import FastAPI
from auth.adapter.inbound.api.login_router import login_router
from auth.adapter.inbound.api.logout_router import logout_router
from auth.adapter.inbound.api.refresh_router import refresh_router
from auth.adapter.inbound.api.oauth_callback_router import oauth_callback_router
from auth.adapter.inbound.api.jwks_router import jwks_router

app = FastAPI(
    title="jsangho Auth Gateway",
    docs_url=None, redoc_url=None, openapi_url=None,
)
app.include_router(login_router, prefix="/auth")
app.include_router(logout_router, prefix="/auth")
app.include_router(refresh_router, prefix="/auth")
app.include_router(oauth_callback_router, prefix="/auth")
app.include_router(jwks_router)  # /.well-known/jwks.json — prefix 없음

@app.get("/healthz")
async def healthz():
    return {"ok": True}
```

- 이번 범위에서는 `uvicorn auth_main:app`으로 **로컬에서만** 단독 기동해 완료 기준을 검증한다. `docker-compose.yaml`에 서비스로 등록하지 않는다(2.8 참고).

### 2.6 Redis 리프레시 토큰 로테이션

기존 `ontology/adapter/outbound/repositories/redis_crawl_job_queue_repository.py`와 동일한 접속 방식(`redis.asyncio`, `REDIS_HOST`/`REDIS_PORT` 환경변수, `decode_responses=True`)을 재사용한다.

```python
# auth/adapter/outbound/redis/refresh_token_repository.py
import redis.asyncio as redis

_REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
_REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
_KEY_PREFIX = "auth:refresh"   # auth:refresh:{jti}
```

- 재사용 감지 시 해당 `sub`의 전체 세션 키를 스캔·폐기.

### 2.7 키 생성 스크립트 `scripts/generate_jwt_keys.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
openssl genrsa -out jwt_private.pem 2048
openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem
echo "jwt_private.pem → auth 전용 .env의 JWT_PRIVATE_KEY 로"
echo "jwt_public.pem  → 그 외 컨테이너 .env의 JWT_PUBLIC_KEY 로"
```

- PEM 파일은 `.gitignore`에 추가되어 있는지 확인한다. 멀티라인 환경변수 주입은 base64 인코딩 후 디코드하는 방식으로 `Keymaker`에서 처리한다.
- 기존 `JWT_SECRET_KEY`(HS256)는 마이그레이션 기간 동안 `.env.example`에서 삭제하지 말고 `deprecated` 주석만 붙인다 — 실제 제거 시점은 사용자가 결정한다.

### 2.8 배포 분리 (컨테이너/서브도메인) — **이번 범위 밖, 코드 이관 완료 후 진행**

`docker-compose.yaml`에 `auth` 서비스를 추가하고 `auth.jsangho.cloud`로 라우팅하는 작업은 이번 지시서(2.1~2.9)에 포함하지 **않는다**. 코드 경계가 먼저다 — `auth_main.py`가 실제로 응답하기 전에 도메인부터 뚫으면 뒤에 아무것도 없는 라우트가 된다.

코드 이관이 끝나고 배포를 분리할 준비가 되면, 별도 커밋/작업으로 아래를 순서대로 진행하고 **그때 다시 사용자 확인을 받는다**:

1. (리포 안) `docker-compose.yaml`에 `auth` 서비스 추가 — 포트는 호스트에 노출하지 않는다:
   ```yaml
     auth:
       build: .
       command: uvicorn auth_main:app --host 0.0.0.0 --port 9000
       env_file: .env.auth          # JWT_PRIVATE_KEY, OAuth client secrets
       restart: unless-stopped
   ```
2. (서버, `DESKTOP-9E3A4EC`, `ssh messi@ssh.jsangho.cloud`) `/etc/cloudflared/config.yml`의 기존 named tunnel(`jsangho.cloud`, ID `97481026-a36b-4026-be61-fc06a4035893`)에 호스트명 하나를 추가한다. `ssh.jsangho.cloud`/`api.jsangho.cloud`가 이미 같은 방식으로 라우팅되어 있다.
   - `ingress`는 반드시 flow-style로 한 줄에 쓴다(`- hostname:` 로 시작하는 줄 자체를 만들지 않는다) — 이 서버는 원격 데스크톱→`nano` 붙여넣기 시 리스트 마커 뒤 공백이 지워지고 자동 들여쓰기가 붙어 YAML이 깨지는 이력이 있다.
   - `cloudflared tunnel route dns jsangho.cloud auth.jsangho.cloud`로 DNS 라우트 등록.
   - **반드시** `sudo cloudflared tunnel --config /etc/cloudflared/config.yml ingress validate` 로 검증한 뒤에만 `sudo systemctl restart cloudflared`. 검증 없이 재시작하면 SSH 라우트(`ssh.jsangho.cloud`)를 포함해 터널 전체가 끊긴다.

### 2.9 `.importlinter` 계약 수정

```ini
[importlinter]
root_packages =
    ontology
    titanic
    kayfabe
    superstar
    admin
    heyman
    soccer
    auth

# ────────────────────────────────────────────
# 계약 4(신규): auth는 그 누구도 import할 수 없다 (허브 ontology 포함)
# 검증이 필요하면 core.security만 사용한다.
# ────────────────────────────────────────────
[importlinter:contract:auth-isolation]
name = auth is not importable by any other app (including the hub)
type = forbidden
source_modules =
    ontology
    titanic
    kayfabe
    superstar
    admin
    heyman
    soccer
forbidden_modules =
    auth
```

- `no_spoke_to_spoke`, `star_topology_hub_only`, `clean_architecture_layers`의 기존 `source_modules`/`layers`/`containers` 목록에도 `auth`를 추가해 다른 스포크와 동일하게 계층·토폴로지 검사를 받게 한다(단, `star_topology_hub_only`의 스포크 라인에는 넣지 않는다 — 허브도 `auth`를 못 보게 하는 건 위 4번 계약이 이미 더 엄격하게 커버한다).

---

## 3. 완료 기준 (Acceptance Criteria)

> 2026-07-23 재검증: `lint-imports`/`ruff check`/`ruff format --check`를 직접 재실행해 확인. 나머지는 코드 존재·grep·git 커밋 로그 기준으로 확인(자동화 테스트로 재확인한 것은 아님 — 아래 각 항목 참고).

- [x] `uvicorn auth_main:app` 단독 기동 성공, `/healthz` 200. — 로컬 확인 + 프로덕션 컨테이너에서도 확인됨(위 2026-07-22 기록).
- [x] `uvicorn main:app` 기동 시 `JWT_PRIVATE_KEY` 없이 정상 동작(import 에러 없음). — `grep -rl JWT_PRIVATE_KEY`로 `apps/auth` 밖 참조 없음을 확인(2026-07-23). `main.py`는 실제 프로덕션에서 계속 서비스 중.
- [x] `auth`에서 발급한 토큰을 `core.security.token_verifier.verify_token`이 공개키만으로 검증 통과. — 스모크 테스트로 확인(자동화 pytest 아님).
- [ ] `aud`가 다른 토큰은 검증 실패(401/403)하는 테스트 존재. — 동작 자체는 스모크 테스트로 확인됨(위 2026-07-22 "검증 완료" 참고)이나, **저장된 pytest 파일은 없음** — 미완.
- [ ] 만료 토큰, 서명 변조 토큰, `alg=none`/`HS256` 강제 토큰 각각 거부하는 테스트 존재. — 동일하게 스모크 테스트로만 확인, pytest 파일 없음 — 미완.
- [ ] 리프레시 토큰 재사용 시 세션 전체 폐기되는 테스트 존재. — `refresh_token_repository.py`의 `consume()`/`revoke_all_for_sub()` 로직은 구현돼 있으나 테스트 파일 없음 — 미완.
- [x] `kayfabe`가 더 이상 `superstar`(또는 `auth`)를 직접 import하지 않음 — `core`의 `UserModel`을 사용. — `ple_match_pick_pg_repository.py`/`ple_events_pg_repository.py` grep으로 `core.entities.user_model`만 import함을 확인(2026-07-23).
- [~] ~~`superstar`에 남은 `jason_mask`/`murder_list` 라우터가 `core.security.dependencies`를 통해서만 인증 검증을 받음.~~ — **대상 소멸로 무효화.** `696cbfa`(0-1절 참고)에서 두 라우터 자체가 `superstar`에서 완전히 삭제되고 `auth`로 이관됐다(`signup_router.py`/`profile_router.py`). `superstar`에 남은 파일에서 grep 확인(2026-07-23) — 관련 코드 없음.
- [x] `lint-imports` 통과(`auth-isolation` 계약 포함, 기존 3개 계약도 회귀 없음). — 2026-07-23 직접 재실행: "Contracts: 4 kept, 0 broken."
- [ ] `pytest` 전체 통과. 기존 테스트 회귀 없음. — `apps/auth`용 테스트 파일 자체가 없음(`find`로 확인, 2026-07-23). 타 앱(titanic/ontology) 테스트는 이 작업과 무관하게 존재하나 auth 관련 회귀 검증 수단은 없음.

---

## 4. 진행 방식

1. 작업 전 `apps/auth`, `apps/superstar`, `apps/kayfabe`(FK 참조 부분), `core/`, `main.py`, `.importlinter` 현재 상태를 읽고 요약 보고 후 시작.
2. 커밋 단위: **2.1(auth 골격+이관) → 2.2(core/security) → 2.3(UserModel core 이동 + kayfabe 위반 해소) → 2.4(superstar/main.py 리와이어링) → 2.5(auth_main.py) → 2.6+2.7(redis+키스크립트) → 2.9(importlinter)** 순으로 기능별 분리 커밋.
3. `docs_gate_router` 이동 여부(2.4)는 커밋 전에 반드시 사용자 확인.
4. 불명확한 지점(`core/security` 물리적 위치를 `core.matrix` 네이밍 관례에 맞출지, `docs_gate_router`의 `aud` 분리 여부, PBKDF2를 bcrypt/argon2로 교체할지)은 추측하지 말고 질문한다.
5. 2.8(실제 컨테이너/서브도메인 분리)은 이번 작업 완료 보고에 "후속 작업 — 사용자 확인 필요" 항목으로만 남긴다. 코드나 compose를 먼저 건드리지 않는다.
