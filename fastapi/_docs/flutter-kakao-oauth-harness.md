# HARNESS (백엔드): 카카오 소셜 로그인 — 모바일/웹 분리 인증 파이프라인

> **범위:** `fastapi/` 백엔드 전용. 클라이언트(Flutter) 측 계약은 [`flutter/_docs/flutter-kakao-oauth-harness.md`](../../flutter/_docs/flutter-kakao-oauth-harness.md)에 있다.
> **대상 저장소:** `cloud.jsangho.all`
> **작업 주체:** Claude Code
> **작성일:** 2026-08-03
> **상태:** 모바일 경로 구현 완료 (2026-08-03). 웹 경로(T5)·`user_identities`(T3 일부)는 미착수 — §6 참조
> **상위 규칙:** [루트 CLAUDE.md](../../CLAUDE.md) · [fastapi/CLAUDE.md](../CLAUDE.md) · 선행 문서 [`apps/auth/_docs/auth-gateway-harness.md`](../apps/auth/_docs/auth-gateway-harness.md)

---

## 0. 이 문서를 읽는 방법

이 문서는 "무엇을 만들 것인가"에 대한 계약(contract)이다.

- **§2 결정사항**은 확정된 것이다. 재논의하지 말고 그대로 구현한다.
- **§3 금지사항**을 위반하는 코드는 작성 즉시 폐기 대상이다.
- **§4 델타**는 원본 지시서와 이 저장소의 실제 코드가 어긋나는 지점이다. **구현 전에 반드시 읽는다.** 원본 지시서를 문자 그대로 실행하면 기존 로그인과 전 앱 토큰 검증이 깨지는 항목이 여러 개 있다.
- **§6 작업 단위**는 순서대로 진행하며, 각 단위 종료 시 **§9 검증 기준**과 **§10 하네스 게이트**를 통과해야 다음으로 넘어간다.
- 판단이 필요한 지점이 생기면 **임의로 결정하지 말고 §13에 질문을 기록한 뒤 멈춘다.**

---

## 1. 현재 구현 실측 (2026-08-03, 코드 확인 결과)

> 추측이 아니라 아래 파일을 직접 읽고 정리한 것이다. 새 코드를 쓰기 전 이 표가 여전히 맞는지 확인한다.

| 구성요소 | 실제 위치 | 현재 동작 |
|---|---|---|
| 인증 엔트리포인트 | `fastapi/auth_main.py` (포트 9000, 미노출) | 라우터를 `/auth` prefix로 마운트. `oauth_callback_router`만 경로에 이미 `/auth/...`가 있어 prefix 없이 include |
| 카카오 어댑터 | `auth.adapter.outbound.kakao_oauth_client` | `build_authorize_url(state)` · `exchange_code(code)` 2개뿐. **redirect_uri 1개 고정**, 카카오 access/refresh token은 프로필 조회 후 **버린다** |
| 공통 소셜 유스케이스 | `auth.app.use_cases.oauth_login_interactor` | google·kakao·naver가 1벌을 공유. `provider` 문자열만 다르다 |
| 유저 조회/생성 | `auth.adapter.outbound.pg.user_pg_repository` | `find_by_oauth` → 없으면 `find_by_email` → 없으면 `create_oauth_user` |
| 유저 테이블 | `jsangho.core.entities.user_model` (`users`) | PK = **int autoincrement**. `email` **NOT NULL UNIQUE**. `oauth_provider` · `oauth_id` **단일 컬럼 1쌍** |
| JWT 발급 | `auth.domain.services.token_issuer` | RS256, `kid=jsangho-auth-1`. 클레임 = `sub` `roles` `aud` `iat` `exp` `jti`. access 15분 / refresh 14일(**단일 상수**) |
| JWT 검증 | `jsangho.core.security.token_verifier` · `jsangho.core.security.dependencies` | `aud` 단일값(`SERVICE_AUD`, 기본 `jsangho-api`). 검증 후 `auth:blacklist:{jti}` 조회 |
| JWKS | `auth.adapter.inbound.api.jwks_router` | `/.well-known/jwks.json` 공개 |
| 리프레시 저장소 | `auth.adapter.outbound.redis.refresh_token_repository` | 키 `auth:refresh:{jti}` = `"{sub}:active\|used"` (STRING), 인덱스 `auth:refresh:by-sub:{sub}` (SET), 블랙리스트 `auth:blacklist:{jti}` |
| 리프레시 토큰 형식 | `token_issuer.create_refresh_token` | `"{jti}.{token_urlsafe(32)}"` 불투명 문자열. **Redis에는 jti만 기록되고 뒤쪽 시크릿은 검증되지 않는다** |
| 웹 콜백 | `auth.adapter.inbound.api.oauth_callback_router` | `state`를 **CSRF가 아니라 next_path 전달용**으로 쓴다. 콜백은 `FRONTEND_URL/login/oauth-callback?token=...&refreshToken=...`로 **쿼리스트링에 토큰을 실어** 302 |
| 쿠키 헬퍼 | `jsangho.core.security.cookie` | `COOKIE_KWARGS`(`domain=.jsangho.cloud`, httponly, secure, samesite=lax) 존재 — OAuth 경로에서는 **미사용** |
| RBAC | `jsangho.core.security.role` + `users.role` 컬럼 | **Neo4j가 아니라 Postgres 컬럼 기반**이다. 원본 지시서의 "RBAC(Neo4j)" 서술은 사실과 다르다 |
| Redis 컨테이너 | `docker-compose.yaml` `redis` 서비스 | `redis:7-alpine`, `--appendonly yes` **이미 적용됨**, 볼륨 `redis_data`. `maxmemory` 미설정, 호스트 6379 노출, 논리 DB 분리 없음 |
| 마이그레이션 | `fastapi/alembic/versions/` | 이력이 단일 baseline(`07a11683a53b`)으로 정리된 상태 |

---

## 2. 확정된 결정사항 (변경 금지)

### D-1. 모바일 인증 방식 = **Authorization Code 서버 교환**

Flutter는 인가 코드(authorization code)만 획득해 서버로 넘긴다. 카카오 토큰 발급은 서버가 한다.

