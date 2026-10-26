# 커리어 샌드박스 — 마이그레이션 적용 절차와 영수증 정책

> 대상 리비전 둘: `f1a8d6c93b24`(세이브 표) · `c3d57e9b14af`(요청 영수증 표).
> 2026-10-22 감사 기준. **아직 개발·운영 어느 DB에도 적용되지 않았다** — 격리된 임시
> PostgreSQL에서만 적용·역전·재적용을 돌렸다(§8). 개발·운영 DB의 실제 상태는 **아직 읽어
> 보지 않았다** — 이 문서는 절차를 적을 뿐 적용을 승인하지 않는다.

---

## 1. 리비전 그래프

```
… → b9c4e7a21f30 (wwe_staff) → f1a8d6c93b24 (sandbox_careers) → c3d57e9b14af (sandbox_career_requests)
```

실측(`alembic/versions/*.py` 27개 전수 파싱):

| 항목 | 값 |
|---|---|
| 리비전 파일 | 27개 |
| 루트 | `07a11683a53b` (하나) |
| head | `c3d57e9b14af` (**하나** — 분기 없음) |
| 끊긴 부모 | 0건 |
| 루트→head 체인 길이 | 27 (선형 · 분기 없음) |
| 두 리비전의 부모 관계 | `c3d57e9b14af` → `f1a8d6c93b24` → `b9c4e7a21f30` |
| 체인 내 위치 | `b9c4e7a21f30`=25번째 · `f1a8d6c93b24`=26번째 · `c3d57e9b14af`=27번째(head) |

`b9c4e7a21f30`에 자식이 둘로 보이는 것은 grep의 착시다(자기 파일이 자기 revision 문자열을
갖는다). 실제 자식은 `f1a8d6c93b24` 하나다.

### 체인을 처음부터 재생하면 무슨 일이 생기나

전체 리비전 27개가 `op.create_table()`로 만드는 표는 **15개**뿐이다(나머지는 칼럼·인덱스·
제약 변경). 그 15개에 대해 알아야 할 것이 셋이다.

| 사실 | 내용 |
|---|---|
| 루트는 baseline이다 | `07a11683a53b_baseline_sync_migration_history_with_.py` — 당시 **live schema를 기준으로 뜬 diff** 중 상점 세 표만 남긴 것이다. 그 이전 스키마는 리비전으로 존재하지 않는다. |
| `users`를 만드는 리비전이 **없다** | 리비전 다섯이 `users.id`를 FK로 참조하는데(루트 baseline 포함) `users` 자체를 `create_table` 하는 리비전은 0개다. `users`는 `core/entities/user_model`의 ORM이고 `create_all`만이 만든다. |
| 옛 `career_*` 다섯 표를 과거 리비전이 만든다 | `e2b8c4f10593_career_simulator_tables.py`가 `career_runs`·`career_log_entries`·`career_rivalries`·`career_seen_events`·`career_trophies`를 만든다. 이 다섯은 **현재 ORM `Base.metadata`에 없다**(커리어 시뮬레이터는 2026-09-28에 지웠고 표만 남겼다). |

즉 **빈 DB에 루트부터 체인을 재생하면** ① 루트의 `point_ledger_entries`가 없는 `users.id`를
FK로 걸어 실패하고, ② 거기를 넘기더라도 지금 코드에 대응이 없는 `career_*` 다섯 표가
되살아난다. 이 둘이 §3-B(신규 DB)에서 `upgrade head` 단독 실행을 권하지 않는 근거다.

---

## 2. 먼저 알아야 하는 것 — `create_all`이 이 표들을 이미 만든다

**이것이 이 문서의 요점이다.** `init_db()`가 기동마다 `Base.metadata.create_all`을 돌리고
(`core/matrix/grid_oracle_database_manager.py:208`에 정의 · `create_all` 호출은 같은 파일
`:233`), `main.py`가 `kayfabe_router`를 import하는 경로에 `career_sandbox_orm`이 들어 있다.

### `create_all`의 대상 범위는 import 그래프가 정한다

`create_all`은 **그 시점까지 import된 ORM 모듈이 `Base.metadata`에 등록한 표 전부**를 만든다.
그래서 "몇 개를 만드느냐"는 어느 모듈을 import했는지에 달려 있다. 둘을 구분한다.

