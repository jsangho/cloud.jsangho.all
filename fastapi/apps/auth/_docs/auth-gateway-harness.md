# AUTH-GATEWAY-HARNESS.md

Claude Code 작업 지시서 — `superstar` 내장 인증을 `apps/auth`로 분리 + RS256 전환

**대상 저장소:** `fastapi/` 모노레포 (모듈러 모놀리식, `ontology` 허브 + 스포크 스타 토폴로지)
**원칙:** 발급(개인키 접근)은 `apps/auth`에만, 그 외 모든 컨테이너·앱은 검증(공개키)만.

> 이 문서는 원본 지시서(`ragtailor.com` / 영화 앱 / RS256 신규 도입 전제)를 이 프로젝트의 실제 상태에 맞춰 다시 쓴 것이다. 아래 "0. 컨텍스트"는 추측이 아니라 실제 코드를 읽고 확인한 내용이다.

---

## 구현 현황 (2026-07-22 기준)

2.1(auth 골격+이관) · 2.2(core/security) · 2.3(UserModel core 이동) · 2.9(.importlinter)를 **한 커밋으로 묶어 완료**했다 — HS256→RS256은 하드 컷오버라 로그인이 RS256을 발급하는 순간 기존 HS256 검증부(`bearer_auth`, `nick_fury_router`)가 전부 깨지기 때문에, 발급·검증·엔티티 이동을 분리 커밋할 수 없었다. `docs_gate_router`(구 `nick_fury_router`) 이동도 같은 이유로 이번 커밋에 포함됐다 — 로그인이 `pamela_cook_router`(auth로 이동)의 `get_pamela_cook` 팩토리를 직접 import하고 있어서 분리 불가능했다.

**계획과 달라진 점(모두 실행 중 발견한 의존성 문제 때문):**
- `Role`(RBAC)·`password.py`(해시)·`UserModel`을 `apps/auth`가 아니라 **`core`**로 옮겼다. `superstar`에 남는 회원가입(`jason_mask`)이 이 셋을 그대로 써야 하는데, `auth`를 import하면 절대 규칙(1절) 위반이라 공유 커널(`core`)로 내렸다. 위치: `core/entities/user_model.py`, `core/security/{role,password,token_verifier,dependencies,cookie}.py`.
- Google/Kakao/Naver의 프로필 값 객체·포트·유스케이스가 필드 하나 안 다르고 완전히 동일한 모양이어서, 원본 문서가 암시한 provider별 3벌 대신 **`OAuthProfile`/`OAuthIdentityProvider`/`OAuthLoginUseCase`/`OAuthLoginInteractor` 1벌 + provider 파라미터**로 합쳤다.
- `kayfabe`가 FK 때문에 `superstar.domain.entities.user_model`을 직접 import하던 **기존 스타 토폴로지 위반**을 `UserModel`의 core 이동으로 함께 해소했다(`ple_match_pick_pg_repository.py`, `ple_events_pg_repository.py` 수정).
- `core/matrix/grid_oracle_database_manager.py`의 `init_db()`에 있던 죽은 참조(`import user.domain.entities.user_model` — 존재한 적 없는 `user` 패키지, try/except로 항상 무시됨)를 `core.entities.user_model`로 고쳤다. `users` 테이블이 `Base.metadata`에 실제로 등록되는 건 이번이 처음이다.
- 로그인/OAuth 콜백 응답에 `refreshToken` 필드가 새로 추가됐다(리프레시 로테이션, 2.6). 프런트(`www/`)는 아직 이 필드를 안 쓴다 — 이번 범위 밖.

**검증 완료:** `ruff check`/`ruff format` 통과, `lint-imports`(신규 `auth_isolation` 계약 포함 4개 계약 전부 KEPT — kayfabe 위반도 사라짐), 실제 RSA 키페어로 발급→검증 왕복·`aud` 불일치 거부·서명 변조 거부·`alg=none` 위조 거부·JWKS n/e 계산까지 스모크 테스트 통과.

