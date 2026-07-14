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
> ERD가 아니라 `wwe_active_roster.csv` 파일(웹 스크래핑으로 수집된 WWE 현역 선수 데이터, 197행)이다.
> 따라서 2번 섹션의 스키마는 ERD 판독이 아니라 **CSV 컬럼 및 실제 데이터 분포 분석**을 근거로 설계되었다.

---

## 0. 환경 정보 (Environment)

- OS: Ubuntu 26.04 (Docker 호스트)
- DB: PostgreSQL + pgvector extension → **Docker 컨테이너 내부에서 실행**
- Migration Tool: Alembic
- ORM: SQLAlchemy (Alembic 표준 구성 기준)
- Container Runtime: Docker + Docker Compose
- 소스 데이터: `wwe_active_roster.csv` (프로젝트 내 적절한 위치, 예: `apps/kayfabe/_data/` 에 배치 후 참조)

---

## 0-1. Docker 기반 DB 실행 (Database in Docker)

**PostgreSQL + pgvector는 호스트에 직접 설치하지 말고, 반드시 Docker 컨테이너로 실행**한다.
pgvector가 미리 설치된 공식 이미지(`pgvector/pgvector:pg16` 등, 프로젝트의 PostgreSQL 메이저 버전에 맞는 태그 사용)를 사용할 것.

> 이 프로젝트에 이미 `soccer-database.md` / `claude_code_prompt_pgvector_alembic.md` 작업 시 구성된
> `docker-compose.yml`, `.env`, pgvector extension이 존재할 가능성이 높다. **먼저 기존 구성을 확인하고,
> 이미 충족되어 있다면 0-1 섹션은 재작업하지 말고 건너뛸 것.** 아래는 미존재 시에만 적용한다.

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

`wwe_active_roster.csv` 파일을 기반으로 아래 1개 테이블을 Docker 컨테이너로 실행 중인
PostgreSQL(pgvector 확장 설치됨)에 Alembic 마이그레이션으로 생성한다.

- `wrestlers`

최종 산출물:

1. `alembic/versions/` 하위에 `wrestlers` 테이블을 생성하는 마이그레이션 파일 1개
2. `alembic upgrade head` 실행 시 오류 없이 스키마가 생성될 것
3. `alembic downgrade -1` 실행 시 깨끗하게 롤백될 것
4. (선택, 6번 섹션 참고) CSV 데이터를 실제로 적재하는 시드 스크립트 또는 별도 데이터 마이그레이션

> 본 작업은 단일 테이블이므로 FK 의존성 순서 문제가 없다. 다만 이 프로젝트에 이미 존재하는
> 다른 도메인 테이블(예: `soccer-database.md`의 `users`, `ple_matches` 등)과 이름이 충돌하지 않는지
> 사전에 확인할 것.

---

## 2. 컨텍스트: CSV 기반 스키마 정의 (Context)

> **중요**: 이 스키마는 ERD가 아니라 `wwe_active_roster.csv`(197행)의 헤더와 실제 데이터 분포를
> 분석하여 도출되었다. CSV는 Wikipedia 위키텍스트를 정규식/mwparserfromhell로 파싱해 만든
> 스크래핑 결과물이라 **원본 데이터 품질이 균일하지 않다.** 아래 표의 "결측 비율"과 "데이터 품질 이슈"를
> 반드시 참고하여 타입을 설계할 것 (예: `height`/`weight`/`debut`는 형식이 통일되어 있지 않아
> INTEGER나 DATE가 아니라 VARCHAR/TEXT로 저장하는 것이 안전하다).

### 2.1 wrestlers (선수)

