# Claude Code 작업 지시서: CSV 기반 pgvector 테이블 생성 (Docker + Alembic) — WWE 선수 로스터

> 본 문서는 Karpathy의 "Harness 원칙"에 따라 작성되었습니다.
> 즉, (1) 명확한 목표(Goal) (2) 충분한 컨텍스트(Context) (3) 명시적 제약(Constraints)
> (4) 단계별 실행 계획(Plan) (5) 자체 검증 루프(Verification Loop) 를 모두 포함하여,
> 에이전트가 스스로 판단·검증·수정할 수 있도록 구성합니다.
>
> 본 문서는 이전에 작성된 `soccer-database.md`(이벤트/경기 예측 플랫폼 ERD, Docker 실행 포함)의
> 구조와 원칙을 그대로 계승하며, 이번 소스(WWE 선수 로스터 CSV)에 맞게 내용을 재구성한 것이다.
>
> **중요한 차이점**: 이전 문서들은 ERD 이미지를 판독하여 스키마를 도출했으나, 이번 작업의 소스는
> ERD가 아니라 CSV 파일(웹 스크래핑으로 수집된 WWE 현역 선수 데이터)이다.
> 따라서 2번 섹션의 스키마는 ERD 판독이 아니라 **CSV 컬럼 및 실제 데이터 분포 분석**을 근거로 설계되었다.
>
> **개정 이력**: 본 문서를 근거로 `wrestlers` 테이블과 마이그레이션(`20260714_03`~`06`)이 이미
> 생성·적용되어 있었다. 이후 소스 CSV가 `wwe_active_roster.csv`(197행, 스크래핑 원본)에서
> `wwe_active_roster_cleaned.csv`(178행, 정제본)로 교체되면서 컬럼 구성이 바뀌어(§2 참고),
> 이번 개정에서 스키마·가정·마이그레이션(`20260714_07`)을 함께 갱신했다.

---

## 0. 환경 정보 (Environment)

- OS: Ubuntu 26.04 (Docker 호스트)
- DB: PostgreSQL + pgvector extension → **Docker 컨테이너 내부에서 실행**
- Migration Tool: Alembic
- ORM: SQLAlchemy (Alembic 표준 구성 기준)
- Container Runtime: Docker + Docker Compose
- 소스 데이터: `apps/kayfabe/_docs/wwe_active_roster_cleaned.csv` (178행, WWE RAW/SmackDown/NXT/Evolve/Free Agent 로스터)

---

## 0-1. Docker 기반 DB 실행 (Database in Docker)

**PostgreSQL + pgvector는 호스트에 직접 설치하지 말고, 반드시 Docker 컨테이너로 실행**한다.
pgvector가 미리 설치된 공식 이미지(`pgvector/pgvector:pg16` 등, 프로젝트의 PostgreSQL 메이저 버전에 맞는 태그 사용)를 사용할 것.

> 이 프로젝트에는 이미 `soccer-database.md` / `wwe-roster-database.md`(본 문서, 이전 개정) 작업 시
> 구성된 `docker-compose.yml`, `.env`, pgvector extension, 그리고 `wrestlers` 테이블 자체가 존재한다.
> **0-1 섹션은 재작업하지 말고 건너뛴다.**

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

`wwe_active_roster_cleaned.csv`(178행) 파일을 기반으로 기존 `wrestlers` 테이블 스키마를
갱신하고, 정제된 데이터를 재적재한다. `wrestlers` 테이블 자체는 이미 `20260714_03`~`06`
마이그레이션으로 생성되어 있으므로, 이번 작업은 **신규 테이블 생성이 아니라 스키마 변경
(컬럼 제거/추가) + 데이터 재적재**다.

최종 산출물:

1. `alembic/versions/20260714_07_...py` — `wrestlers` 테이블에서 `wikipedia_title`/`resides`/
   `debut`/`retired` 컬럼을 제거하고 `stable_team`/`brand` 컬럼을 추가하는 마이그레이션
2. `alembic upgrade head` 실행 시 오류 없이 스키마가 갱신될 것
3. `alembic downgrade -1` 실행 시 깨끗하게 롤백될 것
4. `load_wrestlers_csv.py` 재실행으로 178행이 재적재될 것 (§6 참고)

---

## 2. 컨텍스트: CSV 기반 스키마 정의 (Context)