| 측정 | 표 수 | 의미 |
|---|---|---|
| **`import main` — 실제 기동 그래프** | **23개** | **운영에서 `init_db()`가 실제로 만드는 범위.** 이 수를 기준으로 삼는다. |
| `import kayfabe.adapter.inbound.api` — Kayfabe API 단독 | 17개 | 참고값일 뿐이다. 기동 경로가 아니다. |

실측(둘 다 `PYTHONPATH=apps uv run python`):

```
$ ... -c "from core.matrix.grid_oracle_database_manager import Base; import main; print(len(Base.metadata.tables))"
23
['championship_titles', 'contacts', 'player', 'ple_agent_predictions', 'ple_agent_reports',
 'ple_events', 'ple_knowledge_chunks', 'ple_matches', 'ple_prediction_retrievals',
 'ple_predictions', 'point_ledger_entries', 'receiver_emails', 'sandbox_career_requests',
 'sandbox_careers', 'schedule', 'shop_items', 'stadium', 'team', 'title_acquisitions',
 'user_shop_items', 'users', 'wrestlers', 'wwe_staff']

$ ... -c "... import kayfabe.adapter.inbound.api; print(len(Base.metadata.tables))"
17   # 위 목록에서 contacts·player·receiver_emails·schedule·stadium·team 이 빠진 것
```

두 측정 모두에 `sandbox_careers`·`sandbox_career_requests`가 들어 있고, `users`도 들어 있다
(§1 — `users`는 어느 리비전도 만들지 않으므로 이 경로가 유일한 생성자다).

### `create_all` 호출처는 둘이다

| 호출처 | 언제 | 대상 범위 |
|---|---|---|
| `core/matrix/grid_oracle_database_manager.py:233` — `init_db()` | 백엔드 기동마다 | 기동 그래프 23개 |
| `apps/heyman/adapter/outbound/repositories/email_repository.py:22` — `_ensure_email_table()` | heyman 메일 저장 경로가 처음 불릴 때(`:42`) | **23개보다 넓다** — 그 모듈이 `EmailOrm`(`notifications`)을 상단에서 import하므로 기동 그래프에 없던 표가 그때 추가된다 |

둘째 호출처를 빠뜨리면 "`init_db`만 끄면 `create_all`을 막을 수 있다"고 오판하게 된다.
**막지 못한다.**

따라서 **백엔드가 한 번이라도 기동된 DB에는 두 표가 이미 있다.** alembic이 돈 적이 없어도
그렇다. `create_all`은 `alembic_version`을 만들지 않으므로, 그런 DB는 "표는 최신인데 버전
기록은 비어 있는" 상태가 된다.

그 상태에서 `alembic upgrade head`를 돌리면 **루트부터 전부 적용하려 하고 첫 `CREATE TABLE`에서
`DuplicateTable`(42P07)로 죽는다.** 실패는 안전하지만(트랜잭션이 롤백된다) 절차를 모르면
"마이그레이션이 깨졌다"로 오진한다.

🔴 **거꾸로도 성립하지 않는다.** 표가 `create_all`로 만들어져 있다는 사실은 **과거 리비전이
실제로 실행됐다는 증거가 아니다.** 두 경로는 서로를 모르고, 같은 이름의 표를 만들었다는 것이
그 표에 리비전들이 더한 칼럼·인덱스·제약까지 들어 있다는 뜻은 아니다. 이 구분이 아래 `stamp`
경고의 전부다.

### DDL이 같다는 것은 실측했다

마이그레이션이 내는 DDL과 `create_all`이 내는 DDL을 DB 없이 뽑아 비교했다(alembic offline
`as_sql` + `CreateTable` 컴파일, 둘 다 postgresql 방언). **두 표·두 인덱스·고유 제약·FK·
`ON DELETE CASCADE`까지 동일하다.** 유일한 차이는 정수 기본값의 렌더링이다.

| | 마이그레이션 | ORM `create_all` |
|---|---|---|
| `season` / `week` | `INTEGER DEFAULT '1' NOT NULL` | `INTEGER DEFAULT 1 NOT NULL` |

Postgres가 `'1'`을 정수로 접으므로 `pg_attrdef`에 남는 값은 양쪽 다 `1`이다 — 다만 이건
**개발·운영 DB에서 확인하지 않았다**(§9). 확인 전까지는 §4의 점검 SQL이 내는 실제 값을 믿는다.

**이 동일성이 증명하는 범위는 좁다.** 증명된 것은 "두 리비전이 내는 DDL = ORM이 내는 DDL"
하나뿐이다. 나머지 25개 리비전에 대해서는 아무 말도 하지 않는다 — 그래서 이것만으로는
`stamp`를 정당화하지 못한다(§3-A3).