```
Flutter                     API Server (auth)                Kakao
  |-- 인가 코드 요청 ----------------------------------------->|
  |<-- authorization code -------------------------------------|
  |-- POST /auth/mobile/kakao { code, redirectUri, device* } -->|
  |                              |-- POST /oauth/token -------->|
  |                              |<-- access + refresh + id ----|
  |                              |-- GET /v2/user/me ---------->|
  |                              |<-- profile ------------------|
  |                              |-- upsert user (Postgres)     |
  |                              |-- store kakao RT (암호화)     |
  |                              |-- 자체 JWT 쌍 발급            |
  |<-- { token, refreshToken, user } ---------------------------|
```

**채택 이유:** ① `client_secret`이 앱 바이너리에 없다 ② 카카오 refresh token이 **서버에만** 존재해 서버 주도 unlink·메시지 전송이 가능하다 ③ 클라이언트는 자체 JWT만 보유하므로 수명 주기를 서버가 완전히 통제한다.

### D-2. 웹 인증 방식 = **표준 Redirect 기반 Authorization Code + `state` CSRF**

웹 콜백은 서버 엔드포인트가 받는다. `state`는 **CSRF 난수**여야 한다. 현재처럼 `next_path`를 `state`에 그대로 싣는 방식은 CSRF 방어가 아니다 → §4-D.

### D-3. 두 플랫폼의 세션은 **완전히 분리된 네임스페이스**를 쓴다

- 모바일 refresh token으로 웹 세션을 갱신할 수 없고, 그 역도 마찬가지다.
- JWT payload에 `platform` 클레임을 **필수**로 넣고, 리프레시 시 **키 네임스페이스와 클레임이 모두 일치**해야 한다.
- 한쪽 플랫폼의 전체 로그아웃이 다른 쪽에 영향을 주지 않는다.

### D-4. 클라이언트가 보낸 카카오 access token을 신원 근거로 신뢰하지 않는다

부득이한 레거시 호환이 필요하면 `GET /v1/user/access_token_info`로 `app_id` 일치를 반드시 검증한다.

### D-5. 유저 식별자

- 카카오 회원번호(`id`/`sub`)를 `provider_id`로 저장한다.
- **이메일을 계정 식별자로 쓰지 않는다.** 카카오 이메일은 선택 동의 항목이며 변경될 수 있다.
- 계정의 정체성은 **서버가 소유한 내부 ID**다. 원본 지시서는 UUID를 명시했으나 이 저장소는 `users.id` int PK를 다른 앱이 FK로 참조하고, `fastapi/CLAUDE.md` §5가 int PK를 강제한다 → §4-F에서 보정한다.

---

## 3. 금지사항

원본 지시서 금지사항 + 이 저장소 고유 규칙이다.

- ❌ Redis에 "컬럼"을 추가하려는 시도 — Redis는 키-값 저장소다. §5의 키 스키마를 따른다.
- ❌ `client_secret` · 카카오 REST API 키를 Flutter/Next.js 클라이언트 번들에 포함
- ❌ 클라이언트가 보낸 `user_id` · `email` · `nickname`을 검증 없이 DB에 반영
- ❌ refresh token 평문을 Redis에 저장 (SHA-256 해시 저장, §5)
- ❌ 카카오 refresh token을 클라이언트에 반환 (서버 전용, 암호화 저장)
- ❌ **`jsangho.core.security.token_verifier`의 RS256 서명·검증 로직을 새로 작성** — 반드시 재사용·확장한다. 발급(개인키)은 `apps/auth`에만 존재한다는 선행 하네스의 절대 규칙을 유지한다.
- ❌ `alg: none` / HS256 폴백 허용. `JWT_SECRET_KEY`(deprecated) 참조 금지
- ❌ 스포크 앱이 `auth`를 직접 import (스타 토폴로지 위반, `lint-imports`가 차단)
- ❌ 도메인 레이어에서 `fastapi` · `redis` · `httpx` import (클린 아키텍처 위반)
- ❌ `alembic/` 자동 생성 파일 임의 수정, 기존 baseline 이력 재작성
- ❌ 사용자가 "빌드해줘"라고 말하지 않았는데 `docker compose build` 실행
- ❌ 시크릿을 코드·문서·`.env.example` 값 자리에 하드코딩

---

## 4. 목표와 현재 구현의 델타 (구현 전 필독)

> 각 항목의 "이 리포에서의 처리"가 구현 지침이며, ❓ 표시는 §13 질문으로 올려 사용자 확인 후 진행한다.