> **중요**: 이 스키마는 ERD가 아니라 `wwe_active_roster_cleaned.csv`(178행)의 헤더와 실제
> 데이터 분포를 분석하여 도출되었다. 이전 CSV(`wwe_active_roster.csv`, 197행)에 비해 데이터
> 품질이 크게 개선되었으나(예: `finisher` 결측이 96% → 0%, `ring_names`/`trainer`에 `|` 구분자
> 정상 적용), 완전히 정규화되지는 않았다. 아래 표의 "결측 비율"과 "데이터 품질 이슈"를 반드시
> 참고하여 타입을 설계할 것.

### 2.0 이전 CSV 대비 컬럼 변경 요약

| 구분 | 컬럼 | 비고 |
|---|---|---|
| 제거 | `wikipedia_title` | 신규 CSV에 없음. 위키 문서 제목 sentinel 값 이슈 자체가 사라짐 |
| 제거 | `resides` | 신규 CSV에 없음 (이전에도 197/197 결측이라 유지 실익이 없었음) |
| 제거 | `debut` | 신규 CSV에 없음 |
| 제거 | `retired` | 신규 CSV에 없음 |
| 추가 | `Stable&Team` → `stable_team` | 소속 스테이블/팀 (신규) |
| 추가 | (컬럼 없음) → `brand` | CSV의 `#RAW`/`#SmackDown`/`#Free Agent`/`#NXT`/`#Evolve` 섹션 마커에서 파생 (신규) |
| 유지 | `name`, `real_name`, `ring_names`, `height`, `weight`, `birth_date`, `birth_place`, `billed_from`, `trainer`, `finisher` | 컬럼명 동일, 데이터 품질은 개선 |

### 2.1 wrestlers (선수)

| 컬럼 | 타입 | 제약 | 결측 비율(178행 기준) | 비고 |
|---|---|---|---|---|
| id | BIGSERIAL / BIGINT | PK | - | 신규 surrogate key (CSV에 없음, 변경 없음) |
| name | VARCHAR(150) | NOT NULL | 0/178 | 표시용 링네임 |
| real_name | VARCHAR(200) | NULL 허용 | 3/178 | |
| ring_names | TEXT | NULL 허용 | 0/178 | `\|`로 구분된 다중 값(142/178행이 2개 이상). 이전 CSV는 구분자 없이 이어붙어 있었으나 이번 CSV는 파이프 구분자가 정상 적용됨(§3-b) |
| stable_team | VARCHAR(100) | NULL 허용 | 115/178 | **신규 컬럼**(원본 `Stable&Team`). 개인 참가자는 결측이 정상. distinct 값 25개(예: `The Vision`, `Judgement Day`, `Creed Brothers`) |
| height | VARCHAR(255) | NULL 허용 | 8/178 | 대부분 `NNNcm` 형식으로 통일됨. 잔존 예외: 공백 포함(`"168 cm"`, 6건), 스토리라인 기믹 이중표기(Danhausen `"178cm(200cm)"`) → INTEGER 변환 금지, VARCHAR 유지(기존 `20260714_06`에서 이미 VARCHAR(255)로 확장되어 있어 추가 변경 불요) |
| weight | VARCHAR(255) | NULL 허용 | 22/178 | 대부분 `NNNkg`. 잔존 예외: 공백 변형(6건), 소수점(Randy Orton `"131.5kg"`), Danhausen 기믹(`"82kg(136kg)"`) → VARCHAR 유지 |
| birth_date | VARCHAR(50) | NULL 허용 | 11/178 | 대부분 `YYYY-MM-DD` ISO 형식으로 통일됨. 잔존 예외: PJ Vasa `"1999-04-??"`(일자 미상), Tate Wilder `"19997-09-06"`(§3-h의 원본 CSV 파싱 결함으로 오염된 값) → DATE 타입 강제 변환 금지, VARCHAR 유지 |
| birth_place | VARCHAR(150) | NULL 허용 | 0/178 | 일부 `\|` 다중 값 존재(2건, 여러 출생지 표기 이력) |
| billed_from | VARCHAR(150) | NULL 허용 | 3/178 | 일부 `\|` 다중 값 존재(14건). Ivar 행은 스크래핑 잔재로 따옴표가 값에 섞여 있음(`'"Overseas"Reno, Nevada \| Lynn, Massachusetts'`, §3-f) |
| trainer | TEXT | NULL 허용 | 3/178 | `\|`로 구분된 다중 값(99/178행) |
| finisher | TEXT | NULL 허용 | 0/178 | 이전 CSV는 189/197(96%) 결측이었으나 이번 CSV는 완전히 채워짐 — 데이터 품질이 크게 개선된 컬럼 |
| brand | VARCHAR(20) | NULL 허용 | - | **신규 컬럼**. 원본 CSV의 `#RAW`/`#SmackDown`/`#Free Agent`/`#NXT`/`#Evolve` 브랜드 구분 마커 행에서 파생. 분포: NXT 58 · RAW 52 · SmackDown 51 · Evolve 13 · Free Agent 4 (합 178) |
| embedding | VECTOR(1024) | NULL 허용 | - | RAG 검색용 임베딩 벡터. 차원(1024)은 이 프로젝트 표준 `core.matrix.vault_keymaker_secret_manager.EMBEDDING_DIM`(bge-m3)을 따른다. 변경 없음 |

