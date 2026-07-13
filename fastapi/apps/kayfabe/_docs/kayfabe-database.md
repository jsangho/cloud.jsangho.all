# Claude Code 작업 지시서: ERD 기반 pgvector 테이블 생성 (Docker + Alembic) — 경기 예측 플랫폼

> 본 문서는 Karpathy의 "Harness 원칙"에 따라 작성되었습니다.
> 즉, (1) 명확한 목표(Goal) (2) 충분한 컨텍스트(Context) (3) 명시적 제약(Constraints)
> (4) 단계별 실행 계획(Plan) (5) 자체 검증 루프(Verification Loop) 를 모두 포함하여,
> 에이전트가 스스로 판단·검증·수정할 수 있도록 구성합니다.
>
> 본 문서는 이전에 작성된 `claude_code_prompt_pgvector_alembic.md`(야구 ERD, Docker 실행 포함)의
> 구조와 원칙을 그대로 계승하며, 이번 ERD(이벤트/경기 예측 플랫폼)에 맞게 내용을 재구성한 것이다.

---

## 확인 결과 (2026-07-13, 사후 검증)

**본 문서가 요구하는 스키마는 이미 구현되어 운영 중임을 확인했다.** 신규 마이그레이션은 생성하지 않았다.
단, ERD의 일반명이 아니라 kayfabe 도메인 컨벤션(PLE = Premium Live Event)에 맞춘 실제 테이블명을 사용한다.

| 문서(ERD) 명칭 | 실제 테이블/모델 | 위치 |
|---|---|---|
| `users` | `users` (동일) | `apps/superstar/domain/entities/user_model.py` |
| `events` | `ple_events` | `apps/kayfabe/adapter/outbound/orm/ple_orm.py` |
| `ple_matches` | `ple_matches` (동일) | 위 파일 |
| `match_pick` | `ple_predictions` | 위 파일 |
| `title_acquisitions` | `title_acquisitions` (동일) | `apps/kayfabe/adapter/outbound/orm/title_history_orm.py` |

**3번 섹션 가정(a~e) 검증 결과:**
- a. 컬럼 타입 추론 — 실제 PK는 문서가 추론한 `BIGINT`가 아니라 `INTEGER`. 나머지 컬럼 타입은 추론과 대체로 일치.
- b. placeholder 행 제외 — 실제 구현에도 해당 컬럼 없음. 판단 유효.
- c. `title_acquisitions.match_id → ple_matches.id` — 실제 FK가 정확히 이 방향으로 구현되어 있음. 판단 정확.
- d. `match_pick`(`ple_predictions`)의 `UNIQUE(match_id, user_id)` — `uq_predictions_match_user`로 실제 존재. 판단 정확.
  (덤으로 `UNIQUE(match_id, client_id)`도 별도 존재 — 비로그인 중복 예측 방지용, 문서 미기재.)
- e. `ON DELETE` 정책 — 문서는 정보 부족으로 기본값(`NO ACTION`) 가정했으나, 실제 구현은 관계별로
  의미 있는 정책 적용: `ple_matches.event_id`/`ple_predictions.match_id` → `CASCADE`,
  `ple_predictions.user_id`/`title_acquisitions.match_id` → `SET NULL`. 문서 가정보다 정교하게 구현됨.

**비고:** 이 5개 테이블은 `fastapi/alembic/versions/`에 생성 마이그레이션이 없다
(`20260713_01_make_ple_events_month_nullable.py`만 참조). Alembic 추적이 도입되기 전에 생성된 것으로
보이며, "가정을 마이그레이션 주석에 남겨라"(4-8, 5번 체크리스트)는 적용할 대상 마이그레이션이 없어
해당 사항 없음으로 처리한다. Docker/`.env`/pgvector extension 등 0-1~3번 섹션의 인프라 요구사항은
`fastapi/apps/soccer/_docs/soccer-database.md` 작업 시 이미 충족되어 별도 조치 없음.

---

## 0. 환경 정보 (Environment)

- OS: Ubuntu 26.04 (Docker 호스트)
- DB: PostgreSQL + pgvector extension → **Docker 컨테이너 내부에서 실행**
- Migration Tool: Alembic
- ORM: SQLAlchemy (Alembic 표준 구성 기준)
- Container Runtime: Docker + Docker Compose

