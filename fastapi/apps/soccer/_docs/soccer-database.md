# Claude Code 작업 지시서: ERD 기반 pgvector 테이블 생성 (Alembic)

> 본 문서는 Karpathy의 "Harness 원칙"에 따라 작성되었습니다.
> 즉, (1) 명확한 목표(Goal) (2) 충분한 컨텍스트(Context) (3) 명시적 제약(Constraints)
> (4) 단계별 실행 계획(Plan) (5) 자체 검증 루프(Verification Loop) 를 모두 포함하여,
> 에이전트가 스스로 판단·검증·수정할 수 있도록 구성합니다.

---

## 0. 환경 정보 (Environment)

- OS: Ubuntu 26.04 (Docker 호스트)
- DB: PostgreSQL + pgvector extension → **Docker 컨테이너 내부에서 실행**
- Migration Tool: Alembic (호스트 또는 별도 컨테이너에서 실행, DB는 컨테이너에 접속)
- ORM: SQLAlchemy (Alembic 표준 구성 기준)
- Container Runtime: Docker + Docker Compose

---

## 0-1. Docker 기반 DB 실행 (Database in Docker)

**PostgreSQL + pgvector는 호스트에 직접 설치하지 말고, 반드시 Docker 컨테이너로 실행**한다.
pgvector가 미리 설치된 공식 이미지(`pgvector/pgvector:pg16` 등, 프로젝트의 PostgreSQL 메이저 버전에 맞는 태그 사용)를 사용할 것.

### 0-1-1. 요구 사항

1. 프로젝트 루트에 `docker-compose.yml`(또는 기존 파일이 있다면 그 파일에 서비스 추가)을 작성/수정하여
   `db`(또는 기존 서비스명 관례를 따름) 서비스를 정의한다.
2. 이미지: `pgvector/pgvector:pg16` (프로젝트에서 특정 PostgreSQL 버전을 요구하면 그에 맞는 태그로 조정,
   예: pg15 → `pgvector/pgvector:pg15`)
3. 환경변수: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`를 `.env` 파일(또는 기존 `.env` 관례)로 분리하여 주입.
   하드코딩 금지.
4. 포트: 호스트의 `5432`를 컨테이너의 `5432`로 매핑하되, 이미 5432가 사용 중일 수 있으므로
   충돌 시 호스트 포트를 `.env`의 `POSTGRES_PORT` 변수로 조정 가능하게 할 것 (예: `${POSTGRES_PORT:-5432}:5432`).
5. 데이터 영속성을 위해 named volume(예: `pgdata:/var/lib/postgresql/data`)을 반드시 선언할 것.
   컨테이너 재시작/재생성 시 데이터가 유지되어야 한다.
6. `healthcheck`를 추가하여 (`pg_isready` 사용) 컨테이너가 완전히 기동된 이후에만
   Alembic이 접속을 시도하도록 할 것.
7. `CREATE EXTENSION IF NOT EXISTS vector;`는 컨테이너의 `docker-entrypoint-initdb.d/` 초기화 스크립트로
   1회성 등록하거나(권장), 혹은 3번 섹션의 Alembic 초기 마이그레이션에서 실행하는 방식 중
   프로젝트 관례에 맞는 쪽을 선택하되 **둘 중 하나는 반드시 수행**할 것 (누락 금지).

### 0-1-2. docker-compose.yml 예시 골격 (참고용, 프로젝트 기존 구조 우선)

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

> 위 골격은 참고용이며, 프로젝트에 이미 `docker-compose.yml`이나 다른 서비스(백엔드 앱 등)가
> 존재한다면 그 구조와 네이밍 컨벤션을 따라 병합할 것. 새로 만드는 것이 최후의 수단이다.

### 0-1-3. Alembic → 컨테이너 DB 접속 설정

- `alembic.ini`의 `sqlalchemy.url` 또는 `env.py`에서 읽어오는 접속 문자열이
  Docker 컨테이너의 DB를 가리키도록 설정할 것.
  - Alembic을 호스트에서 실행하는 경우: `postgresql+psycopg2://<user>:<pw>@localhost:${POSTGRES_PORT:-5432}/<db>`
  - Alembic도 컨테이너(같은 docker network) 내부에서 실행하는 경우: 호스트명은 `localhost`가 아닌
    서비스명(`db`)을 사용할 것: `postgresql+psycopg2://<user>:<pw>@db:5432/<db>`