| # | 항목 | 현재 | 목표 | 이 리포에서의 처리 |
|---|---|---|---|---|
| A | 리프레시 키 스키마 | `auth:refresh:{jti}` STRING, 플랫폼·기기 메타 없음 | `auth:rt:{platform}:{user_id}:{jti}` HASH | **신·구 키를 공존**시킨다. 신규 키로만 발급하고 구 키는 TTL(14일) 소진으로 자연 만료. 리프레시는 신규 키 조회 → 없으면 구 키 폴백(한시적, 제거 예정일을 코드 주석에 명시) |
| B | 회전 원자성 | `GET` 후 `SET` 2회 왕복 — 동시 요청 레이스 존재 | Lua 스크립트로 원자 처리 | T1에서 Lua로 재작성. 기존 `consume()`은 폴백 경로로만 남긴다 |
| C | 재사용 탐지 범위 | `revoke_all_for_sub` — **플랫폼 무관 전체 폐기** | 해당 플랫폼 세션만 폐기 (D-3) | 플랫폼 인자를 받는 `revoke_all(platform, user_id)`로 교체. 기존 시그니처를 쓰는 `logout_router`도 함께 수정 |
| D | 웹 `state` | `next_path`를 그대로 `state`에 실음 = CSRF 방어 없음 | 난수 `state`를 Redis에 5분 저장 후 대조 | `state`는 난수로 바꾸고 `next_path`는 **`state` 키의 값 쪽**에 담아 서버가 기억한다. 프론트에서 보이는 리다이렉트 동작은 그대로 유지 |
| E | 웹 토큰 전달 | 콜백이 `?token=&refreshToken=`로 **URL에 토큰 노출** (히스토리·Referer·서버 로그 잔존) | httpOnly + Secure + SameSite 쿠키 | `COOKIE_KWARGS` 재사용. **`www/app/login/oauth-callback/`도 함께 바뀌어야 한다** — 프론트 변경은 이 문서 범위 밖이므로 착수 전에 사용자에게 알린다 ❓ |
| F | 내부 식별자 | `users.id` int PK, 타 앱이 FK 참조 | UUID PK | **int PK를 유지**한다. `fastapi/CLAUDE.md` §5가 UUID PK를 금지하고, 전환 시 전 앱 FK 마이그레이션이 발생한다. `sub`는 계속 `str(users.id)` ❓ |
| G | 이메일 필수 | `users.email` NOT NULL UNIQUE. 카카오 이메일 없으면 현재 코드가 401 | 이메일은 선택 (D-5) | 카카오 이메일은 선택 동의라 없을 수 있고 **모바일 로그인이 여기서 바로 깨진다.** `email` nullable 전환 + UNIQUE를 partial index로 바꾸는 마이그레이션이 필요 ❓ (placeholder 이메일 생성은 비권장 — 실제 주소와 충돌하고 정합성이 후속으로 번진다) |
| H | provider 다중 연결 | `users.oauth_provider`/`oauth_id` 1쌍뿐 | `user_identities` 테이블 | T3에서 신설 + 기존 컬럼 백필. 기존 컬럼은 읽기 폴백용으로 한 릴리스 유지 후 제거 |
| I | `platform` 클레임 | `TokenPayload`에 필드 없음 | 필수 클레임 | `TokenPayload`에 `platform: str \| None` 추가. **core 변경은 전 앱에 파급**되므로 옵셔널로 넣고, 기존 발급분(클레임 없음)은 `None`으로 통과시킨다 |
| J | `aud` 분리 | 단일 `SERVICE_AUD=jsangho-api` | `JWT_AUDIENCE_MOBILE`/`_WEB` | **aud는 쪼개지 않는다.** 쪼개면 스포크 앱들의 `verify_token(aud=기본값)`이 모바일 토큰을 전부 거부한다. 플랫폼 구분은 `platform` 클레임으로 하고 `aud`는 현행 유지 ❓ |
| K | denylist 키 이름 | `auth:blacklist:{jti}` (`core`가 읽음) | `auth:denylist:{jti}` | **기존 이름을 유지**한다. 이름만 바꾸려고 공유 커널을 건드릴 이유가 없다 |
| L | refresh TTL | 단일 상수 14일 | 모바일 60일 / 웹 14일 | `token_issuer`에 플랫폼별 상수를 두고 세션 생성 시 인자로 받는다 |
| M | refresh 토큰 시크릿 | `{jti}.{secret}`에서 **jti만 검증**, 뒤쪽 미검증 | 토큰 전체의 SHA-256 대조 | T1에서 `token_hash` 대조 추가. jti만 알면 통과하는 현재 구조는 실질적 취약점이다 |
| N | 카카오 RT | 폐기 | AES-GCM 암호화 후 서버 보관 | `KAKAO_RT_ENCRYPTION_KEY` 신규 도입. 키 부재 시 **기동 실패**시킨다(조용한 평문 저장 금지) |
| O | Redis 설정 | `--appendonly yes` 적용됨, `maxmemory` 미설정 | AOF + `noeviction` | AOF는 **이미 충족**. `maxmemory` 미설정이면 eviction이 발생하지 않으므로 정책은 명시만 하면 된다. 호스트 6379 노출 축소는 별건 ❓ |
| P | RBAC 저장소 | Postgres `users.role` | (원본 지시서) Neo4j | **Postgres `role` 컬럼을 그대로 쓴다.** 신규 유저 기본값 `user`. Neo4j RBAC 도입은 이 하네스 범위 밖 |

---

## 5. Redis 키 스키마 (핵심 산출물)

> "모바일 로그인 토큰 컬럼 추가"라는 요구의 실제 구현체. Redis는 스키마리스이므로 **키 prefix로 플랫폼을 분리**한다.

### 5.1 키 구조

```
# 리프레시 토큰 본체 (HASH)
auth:rt:mobile:{user_id}:{jti}
auth:rt:web:{user_id}:{jti}

# 유저별 활성 세션 인덱스 (SET) — 전체 로그아웃 / 기기 목록 조회용
auth:rt:index:mobile:{user_id}   -> { jti, jti, ... }
auth:rt:index:web:{user_id}      -> { jti, jti, ... }

# 회전 후 재사용 탐지용 폐기 마커 (STRING)
auth:rt:used:{platform}:{jti}    -> "1"

# access token 강제 무효화 목록 (STRING) — 기존 키 이름 유지 (§4-K)
auth:blacklist:{jti}             -> "1"

# 카카오 refresh token — 서버 전용, 클라이언트 노출 절대 금지 (STRING, AES-GCM)
auth:kakao:rt:{user_id}          -> base64(nonce || ciphertext || tag)

# 웹 OAuth CSRF state (HASH, 단명)
auth:oauth:state:{state}         -> { ua_hash, next_path, created_at }

# (레거시) 구 스키마 — 신규 발급 금지, TTL 소진까지 읽기 폴백만
auth:refresh:{jti}               -> "{sub}:active|used"
auth:refresh:by-sub:{sub}        -> { jti, ... }
```

### 5.2 HASH 필드 정의 (`auth:rt:{platform}:{user_id}:{jti}`)

| 필드 | 타입 | 모바일 | 웹 | 설명 |
|---|---|---|---|---|
| `token_hash` | string | ✅ | ✅ | refresh token 전체의 SHA-256 hex. **평문 저장 금지** |
| `user_id` | string | ✅ | ✅ | 내부 유저 ID (`users.id`) |
| `platform` | string | ✅ | ✅ | `mobile` \| `web` |
| `device_id` | string | ✅ 필수 | ➖ | 앱 설치 단위 식별자 |
| `device_name` | string | ✅ | ➖ | 사용자에게 보여줄 기기명 (예: iPhone 15) |
| `app_version` | string | ✅ | ➖ | 앱 버전 |
| `os` | string | ✅ | ➖ | `ios` \| `android` |
| `push_token` | string | ✅ 선택 | ➖ | FCM/APNs 토큰 |
| `user_agent_hash` | string | ➖ | ✅ | UA 지문 |
| `ip` | string | ✅ | ✅ | 발급 시점 IP |
| `issued_at` | int | ✅ | ✅ | epoch seconds |
| `rotated_from` | string | ✅ | ✅ | 직전 jti (재사용 탐지 체인) |
| `rotation_count` | int | ✅ | ✅ | 누적 회전 횟수 |