| 컬럼 | 타입 | 제약 | 결측 비율(197행 기준) | 비고 |
|---|---|---|---|---|
| id | BIGSERIAL / BIGINT | PK | - | 신규 surrogate key (CSV에 없음) |
| wikipedia_title | VARCHAR(255) | NULL 허용 | 0/197 | Wikipedia 문서 제목. 문서가 없는 경우 `(no wiki page)` 같은 sentinel 문자열이 값으로 들어올 수 있음(UNIQUE 제약 금지 사유, 3번 섹션 참고) |
| name | VARCHAR(150) | NOT NULL | 0/197 | 표시용 링네임 |
| real_name | VARCHAR(200) | NULL 허용 | 38/197 결측 | |
| ring_names | TEXT | NULL 허용 | 97/197 결측 | **구분자 없이 이어붙은 문자열**(예: `"Arthur Klauser-SaxonBravo AmericanoElephant Mask..."`). 3번 섹션 가정 참고 |
| height | VARCHAR(50) | NULL 허용 | 71/197 결측 | 형식 불일치(`"5 ft 7 in"`, `"178cm"`, 범위 표기 `"6 ft 8 in (203 cm) – 6 ft 9 in (206 cm)"` 등 혼재) → INTEGER 변환 금지, 원문 그대로 저장. 실제 최대 길이(정제 후) 기준으로 VARCHAR(20)→VARCHAR(50)로 조정 (적재 시 각주 오염 데이터 정제, 3번 섹션 가정 f 참고) |
| weight | VARCHAR(30) | NULL 허용 | 91/197 결측 | 형식 불일치(`"156 lb"`, `"220 lbs"`, `"202lb"` 등) → 원문 그대로 저장. VARCHAR(20)→VARCHAR(30)로 조정 (3번 섹션 가정 f 참고) |
| birth_date | VARCHAR(50) | NULL 허용 | 173/197 결측 | 결측이 압도적으로 많고, 존재하는 값도 `"April 18, 1992"` 형태의 자연어 문자열 → DATE 타입 강제 변환 금지. VARCHAR(30)→VARCHAR(50)로 조정 (3번 섹션 가정 f 참고) |
| birth_place | VARCHAR(150) | NULL 허용 | 31/197 결측 | |
| resides | VARCHAR(150) | NULL 허용 | **197/197 결측 (전량 NULL)** | 3번 섹션 가정 참고 — 컬럼 존치 여부 판단 필요 |
| billed_from | VARCHAR(150) | NULL 허용 | 56/197 결측 | |
| trainer | TEXT | NULL 허용 | 41/197 결측 | **구분자 없이 이어붙은 문자열** (ring_names와 동일한 이슈) |
| debut | VARCHAR(30) | NULL 허용 | 3/197 결측 | 형식 불일치(`"April 3, 2005"` 전체 날짜 / `"2012"` 연도만 / `"15 April 2017"` 등) → 원문 그대로 저장 |
| retired | VARCHAR(30) | NULL 허용 | 194/197 결측 | 대부분 현역이므로 결측이 정상 |
| finisher | TEXT | NULL 허용 | 189/197 결측 | |
| embedding | VECTOR(1024) | NULL 허용 | - | RAG 검색용 임베딩 벡터. 차원(1024)은 이 프로젝트 표준 `core.matrix.vault_keymaker_secret_manager.EMBEDDING_DIM`(bge-m3)을 따른다 (`receiver_emails`/soccer 4개 테이블과 동일 컨벤션, 사용자 확인 완료) |

### 2.2 관계 요약 (Relationships)

- 이번 소스는 단일 CSV 파일이므로 FK로 연결되는 다른 테이블이 없다. `wrestlers`는 독립 테이블이다.
- 향후 `soccer-database.md`의 `title_acquisitions.competitor_name` 같은 자유 텍스트 컬럼과
  `wrestlers.name`을 애플리케이션 레벨에서 매칭할 가능성이 있으나, 이번 마이그레이션 범위에는
  **FK 제약을 포함하지 않는다** (이름 매칭은 정확도가 낮아 DB 레벨 FK로 강제하기 부적절).

---

## 3. 제약 사항 (Constraints)

1. **DB는 반드시 Docker 컨테이너로 실행할 것.** 호스트 직접 설치 금지.
2. DB 크리덴셜은 `.env`로 분리하고 `.gitignore`에 포함되어야 하며, `.env.example`도 함께 제공할 것.
   (이미 다른 도메인 작업으로 구성되어 있다면 재작업하지 말 것.)
3. **기존 alembic 환경을 임의로 재초기화하지 말 것.** 기존 `alembic.ini`/`env.py`가 있으면 그 구조를 따를 것.
4. `downgrade()`는 `upgrade()`의 정확한 역순으로 drop 할 것 (단일 테이블이므로 단순 `DROP TABLE wrestlers`).
5. pgvector extension 확인/생성(`CREATE EXTENSION IF NOT EXISTS vector;`)을 누락하지 말 것.
   이미 다른 마이그레이션에서 보장되어 있다면 중복 생성하지 말고 `IF NOT EXISTS`로 안전하게 처리할 것.