### 책임이 어떻게 갈려 있나 (혼동하지 않기 위해)

| | 표를 만든다 | `alembic_version`을 쓴다 | 언제 |
|---|---|---|---|
| `create_all` (`init_db`) | **그렇다** (없는 표만) | **아니다** | 백엔드 기동마다 |
| `alembic upgrade` | 그렇다 | 그렇다 | 사람이 부를 때만 |

**둘은 서로를 모른다.** `create_all`은 버전을 남기지 않으므로 alembic 입장에서는
"아무것도 적용되지 않은 DB"로 보이고, alembic이 만든 표는 `create_all`이 "이미 있다"고
건너뛴다. 지금 이 저장소는 **사실상 `create_all`이 표 생성을 소유**하고 있고 마이그레이션
파일은 그 옆에 쌓이는 기록이다.

🔴 **이 작업에서 그 소유를 바꾸지 않는다.** `create_all`을 떼고 alembic으로 넘기는 것은
sandbox 두 표의 문제가 아니라 **기동 그래프 23개 표 전체**의 문제이고(게다가 `users`를 만드는
리비전이 아예 없다 — §1), 되돌리기 어려운 변경이다.

---

## 3. 적용 절차 — 신규 DB와 기존 DB는 다른 문제다

**어느 쪽인지 모른 채 시작하지 않는다.** 먼저 §4의 읽기 전용 점검을 **전부** 돌려 출력을
확보한다. 그 출력 없이는 아래 어느 절차도 고르지 않는다.

### 3-0. `stamp`에 대해 먼저 알아야 할 것

이 절의 경고는 전부 이 성질 하나에서 나온다.

| 사실 | 결과 |
|---|---|
| `stamp`는 **스키마를 만들지 않는다.** `alembic_version` 한 줄을 쓸 뿐이다. | 틀리게 stamp하면 빠진 DDL이 **영구히 빠진 채** "적용됐다"고 기록된다. 이후 `upgrade`가 그 구간을 영원히 건너뛴다. |
| `stamp X`는 X 하나가 아니라 **루트부터 X까지의 조상 전부**가 적용됐다고 선언한다. | `stamp c3d57e9b14af`(head) = 리비전 **27개 전부** 적용 선언. `stamp b9c4e7a21f30` = **25개** 적용 선언. `stamp f1a8d6c93b24` = **26개** 적용 선언. |
| §4의 SQL은 **sandbox 두 표만** 본다. | 어떤 stamp도 §4만으로는 정당화되지 않는다. 선언하는 범위가 점검하는 범위보다 훨씬 넓다. |
| `alembic_version`이 없거나 비어 있다 ≠ 안전하다 | 그것은 "alembic이 돈 적 없다"는 뜻일 뿐이고, 스키마가 어떤 모양인지는 아무것도 말해 주지 않는다. `create_all`이 만든 표가 이미 가득할 수 있다. |

🔴 **DB의 리비전 기록과 실제 스키마가 어긋나면 자동으로 적용하지 않고 멈춘다.** 어긋남을
발견한 시점에서 이 문서의 절차는 끝이고, 그 다음은 DB 관리자의 판단이다.

---

### 3-A. 기존 DB (백엔드가 이미 기동된 적 있는 DB)

개발·운영 Supabase가 여기에 해당할 가능성이 높다. §4로 아래 셋 중 하나로 분류한다.

#### A-1. 두 표가 없고 `alembic_version`에 리비전이 **실제로 기록돼 있다**

alembic 기록이 실제로 존재하는 **유일하게 단순한** 경우다. 백엔드를 **기동하기 전에** 돌린다.

```bash
cd fastapi && uv run alembic upgrade head --sql   # 1) 먼저 눈으로 본다
cd fastapi && uv run alembic upgrade head         # 2) 확인한 뒤에만
```

기록이 `b9c4e7a21f30`이면 두 리비전만 적용된다. 그보다 앞쪽이면 그 사이 리비전도 함께
돌므로 `--sql` 출력을 끝까지 읽는다. 백엔드가 먼저 기동되면 `create_all`이 두 표를 만들어
이 경로가 A-3으로 바뀐다.

#### A-2. `sandbox_careers`만 있고 `sandbox_career_requests`가 없다

세이브 표가 먼저 `create_all`로 생긴 뒤 영수증 코드가 올라간 경우다.