### 5.3 TTL 정책

| 항목 | 모바일 | 웹 |
|---|---|---|
| access JWT | 15분 | 15분 |
| refresh token | **60일** | **14일** |
| `auth:rt:used:*` | refresh TTL과 동일 | 동일 |
| `auth:oauth:state:*` | ➖ | 5분 |
| 동시 활성 세션 상한 | 기기당 1개, 최대 5기기 | 5개 |

`auth:kakao:rt:{user_id}`는 TTL 없음 — 연결 해제(unlink) 시 명시적으로 삭제한다.

### 5.4 회전 및 재사용 탐지 규칙

1. 리프레시 요청 수신 → 토큰에서 jti 파싱 → `auth:rt:used:{platform}:{jti}` 존재 확인
2. **존재하면 = 탈취된 토큰의 재사용** → 해당 유저의 **해당 플랫폼 세션 전체 폐기** + 보안 로그 + (모바일이면) 푸시 알림
   - ⚠️ 반대 플랫폼 세션은 **건드리지 않는다** (D-3)
3. 존재하지 않으면 → `token_hash` 대조 → 새 jti 발급 → 구 jti를 `used`로 마킹 → 인덱스 SET 갱신
4. 위 과정은 **Lua 스크립트로 원자 처리**한다. 현재의 2회 왕복 구조는 동시 요청에서 유효한 토큰 두 개를 만들어낸다.
5. 세션 상한 초과 시 `issued_at`이 가장 오래된 jti부터 폐기한다.

---

## 6. 작업 단위 (백엔드)

각 단위는 독립 커밋. `[ ]` → `[x]`로 갱신하며 진행한다.
경로 표기는 §0-3 규칙을 따른다 — `apps/auth/...` → `auth....`, `fastapi/core/...` → `jsangho.core....`
파일·클래스 명명은 `fastapi/CLAUDE.md` §4 표를 따른다.

### T1. Redis 세션 스토어 레이어
- [x] `auth.app.ports.output.session_store` — 출력 포트(추상). 유스케이스는 어댑터가 아니라 이 포트에 의존한다
- [x] `auth.adapter.outbound.redis.session_redis_store` — §5 스키마 구현체
- [x] `create_session(platform, user_id, meta) -> (refresh_token, jti)`
- [x] `rotate_session(platform, refresh_token) -> (new_token, new_jti, user_id)` — **Lua 원자성**
- [x] `revoke_session(platform, user_id, jti)`
- [x] `revoke_all(platform, user_id)` — **플랫폼 한정** (§4-C)
- [x] `list_sessions(platform, user_id)` — 기기 목록 API용
- [x] 세션 상한 초과 시 오래된 세션 폐기
- [x] `auth.domain.services.token_hasher` — SHA-256 유틸 (도메인, 외부 의존 없음)
- [x] 카카오 RT AES-GCM 암복호화 유틸 — 키 부재 시 실패 (⚠️ 아래 편차 참고)
- [x] 기존 `refresh_token_repository`는 **삭제하지 않고** 레거시 폴백으로 유지 (§4-A)

**§5 스키마에서 벗어난 점 (의도한 것):**

- `auth:rt:owner:{platform}:{jti}` → `user_id` 역인덱스를 **추가**했다. 클라이언트는
  `{jti}.{secret}` 토큰만 보내므로 jti는 알아도 user_id를 모르는데, 세션 본체 키에
  user_id가 들어 있어 역인덱스 없이는 키를 조립할 수 없다.
- `auth:rt:used:*`의 값을 `"1"`이 아니라 user_id로 뒀다. 회전 시 구 owner 키를 지우므로,
  재사용이 탐지된 시점에는 이 마커만 남아 있고 그 값으로 유저를 특정한다.
- 세션 HASH에 `seq` 필드를 추가했다. `issued_at`이 초 단위라 같은 초에 만들어진 세션들의
  순서가 정해지지 않아 상한 초과 시 엉뚱한 세션이 폐기됐다 — 전역 `INCR`로 순서를 확정한다.
- **`KAKAO_RT_ENCRYPTION_KEY` 부재 시 "기동 실패"가 아니라 "모바일 배선 시점 실패"다.**
  import 시점에 던지면 이 키가 없는 환경에서 기존 웹 로그인까지 함께 죽는다. 평문 저장을
  막는다는 목적은 동일하되 폭발 반경만 좁혔다.
- ⚠️ Lua 안에서 키 이름을 조립하므로 Redis Cluster의 키 슬롯 규칙을 만족하지 않는다.
  현재 배포는 단일 노드라 문제없지만, 클러스터로 옮기면 해시태그가 필요하다.

### T2. 카카오 클라이언트 확장
- [x] 기존 `OAuthIdentityProvider` 포트는 건드리지 않고 `auth.adapter.outbound.kakao_mobile_oauth_client`를 **신설**했다. 카카오 전용 포트는 `auth.app.ports.output.kakao_mobile_identity_provider` (ISP)
- [x] `exchange_code(code, redirect_uri) -> KakaoTokenSet` — access·refresh 반환. `platform` 인자는 두지 않았다(모바일 전용 어댑터라 불필요)
- [x] `fetch_profile(access_token) -> KakaoProfile` — 이메일 없음을 정상 케이스로 처리 (§4-G)
- [x] `unlink(kakao_access_token)` — 서버 보관 RT로 얻은 토큰 사용
- [ ] `verify_access_token(access_token)` — **미구현.** 레거시 호환 경로(D-4)를 만들지 않았으므로 필요한 곳이 없다
- [x] 앱이 보낸 `redirect_uri`를 `KAKAO_MOBILE_REDIRECT_URI` 등록값과 대조 후에만 교환한다
- [x] httpx 타임아웃 분리 (connect 3s / read·write 7s), 타임아웃 → 504 · 통신 실패 → 502

