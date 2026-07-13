# Claude Code 작업 지시서: ERD 기반 pgvector 테이블 생성 (Alembic)

> 본 문서는 Karpathy의 "Harness 원칙"에 따라 작성되었습니다.
> 즉, (1) 명확한 목표(Goal) (2) 충분한 컨텍스트(Context) (3) 명시적 제약(Constraints)
> (4) 단계별 실행 계획(Plan) (5) 자체 검증 루프(Verification Loop) 를 모두 포함하여,
> 에이전트가 스스로 판단·검증·수정할 수 있도록 구성합니다.

---

## 0. 환경 정보 (Environment)

- OS: Ubuntu 26.04
- DB: PostgreSQL + pgvector extension
- Migration Tool: Alembic
- ORM: SQLAlchemy (Alembic 표준 구성 기준)

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

> 주의: ERD 원본에 `statdium_name`이라는 오탈자(stadium이 아님)가 그대로 표기되어 있다.
> **컬럼명은 오탈자를 포함하여 원본 그대로 생성**한다 (임의 수정 금지).

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
   단, pgvector extension이 설치되어 있는지 여부만 `CREATE EXTENSION IF NOT EXISTS vector;`로 확인/보장하는
   초기 마이그레이션(또는 기존 초기 마이그레이션)이 있는지 점검할 것. 없다면 최초 마이그레이션에
   extension 생성 구문을 포함할 것 (추후 vector 컬럼 확장을 대비).
6. 모든 VARCHAR 길이와 컬럼명은 위 스키마 정의를 **그대로** 따를 것 (오탈자 포함).
7. FK 제약 조건에 대한 `ON DELETE` 정책이 ERD에 명시되어 있지 않으므로,
   기본값(`NO ACTION`)을 사용하되, 이 부분은 가정임을 마이그레이션 파일 주석으로 명시할 것.

---

## 4. 실행 계획 (Plan) — 순서대로 진행

1. 프로젝트 루트에서 기존 alembic 설정 여부 확인 (`alembic.ini`, `alembic/env.py` 존재 여부)
2. DB 접속 정보(`sqlalchemy.url` 또는 `.env`)를 확인하여 실제 PostgreSQL + pgvector 인스턴스에
   연결 가능한지 점검
3. (모델 기반이라면) `Stadium`, `Team`, `Schedule`, `Player` SQLAlchemy 모델 작성
4. `alembic revision --autogenerate -m "create stadium, team, schedule, player tables"`
   또는 수동으로 `op.create_table()` 기반 마이그레이션 파일 작성
5. 생성된 마이그레이션 파일을 열어 **자동 생성된 타입/제약이 위 스키마와 일치하는지 diff 검토**
6. `alembic upgrade head` 실행
7. `\d stadium`, `\d team`, `\d schedule`, `\d player` (psql) 또는 동등한 방법으로
   실제 생성된 컬럼/타입/FK를 스키마 정의와 1:1 대조 검증
8. `alembic downgrade -1` 실행하여 롤백이 에러 없이 되는지 확인
9. 다시 `alembic upgrade head`로 원복

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

모든 항목이 체크된 후에만 작업 완료로 보고할 것. 실패 시 원인을 명시하고 재시도할 것.

---

## 6. 출력 형식 (Output)

작업 완료 후 다음을 요약하여 보고할 것:

1. 생성/수정된 파일 목록 (경로 포함)
2. `alembic upgrade head` 실행 결과 로그 요약
3. 검증 루프(5번 섹션) 체크리스트 결과
4. 발견된 이슈나 ERD와 다르게 해석/가정한 부분이 있다면 명시