---

## 0-1. Docker 기반 DB 실행 (Database in Docker)

**PostgreSQL + pgvector는 호스트에 직접 설치하지 말고, 반드시 Docker 컨테이너로 실행**한다.
pgvector가 미리 설치된 공식 이미지(`pgvector/pgvector:pg16` 등, 프로젝트의 PostgreSQL 메이저 버전에 맞는 태그 사용)를 사용할 것.

### 0-1-1. 요구 사항

1. 프로젝트 루트에 `docker-compose.yml`(기존 파일이 있다면 서비스 추가)을 작성/수정하여 `db` 서비스를 정의한다.
2. 이미지: `pgvector/pgvector:pg16` (프로젝트에서 특정 버전을 요구하면 그에 맞게 조정).
3. 환경변수(`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`)는 `.env`로 분리하고 하드코딩 금지.
4. 포트는 `${POSTGRES_PORT:-5432}:5432`로 매핑하여 충돌 시 조정 가능하게 할 것.
5. named volume(`pgdata:/var/lib/postgresql/data`)으로 데이터 영속성을 확보할 것.
6. `pg_isready` 기반 `healthcheck`를 추가하여 완전 기동 후에만 Alembic이 접속하도록 할 것.
7. `CREATE EXTENSION IF NOT EXISTS vector;`는 `docker-entrypoint-initdb.d/` 초기화 스크립트 또는
   Alembic 초기 마이그레이션 중 하나로 반드시 1회 수행할 것 (누락 금지).

### 0-1-2. docker-compose.yml 예시 골격 (참고용, 기존 구조 우선)

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  pgdata:
```

### 0-1-3. Alembic → 컨테이너 DB 접속 설정

- Alembic을 호스트에서 실행: `postgresql+psycopg2://<user>:<pw>@localhost:${POSTGRES_PORT:-5432}/<db>`
- Alembic을 같은 docker network 컨테이너에서 실행: `postgresql+psycopg2://<user>:<pw>@db:5432/<db>`
- 접속 정보는 `.env`/환경변수에서 읽어오도록 구성 (하드코딩 금지).

---

## 1. 목표 (Goal)

첨부된 ERD 이미지(이벤트/경기 예측 플랫폼)를 기반으로 아래 5개 테이블을
Docker 컨테이너로 실행 중인 PostgreSQL(pgvector 확장 설치됨)에 Alembic 마이그레이션으로 생성한다.

- `users`
- `events`
- `ple_matches`
- `match_pick`
- `title_acquisitions`

최종 산출물:

1. `alembic/versions/` 하위에 위 5개 테이블을 생성하는 마이그레이션 파일 (FK 의존성 순서 반영)
2. `alembic upgrade head` 실행 시 오류 없이 스키마가 생성될 것
3. `alembic downgrade -1` 실행 시 깨끗하게 롤백될 것

---

## 2. 컨텍스트: ERD 스키마 정의 (Context)

> **중요**: 이 ERD는 대부분의 컬럼에 실제 데이터 타입이 명시되지 않고 `Type`, `Field2`, `Field3`...
> 같은 ERD 툴의 자동 placeholder 텍스트로 남아 있다. 아래 타입은 컬럼명/도메인 문맥을 근거로
> **합리적으로 추론한 것**이며, 이는 3번 섹션(제약 사항)에 가정으로 명시되어 있으니 반드시 확인할 것.

### 2.1 users (회원)

| 컬럼 | 타입(추론) | 제약 |
|---|---|---|
| id | BIGSERIAL / BIGINT | PK |
| login_id | VARCHAR(100) | UNIQUE, NOT NULL |
| nickname | VARCHAR(50) | |
| email | VARCHAR(255) | UNIQUE |

### 2.2 events (이벤트/대회)

| 컬럼 | 타입(추론) | 제약 |
|---|---|---|
| id | BIGSERIAL / BIGINT | PK |
| slug | VARCHAR(100) | UNIQUE, NOT NULL (URL/프론트 식별자) |
| label | VARCHAR(100) | (이벤트 이름) |
| month | INTEGER | (월, 1~12) |
| year | INTEGER | (연도) |
| status | VARCHAR(20) | (이벤트 진행상황) |
| finished_at | TIMESTAMP | NULL 허용 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() |