- 접속 정보는 하드코딩하지 말고 `.env` 또는 환경변수에서 읽어오도록 구성할 것.

---

## 1. 목표 (Goal)

첨부된 ERD 이미지를 기반으로 아래 4개 테이블을 PostgreSQL(pgvector 확장 설치됨)에
Alembic 마이그레이션으로 생성한다.

- `stadium`
- `schedule`
- `team`
- `player`

최종 산출물은 다음과 같다.

1. `alembic/versions/` 하위에 위 4개 테이블을 생성하는 마이그레이션 파일 1개(또는 논리적으로 분리된 여러 개)
2. `alembic upgrade head` 실행 시 오류 없이 스키마가 생성될 것
3. `alembic downgrade -1` 실행 시 깨끗하게 롤백될 것 (drop 순서까지 고려)

---

## 2. 컨텍스트: ERD 스키마 정의 (Context)

아래는 첨부 이미지(ERD)를 판독한 결과다. **타입/길이/PK/FK를 임의로 변경하지 말고 그대로 구현**하라.
단, `N/A`로 표시된 값은 "NULL 허용" 의미이며 별도 제약이 없다는 뜻이다.

### 2.1 stadium (경기장)

| 컬럼 | 타입 | 제약 |
|---|---|---|
| stadium_id | VARCHAR(10) | PK |
| statdium_name | VARCHAR(40) | |
| hometeam_id | VARCHAR(10) | |
| seat_count | INTEGER | |
| address | VARCHAR(60) | |
| ddd | VARCHAR(10) | |
| tel | VARCHAR(10) | |
| embedding | VECTOR(1024) | NULL 허용 |

> 주의: ERD 원본에 `statdium_name`이라는 오탈자(stadium이 아님)가 그대로 표기되어 있다.
> **컬럼명은 오탈자를 포함하여 원본 그대로 생성**한다 (임의 수정 금지).
>
> `embedding`은 ERD에는 없으나 RAG 검색용으로 사용자 요청에 따라 stadium/team/schedule/player
> 4개 테이블 모두에 추가했다. 차원(1024)은 이 프로젝트 표준
> `core.matrix.vault_keymaker_secret_manager.EMBEDDING_DIM`(bge-m3)을 따른다
> (`20260714_03` 마이그레이션, `wrestlers`/`receiver_emails`와 동일 컨벤션).

### 2.2 schedule (경기 일정)

| 컬럼 | 타입 | 제약 |
|---|---|---|
| sche_date | VARCHAR(10) | PK |
| stadium_id | VARCHAR(10) | FK → stadium.stadium_id |
| gubun | VARCHAR(10) | |
| hometeam_id | VARCHAR(10) | |
| awayteam_id | VARCHAR(10) | |
| home_score | INTEGER | |
| away_score | INTEGER | |
| embedding | VECTOR(1024) | NULL 허용 |

> `embedding`은 ERD에는 없으나 RAG 검색용으로 추가했다 (2.1 stadium 절 설명 참고).

관계: `stadium (1) ── (0..N) schedule` (stadium 삭제 시 schedule 처리 정책은 4번 섹션 참고)

### 2.3 team (구단)

| 컬럼 | 타입 | 제약 |
|---|---|---|
| team_id | VARCHAR(10) | PK |
| region_name | VARCHAR(10) | |
| team_name | VARCHAR(40) | |
| e_team_name | VARCHAR(50) | |
| orig_yyyy | VARCHAR(10) | |
| zip_code1 | VARCHAR(10) | |
| zip_code2 | VARCHAR(10) | |
| address | VARCHAR(80) | |
| ddd | VARCHAR(10) | |
| tel | VARCHAR(10) | |
| fax | VARCHAR(10) | |
| homepage | VARCHAR(50) | |
| owner | VARCHAR(10) | |
| stadium_id | VARCHAR(10) | FK → stadium.stadium_id |
| embedding | VECTOR(1024) | NULL 허용 |

> `embedding`은 ERD에는 없으나 RAG 검색용으로 추가했다 (2.1 stadium 절 설명 참고).