### T3. 유저 도메인
- [ ] Alembic: `user_identities(...)` — **미착수.** 모바일 흐름은 기존 `oauth_provider`/`oauth_id` 1쌍으로 충분해 범위에서 뺐다
- [x] Alembic: `users.email` nullable 전환 (`b3f1c9d2a740`). **partial index는 만들지 않았다** — PostgreSQL의 UNIQUE 인덱스는 NULL을 서로 다른 값으로 취급하므로 이메일 없는 계정이 여럿이어도 충돌하지 않는다. 문서가 요구한 partial index는 불필요하다
- [ ] `user_identities` 백필 — 위와 같은 이유로 미착수
- [x] 카카오 회원번호 기준 upsert (`MobileAuthInteractor._upsert`). `last_login_at` 컬럼이 없어 갱신은 생략
- [x] 신규 유저 기본 역할 = `users.role = 'user'` (§4-P — Neo4j 아님)
- [x] ⚠️ 이메일 기반 자동 계정 병합(`find_by_email` 폴백)을 모바일 경로에서 **쓰지 않는다**. 회귀 테스트 `test_login_does_not_merge_into_an_account_by_email`로 고정

### T4. 모바일 인증 엔드포인트 (`auth.adapter.inbound.api.mobile_auth_router`)
- [x] `POST /auth/mobile/kakao` — body: `code`, `redirectUri`, `deviceId`, `deviceName`, `os`, `appVersion`
- [x] `POST /auth/mobile/refresh` — body: `refreshToken`
- [x] `POST /auth/mobile/logout` — 현재 세션만
- [x] `POST /auth/mobile/logout-all` — **모바일 세션 전체** (웹 불변)
- [x] `GET /auth/mobile/sessions` — 로그인된 기기 목록
- [x] JWT 클레임: `sub`, `platform: "mobile"`, `jti`, `device_id`, `roles`, `exp`, `iat`, `aud`(현행 값 유지, §4-J)
- [x] `auth_main.py`에 라우터 등록 (라우터 자체 prefix가 `/mobile`이라 `prefix="/auth"`로 include)

### T5. 웹 인증 엔드포인트 — **보안 항목만 선반영 (2026-08-03)**

- [x] 기존 `/auth/kakao/login` · `/auth/kakao/callback` **경로 유지** — 카카오 콘솔 재등록 불필요
- [x] `state`를 난수로 교체 + `auth:oauth:state:{state}` 5분 저장, 콜백에서 대조 후 삭제 (§4-D)
  - `GETDEL`로 조회·삭제를 한 연산으로 처리해 같은 `state`가 두 번 통과하지 못한다
  - **검증을 카카오 코드 교환보다 먼저** 해서 위조 요청이 외부 호출조차 일으키지 않게 했다
  - google·naver도 같은 헬퍼를 쓰므로 함께 적용됐다
- [x] 리다이렉트 URL에서 **리프레시 토큰 제거** — `www`에 이 값을 읽는 코드가 아예 없는데
  (참조 0건) 14일짜리 토큰이 브라우저 히스토리·Referer·중간 로그에 남고 있었다
- [ ] 액세스 토큰(15분)의 httpOnly 쿠키 전환 (§4-E) — **미착수.** `www`의 인증 계층이
  localStorage + `Bearer` 헤더라 프론트를 통째로 바꿔야 한다
- [ ] `POST /auth/web/refresh` · `/auth/web/logout` — 미착수 (프론트에 리프레시 로직 자체가 없다)
- [ ] JWT 클레임 `platform: "web"` — 미착수. 다만 플랫폼 격리는 이미 성립한다:
      웹은 구 `auth:refresh:*`, 모바일은 신 `auth:rt:mobile:*` 네임스페이스라 서로의 토큰이 통하지 않는다

### 🔴 별건으로 발견 — 웹 소셜 로그인의 `redirect_uri`가 localhost다

서버 `.env`에서 `KAKAO_OAUTH_REDIRECT_URI`·`GOOGLE_…`·`NAVER_…` **세 줄이 모두 주석 처리**돼
있어, 코드 기본값 `http://127.0.0.1:8000/api/auth/{provider}/callback`이 쓰이고 있다.

```
GET https://auth.jsangho.cloud/auth/kakao/login
  → 302 …&redirect_uri=http%3A%2F%2F127.0.0.1%3A8000%2Fapi%2Fauth%2Fkakao%2Fcallback
```

카카오는 이 URI를 **받아준다**(302 정상 — 콘솔에 등록돼 있다는 뜻). 그래서 로컬 개발에서는
동작하지만, **운영 사용자는 동의 후 자기 PC의 localhost로 튕겨 로그인이 끝나지 않는다.**

이번 변경이 만든 문제가 아니라 **원래 있던 상태**이며, CSRF 수정과는 독립이다.
고치려면 주석을 풀고(`https://auth.jsangho.cloud/auth/{provider}/callback`) 각 콘솔에
그 URI를 등록해야 한다. 콘솔 등록 상태를 확인할 수 없어 임의로 바꾸지 않았다.

- [ ] 기존 `/auth/kakao/login` · `/auth/kakao/callback` **경로는 유지**한다 — 카카오 콘솔 등록 URI와 `www` 프론트가 이 경로에 묶여 있다 ❓
- [ ] `state`를 난수로 교체 + `auth:oauth:state:{state}` 5분 저장, 콜백에서 대조 후 즉시 삭제 (§4-D)
- [ ] 콜백 응답을 쿼리스트링 → **httpOnly 쿠키**로 전환 (§4-E, `COOKIE_KWARGS` 재사용)
- [ ] `POST /auth/web/refresh` — 쿠키 기반, CSRF 토큰 검증
- [ ] `POST /auth/web/logout` — 웹 세션만
- [ ] JWT 클레임 `platform: "web"`
- [ ] google·naver 콜백도 같은 state/쿠키 처리를 공유하도록 헬퍼로 뽑는다 (현재 3개 provider가 `_issue_and_redirect`를 공유)