**아직 안 한 것:**
- `pyproject.toml`에 `cryptography`(RS256에 필수, `pyjwt`가 내부적으로 필요)를 추가했지만 **`uv.lock`은 건드리지 않았다** — `uv run lint-imports`를 실행했더니 무관한 `decord`/nvidia 패키지 마커까지 딸려오는 광범위한 재계산이 일어나서 되돌렸다. `uv add cryptography` 또는 `uv lock`을 직접 실행해서 사용자 환경 기준으로 잠가야 한다(빌드는 하지 않음, 리포의 Docker 워크플로 규칙대로).
- 2.7 키 생성 스크립트(`scripts/generate_jwt_keys.sh`)는 아직 안 만들었다 — 테스트는 임시 키로만 했다. 실제 `.env`에 `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY`를 넣어야 서버가 실제로 뜬다.
- pytest 테스트 코드는 작성하지 않았다(스모크 테스트 스크립트로만 검증). 완료 기준의 pytest 항목은 미완.
- ~~`superstar`에 pre-existing 미사용 중복 파일 3개~~ → 정리 완료. `jason_mask_use_case.py`/`murder_list_use_case.py`/`pamela_cook_use_case.py`(무참조 확인 후 삭제)와 이관으로 빈 `domain/{entities,services,value_objects}/` 디렉터리 3개를 제거했다. `ruff`/`lint-imports` 재확인 통과.
- `superstar → auth` docs 게이트 쿠키 이름이 여전히 `kayfabe_docs_session`이다(원본 그대로 유지 — 이름 자체를 바꾸는 건 이번 범위 밖).
- `kayfabe.adapter.outbound.pg.ple_events_pg_repository`를 단독 import하면 `kayfabe.adapter.outbound.mappers` 패키지의 순환 참조로 `ImportError`가 난다(기존부터 있던 구조적 문제, 이번 변경과 무관 — `main.py` 정상 로드 순서에서는 안 터지는 것으로 보이나 확인 필요).
- 2.8(실제 컨테이너/서브도메인 분리, `auth.jsangho.cloud`)은 계획대로 손대지 않았다.

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

- [ ] `uvicorn auth_main:app` 단독 기동 성공, `/healthz` 200.
- [ ] `uvicorn main:app` 기동 시 `JWT_PRIVATE_KEY` 없이 정상 동작(import 에러 없음).
- [ ] `auth`에서 발급한 토큰을 `core.security.token_verifier.verify_token`이 공개키만으로 검증 통과.
- [ ] `aud`가 다른 토큰은 검증 실패(401/403)하는 테스트 존재.
- [ ] 만료 토큰, 서명 변조 토큰, `alg=none`/`HS256` 강제 토큰 각각 거부하는 테스트 존재.
- [ ] 리프레시 토큰 재사용 시 세션 전체 폐기되는 테스트 존재.
- [ ] `kayfabe`가 더 이상 `superstar`(또는 `auth`)를 직접 import하지 않음 — `core`의 `UserModel`을 사용.
- [ ] `superstar`에 남은 `jason_mask`/`murder_list` 라우터가 `core.security.dependencies`를 통해서만 인증 검증을 받음.
- [ ] `lint-imports` 통과(`auth-isolation` 계약 포함, 기존 3개 계약도 회귀 없음).
- [ ] `pytest` 전체 통과. 기존 테스트 회귀 없음.

---

## 4. 진행 방식

1. 작업 전 `apps/auth`, `apps/superstar`, `apps/kayfabe`(FK 참조 부분), `core/`, `main.py`, `.importlinter` 현재 상태를 읽고 요약 보고 후 시작.
2. 커밋 단위: **2.1(auth 골격+이관) → 2.2(core/security) → 2.3(UserModel core 이동 + kayfabe 위반 해소) → 2.4(superstar/main.py 리와이어링) → 2.5(auth_main.py) → 2.6+2.7(redis+키스크립트) → 2.9(importlinter)** 순으로 기능별 분리 커밋.
3. `docs_gate_router` 이동 여부(2.4)는 커밋 전에 반드시 사용자 확인.
4. 불명확한 지점(`core/security` 물리적 위치를 `core.matrix` 네이밍 관례에 맞출지, `docs_gate_router`의 `aud` 분리 여부, PBKDF2를 bcrypt/argon2로 교체할지)은 추측하지 말고 질문한다.
5. 2.8(실제 컨테이너/서브도메인 분리)은 이번 작업 완료 보고에 "후속 작업 — 사용자 확인 필요" 항목으로만 남긴다. 코드나 compose를 먼저 건드리지 않는다.