6. **아래는 CSV 데이터 품질 특성상 이번 작업에서 취한 가정(Assumption)이다. 마이그레이션 파일 상단
   주석에 반드시 동일하게 명시할 것:**
   - a. `height`, `weight`, `birth_date`, `debut`, `retired`는 원본 CSV에서 형식이 통일되어 있지 않아
     (단위 혼재, 연도만 있는 경우 등) INTEGER/DATE로 강제 변환하지 않고 **원문 그대로 VARCHAR/TEXT로
     저장**하기로 가정하였다. 추후 별도 정규화(ETL) 단계가 필요할 수 있다.
   - b. `ring_names`, `trainer` 컬럼은 스크래핑 과정에서 여러 값이 **구분자 없이 이어붙은 상태**로
     수집되었다(예: `"Josh ProhibitionLou MarconiWWE Performance Center"`). 이번 마이그레이션은
     원본 그대로 TEXT로 저장하며, 값 분리(delimiter 삽입)는 스키마 책임이 아니라 별도 데이터 정제
     스크립트의 책임으로 가정하였다.
   - c. `wikipedia_title`은 위키 문서가 없는 선수의 경우 `(no wiki page)` 같은 sentinel 문자열이
     들어갈 수 있어 **UNIQUE 제약을 적용하지 않기로** 가정하였다. 실제 문서 제목이 있는 행에 한해
     애플리케이션 레벨에서 중복을 체크할 것.
   - d. `resides` 컬럼은 현재 CSV 197행 전체가 결측(NULL)이다. 이번 마이그레이션은 **컬럼을
     유지하되 전량 NULL을 허용**하는 것으로 가정하였다. 데이터가 영구히 채워지지 않을 것으로
     판단되면 추후 컬럼 삭제 마이그레이션을 고려할 것 — 이번 작업 범위에서 임의로 삭제하지 않는다.
   - e. `embedding VECTOR(1024)` 컬럼은 CSV에는 존재하지 않으나, 이 프로젝트가 WWE 선수 정보
     기반 RAG 시스템 구축을 목적으로 한다는 배경 하에 **RAG 검색용 임베딩 저장 컬럼을 선제적으로
     추가**하기로 가정하였다. 차원(1024)은 이 프로젝트가 이미 사용 중인 표준
     `core.matrix.vault_keymaker_secret_manager.EMBEDDING_DIM`(bge-m3)을 따른다 — 애초 문서 초안의
     1536(OpenAI 가정)은 프로젝트 표준과 달라 사용자 확인 후 정정했다.
   - f. `height`/`weight`/`birth_date`는 스크래핑 과정에서 위키백과 각주(citation) 텍스트가
     값 뒤에 그대로 붙어버린 행이 일부 있었다(예: Josh Briggs weight `"290 lbJosh Briggs stats on
     WWE.com"`, Jacy Jayne height, Anthony Luke height, Nikkita Lyons birth_date). 원본 CSV 파일
     자체는 건드리지 않고, **적재 스크립트 단계에서만** 각주 텍스트를 제거했다(값 전체가 각주뿐인
     경우 NULL 처리: Anthony Luke height, Nikkita Lyons birth_date). 아울러 Hikuleo의 범위 표기
     height(`"6 ft 8 in (203 cm) – 6 ft 9 in (206 cm)"`, 40자)처럼 정상 데이터인데도 길이가 길어
     `VARCHAR(20)`/`VARCHAR(30)`을 초과하는 사례가 있어, height는 VARCHAR(50), weight는
     VARCHAR(30), birth_date는 VARCHAR(50)으로 여유 있게 조정했다(사용자 확인 완료).
   - g. CSV 197행에는 `name` 기준 완전 중복 행이 8명(총 18행: Anthony Luke, Anya Rune,
     Brogan Finlay, Bronco Nima, Creed Brothers, Hikuleo, Shiloh Hill, Tate Wilder) 존재했다.
     전수 대조 결과 각 중복 행은 모든 컬럼 값이 완전히 동일한 진짜 중복이라, 적재 후 이름당
     최소 `id`만 남기고 나머지 10행을 삭제했다(사용자 확인 완료). 최종 적재 건수는
     **187행**(197 - 10)이다. `name`에 UNIQUE 제약은 추가하지 않았다(현실적으로 동명이인
     가능성이 있어 스키마 레벨 강제는 이번 범위에서 보류).
7. CSV 데이터를 실제 적재하려면 `ring_names`/`trainer`의 구분자 없는 이어붙임 문제 때문에
   그대로 벌크 insert만 하고 후처리 정제는 별도 단계로 미룰 것. 마이그레이션 자체에서 데이터 정제
   로직을 수행하지 말 것 (스키마 생성과 데이터 정제는 관심사 분리, 단 3-f의 각주 오염 정제는 예외로
   적용했다).

---

## 4. 실행 계획 (Plan) — 순서대로 진행

1. 기존 `docker-compose.yml`/`.env`/pgvector extension이 이미 구성되어 있는지 확인
   (`soccer-database.md` 작업 이력 참고) → 있으면 0-1 섹션 생략, 없으면 신규 작성