관계: `stadium (1) ── (N) team` (홈구장 참조)

### 2.4 player (선수)

| 컬럼 | 타입 | 제약 |
|---|---|---|
| player_id | VARCHAR(10) | PK |
| player_name | VARCHAR(20) | |
| e_player_name | VARCHAR(40) | |
| nickname | VARCHAR(30) | |
| join_yyyy | VARCHAR(10) | |
| position | VARCHAR(10) | |
| back_no | INTEGER | |
| nation | VARCHAR(20) | |
| birth_date | DATE | |
| solar | VARCHAR(10) | |
| height | INTEGER | |
| weight | INTEGER | |
| team_id | VARCHAR(10) | FK → team.team_id |
| embedding | VECTOR(1024) | NULL 허용 |

> `embedding`은 ERD에는 없으나 RAG 검색용으로 추가했다 (2.1 stadium 절 설명 참고).

관계: `team (1) ── (0..N) player`

---

## 3. 제약 사항 (Constraints)

1. **기존 alembic 환경을 임의로 재초기화하지 말 것.** `alembic.ini`, `env.py`가 이미 존재하면
   해당 설정(특히 `sqlalchemy.url`, `target_metadata`)을 먼저 읽고 그 구조를 따를 것.
   존재하지 않을 경우에만 `alembic init alembic`으로 새로 생성할 것.
2. SQLAlchemy 모델을 사용하는 프로젝트라면 `models/` 또는 이에 준하는 디렉토리에
   `Stadium`, `Schedule`, `Team`, `Player` 모델 클래스를 먼저 정의하고,
   Alembic autogenerate(`alembic revision --autogenerate`)로 마이그레이션을 생성할 것.
   모델이 없는 순수 스크립트 기반 프로젝트라면 `op.create_table()`을 사용한 수동 마이그레이션으로 작성할 것.
   (프로젝트 구조를 먼저 확인한 뒤 방식을 결정할 것.)
3. 테이블 생성 순서는 FK 의존성을 지킬 것: `stadium` → `team` → `schedule`, `player`
   (schedule과 player는 순서 무관, 단 각각 stadium/team보다는 뒤에 생성)
4. `downgrade()` 함수는 `upgrade()`의 역순으로 정확히 drop 하도록 작성할 것
   (FK 참조 테이블을 참조 대상 테이블보다 먼저 drop).
5. pgvector 관련 벡터 컬럼은 이번 ERD에는 명시되어 있지 않으므로 **임의로 vector 컬럼을 추가하지 말 것.**
   (단, 이후 사용자가 명시적으로 요청하여 `20260714_03` 마이그레이션에서 4개 테이블 전부에
   `embedding VECTOR(1024)`를 예외적으로 추가했다 — 2번 섹션 각 표 참고.)
   단, pgvector extension이 설치되어 있는지 여부만 `CREATE EXTENSION IF NOT EXISTS vector;`로 확인/보장하는
   초기 마이그레이션(또는 기존 초기 마이그레이션)이 있는지 점검할 것. 없다면 최초 마이그레이션에
   extension 생성 구문을 포함할 것 (추후 vector 컬럼 확장을 대비).
6. 모든 VARCHAR 길이와 컬럼명은 위 스키마 정의를 **그대로** 따를 것 (오탈자 포함).
7. FK 제약 조건에 대한 `ON DELETE` 정책이 ERD에 명시되어 있지 않으므로,
   기본값(`NO ACTION`)을 사용하되, 이 부분은 가정임을 마이그레이션 파일 주석으로 명시할 것.
8. **DB는 반드시 Docker 컨테이너로 실행할 것.** 호스트에 `apt install postgresql` 등으로
   직접 설치하지 말 것. 기존 `docker-compose.yml`이 있다면 새 서비스를 추가하는 방식으로 확장하고,
   없다면 0-1-2 골격을 기반으로 신규 작성할 것.
9. DB 접속 크리덴셜(`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` 등)은
   `.env` 파일로 분리하고, `.env`가 `.gitignore`에 포함되어 있는지 확인할 것
   (없다면 추가). `.env.example`(값은 비우거나 placeholder)도 함께 제공할 것.

---

## 4. 실행 계획 (Plan) — 순서대로 진행