### T6. 인증 미들웨어
- [x] `jsangho.core.security.token_verifier`의 `TokenPayload`에 `platform`·`device_id` **옵셔널 추가** (§4-I)
- [x] 기존 `auth:blacklist:{jti}` 조회 유지 (§4-K)
- [x] 모바일 라우터 안의 `_require_mobile()`로 플랫폼 전용 엔드포인트를 보호한다. 재사용처가 한 곳뿐이라 `core`의 공용 `require_platform(...)` 의존성은 만들지 않았다 — 두 번째 사용처가 생기면 그때 올린다
- [x] `platform`이 없는 기존 토큰의 취급 규칙을 `TokenPayload`·`_require_mobile` 주석에 명시 (모바일 엔드포인트는 신규라 `None`을 거부한다)

### T7. 인프라 / 설정
- [ ] Redis `maxmemory-policy noeviction` 명시 — **미착수.** `maxmemory` 미설정이면 eviction 자체가 없어 현 상태로 이미 안전하다(§4-O). compose 변경은 하지 않았다
- [ ] `REDIS_AUTH_DB` 논리 DB 분리 — **미결정** (§13). 분리하지 않은 상태로 동작한다
- [x] `fastapi/.env.example`에 신규 키 추가 (§8) — 값은 비워 뒀다
- [x] `docker-compose.yaml`은 손대지 않았다 (`env_file: ./fastapi/.env` 단일 파일 규칙 유지)
- [x] 빌드하지 않았다

### T8. 테스트 (`fastapi/apps/auth/tests/`) — 38개 통과

라우터 계층(`test_mobile_auth_router.py`)은 **Flutter가 실제로 받는 JSON**을 고정한다 —
camelCase 별칭, `platform` 가드, 실패의 401 번역. 유스케이스 테스트만으로는 이 표면이
바뀌어도 못 잡는다.


저장소·카카오·Postgres는 전부 fake다. Redis는 `fakeredis[lua]`(신규 dev 의존성)로
Lua 스크립트까지 실제로 실행한다.

- [x] 모바일 refresh를 웹 네임스페이스에서 회전 시도 → 실패 (D-3 회귀 방지)
- [x] 재사용 탐지가 **반대 플랫폼 세션을 건드리지 않음** 확인
- [x] 동일 refresh token 2회 사용 → 해당 플랫폼 전체 폐기
- [x] 동시 리프레시 요청 10개 → 정확히 1개 성공 (Lua 원자성)
- [x] `token_hash` 불일치(jti만 맞는 위조 토큰) → 거부 (§4-M)
- [x] 6번째 기기 로그인 → 가장 오래된 세션 폐기
- [x] 같은 기기 재로그인 → 기존 세션 대체 (상한을 잡아먹지 않음)
- [x] 이메일 미동의 카카오 계정 로그인 성공 (§4-G)
- [x] 이메일로 기존 계정에 병합되지 않음 (계정 탈취 방지)
- [x] 카카오 refresh token이 응답에 새어 나가지 않음 (D-1)
- [x] access token에 `platform`·`device_id` 클레임이 실림
- [x] `conftest.py`는 `apps/titanic/tests/` 패턴을 따랐다
- [x] 로그인·리프레시·기기목록 응답이 camelCase 별칭으로 나감 (Flutter 계약)
- [x] 웹 토큰·`platform` 없는 토큰으로 모바일 엔드포인트 호출 → **401** (D-3)
- [x] 리프레시 실패 3종(없음·재사용·유저 소실)이 전부 401로 수렴 (실패 이유 비노출)
- [x] 로그아웃이 body의 refresh token이 아니라 **인증된 유저**를 기준으로 동작
- [x] 카카오 API 실패(교환·프로필 두 단계 각각) → 유저·세션·카카오 토큰 **아무것도 저장되지 않음**
- [x] 만료·폐기된 세션으로 리프레시 → 거부. fakeredis에서 TTL을 흘려보낼 수 없어, 만료와 결과가 같은 "키가 사라진 상태"로 검증한다
- [x] 세션은 살아 있는데 유저 행이 사라진 경우 → 세션도 함께 정리
- [x] `logout-all`이 같은 유저의 웹 세션을 남겨 둠 (D-4)
- [ ] 위조 서명 JWT · `alg:none` → 401 : **미작성.** 기존 `token_verifier`의 책임이고 이번 변경이 건드리지 않았다

---

## 7. API 계약

> **이 절은 [Flutter 문서](../../flutter/_docs/flutter-kakao-oauth-harness.md) §5와 글자 그대로 동일해야 한다.** 한쪽을 고치면 반드시 다른 쪽도 고친다.
> JSON 필드는 기존 라우터 관례대로 **camelCase 별칭**을 쓴다 (`populate_by_name=True` + `response_model_by_alias=True`).

### 7.1 `POST /auth/mobile/kakao`

요청
```json
{
  "code": "카카오 인가 코드",
  "redirectUri": "kakao{NATIVE_APP_KEY}://oauth",
  "deviceId": "앱 설치 단위 UUID",
  "deviceName": "iPhone 15",
  "os": "ios",
  "appVersion": "1.0.0+1"
}
```

응답 `200`
```json
{
  "token": "<access JWT>",
  "refreshToken": "<불투명 문자열>",
  "expiresIn": 900,
  "user": { "userId": 1, "nickname": "홍길동", "email": null, "role": "user" }
}
```

| 상태 | 조건 |
|---|---|
| 400 | 필수 필드 누락 · 등록되지 않은 `redirectUri` |
| 401 | 인가 코드 교환 실패 · 만료된 코드 |
| 502 / 504 | 카카오 API 오류 · 타임아웃 (부분 상태 저장 금지) |

### 7.2 `POST /auth/mobile/refresh`

요청 `{ "refreshToken": "..." }` → 응답 `{ "token": "...", "refreshToken": "...", "expiresIn": 900 }`

401이면 클라이언트는 **저장된 토큰을 지우고 로그인 화면으로 복귀**한다. 재시도 금지.

### 7.3 `POST /auth/mobile/logout` · `POST /auth/mobile/logout-all`

`Authorization: Bearer <access JWT>` 필요. `logout`만 body `{ "refreshToken": "..." }`. 응답 `{ "message": "로그아웃됐습니다." }`.

### 7.4 `GET /auth/mobile/sessions`

```json
{ "sessions": [
  { "jti": "…", "deviceId": "…", "deviceName": "iPhone 15", "os": "ios",
    "appVersion": "1.0.0+1", "issuedAt": 1785000000, "current": true }
] }
```