- `alembic_version`이 `b9c4e7a21f30`이면 → **기록이 실제로 있으므로** A-1과 같다.
  `upgrade head`는 `f1a8d6c93b24`부터 돌려 하는데 `sandbox_careers`가 이미 있으므로
  `DuplicateTable`로 실패한다. 이 충돌을 `stamp f1a8d6c93b24`로 넘기려면 아래 A-3과 같은
  판단이 필요하다.
- `alembic_version`이 없거나 비어 있으면 → A-3과 같다.

#### A-3. 표가 있는데 `alembic_version`이 없거나 비어 있다

**표 전체를 `create_all`이 만든 DB다.** 이 저장소의 현실이 이것이다. 선택은 둘이다.

1. **alembic을 건드리지 않는다.** 두 표가 없으면 백엔드 기동이 `create_all`로 만든다.
   가장 적은 동작이고, **이 저장소가 지금까지 실제로 해 온 방식이다.** 리비전 파일은 기록으로
   남고 `alembic_version`은 계속 비어 있다.
2. **alembic 기록을 맞춘다** — `stamp` 뒤 `upgrade`.

🔴 **2번은 이 작업에서 권하지 않는다.** §3-0대로 `stamp`는 조상 전부를 선언하는데, §4가 보는
것은 sandbox 두 표뿐이다. 나머지 표(`ple_*`·`shop_*`·`wwe_staff`·`title_*`·`knowledge_*`…)가
정말 그 리비전들의 모양인지 — 25~27개 리비전이 더한 칼럼·인덱스·제약이 전부 들어 있는지 —
확인하는 것은 **전혀 다른 크기의 작업**이고 아직 하지 않았다. 그 대조 없이 stamp하면 빠진
DDL이 영구히 빠진다.

**§2에서 실측한 DDL 동일성은 여기를 구해 주지 않는다.** 그것이 덮는 범위는 두 리비전뿐이고
(§2), stamp가 선언하는 범위는 체인 전체다.

> **미확정.** "기존 DB의 alembic 기록을 어떻게 현실과 맞출 것인가"는 전체 스키마 대조가
> 선행 과제이고, sandbox 기능 출시와 **독립된 결정**이다. 이 문서는 그 절차를 정하지 않는다.
> 진행하려면 DB 관리자가 전체 대조 결과를 보고 판단한다.

---

### 3-B. 완전히 신규인 DB (표가 하나도 없는 DB)

🔴 **`alembic upgrade head` 단독 실행을 권하지 않는다.** 근거는 §1에서 실측한 둘이다.

1. **`users` FK 대상이 없다.** 루트 baseline `07a11683a53b`의 `point_ledger_entries`가
   `users.id`를 FK로 거는데, `users`를 만드는 리비전이 **27개 중 0개**다. 빈 DB에서는 그
   시점에 실패한다. (두 sandbox 리비전도 같은 FK를 건다 — §4-⑦이 이것을 본다.)
2. **지금 코드에 없는 표가 되살아난다.** `e2b8c4f10593`이 옛 `career_*` 다섯 표를 만든다.
   이 다섯은 현재 ORM `Base.metadata` 23개에 **없다.** 체인을 재생하면 대응 코드가 없는
   표가 신규 DB에 생긴다.

표를 만드는 쪽은 현실적으로 `create_all`뿐이다(기동 그래프 23개 — `users` 포함).

> **미확정.** 신규 DB에서 `create_all`로 만든 스키마와 alembic 리비전 기록을 **어떻게
> 일치시킬지는 검증된 방법이 없다.** 자연스러운 후보는 "`create_all` 뒤 `stamp head`"지만,
> 그것은 §3-0대로 리비전 27개 전부가 적용됐다고 선언하는 것이고 — 그중에는 `create_all`이
> 결코 만들지 않는 `career_*` 다섯 표를 만드는 리비전도 들어 있다. 즉 그 선언은 **사실이
> 아니다.** 이 조합은 격리 PG에서도 검증하지 않았다(§8은 두 리비전의 적용·역전·재적용만
> 돌렸다). **DB 관리자가 판단할 사항으로 남긴다.**

---

## 4. 사전 점검 SQL (읽기 전용)

적용 전에 **전부** 돌리고 출력을 남긴다. 읽기만 하므로 운영에도 안전하지만, 운영 접속은
이 작업의 범위가 아니다. **이 점검은 §3의 분류를 위한 것이지, 그 자체로 `stamp`를
정당화하지 않는다**(§3-0).