### 2.2 관계 요약 (Relationships)

- 이번 소스는 단일 CSV 파일이므로 FK로 연결되는 다른 테이블이 없다. `wrestlers`는 독립 테이블이다.
- `brand`, `stable_team`은 정규화된 참조 테이블(FK)이 아니라 CSV 원문을 그대로 담는 자유 텍스트
  컬럼이다. 향후 브랜드/스테이블 단위 조회가 잦아지면 별도 마스터 테이블 도입을 고려할 수 있으나,
  이번 마이그레이션 범위에는 포함하지 않는다.
- 향후 `soccer-database.md`의 `title_acquisitions.competitor_name` 같은 자유 텍스트 컬럼과
  `wrestlers.name`을 애플리케이션 레벨에서 매칭할 가능성이 있으나, 이번 마이그레이션 범위에는
  **FK 제약을 포함하지 않는다** (이름 매칭은 정확도가 낮아 DB 레벨 FK로 강제하기 부적절).

---

## 3. 제약 사항 (Constraints)

1. **DB는 반드시 Docker 컨테이너로 실행할 것.** 호스트 직접 설치 금지.
2. DB 크리덴셜은 `.env`로 분리하고 `.gitignore`에 포함되어야 하며, `.env.example`도 함께 제공할 것.
   (이미 구성되어 있으므로 재작업하지 말 것.)
3. **기존 alembic 환경을 임의로 재초기화하지 말 것.** 기존 `alembic.ini`/`env.py`가 있으면 그 구조를 따를 것.
   이번 작업은 `20260714_06`(head) 위에 `20260714_07`을 추가하는 **증분 마이그레이션**이다.
4. `downgrade()`는 `upgrade()`의 정확한 역순으로 처리할 것 (드롭한 컬럼은 재생성, 추가한 컬럼은 드롭).
5. pgvector extension 확인/생성은 이미 이전 마이그레이션에서 보장되어 있으므로 이번 작업에서
   중복 생성하지 않는다.