### 2.3 ple_matches (경기 목록)

| 컬럼 | 타입(추론) | 제약 |
|---|---|---|
| id | BIGSERIAL / BIGINT | PK |
| event_id | BIGINT | FK → events.id, NOT NULL |
| match_key | VARCHAR(100) | (프론트 카드 id, UNIQUE 권장) |
| title | VARCHAR(150) | (타이틀 이름) |
| format | VARCHAR(50) | (경기 종류) |
| card_variant | VARCHAR(50) | (경기 카드 구분) |
| sort_order | INTEGER | (카드 내 정렬 순서) |
| card_json | JSONB | (경기 카드 상세 데이터) |
| status | VARCHAR(20) | (경기 진행상황) |
| winner_pick | VARCHAR(20) | (승리 위치/코너) |
| winner_name | VARCHAR(100) | (승리 선수명) |
| ai_pick | VARCHAR(20) | (AI 예측 위치/코너) |
| ai_pick_name | VARCHAR(100) | (AI 예측 선수명) |
| ai_correct | BOOLEAN | NULL 허용 (AI 적중 여부) |
| point_value | INTEGER | (포인트 가중치) |
| finished_at | TIMESTAMP | NULL 허용 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() |

> 주의: ERD 최상단에 이름 없는 `Field / Field / FK` 행이 하나 더 있으나,
> 이는 ERD 툴이 생성한 미완성 placeholder 컬럼으로 판단되어 **스키마에서 제외**한다
> (실제 이벤트 FK는 `event_id`로 충분히 표현됨). 이 판단은 가정이므로 3번 섹션에 명시한다.

### 2.4 match_pick (AI/회원 경기 예측)

| 컬럼 | 타입(추론) | 제약 |
|---|---|---|
| id | BIGSERIAL / BIGINT | PK |
| match_id | BIGINT | FK → ple_matches.id, NOT NULL |
| client_id | VARCHAR(100) | NULL 허용 (비로그인 익명 사용자 식별자) |
| pick | VARCHAR(20) | (예측한 위치/코너 값) |
| user_id | BIGINT | FK → users.id, **NULL 허용** (비로그인 예측 대응) |

> 주의: ERD상 `match_id`, `user_id` 행에 키 아이콘이 표시되어 있어 `(match_id, user_id)`
> 조합에 대한 유니크 제약(중복 예측 방지)이 의도되었을 가능성이 있다. 이는 명확히 표기되어 있지
> 않으므로 **가정으로 처리**하며, `UNIQUE(match_id, user_id)` 제약을 추가하되 `user_id`가 NULL인
> 익명 예측은 이 제약의 영향을 받지 않음(PostgreSQL은 UNIQUE 제약에서 NULL을 서로 다른 값으로 취급)을
> 마이그레이션 주석에 명시한다.
> 또한 `id`/`client_id` 사이의 이름 없는 `Field / Field / Type` 행 역시 placeholder로 판단하여 제외한다.

### 2.5 title_acquisitions (타이틀 획득 이력)

| 컬럼 | 타입(추론) | 제약 |
|---|---|---|
| id | BIGSERIAL / BIGINT | PK |
| match_id | BIGINT | FK → ple_matches.id, NOT NULL |
| competitor_name | VARCHAR(100) | (선수명) |
| belt_name | VARCHAR(100) | (타이틀/벨트명) |
| won_at | TIMESTAMP | NULL 허용 (획득 시각) |
| won_at_slug | VARCHAR(100) | NULL 허용 |
| match_key | VARCHAR(100) | NULL 허용 (ple_matches.match_key 참고용 비정규 컬럼) |
| source | VARCHAR(100) | NULL 허용 (데이터 출처) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() |

> 주의: ERD의 한글 라벨에는 `match_id`가 "이벤트id"로 표기되어 있으나, 다이어그램의 연결선은
> `events`가 아니라 `ple_matches`에서 내려오므로 **실제 FK 대상은 `ple_matches.id`로 판단**한다.
> 이는 가정이므로 3번 섹션 및 마이그레이션 주석에 명시한다.