```sql
-- ① alembic 기록. 행이 없으면 "alembic 미적용" 이다.
--    표가 없다는 뜻도, 안전하다는 뜻도 아니다 — create_all 이 만든 표가 가득할 수 있다.
SELECT version_num FROM alembic_version;
-- 표 자체가 없으면: SELECT to_regclass('public.alembic_version');  → NULL

-- ② 두 표의 존재
SELECT to_regclass('public.sandbox_careers')         AS careers,
       to_regclass('public.sandbox_career_requests') AS requests;

-- ③ 칼럼·타입·기본값 (기대값은 §2)
SELECT table_name, column_name, data_type, is_nullable, column_default
  FROM information_schema.columns
 WHERE table_name IN ('sandbox_careers', 'sandbox_career_requests')
 ORDER BY table_name, ordinal_position;

-- ④ 제약. uq_sandbox_career_requests_scope 가 있어야 한다.
--    **`'…'::regclass` 로 쓰지 않는다** — 표가 없으면 캐스트 자체가 에러를 내서,
--    "없다" 를 확인하려는 질의가 죽는다. 이름으로 조인한다.
SELECT c.relname AS tbl, con.conname, con.contype, pg_get_constraintdef(con.oid)
  FROM pg_constraint con
  JOIN pg_class c ON c.oid = con.conrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public'
   AND c.relname IN ('sandbox_careers', 'sandbox_career_requests')
 ORDER BY c.relname, con.conname;

-- ⑤ 인덱스. **여섯 줄**이 기대된다 — 표마다 셋이다:
--    sandbox_careers         = PK + ix_user_id + ix_user_updated
--    sandbox_career_requests = PK + 고유 제약의 인덱스 + ix_career_id
SELECT tablename, indexname, indexdef
  FROM pg_indexes
 WHERE tablename IN ('sandbox_careers', 'sandbox_career_requests')
 ORDER BY tablename, indexname;

-- ⑥ 데이터가 있나. 있으면 downgrade 는 세이브를 지운다.
--    ②가 두 표의 존재를 확인한 **뒤에만** 돌린다 — 없는 표를 세면 에러다.
SELECT (SELECT count(*) FROM sandbox_careers)         AS careers,
       (SELECT count(*) FROM sandbox_career_requests) AS receipts;

-- ⑦ FK 대상이 있나. users 가 없으면 두 리비전 다 실패한다.
--    users 를 만드는 리비전은 없다(§1) — create_all 만이 만든다.
SELECT to_regclass('public.users') AS users;

-- ⑧ 신규 DB인지 기존 DB인지 가른다(§3). 표가 하나도 없으면 전부 NULL 이다.
--    career_* 다섯은 과거 리비전 e2b8c4f10593 이 만드는 표이고 현재 ORM 에는 없다 —
--    여기 값이 있으면 그 리비전이 돌았거나 옛 코드가 create_all 로 만든 것이다.
SELECT to_regclass('public.users')          AS users,
       to_regclass('public.shop_items')     AS shop_items,
       to_regclass('public.career_runs')    AS career_runs,
       to_regclass('public.career_trophies') AS career_trophies;
```

### 기대되는 ④·⑤ 출력

```
sandbox_careers            PRIMARY KEY (id)
sandbox_careers            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
sandbox_career_requests    PRIMARY KEY (id)
sandbox_career_requests    UNIQUE (user_id, career_id, request_id)   ← uq_sandbox_career_requests_scope
sandbox_career_requests    FOREIGN KEY (user_id)   REFERENCES users(id) ON DELETE CASCADE
sandbox_career_requests    FOREIGN KEY (career_id) REFERENCES sandbox_careers(id) ON DELETE CASCADE

ix_sandbox_careers_user_id            (user_id)
ix_sandbox_careers_user_updated       (user_id, updated_at DESC)
ix_sandbox_career_requests_career_id  (career_id, id)
```

---

## 5. Supabase 접속 — pooler, 포트 5432

`alembic/env.py`가 `DATABASE_URL`을 psycopg(동기)로 바꿔 쓴다. Supabase에 대고 돌릴 때
걸리는 함정 셋은 루트 `CLAUDE.md`에 적힌 것과 같다.

| 함정 | 내용 |
|---|---|
| `db.<ref>.supabase.co` | **IPv6 전용**이다. IPv4만 있는 호스트에서 `Network is unreachable`. |
| 포트 6543 (transaction) | prepared statement를 못 써서 **alembic·SQLAlchemy가 깨진다.** |
| 사용자명 | pooler는 `postgres.<ref>` 형식이다 — 그냥 `postgres`가 아니다. |