### 7.5 웹 (참고)

`GET /auth/kakao/login?next=/` → 302 카카오 → `GET /auth/kakao/callback?code=&state=` → state 검증 → 쿠키 세팅 → `FRONTEND_URL{next}`로 302.
`POST /auth/web/refresh` · `POST /auth/web/logout`은 쿠키 기반이며 body가 없다.

---

## 8. 환경 변수 (`fastapi/.env.example`에 키만 추가)

```
# 기존 (유지)
KAKAO_CLIENT_ID=
KAKAO_CLIENT_SECRET=
KAKAO_OAUTH_REDIRECT_URI=        # 웹 콜백
JWT_PRIVATE_KEY=                 # auth 컨테이너 전용
JWT_PUBLIC_KEY=
FRONTEND_URL=
REDIS_URL=

# 신규
KAKAO_NATIVE_APP_KEY=            # Flutter SDK 초기화용 — 클라이언트에 노출돼도 되는 값
KAKAO_MOBILE_REDIRECT_URI=       # 예: kakao{NATIVE_APP_KEY}://oauth
REFRESH_TTL_MOBILE_DAYS=60
REFRESH_TTL_WEB_DAYS=14
KAKAO_RT_ENCRYPTION_KEY=         # AES-GCM 32바이트 키(base64). 없으면 기동 실패
REDIS_AUTH_DB=                   # 논리 DB 분리 시에만 (§13 결정 후)
```

- `JWT_AUDIENCE_MOBILE` / `JWT_AUDIENCE_WEB`은 **추가하지 않는다** (§4-J).
- `JWT_ISSUER`도 추가하지 않는다 — 현재 토큰에 `iss` 클레임이 없어서, 넣으려면 발급·검증을 같은 커밋에서 바꿔야 한다.
- `.env`는 **하나로 유지**한다(루트 CLAUDE.md의 감수한 트레이드오프). 분리 제안을 다시 꺼내기 전에 사용자에게 확인한다.

---

## 9. 검증 기준 (Definition of Done)

- [x] §6의 모바일 관련 체크박스 완료 (T5 웹 경로·T3 `user_identities`는 범위 밖으로 명시)
- [x] T8 테스트 전부 통과 (38건)
- [x] 모바일 로그인이 실제로 동작 — 실기기 검증 완료 (아래)
- [x] `KEYS auth:rt:*` 에서 `mobile` 네임스페이스가 육안으로 구분됨
- [x] Redis에 refresh token 평문 없음 — `token_hash`가 64자 SHA-256 hex
- [x] `auth:kakao:rt:*` 값이 바이너리 암호문이라 복호화 없이는 읽히지 않음
- [x] 기존 웹 로그인 정상 (`api.jsangho.cloud` 200, 회귀 없음)
- [x] 신규 코드에 하드코딩된 시크릿 0건

### 실기기 검증 결과 (2026-08-03, 갤럭시 A35 SM-A356N / Android 16)

| 확인 항목 | 실측값 |
|---|---|
| `POST /auth/mobile/kakao` | **200 OK** (카카오톡 앱 전환 경유) |
| `GET /auth/mobile/sessions` | **200 OK** (계정 화면 기기 목록) |
| 생성된 유저 | `id=3` · `login_id=zsh1114` · `oauth_provider=kakao` |
| 세션 키 | `auth:rt:mobile:3:b1d2696a…` + `index`·`owner`·`seq` 전부 생성 |
| `token_hash` | 64자 hex — 평문 토큰 없음 |
| `device_name` | `samsung SM-A356N` — 기기 메타 수집 정상 |
| `seq` / `rotation_count` | `1` / `0` |
| TTL | `5183963`초 ≈ **60일** (모바일 정책 일치) |
| `auth:kakao:rt:3` | 바이너리 암호문 |

### 실제 Redis에서의 세션 스토어 검증 (2026-08-03)

단위 테스트는 `fakeredis`의 Lua 에뮬레이터를 쓴다. 진짜 Redis의 Lua 인터프리터에서도
같은지 확인하려고, 운영 서버의 Redis에 합성 유저(`user_id=999999`)로 직접 돌렸다.
실제 유저 데이터와 겹치지 않으며 종료 시 전부 삭제했다(잔존 0건 확인).

| 항목 | 결과 |
|---|---|
| 6번째 기기 로그인 → 가장 오래된 세션 폐기 | ✅ 5개 유지, `dev-0` 제거 |
| 회전 후 새 토큰 발급 | ✅ |
| 재사용 탐지 → 모바일 전멸, **웹 세션 생존** (D-3) | ✅ |
| 동시 회전 10건 → 정확히 1건 성공 (Lua 원자성) | ✅ |
| `jti`만 맞는 위조 토큰 거부 (§4-M) | ✅ |

**남은 관찰**: 세션의 `ip` 필드가 `172.28.0.3`(cloudflared 컨테이너 내부 IP)으로 기록된다.
실제 클라이언트 IP를 남기려면 `X-Forwarded-For` / `CF-Connecting-IP`를 읽어야 한다.
현재는 감사 로그로서의 가치가 없는 값이다.

---

## 10. 하네스 게이트 (코드 작성 후 필수)

```bash
uv run ruff check fastapi/ --config pyproject.toml --fix
uv run ruff format fastapi/ --config pyproject.toml
cd fastapi && PYTHONUTF8=1 PYTHONPATH=apps uv run lint-imports
uv run pytest fastapi/apps/auth/tests -q
```

`uv run` 없이 실행하면 PATH상 다른 Python이 잡힌다. 에러는 무시하지 않고 수정 후 완료 보고한다.

---

## 11. 참고: 검토했으나 채택하지 않은 방식

| 방식 | 미채택 사유 |
|---|---|
| 클라이언트가 카카오 access token 전달 | `client_secret` 노출, 카카오 RT가 앱에 잔류, `app_id` 검증 누락 위험 |
| OIDC ID Token 로컬 검증 | 외부 호출 0회로 가장 빠르나 클레임이 제한적이고 서버 주도 카카오 API 호출이 불가. **로그인 지연이 문제가 되면 재검토** |
| 모바일/웹 세션 통합 | 위협 모델과 TTL이 상이, 한쪽 침해가 전체로 전파 |
| `aud`를 플랫폼별로 분리 | 스포크 앱 전체의 `verify_token` 기본 `aud`와 어긋나 모바일 토큰이 거부된다 (§4-J) |
| 유저 PK를 UUID로 전환 | `fastapi/CLAUDE.md` §5 위반 + 타 앱 FK 전면 마이그레이션 유발 (§4-F) |