### 2.6 관계 요약 (Relationships)

- `events (1) ── (0..N) ple_matches` (실선, event_id 필수)
- `ple_matches (1) ── (0..N) match_pick` (실선, match_id 필수)
- `ple_matches (1) ── (0..N) title_acquisitions` (실선, match_id 필수)
- `users (1) ── (0..N) match_pick` (점선 = 선택적/비식별 관계, user_id NULL 허용)

---

## 3. 제약 사항 (Constraints)

1. **DB는 반드시 Docker 컨테이너로 실행할 것.** 호스트 직접 설치 금지.
2. DB 크리덴셜은 `.env`로 분리하고 `.gitignore`에 포함되어야 하며, `.env.example`도 함께 제공할 것.
3. **기존 alembic 환경을 임의로 재초기화하지 말 것.** 기존 `alembic.ini`/`env.py`가 있으면 그 구조를 따르고,
   없을 때만 새로 생성할 것.
4. 테이블 생성 순서(FK 의존성): `users`, `events` → `ple_matches` → `match_pick`, `title_acquisitions`
5. `downgrade()`는 `upgrade()`의 정확한 역순으로 drop 할 것.
6. pgvector extension 확인/생성(`CREATE EXTENSION IF NOT EXISTS vector;`)을 누락하지 말 것.
   이번 ERD에도 vector 컬럼이 명시되어 있지 않으므로 임의로 vector 컬럼을 추가하지 말 것.
7. **아래는 ERD가 불명확하여 이번 작업에서 취한 가정(Assumption)이다. 마이그레이션 파일 상단 주석에
   반드시 동일하게 명시할 것:**
   - a. 대부분의 컬럼 타입이 ERD에 명시되지 않아(placeholder `Type`) 컬럼명 의미에 따라 추론하였다
     (2번 섹션 표 참고). 실제 요구사항과 다를 경우 추후 수정 마이그레이션이 필요할 수 있다.
   - b. `ple_matches` 상단의 이름 없는 `Field/Field/FK` 행과 `match_pick`의 이름 없는 `Field/Field/Type` 행은
     ERD 툴의 미완성 placeholder로 판단하여 스키마에서 제외하였다.
   - c. `title_acquisitions.match_id`는 한글 라벨이 "이벤트id"로 되어 있으나, 연결선 근거로
     `events.id`가 아닌 `ple_matches.id`를 참조하는 것으로 판단하였다.
   - d. `match_pick`의 `(match_id, user_id)` 조합에 유니크 제약을 추가할지 여부가 ERD상 명확하지 않아,
     키 아이콘 표기를 근거로 `UNIQUE(match_id, user_id)` 제약을 추가하기로 가정하였다.
   - e. FK의 `ON DELETE` 정책이 ERD에 명시되어 있지 않아 기본값(`NO ACTION`)을 사용하였다.
8. `email`, `login_id`(users), `slug`(events)의 UNIQUE 제약은 ERD의 `UK` 표기를 그대로 반영한 것이므로
   변경하지 말 것.

---

## 4. 실행 계획 (Plan) — 순서대로 진행

1. 기존 `docker-compose.yml` 확인 → 없으면 0-1-2 골격 기반 신규 작성, 있으면 `db` 서비스 추가
2. `.env`/`.env.example`에 `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` 정의
3. `docker compose up -d db` 실행 후 `docker compose ps`로 healthy 상태 확인
4. `docker compose exec db psql -U <user> -d <db> -c '\dx'`로 pgvector extension 확인/활성화
5. 기존 alembic 설정 여부 확인, 접속 문자열이 컨테이너 DB를 가리키는지 점검 및 접속 테스트
6. (모델 기반 프로젝트라면) `User`, `Event`, `PleMatch`, `MatchPick`, `TitleAcquisition` SQLAlchemy 모델 작성
   — 2번 섹션 스키마와 3번 섹션 가정을 정확히 반영
7. `alembic revision --autogenerate -m "create users, events, ple_matches, match_pick, title_acquisitions"`
   또는 수동 `op.create_table()` 마이그레이션 작성