```
postgresql+psycopg://postgres.<ref>:<PW>@aws-0-<region>.pooler.supabase.com:5432/postgres
```

필요한 권한: `public` 스키마에 `CREATE`, `users`에 `REFERENCES`, `alembic_version`에 쓰기.
Supabase의 `postgres` 역할은 셋을 다 갖는다.

`env.py`는 `.env`를 `override=True`로 읽으므로 **셸의 `DATABASE_URL`은 `.env`에 눌린다.**
개발 DB로 돌리려면 `.env`의 값을 개발용으로 바꿔야 하고, **운영 URL을 로컬 `.env`에 넣지
않는다**(로컬 스크립트가 운영을 건드린다).

---

## 6. 되돌리기의 성질

🔴 **`downgrade`는 데이터를 지운다.** 아래는 성질 설명이지 실행 권고가 아니다. 돌리기 전에
§4-⑥으로 행 수를 세고, 남길 데이터가 있는지 먼저 판단한다. 보존 검토 없이 돌리지 않는다.

**이 두 리비전의 `downgrade`는 각자 자기 표만 떨어뜨린다.** 옛 `career_*` 다섯 표는 어느 쪽도
건드리지 않는다 — 두 리비전의 `upgrade`/`downgrade`에 등장하는 대상은 `sandbox_careers`·
`sandbox_career_requests`와 그 인덱스뿐이다(실측: `op.*` 호출 전수).

- `c3d57e9b14af` 되돌리기 = **영수증을 버린다.** 그 순간 전송 중이던 요청의 재시도가
  다시 적용될 수 있다. 조용한 동작이 아니다.
- `f1a8d6c93b24` 되돌리기 = **세이브를 지운다.** `sandbox_career_requests`가 FK CASCADE로
  매달려 있으므로 순서를 거꾸로 하면 실패한다(alembic이 알아서 역순으로 돈다).
- 되돌린 뒤 백엔드를 기동하면 `create_all`이 두 표를 **다시 만든다**(빈 표로). 되돌리기가
  유지되지 않는다는 뜻이다.

### 체인 전체를 돌리는 것은 다른 이야기다

위의 "`career_*`를 건드리지 않는다"는 **이 두 리비전에만** 해당한다. 리비전 체인을 처음부터
재생하면(신규 DB의 `upgrade head`) `e2b8c4f10593`이 `career_*` 다섯 표를 **만든다**. 반대로
체인 전체를 `downgrade base`로 내리면 그 다섯 표를 **떨어뜨린다** — 현재 ORM에 없는 표이므로
`create_all`이 되살리지도 않는다. 둘을 섞어 읽지 않는다(§1 · §3-B).

---

## 7. 영수증 보존 정책과 실측 크기

### 정리 순서는 `id` 기준이다

`SandboxCareerPgRepository._prune_receipts`가 쓰기와 **같은 트랜잭션에서** 그 커리어의
영수증을 최신 `RECEIPT_KEEP`(=8)개로 자른다. 크론도 배치도 없다.

`created_at`이 아니라 `id`로 자르는 것이 중요하다 — `func.now()`는 **트랜잭션 시각**이라 한
트랜잭션 안의 여러 행이 같은 값을 갖고, 정렬이 흔들린다. `id`는 시퀀스라 단조 증가다.

### 성공한 요청만 적는다

`_mutate`가 도메인 호출이 성공한 뒤에만 `RequestReceipt`를 만들어 `save`에 넘긴다. 도메인이
`ValueError`를 내면 세이브도 영수증도 쓰이지 않는다 — 그래서 **실패한 요청의 키는 재사용
가능**하고, 입력을 고쳐 같은 키로 보내면 지문이 달라 409로 잡힌다. 테스트가 둘 다 고정한다
(`test_a_failed_request_leaves_the_key_reusable` ·
`test_a_failed_request_can_be_corrected_under_the_same_key`).

### 실측 크기 (DB 없이 — JSON 텍스트 바이트)

영수증의 `response`에 들어가는 것은 `asdict(CareerViewDto)`다. 진짜 도메인으로 한 커리어를
**은퇴까지(12시즌 · 성공한 쓰기 2,591건)** 굴리고 매 쓰기의 직렬화 길이를 셌다.

| | 영수증 `response` | 세이브 `world` |
|---|---|---|
| 평균 | **19,621 B** | 200,362 B |
| 중앙 | 20,141 B | — |
| 최소 | 5,745 B | — |
| p95 | 27,033 B | — |
| 최대 | **29,320 B** | 277,982 B |