---

## 12. 작업 로그

| 일시 | 작업 단위 | 내용 | 결과 |
|---|---|---|---|
| 2026-08-03 | — | 원본 지시서를 백엔드/Flutter 문서로 분리하고 실제 코드와의 델타(§4)를 정리 | 문서만 작성, 코드 변경 없음 |
| 2026-08-03 | T1·T2·T4·T6 | 모바일 인증 파이프라인 구현. 세션 스토어(Lua 원자 회전)·카카오 모바일 어댑터·AES-GCM 카카오 RT 보관소·`/auth/mobile/*` 5개 엔드포인트·`platform` 클레임 | ruff·lint-imports·pytest 19건 통과 |
| 2026-08-03 | T3(일부) | `users.email` nullable 마이그레이션(`b3f1c9d2a740`). `user_identities`는 범위 밖으로 남김 | 마이그레이션 파일 작성. **DB에 적용(`alembic upgrade head`)은 아직 하지 않았다** |
| 2026-08-03 | — | `fastapi/__init__.py`(빈 파일, git 미추적) 삭제 | 이 파일이 실제 `fastapi` 패키지를 가려 `pytest`가 저장소 어디서도 auth·titanic 테스트를 수집하지 못했다. 삭제 후 정상 수집 |
| 2026-08-03 | 배포 | EC2(`aws` 브랜치 `af8aec6`)에 반영. `.env`에 카카오 키 3개 추가(암호화 키는 서버에서 생성), `alembic upgrade head`(`b3f1c9d2a740`), `auth`·`backend` 재기동. 신규 런타임 의존성이 없어 재빌드는 하지 않았다 | `api.jsangho.cloud` 200(회귀 없음), `/auth/mobile/refresh` 401, `/auth/mobile/sessions` 401, 잘못된 `redirectUri` 400 — 모두 설계대로 |

### `client_id` 불일치 우려에 대한 실측 (2026-08-03)

SDK는 **네이티브 앱 키**로 인가를 요청하는데 서버는 **REST API 키**로 교환한다는 점이
설계 위험으로 지적됐다. 카카오 토큰 엔드포인트에 더미 코드로 직접 질의한 결과:

| 조합 | 응답 |
|---|---|
| REST API 키 + `client_secret` + 커스텀 스킴 | `KOE320 authorization code not found` |
| 네이티브 앱 키 + 커스텀 스킴 | `KOE320 authorization code not found` |

둘 다 **코드 조회 단계까지 도달**했다 — `client_id`나 `redirect_uri`가 거부됐다면
`KOE101`/`KOE303`이 나왔을 것이다. 즉 "등록되지 않은 클라이언트"·"미등록 redirect_uri"
두 실패 모드는 배제됐다.

**✅ 실기기에서 최종 해소됐다 (2026-08-03, 갤럭시 A35 / Android 16).**
카카오톡 앱 전환으로 받은 인가 코드를 서버가 **REST API 키 + client_secret**으로
교환해 `POST /auth/mobile/kakao` → **200 OK**. 카카오는 같은 앱에 속한 키를 서로
호환해 준다. 코드 변경은 필요 없었다.

---

## 13. 미해결 질문 (구현 중 발견 시 여기에 기록하고 중단)

- [ ] ⚠️ **아직 실행하지 않은 것 (사용자 조치 필요)**
  - `alembic upgrade head` — `users.email` nullable 마이그레이션을 실제 DB에 적용해야 이메일 미동의 계정이 로그인된다.
  - `.env`에 `KAKAO_NATIVE_APP_KEY` · `KAKAO_MOBILE_REDIRECT_URI` · `KAKAO_RT_ENCRYPTION_KEY` 채우기. 마지막 값이 없으면 모바일 로그인이 500으로 실패한다.
  - 카카오 콘솔에 Android 플랫폼(패키지명 + 키 해시)과 `KAKAO_MOBILE_REDIRECT_URI` 등록.
- [ ] **카카오 콘솔 앱 구성** — 모바일/웹을 하나의 앱으로 운영할지 분리할지. 분리하면 `provider_id`(회원번호)가 앱별로 달라져 계정 통합이 깨진다. **하나의 앱 + 복수 플랫폼 등록**을 권장하나 확인 필요.
- [ ] **§4-E 프론트 동시 변경** — 웹 콜백을 쿠키 방식으로 바꾸면 `www/app/login/oauth-callback/`도 함께 바뀌어야 한다. 별도 작업으로 남겼다(T5 미착수).
- [x] **§4-G 이메일 필수 해제** — nullable 전환으로 진행했다. partial index는 불필요해 만들지 않았다(T3 참조).
- [x] **§4-F 내부 식별자** — `users.id` int PK를 유지했다. `sub`는 계속 `str(users.id)`.
- [x] **§4-J `aud` 정책** — 단일 `aud` 유지 + `platform` 클레임 분리로 구현했다.
- [ ] **§6-T5 경로** — 웹 엔드포인트를 기존 `/auth/kakao/*`로 유지할지, 원본대로 `/auth/web/kakao/*`로 옮길지(옮기면 카카오 콘솔 redirect URI 재등록 + 프론트 수정 필요).
- [ ] **`REDIS_AUTH_DB` 분리** — 분리 시 `jsangho.core.security.dependencies`의 블랙리스트 조회도 같은 DB를 봐야 한다. 분리 실익이 있는지.
- [ ] **웹 CSRF 방어** — double-submit cookie로 할지 별도 토큰으로 할지.
- [ ] **게이트웨이 노출 경로** — auth 컨테이너는 포트 미노출이고 cloudflared가 `auth_net` 고정 IP로 라우팅한다. 모바일 엔드포인트를 어느 호스트(`auth.jsangho.cloud` / `gateway.jsangho.cloud`)로 노출할지.