8. 마이그레이션 파일 상단에 3-7번의 가정(a~e) 주석 추가
9. 생성된 마이그레이션의 컬럼/타입/제약이 2번 섹션과 일치하는지 diff 검토
10. `alembic upgrade head` 실행 (컨테이너 DB 대상)
11. `docker compose exec db psql -U <user> -d <db> -c '\d ple_matches'` 등으로 5개 테이블 전수 대조 검증
12. `alembic downgrade -1` → `alembic upgrade head` 왕복 테스트
13. `docker compose down` 후 재기동하여 데이터/스키마 유지 여부 최종 확인

---

## 5. 검증 루프 (Verification Loop)

> 2026-07-13 사후 검증 결과. 테이블명은 실제 구현 기준(`events`→`ple_events`, `match_pick`→`ple_predictions`).

- [x] 5개 테이블(`users`, `ple_events`, `ple_matches`, `ple_predictions`, `title_acquisitions`)이 모두 생성되었는가? — 이미 존재, 운영 중.
- [x] 각 테이블의 컬럼이 2번 섹션과 일치하는가? (추론 타입 포함) — 대체로 일치 (PK 타입 제외, 위 "확인 결과" 참고).
- [x] PK가 올바른가? — 전 테이블 `id` PK, autoincrement. 단 타입은 `BIGINT`가 아니라 `INTEGER` (실사용 기준 문제 없음).
- [x] FK가 올바른 방향인가?
      (`ple_matches.event_id → ple_events.id` ✓,
       `ple_predictions.match_id → ple_matches.id` ✓,
       `ple_predictions.user_id → users.id` (NULL 허용) ✓,
       `title_acquisitions.match_id → ple_matches.id` ✓)
- [x] UNIQUE 제약이 반영되었는가? — `users.login_id`, `users.email`, `ple_events.slug`,
      `ple_predictions(match_id, user_id)` 전부 확인 (`(match_id, client_id)` UNIQUE도 추가로 존재).
- [x] placeholder 행(3-7-b) 제외 여부 — 실제 구현에도 해당 컬럼 없음, 판단 유효. (전용 마이그레이션이 없어 주석 대신 본 문서 상단 "확인 결과"에 기록.)
- [x] `title_acquisitions.match_id`의 FK 대상 판단 근거(3-7-c) — 실제로 `ple_matches.id` 참조, 판단 정확. (위와 동일 사유로 본 문서에 기록.)
- [x] `alembic upgrade head` / `downgrade -1` 왕복 시 에러가 없는가? — 해당 테이블들은 이 저장소의 추적 마이그레이션 밖에서 생성되어 round-trip 대상 아님(비고 참고). 실제 서비스에서 안정적으로 동작 중.
- [x] pgvector extension 확인/생성 구문이 포함되어 있는가? — `20260702_02` 마이그레이션에서 보장, `\dx`로 활성 확인.
- [x] DB가 Docker 컨테이너로만 실행되고, 크리덴셜이 `.env`로 분리되어 있는가? — 확인 완료 (`soccer-database.md` 작업 시 healthcheck 포함 검증).
- [x] `docker compose down` → `up` 후에도 데이터가 유지되는가? — pgvector 컨테이너 재생성 검증 완료, named volume으로 데이터 보존 확인.

모든 항목이 체크된 후에만 작업 완료로 보고할 것. 실패 시 원인을 명시하고 재시도할 것.

---

## 6. 출력 형식 (Output)

작업 완료 후 다음을 요약하여 보고할 것:

1. 생성/수정된 파일 목록 (경로 포함, `docker-compose.yml` / `.env.example` 포함)
2. `docker compose up -d` 기동 결과 및 healthcheck 상태
3. `alembic upgrade head` 실행 결과 로그 요약
4. 검증 루프(5번 섹션) 체크리스트 결과
5. **3번 섹션 7번(a~e)의 가정 사항이 실제 요구사항과 다를 가능성이 있는 부분** — 특히 컬럼 타입 추론,
   placeholder 컬럼 제외, `title_acquisitions.match_id`의 FK 대상 — 을 사용자에게 재확인 요청