- 커리어당 영수증 최악 크기 = 8 × 29,320 B ≈ **235 KB.** 같은 시점 세이브(278 KB)의 0.8배다.
- 영수증이 커지는 이유는 `recent_log`(12줄 상한)가 아니라 **시즌 요약·관계·로스터**가
  시즌마다 늘기 때문이다. 상한 8개가 있으므로 **커리어당 총량은 유한하다.**
- **이 수치는 JSON 텍스트 바이트이고 디스크 크기가 아니다.** 두 칸 다 8 KB를 넘으므로
  JSONB가 TOAST로 나가 pglz 압축을 받는다 — 실제 저장량은 이보다 작다. **디스크 크기는
  아직 측정하지 않았다**(§9 BLOCKED) — §8의 격리 PG 실행에서도 재지 않았다.

> 마이그레이션 독스트링의 "세이브 JSON이 수십 배로 부푼다"는 **상한이 없을 때**의 이야기다
> (영수증을 세이브 안에 넣는 설계를 반대하는 근거였다). 상한 8개가 걸린 지금 실측 비율은
> 0.8–2.2배다. 주장 자체는 유지되지만 숫자는 이쪽이 정확하다.

### 한계 — 영수증이 잘린 뒤의 같은 키는 새 요청이다

같은 커리어에 쓰기가 **8번 더 성공한 뒤** 도착한 재시도는 중복으로 식별되지 않고 한 번 더
적용된다. 재시도 창은 요청 하나(타임아웃 수십 초)이고 그 사이 같은 커리어로 여덟 번 더 쓰는
경로가 없으므로 감수한 트레이드오프다. **API 계약에 적혀 있어야 하는 성질이므로**
`career_sandbox_router`의 `Idempotency-Key` 헤더 설명에 함께 넣었다(OpenAPI로 나간다).

---

## 8. PostgreSQL 통합 테스트 — 격리 PG에서 12건 전부 통과

`apps/kayfabe/tests/adapter/outbound/pg/test_sandbox_career_pg_repository.py` (12건).
**DSN을 주지 않으면 전부 skip**이므로 기존 `pytest apps`에 섞여도 초록을 깨지 않는다.

```bash
cd fastapi
KAYFABE_TEST_DATABASE_URL='postgresql+psycopg://user:pw@127.0.0.1:5432/kayfabe_test' \
  PYTHONPATH=apps uv run pytest \
  apps/kayfabe/tests/adapter/outbound/pg/test_sandbox_career_pg_repository.py -v
```

| # | 무엇을 보나 | 테스트 |
|---|---|---|
| 1 | `id DESC LIMIT 8` 정리의 실제 SQL | `test_receipts_are_pruned_to_the_newest_eight` |
| 1b | 상한이 커리어당으로 갈리나 | `test_pruning_is_scoped_to_one_career` |
| 2 | `FOR UPDATE`가 둘째 읽기를 **실제로 멈추나** | `test_a_second_locked_read_waits_for_the_first_transaction` |
| 2b | 읽기 전용은 줄 서지 않나 | `test_a_plain_read_does_not_wait` |
| 3 | 동시 삽입에서 고유 제약이 하나만 통과시키나 | `test_concurrent_identical_receipts_let_exactly_one_through` |
| 4 | 충돌 뒤 롤백 + 영수증 재조회 | `test_a_duplicate_receipt_raises_and_rolls_the_save_back` |
| 5 | 같은 키·같은 payload → 응답 재생 | `test_the_same_key_replays_the_stored_response` |
| 6 | 같은 키·다른 payload → 충돌 | `test_the_same_key_with_a_different_payload_conflicts` |
| 7 | 영수증과 세이브 변경의 원자성 | `test_a_duplicate_receipt_raises_and_rolls_the_save_back` (거울 칼럼 + JSON 대조) |
| 7b | 거부된 쓰기는 아무것도 남기지 않나 | `test_a_rejected_write_stores_nothing` |
| 8 | `ON DELETE CASCADE` (커리어 · 유저) | `test_deleting_a_career_takes_its_receipts` · `test_deleting_the_user_takes_careers_and_receipts` |
| — | 소유권이 쿼리에 있나 | `test_a_stranger_sees_nothing_and_cannot_write` |