6. **아래는 CSV 데이터 품질 특성상 이번 작업에서 취한 가정(Assumption)이다. 마이그레이션 파일 상단
   주석에 반드시 동일하게 명시할 것:**
   - a. `height`, `weight`, `birth_date`는 이전 CSV보다 형식이 훨씬 통일되었으나(대부분 `NNNcm`/
     `NNNkg`/`YYYY-MM-DD`) 여전히 완전히 정규화되지는 않았다(공백 변형, 소수점, 스토리라인
     기믹 이중표기, 일자 미상 placeholder). 이번에도 INTEGER/DATE로 강제 변환하지 않고
     **원문 그대로 VARCHAR로 저장**한다.
   - b. `ring_names`, `trainer` 컬럼은 이번 CSV에서 `|` 구분자가 정상 적용되어 있다(이전 CSV의
     "구분자 없이 이어붙음" 문제는 해소됨). 다만 이번 마이그레이션에서도 값 분리(다중값 →
     별도 테이블)는 스키마 책임이 아니라 애플리케이션/조회 레벨의 책임으로 두고, 단일 TEXT
     컬럼에 원문(`|` 포함) 그대로 저장한다.
   - c. `wikipedia_title` 컬럼이 이번 CSV에는 없으므로 관련 UNIQUE 예외 가정은 더 이상 필요
     없다. 대신 `name` 기준으로 전수 재검사한 결과 178행 전원이 유일하다(완전 중복 0건).
     다만 동명이인 가능성을 배제할 수 없어 이번에도 `name`에 DB 레벨 UNIQUE 제약은 추가하지
     않는다(기존 방침 유지).
   - d. `resides`, `debut`, `retired` 컬럼은 이번 CSV에 아예 존재하지 않는다. 이전에는 `resides`가
     197/197 전량 NULL임에도 컬럼을 유지했었으나, 이번 마이그레이션에서는 소스에 없는 컬럼을
     그대로 유지할 실익이 없다고 판단해 **세 컬럼 모두 DROP**한다.
   - e. `embedding VECTOR(1024)` 컬럼은 변경하지 않는다. 이 프로젝트가 이미 사용 중인 표준
     `core.matrix.vault_keymaker_secret_manager.EMBEDDING_DIM`(bge-m3)을 그대로 따른다.
   - f. 잔존 스크래핑 오염: Ivar의 `billed_from`에 따옴표가 값에 섞여 들어간 사례
     (`'"Overseas"Reno, Nevada | Lynn, Massachusetts'`)가 1건 남아 있다. 이전 CSV(각주 텍스트
     오염 8건 이상)보다 훨씬 적지만 완전히 사라지지는 않았다. 원본 CSV는 건드리지 않고,
     이번 작업 범위에서는 별도 정제 없이 원문 그대로 적재한다.
   - g. 이번 CSV(178행)에는 `name` 기준 중복도, 전체 컬럼 완전 중복 행도 존재하지 않는다.
     따라서 이전처럼 "197 - 10 = 187"식의 dedup 보정이 필요 없다 — **최종 적재 건수는 178행**이다.
     적재 스크립트는 재실행 안전성(idempotency)을 위해 여전히 `name` 기준 upsert로 동작하지만,
     이번 CSV의 중복 제거가 목적은 아니다. 다만 DB에는 이미 이전 CSV(197행) 기준으로 187행이
     적재되어 있고, 두 CSV의 `name` 집합은 완전히 겹치지 않는다(이전에만 있던 이름 49개, 신규에만
     있는 이름 39개, `python3` 전수 대조로 확인). upsert만으로는 이전 CSV에만 있던 49행이 그대로
     남아 최종 건수가 178이 아니게 되므로, 적재 스크립트는 upsert 전에 **신규 CSV의 `name` 집합에
     없는 기존 행을 먼저 삭제**한다.
   - h. **원본 CSV 파싱 결함(신규 발견)**: 원본 파일 145~146행에서 Tank Ledger의 `trainer` 값
     (`"WWE Performance Center...`)에 닫는 따옴표가 누락되어 있다. 표준 CSV 파서(Python `csv`
     모듈 등)는 이 경우 다음 줄(Tate Wilder의 전체 행)까지 하나의 필드로 삼켜 두 선수의 데이터가
     15개 컬럼짜리 단일 레코드로 잘못 병합된다(이 병합 과정에서 Tate Wilder의 `birth_date`도
     원본에 이미 `"19997-09-06"`처럼 오염된 상태로 확인됨, a 참고). 원본 CSV는 건드리지 않고,
     적재 스크립트(`load_wrestlers_csv.py`)가 파싱 직후 이 두 행을 알려진 값으로 수동 분리하도록
     예외 처리를 추가했다. 이 예외 처리가 없으면 178행이 177행으로 줄고 두 선수의 정보가
     뒤섞인다.
   - i. **brand 컬럼 파싱(신규)**: 원본 CSV는 브랜드별로 `#RAW`/`#SmackDown`/`#Free Agent`/`#NXT`/
     `#Evolve` 마커 행(단일 필드, `#`로 시작)으로 섹션이 구분되어 있다. 적재 스크립트는 이 마커를
     만날 때마다 "현재 브랜드" 상태를 갱신하고, 이후 나오는 선수 행마다 `brand` 컬럼에 채워
     넣는다. 마커 행 자체는 `wrestlers` 테이블에 데이터로 적재되지 않는다.
7. `ring_names`/`trainer`는 이미 `|` 구분자가 있으므로 별도 파싱 로직 없이 원문 그대로 저장한다.
   마이그레이션 자체(스키마 변경)에서는 데이터 정제 로직을 수행하지 않는다 — 3-h의 병합 행 복구,
   3-i의 brand 파싱은 스키마가 아니라 **로더 스크립트**의 책임으로 둔다.

---

## 4. 실행 계획 (Plan) — 순서대로 진행

1. `alembic current`로 현재 head가 `20260714_06`인지 확인 (기존 `wrestlers` 테이블·03~06
   마이그레이션이 이미 적용되어 있음을 전제).
2. 새 CSV(`apps/kayfabe/_docs/wwe_active_roster_cleaned.csv`, 178행)와 이전 CSV의 컬럼 차이를
   2번 섹션 기준으로 재확인.
3. `WrestlerOrm`(`apps/kayfabe/adapter/outbound/orm/wrestler_orm.py`)에서 `wikipedia_title`/
   `resides`/`debut`/`retired`를 제거하고 `stable_team`/`brand`를 추가.