1. 프로젝트 루트에서 기존 `docker-compose.yml` 존재 여부 확인. 있으면 DB 서비스 추가/확인,
   없으면 0-1-2 골격 기반으로 신규 작성
2. `.env` / `.env.example` 파일에 `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` 정의
3. `docker compose up -d db` (또는 해당 서비스명)로 컨테이너 기동
4. `docker compose ps` 및 healthcheck 상태로 DB 컨테이너가 정상(healthy) 기동되었는지 확인
5. `docker compose exec db psql -U <user> -d <db> -c '\dx'`로 pgvector extension이
   설치/활성화되어 있는지 확인 (없다면 0-1-1의 7번 방식 중 하나로 활성화)
6. 프로젝트 루트에서 기존 alembic 설정 여부 확인 (`alembic.ini`, `alembic/env.py` 존재 여부)
7. `sqlalchemy.url`(또는 `env.py`에서 읽는 접속 문자열)이 컨테이너 DB를 정확히 가리키는지 점검
   (0-1-3 참고), 실제 접속 테스트
8. (모델 기반이라면) `Stadium`, `Team`, `Schedule`, `Player` SQLAlchemy 모델 작성
9. `alembic revision --autogenerate -m "create stadium, team, schedule, player tables"`
   또는 수동으로 `op.create_table()` 기반 마이그레이션 파일 작성
10. 생성된 마이그레이션 파일을 열어 **자동 생성된 타입/제약이 위 스키마와 일치하는지 diff 검토**
11. `alembic upgrade head` 실행 (컨테이너 DB 대상)
12. `docker compose exec db psql -U <user> -d <db> -c '\d stadium'` 등으로
    실제 생성된 컬럼/타입/FK를 스키마 정의와 1:1 대조 검증
13. `alembic downgrade -1` 실행하여 롤백이 에러 없이 되는지 확인
14. 다시 `alembic upgrade head`로 원복
15. `docker compose down`(컨테이너만 정지, volume은 유지) 시에도 데이터가 보존되는지
    (`docker compose up -d` 재기동 후 데이터 확인) 최종 점검

---

## 5. 검증 루프 (Verification Loop)

작업 완료 전 아래를 **반드시 자체 점검**하고, 실패 항목이 있으면 수정 후 재검증할 것.

- [ ] 4개 테이블이 모두 생성되었는가?
- [ ] 각 테이블의 컬럼명·타입·길이가 2번 섹션 스키마와 정확히 일치하는가? (오탈자 포함)
- [ ] PK가 올바르게 설정되었는가? (`stadium_id`, `sche_date`, `team_id`, `player_id`)
- [ ] FK가 올바른 방향으로 설정되었는가?
      (`schedule.stadium_id → stadium.stadium_id`,
       `team.stadium_id → stadium.stadium_id`,
       `player.team_id → team.team_id`)
- [ ] `alembic upgrade head` / `alembic downgrade -1` 왕복 시 에러가 없는가?
- [ ] pgvector extension 확인/생성 구문이 누락 없이 포함되어 있는가?
- [ ] 마이그레이션 파일에 가정 사항(ON DELETE 정책 등)이 주석으로 남아 있는가?
- [ ] DB가 호스트에 직접 설치되지 않고 **Docker 컨테이너**로만 실행되는가?
- [ ] `docker-compose.yml`에 healthcheck, named volume이 포함되어 있는가?
- [ ] DB 크리덴셜이 하드코딩되지 않고 `.env`로 분리되어 있으며, `.gitignore`에 포함되어 있는가?
- [ ] 컨테이너 재기동(`docker compose down` → `up`) 후에도 데이터가 유지되는가? (volume 검증)

모든 항목이 체크된 후에만 작업 완료로 보고할 것. 실패 시 원인을 명시하고 재시도할 것.

---

## 6. 출력 형식 (Output)

작업 완료 후 다음을 요약하여 보고할 것:

1. 생성/수정된 파일 목록 (경로 포함, `docker-compose.yml` / `.env.example` 포함)
2. `docker compose up -d` 기동 결과 및 healthcheck 상태
3. `alembic upgrade head` 실행 결과 로그 요약
4. 검증 루프(5번 섹션) 체크리스트 결과
5. 발견된 이슈나 ERD와 다르게 해석/가정한 부분이 있다면 명시