**안전 장치**: 전용 환경변수만 읽고(`DATABASE_URL`은 보지 않는다), 그 둘이 같으면
`UsageError`로 거부한다. 표는 `checkfirst=True`로만 만들고 `DROP`하지 않으며, 정리는
**이 테스트가 만든 유저 행 하나**를 지우는 것뿐이다(CASCADE가 나머지를 데려간다).

### 실행 결과 (2026-10-22 · 격리 PostgreSQL)

| 항목 | 결과 |
|---|---|
| 실행 대상 | 위 12건 |
| 통과 | **12건** |
| 실패·에러 | 0건 |
| 발견된 코드 결함 | 0건 |

처음 1건이 빨갰지만 **코드 결함이 아니라 기대값 문제**였다 — 영수증 칸이 `JSONB`라
`asdict`가 낸 `tuple`(`roster`·`pending`)이 `list`로 돌아온다. 테스트를 JSON 왕복 비교로
고쳤다(파일 내 주석 참조). 가짜 저장소에는 없던 차이라 PG 없이는 드러나지 않았다.

**스키마는 마이그레이션이 만든 것을 썼다.** 즉 이 12건은 `create_all`이 아니라 두 리비전이
낸 DDL 위에서 통과했다.

### 같은 격리 PG에서 함께 확인한 것

| 항목 | 결과 |
|---|---|
| 두 리비전 적용 (`upgrade`) | 통과 |
| 역전 (`downgrade`) | 통과 |
| 재적용 (`upgrade` 재실행) | 통과 |
| 적용 결과 ↔ ORM 스키마 카탈로그 대조 | 일치 |

🔴 **이 검증의 범위는 두 리비전뿐이다.** 격리 PG에서 돌린 것은 `b9c4e7a21f30` 이후의 두
리비전이지 **체인 27개 전체가 아니다.** 신규 DB에서의 전체 재생(§3-B)과 기존 DB의 전체
스키마 대조(§3-A3)는 이것으로 덮이지 않는다.

---

## 9. 상태 — 해결된 것과 아직 막힌 것

### 해결됨 (2026-10-22)

| 항목 | 어떻게 |
|---|---|
| PostgreSQL 테스트 12건 실행 | 격리 PG에서 **12건 전부 통과**, 결함 0 (§8) |
| 두 리비전의 적용·역전·재적용 | 같은 격리 PG에서 통과 (§8) |
| 마이그레이션 스키마 ↔ ORM 스키마 대조 | 카탈로그 비교 일치 (§8) |
| `create_all` 대상 표 수 | 기동 그래프 **23개**로 실측 (§2) |
| `create_all` 호출처 전수 | `init_db()` + heyman `_ensure_email_table()` 둘 (§2) |
| 리비전 그래프 · 루트의 성격 · `users` 생성자 부재 · `career_*` 다섯의 출처 | 리비전 27개 AST 전수 파싱 (§1) |

### 아직 막혀 있음 (BLOCKED)

| 항목 | 막힌 이유 |
|---|---|
| **개발 Supabase에 실제 적용** | 접속 정보가 없다. **아직 하지 않았다.** |
| **운영 DB에 실제 적용** | 범위 밖이다. **아직 하지 않았다.** |
| 개발·운영 DB의 읽기 전용 점검(§4) 실행 | 접속 정보가 없다 — §3의 분류를 못 한 상태다 |
| `alembic current` / `upgrade --sql` 실행 | `env.py`가 `.env`의 `DATABASE_URL`을 요구하고 로컬은 빈 값이다 |
| `--autogenerate` 로 드리프트 확인 | **하지 않았다.** DB 연결이 필요하다. §2의 정적 DDL 비교와 §8의 카탈로그 대조는 **두 표만** 덮으므로 대체가 아니다 |
| 체인 27개 전체 재생 검증 | 격리 PG에서도 돌리지 않았다 (§8) |
| 기존 DB의 전체 스키마 ↔ 리비전 대조 | 착수하지 않았다 — §3-A3의 선행 과제 |
| `DEFAULT '1'` → `1` 접힘 | 대상 DB의 `pg_attrdef`를 봐야 한다 |
| **JSONB 디스크 크기** | **측정하지 않았다.** `pg_column_size`가 필요하고 §7 수치는 JSON 텍스트 바이트다 |

---

## 관련 문서

| 문서 | 역할 |
|---|---|
| 루트 `CLAUDE.md` | Supabase pooler 규칙 · 로컬 더미 모드 |
| `_docs/db-rules.md` | DB 일반 규칙 |
| `_docs/ENTITY_RULE.md` | 엔티티 필수 규칙 |