4. `alembic/versions/20260714_07_...py` 마이그레이션 작성(수동 `op.drop_column`/`op.add_column`),
   `down_revision = "20260714_06"`.
5. 마이그레이션 파일 상단에 3번 섹션의 가정(a~i, 특히 신규 h/i) 주석 추가.
6. `load_wrestlers_csv.py`를 새 CSV 경로/컬럼 매핑/브랜드 마커 파싱/병합 행(3-h) 복구 로직으로 수정.
7. RAG 관련 파일(`wrestler_chat_repository.py`의 `_describe`, `backfill_wrestler_embeddings.py`의
   `_wrestler_text`)에서 제거된 `debut`/`retired` 참조를 `stable_team`/`brand`로 교체.
8. `alembic upgrade head` 실행 (컨테이너 DB 대상).
9. `docker compose exec pgvector psql -U <user> -d <db> -c '\d wrestlers'`로 컬럼 변경 전수 대조 검증.
10. `load_wrestlers_csv.py` 재실행 → `SELECT COUNT(*) FROM wrestlers;` = 178, `brand` 분포가
    §2.1과 일치하는지 확인.
11. `alembic downgrade -1` → `alembic upgrade head` 왕복 테스트.
12. `ruff check`/`ruff format`/`lint-imports` 실행 (fastapi 작업 후 하네스 게이트).

---

## 5. 검증 루프 (Verification Loop)

작업 완료 전 아래를 **반드시 자체 점검**하고, 실패 항목이 있으면 수정 후 재검증할 것.

- [ ] `wrestlers` 테이블에서 `wikipedia_title`/`resides`/`debut`/`retired`가 제거되었는가?
- [ ] `stable_team`(VARCHAR(100))/`brand`(VARCHAR(20)) 컬럼이 추가되었는가?
- [ ] 나머지 컬럼(`name`~`finisher`, `embedding`)의 타입이 2번 섹션 표와 정확히 일치하는가?
      (`height`/`weight`/`birth_date`가 INTEGER/DATE로 잘못 변환되지 않았는가?)
- [ ] PK(`id`)가 그대로 유지되었는가?
- [ ] `name`에 UNIQUE 제약이 **잘못 추가되지 않았는가**? (3-c 가정 확인)
- [ ] `embedding` 컬럼이 `VECTOR(1024)` 타입을 유지하는가? (변경 대상 아님)
- [ ] `alembic upgrade head` / `alembic downgrade -1` 왕복 시 에러가 없는가?
- [ ] 마이그레이션 파일에 가정 사항(3번 섹션 a~i)이 주석으로 남아 있는가?
- [ ] 로더 스크립트가 145~146행 병합 행(3-h)을 Tank Ledger/Tate Wilder 두 행으로 정확히
      복구하는가? (복구 실패 시 `SELECT COUNT(*)`가 178이 아니라 177이 됨)
- [ ] `SELECT COUNT(*) FROM wrestlers;` 결과가 **178**과 일치하는가?
- [ ] `brand` 분포가 NXT 58 / RAW 52 / SmackDown 51 / Evolve 13 / Free Agent 4와 일치하는가?
- [ ] DB가 호스트에 직접 설치되지 않고 **Docker 컨테이너**로만 실행되는가?
- [ ] 컨테이너 재기동(`docker compose down` → `up`) 후에도 데이터가 유지되는가? (volume 검증)

모든 항목이 체크된 후에만 작업 완료로 보고할 것. 실패 시 원인을 명시하고 재시도할 것.

---

## 6. 출력 형식 (Output)

작업 완료 후 다음을 요약하여 보고할 것:

1. 생성/수정된 파일 목록 (경로 포함: ORM / 마이그레이션 / 로더 스크립트 / RAG 참조 수정 파일)
2. `alembic upgrade head` 실행 결과 로그 요약
3. 검증 루프(5번 섹션) 체크리스트 결과
4. `load_wrestlers_csv.py` 재실행 결과(inserted/updated 건수, 최종 `COUNT(*)`)
5. **3번 섹션의 가정 중 실제 요구사항과 다를 가능성이 있는 부분** — 특히 다음은 재확인 요청할 것:
   - `stable_team`/`brand` 컬럼 폭(VARCHAR(100)/VARCHAR(20))이 향후 데이터로 충분한지 (가정 없음,
     현재 관측된 최대 길이는 각각 23자/10자)
   - Ivar의 `billed_from` 따옴표 오염(가정 f)을 이후 별도로 정제할 계획이 있는지