2. 기존 alembic 설정 여부 확인, 접속 문자열이 컨테이너 DB를 가리키는지 점검 및 접속 테스트
3. `wwe_active_roster.csv`를 프로젝트 내 적절한 위치(예: `apps/kayfabe/_data/wwe_active_roster.csv`)에 배치
4. (모델 기반 프로젝트라면) `Wrestler` SQLAlchemy 모델 작성 — 2번 섹션 스키마와 3번 섹션 가정(a~e)을
   정확히 반영, `pgvector.sqlalchemy`의 `Vector` 타입 사용
5. `alembic revision --autogenerate -m "create wrestlers table"` 또는 수동 `op.create_table()` 마이그레이션 작성
6. 마이그레이션 파일 상단에 3번 섹션의 가정(a~e) 주석 추가
7. 생성된 마이그레이션의 컬럼/타입/제약이 2번 섹션과 일치하는지 diff 검토
8. `alembic upgrade head` 실행 (컨테이너 DB 대상)
9. `docker compose exec db psql -U <user> -d <db> -c '\d wrestlers'`로 컬럼/타입 전수 대조 검증
10. (선택) CSV → `wrestlers` 테이블 벌크 적재 스크립트 작성 및 실행, 197행 전체 적재 후
    완전 중복 행(3번 섹션 가정 g) 10행 제거 — 최종 `SELECT COUNT(*) FROM wrestlers;` = 187
11. `alembic downgrade -1` → `alembic upgrade head` 왕복 테스트
12. `docker compose down` 후 재기동하여 데이터/스키마 유지 여부 최종 확인

---

## 5. 검증 루프 (Verification Loop)

작업 완료 전 아래를 **반드시 자체 점검**하고, 실패 항목이 있으면 수정 후 재검증할 것.

- [ ] `wrestlers` 테이블이 생성되었는가?
- [ ] 컬럼명·타입이 2번 섹션 표와 정확히 일치하는가? (특히 `height`/`weight`/`birth_date`/`debut`가
      VARCHAR/TEXT로, INTEGER/DATE로 잘못 변환되지 않았는가?)
- [ ] PK(`id`)가 올바르게 설정되었는가?
- [ ] `wikipedia_title`에 UNIQUE 제약이 **잘못 추가되지 않았는가**? (3-c 가정 확인)
- [ ] `embedding` 컬럼이 `VECTOR(1536)` 타입으로 생성되었는가? (pgvector extension 미설치 시 실패하므로
      extension 활성화가 먼저 되었는지 함께 확인)
- [ ] `alembic upgrade head` / `alembic downgrade -1` 왕복 시 에러가 없는가?
- [ ] pgvector extension 확인/생성 구문이 누락 없이 포함되어 있는가? (중복 생성 에러 없이 `IF NOT EXISTS`로 안전 처리됐는가?)
- [ ] 마이그레이션 파일에 가정 사항(3번 섹션 a~e)이 주석으로 남아 있는가?
- [ ] DB가 호스트에 직접 설치되지 않고 **Docker 컨테이너**로만 실행되는가?
- [ ] DB 크리덴셜이 하드코딩되지 않고 `.env`로 분리되어 있으며, `.gitignore`에 포함되어 있는가?
- [ ] 컨테이너 재기동(`docker compose down` → `up`) 후에도 데이터가 유지되는가? (volume 검증)
- [ ] (데이터 적재를 수행한 경우) 중복 제거 후 `SELECT COUNT(*) FROM wrestlers;` 결과가 187과 일치하는가?

모든 항목이 체크된 후에만 작업 완료로 보고할 것. 실패 시 원인을 명시하고 재시도할 것.

---

## 6. 출력 형식 (Output)

작업 완료 후 다음을 요약하여 보고할 것:

1. 생성/수정된 파일 목록 (경로 포함, 모델 파일 / 마이그레이션 파일 / (선택) 시드 스크립트 포함)
2. `docker compose up -d` 기동 결과 및 healthcheck 상태 (기존 구성을 재사용한 경우 그 사실을 명시)
3. `alembic upgrade head` 실행 결과 로그 요약
4. 검증 루프(5번 섹션) 체크리스트 결과
5. **3번 섹션의 가정(a~e)이 실제 요구사항과 다를 가능성이 있는 부분** — 특히 다음 두 가지는
   반드시 사용자에게 재확인 요청할 것:
   - `embedding VECTOR(1536)` 차원이 실제 사용할 임베딩 모델과 일치하는지 (가정 e)
   - `ring_names`/`trainer`의 구분자 없는 이어붙임 데이터를 이후 어떻게 정제할 계획인지 (가정 b)