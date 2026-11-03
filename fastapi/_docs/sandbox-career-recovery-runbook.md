# 커리어 세이브 v3 — 복구 Runbook

> 대상: Phase 1(세이브 v3 · `matches` · `match_records_since`) 배포 이후의 복구.
> 도구: `apps/kayfabe/scripts/career_save_recovery.py`. 테스트:
> `apps/kayfabe/tests/scripts/test_career_save_recovery.py`.
> 2026-11-03 작성. **도구는 격리 PostgreSQL 16.2에서만 검증했다. 운영(Supabase 17.6)에서는
> 한 번도 실행하지 않았다.**

> 🔴 **이 문서의 운영 명령을 승인 없이 복사해 실행하지 않는다.** 운영 세이브를 바꾸는 모든
> 작업(§3·§4·§5)은 실행 직전에 §9의 승인 항목을 사용자에게 받는다. 승인은 한 번에 한
> career, 한 번의 실행에만 유효하다.

> 🔒 **도구는 지금 운영 DB에서 돌지 않는다 — 코드가 막는다.** 루프백이 아닌 호스트, 운영
> project ref가 들어 있는 DSN(원문은 공개 저장소에 두지 않고 SHA-256만 대조한다 · 앞 12자
> `5bd7917e6370` = 운영 백업 메타의 `project_ref_sha12`), `supabase`/`pooler`가 들어 있는 DSN,
> `supabase*` 역할이 있는 서버는 전부 거부한다(종료 코드 3). 운영에서 쓰려면 **가드를 여는 별도 커밋**을
> 리뷰·승인받아야 한다(§10-3). 의도한 마찰이다.

---

## 0. 판본과 구버전 호환 — 왜 이 문서가 필요한가

| 백엔드 | 코덱 | v1 | v2 | v3 |
|---|---|---|---|---|
| `8c965da`(Phase 0/0.5 · 현재 운영) | `SCHEMA_VERSION = 2` | 읽음(메모리에서 v2로) | 읽음 | **`CorruptSaveError` → 500** |
| `64dae6e`(Phase 1) | `SCHEMA_VERSION = 3` | 읽음 | 읽음 | 읽음 |

- **조회는 저장하지 않는다.** `view`·`log`·`matches`·`match`는 `repo.load`만 부른다. 세이브가
  v3로 바뀌는 것은 **첫 쓰기**(`_mutate` — 행동·진행·정산·다음 시즌)뿐이다.
- 그래서 시간선이 둘로 나뉜다. **첫 v3 쓰기 전**이면 코드 롤백만으로 끝난다(§1).
  **그 뒤**면 v3 행이 구버전에서 500이 되므로 데이터 조치가 함께 가야 한다(§2 → §3/§4).

---

## 1. 배포 직후 · 첫 v3 쓰기 전 — 코드만 롤백

**전제**: 운영 DB에 `version = 3`인 행이 0건이다. 추측하지 말고 읽어서 확인한다.

```bash
# 읽기 전용 추출(B단계 스크립트). 행마다 schema_version 이 나온다.
# 운영 세이브 전체가 담긴다 — /tmp(누구나 읽는 tmpfs)가 아니라 700 디렉터리에, 0600 으로.
umask 077
B=~/.local/share/kayfabe-production-backups
TS=$(date +%Y%m%d_%H%M)
ssh aws-ec2 'docker exec -i -w /app/fastapi -e PYTHONPATH=/app/fastapi/apps:/app/fastapi cloudjsanghoall-backend-1 python -' \
  < $B/extract_backup_phase1b_20261103_2315.py > $B/envelope_$TS.json 2> $B/envelope_$TS.err
cat $B/envelope_$TS.err       # ro default=on txn=on ... xid=None->None 이어야 한다
python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print([(r['id'],r['schema_version']) for r in d['careers']['rows']])" $B/envelope_$TS.json
```

**예상 출력**: `[(1, 1), (2, 2), (3, 1)]`처럼 **3이 하나도 없다**.

**절차**(3이 0건일 때만):

```bash
ssh aws-ec2 bash -s <<'EOF'
set -euo pipefail
cd /home/ec2-user/cloud.jsangho.all
git switch --detach 8c965da </dev/null
docker compose restart backend </dev/null      # build 불필요 — 의존성이 같다
echo STEP=done
EOF
```

**성공 기준**: `STEP=done` · `docker compose ps`에 backend `Up N seconds` · 컨테이너 안에서
`SCHEMA_VERSION == 2` · 위 추출을 다시 돌려 지문과 판본이 롤백 전과 같다.

**3이 하나라도 있으면 이 절은 쓰지 않는다** → §2.

---

## 2. 첫 v3 쓰기 이후 — repair-forward (우선 정책)

**지금 repair-forward 전용 운영 스크립트는 없다.** 이 절의 수단은 "고친 백엔드 코드를 다시
배포"뿐이다. 데이터를 손으로 고치는 범용 도구는 일부러 만들지 않았다.

1. **증상 확인** — `docker compose logs --tail 200 backend`에서 `CorruptSaveError`·500을 찾는다.
   응답 본문은 `세이브를 읽을 수 없습니다`다(라우터가 500으로 바꾼다).
2. **문제 career 식별** — 로그의 경로(`/api/sandbox/careers/{id}/…`)에서 id를 얻는다. 그리고
   읽기 전용 추출로 그 행의 `schema_version`·`world_jsonb_md5`·`match_records`를 본다.
3. **원본 보존** — 같은 추출이 곧 백업이다. 행의 `world` 전체(MatchRecord 포함)가 들어 있다.
   §7대로 SHA256SUMS를 만들고 검증한다. **보존하기 전에는 아무것도 바꾸지 않는다.**
4. **원인 재현** — 그 행의 `world`를 격리 PG에 넣고(테스트의 `_put_raw`와 같다) 현재 코드로
   `repo.load`를 부른다. 재현되면 코덱/도메인을 고치고 테스트를 추가한다.
5. **검증 → 배포** — `ho`에서 게이트(ruff·format·lint-imports·pytest, PG 테스트 포함) → CI 초록
   → `aws` 병합 → 배포 스킬. 배포 뒤 그 career의 GET이 200이고, 추출한 md5가 **GET 전후로
   같아야** 한다(조회는 저장하지 않는다).

**전환 기준** — 아래 중 하나면 §3 또는 §4로 간다.

- 원인을 몇 시간 안에 고칠 수 없고, 그동안 사용자가 쓰지 못하는 것이 더 큰 손실이다.
- 새 코드 자체를 되돌려야 한다(그러면 v3 행이 전부 500이다 → §3).
- 세이브 내용이 논리적으로 망가졌고, 망가지기 전 백업이 있다 → §4.

---

## 3. v3 → v2 비상 다운그레이드

> ⚠️ **MatchRecord 영구 삭제.** 다운그레이드는 `matches`(최대 104건)와 `match_records_since`를
> 지운다. 구버전이 읽을 수 있게 되는 것과 기록을 되살릴 수 있는 것은 **다르다** — 기록은
> 도구가 남기는 사전 이미지와 백업에만 남는다. 나중에 v3로 다시 올리면 `matches=[]`,
> `match_records_since=[그때 시즌, 주]`로 새로 시작한다.

**도구가 하는 일**(한 트랜잭션):

1. 대상 행 `SELECT … FOR UPDATE`(`lock_timeout` 5초 — 앱이 쥐고 있으면 기다리지 않고 멈춘다)
2. 행이 정확히 1개 · `user_id` 일치 · `version`이 정수 3 · MatchRecord 모양 · `match_records_since`
   모양(`null` 또는 `[int, int]`) 확인
3. 기대값 확인: `--expect-md5`(현재 `md5(world::text)`) · `--expect-matches` · `--expect-receipts`
4. 사전 이미지 파일 작성(행 전체 + 그 career 영수증 + 지문 · 0600 · 덮어쓰기 금지 · fsync)
5. `UPDATE … SET world = (world - 'matches' - 'match_records_since') || {"version": 2}
   WHERE id AND user_id AND md5` → 정확히 1행이고 결과가 계획과 같은지
6. `DELETE FROM sandbox_career_requests WHERE career_id = <그 career>` → 지운 id 집합이 미리 읽은
   집합과 같은지
7. 지문 비교: **다른 career와 그 영수증이 그대로인지** · 대상 행이 v2이고 두 칸이 없는지
8. COMMIT. 하나라도 어긋나면 rollback.

`updated_at`은 바꾸지 않는다(목록 순서가 흔들리지 않게).

**순서** — 새 백엔드가 도는 채로 내리면 다음 쓰기에 다시 v3가 된다. 그래서:

1. 사전 백업(§7) → 2. `docker compose stop backend` → 3. 다운그레이드 드라이런 → 4. 실행 →
5. `git switch --detach 8c965da` → 6. `docker compose start backend` → 7. 그 career GET 200.

**명령**(격리 PG 예시 — 운영은 §10-3 전까지 거부된다):

```bash
cd fastapi
export KAYFABE_RECOVERY_DATABASE_URL='postgresql://pgtest@127.0.0.1:55433/kayfabe_test'
# 1) 드라이런 — READ ONLY 트랜잭션. 아무것도 바꾸지 않는다.
uv run python apps/kayfabe/scripts/career_save_recovery.py downgrade-v3 --career-id 2 --user-id 6
```

**예상 출력** — 코드의 출력 키를 따라 손으로 쓴 **발췌 예시**다(실제 실행 결과를 붙인 것이
아니다. 실제 출력에는 `server`·`op`·`career_id`·`user_id`·`before.season_week`·
`planned.removed_keys`·`fingerprint_before`도 있다. 값은 대상마다 다르다):

```json
{"mode": "dry-run",
 "before": {"version": 3, "world_jsonb_md5": "…", "match_records": 40, "match_records_since": [1, 19]},
 "planned": {"version": 2, "match_records_lost": 40, "receipts_to_delete": [41, 42]},
 "execute_flags": "--execute --confirm downgrade-v3:career=2:user=6 --expect-md5 … --expect-matches 40 --expect-receipts 2 --pre-image-dir <DIR>"}
```

```bash
# 2) 실행 — 드라이런의 execute_flags 를 그대로 붙인다(<DIR> 만 채운다).
mkdir -m 700 -p ~/.local/share/kayfabe-production-backups/preimages
uv run python apps/kayfabe/scripts/career_save_recovery.py downgrade-v3 --career-id 2 --user-id 6 \
  --execute --confirm downgrade-v3:career=2:user=6 --expect-md5 <MD5> --expect-matches 40 \
  --expect-receipts 2 --pre-image-dir ~/.local/share/kayfabe-production-backups/preimages
```

**성공 기준**: 종료 코드 0 · `"committed": true` · `after.version == 2` · `receipts_deleted`가
드라이런의 목록과 같다 · `pre_image.sha256`이 파일과 일치(`sha256sum`) · 재실행하면 종료 코드 4
(`판본이 3 이 아니다`)로 멈춘다.

---

## 4. 선택 career 백업 복원

> ⚠️ **백업 이후의 진행은 사라진다.** 드라이런의 `planned.progress_after_backup_is_lost`가
> `true`면 현재 행이 백업과 다르다는 뜻이다. 지워질 시간선은 사전 이미지 파일에 남는다.
> 단 **사전 이미지는 그대로 `--backup`에 넣을 수 없다** — 모양이 `{"row": …, "receipts": …}`라
> 도구가 찾는 `{"rows": [...]}`가 아니다. 되살리려면 `row`를 `{"rows": [row]}`로 감싼 새 파일과
> 그 파일의 SHA256SUMS를 만들어 입력한다(이 경로는 테스트하지 않았다).
> **사용자에게 무엇을 잃는지 알린 뒤에만** 실행한다.

**도구가 하는 일**(한 트랜잭션):

1. 백업 파일을 SHA256SUMS로 검증 → 그 안에서 `--career-id`인 행이 **정확히 1개** · 백업의
   `user_id == --user-id` · 판본 1/2/3 · `world_jsonb_md5` 있음
2. 현재 행 `FOR UPDATE`(없어도 된다) · 있으면 `user_id` 일치
3. 기대값: `--expect-current-md5`(또는 행이 없으면 `--expect-absent`) · `--expect-receipts`
4. 사전 이미지 작성(현재 행 · 그 career 영수증 · 지문)
5. 원래 id로 upsert(`ON CONFLICT (id) … WHERE user_id 같음` — 소유자는 바꾸지 않는다).
   `updated_at`은 백업 값으로 되돌린다. `created_at`은 **행이 없을 때만** 백업 값으로 넣고,
   행이 있으면 그대로 둔다(같은 id의 생성 시각은 바뀌지 않으므로 값은 같다).
   **복원된 `md5(world::text)`가 백업의 서버 md5와 같아야** 한다(JSONB 무손실 검증)
6. 그 career의 영수증만 DELETE(지운 id 집합 = 미리 읽은 집합)
7. 시퀀스: **복원 id가 시퀀스 뒤에 있을 때만** `setval(…, max(id), true)`. 근거: 그 경우 다음
   `create`가 같은 id를 뽑아 PK 충돌이 난다. 그 외에는 건드리지 않는다(뒤로 감지 않는다)
8. 지문 비교로 다른 career 불변 확인 · 복원 후 `world`가 백업과 같은지 → COMMIT

여러 career를 한 번에 복원하는 옵션은 **없다**. career마다 따로 드라이런·승인·실행한다.

```bash
B=~/.local/share/kayfabe-production-backups
uv run python apps/kayfabe/scripts/career_save_recovery.py restore --career-id 2 --user-id 6 \
  --backup $B/kayfabe_production_phase1b_predeploy_careers_20261103_2315.json \
  --sha256sums $B/SHA256SUMS.phase1b_predeploy_20261103_2315
```

**예상 출력**(발췌): `"backup": {"version": 2, …}`, `"current": {"version": 3, …}`,
`"planned": {"receipts_to_delete": […], "backup_receipts_restored": 0, "sequence_setval": false,
"progress_after_backup_is_lost": true}`, 그리고 `execute_flags`.

실행은 §3처럼 `execute_flags`를 붙인다. **성공 기준**: 종료 코드 0 · `after.world_jsonb_md5 ==
backup.world_jsonb_md5` · `receipts_deleted` = 드라이런 목록 · 같은 플래그로 재실행하면 종료 코드 4
(현재 md5가 바뀌었으므로) · 새 드라이런 값으로 재실행하면 같은 결과(멱등).

---

## 5. 영수증(`sandbox_career_requests`)을 지우는 이유와 범위

- 영수증은 `Idempotency-Key` → **그때의 응답 본문**이다. 같은 키가 다시 오면 인터랙터는 세이브를
  건드리지 않고 저장된 응답을 그대로 돌려준다.
- 세이브를 과거로 돌리고 영수증을 남기면, 클라이언트가 재시도한 옛 키가 **지워진 시간선의 응답**을
  받고 **아무것도 적용되지 않는다**. 2026-11-03 격리 리허설에서 실측했다.
- 그래서 §3·§4는 **그 career의 영수증만** 같은 트랜잭션에서 지운다. 다른 career의 영수증은
  지문으로 불변을 확인한다(테스트: `…_drops_only_the_two_keys_and_this_careers_receipts`).
- **백업의 영수증은 복원하지 않는다.** 감사용이다(`…_requests_….json`의 `note`).
- 표 전체를 비우는 명령은 이 도구에 없다. 만들지 않는다.

---

## 6. MatchRecord 손실 요약

| 작업 | MatchRecord |
|---|---|
| §1 코드 롤백(첫 쓰기 전) | 해당 없음(0건) |
| §2 repair-forward | **보존** |
| §3 다운그레이드 | **영구 삭제** — 사전 이미지에만 남는다 |
| §4 v1/v2 백업 복원 | **삭제**(백업에 없던 것) — 사전 이미지에만 남는다 |
| §4 v3 백업 복원 | 백업 시점까지 |

---

## 7. 백업과 SHA256 검증

```bash
B=~/.local/share/kayfabe-production-backups     # 700 · 파일 600 · ext4(재부팅에 남는다)
cd $B && sha256sum -c SHA256SUMS.phase1b_predeploy_20261103_2315
stat -c '%a %n' . *                              # 700 / 600
```

**예상 출력**: 파일마다 `OK`. 하나라도 `FAILED`면 **그 백업으로 복원하지 않는다**(도구도
`백업 파일 SHA256 이 맞지 않는다`로 멈춘다).

새 백업은 B단계 추출 스크립트로 만든다(§1의 명령). 봉투를 세 파일(careers · requests ·
schema_audit)로 나누고, `sha256sum <파일들> > SHA256SUMS.<이름>`을 만든다. 기존 파일은
덮어쓰지 않는다. 추출 전후 지문(`… python - fp`)이 같아야 한다.

---

## 8. 운영 DB와 격리 DB 식별

| | 운영 | 격리(테스트) |
|---|---|---|
| 호스트 | `aws-0-ap-northeast-2.pooler.supabase.com:5432` | `127.0.0.1:55433` |
| 사용자명 | `postgres.<운영 ref>`(20자 · 원문은 서버 `.env`에만) | `pgtest` |
| 버전 | 17.6 | 16.2(pgserver 번들) |
| `supabase*` 역할 | 있다 | 없다 |
| DSN 출처 | 서버 `fastapi/.env` → Keymaker | `KAYFABE_RECOVERY_DATABASE_URL` / `KAYFABE_TEST_DATABASE_URL` |

```bash
uv run python apps/kayfabe/scripts/career_save_recovery.py fingerprint
```

출력의 `server.server_addr`·`database`·`version`으로 확인한다. 도구는 DSN·비밀번호를 출력하지
않는다. **로컬 `.env`에 운영 DSN을 넣지 않는다.**

격리 PG 띄우기(이 머신에는 도커가 없다):

```bash
PGB=~/.cache/uv/archive-v0/<hash>/pgserver/pginstall/bin     # find ~/.cache/uv -path '*pgserver/pginstall/bin'
export PGDATA=<scratch>/pgdata
$PGB/initdb -D $PGDATA -U pgtest --auth-local=trust --auth-host=trust --locale=C --encoding=UTF8
$PGB/pg_ctl -D $PGDATA -l <scratch>/pg.log -o "-p 55433 -h 127.0.0.1 -c unix_socket_directories=" start
$PGB/createdb -h 127.0.0.1 -p 55433 -U pgtest --encoding=UTF8 --template=template0 kayfabe_test
# 끝나면: $PGB/pg_ctl -D $PGDATA -m fast stop
```

---

## 9. 실행 전 승인 항목

운영 세이브를 바꾸기 전에 사용자에게 **아래를 전부 보여 주고** 승인을 받는다.

1. 작업 종류(§3/§4)와 대상 `career_id`·`user_id`(테스트 계정인지 실사용자인지)
2. 드라이런 출력 전체 — 특히 `before`/`current`의 판본·md5, 잃는 MatchRecord 수, 지울 영수증 id
3. 사전 백업 파일 이름과 `sha256sum -c` 결과
4. §4라면 `progress_after_backup_is_lost`와 잃는 진행(현재 시즌·주 → 백업 시즌·주)
5. 백엔드 정지 여부와 예상 중단 시간
6. 실행 직후 검증 계획(GET 200 · 지문 · 재실행 시 종료 코드 4)

---

## 10. 중단 조건과 실패 시 대응

### 10-1. 종료 코드

| 코드 | 뜻 | DB | 대응 |
|---|---|---|---|
| 0 | 드라이런 완료 / 커밋 완료 | 드라이런: 불변 · 실행: 변경됨 | 성공 기준 확인 |
| 2 | 사용법 오류(승인·기대값·디렉터리 누락) | **접속도 안 함** | 플래그 보완 |
| 3 | 가드 거부(격리 DB 아님) | **접속 안 함** 또는 즉시 끊음 | 대상 DB를 다시 확인. 운영이면 §10-3 |
| 4 | 사전 조건 불일치 | **불변** | 드라이런을 다시 돌려 무엇이 바뀌었는지 본다 |
| 5 | 실행 중 예외(잠금 시간 초과 포함) | **rollback 됨** | stderr의 예외 이름 확인. `LockNotAvailable`이면 앱이 그 행을 쓰는 중 — 백엔드를 멈추고 재시도 |

종료 코드 4·5에서도 사전 이미지 파일은 남을 수 있다 — 사전 이미지를 쓴 **뒤** 검증이 어긋나
rollback한 경우다. DB가 바뀌기 전 상태라 무해하다. 사전 이미지는 끝까지 쓰고 파일·디렉터리를
fsync한 뒤 **다시 읽어 SHA256을 대조**한다. 어긋나면 커밋하지 않는다(코드 5 · `OSError`).

### 10-2. 멈춰야 하는 순간

- 드라이런과 실행 사이에 md5·영수증 수가 바뀌었다(코드 4) → 사용자가 플레이 중이다. 백엔드 정지 후 드라이런부터.
- `user_id`가 예상과 다르다 → 대상을 잘못 짚었다. **절대 `--user-id`를 맞춰서 재시도하지 않는다.**
- SHA256 불일치 · 백업에 대상 행 0개/2개 이상 → 다른 백업을 찾는다.
- 복원 md5 불일치(`복원한 world md5 가 백업과 다르다`) → JSONB 왕복 문제. 도구가 rollback했다. 조사 전 재시도 금지.

### 10-3. 운영에서 실행하려면

현재 가드는 운영을 **무조건** 거부한다. 운영 실행은 다음을 모두 거친다.

1. 가드를 여는 변경(예: 승인된 ref 하나만 받는 명시적 플래그)을 별도 커밋으로 만들고 리뷰받는다.
2. DSN 전달 방법을 정한다 — `docker exec -e`는 프로세스 목록·셸 이력에 남는다. 컨테이너 안에서
   Keymaker로 읽는 경로가 필요하다(지금 도구에는 없다).
3. 운영 쓰기 경로(pooler 5432 위의 `FOR UPDATE`·`lock_timeout`·`setval` 권한)를 먼저 무해한
   대상으로 확인한다 — **아직 아무도 확인하지 않았다.**
4. §9 승인 → 실행 → 가드 변경을 되돌린다.

---

## 11. 검증 기록

| 항목 | 결과 |
|---|---|
| 격리 PG | PostgreSQL 16.2(pgserver 0.1.4 번들) · `127.0.0.1:55433` · UTF8 |
| 도구 테스트 | 51건(가드 24건은 DB 없이 · PG 27건 — 사전 이미지 부분 쓰기·쓰기 정지·재확인 불일치 3건 포함). 운영 ref 차단은 가짜 ref의 해시를 주입해 검증한다(진짜 ref는 커밋하지 않은 일회성 검사로 거부를 확인) |
| 구버전 코덱 | `8c965da` 트리를 `git archive`로 풀어 별도 프로세스에서 다운그레이드 결과 로드·왕복 동일 · v3는 거부 |
| 변이 시험 | 영수증 범위·판본 검사·드라이런 READ ONLY·행 수·백업 user·SHA256·운영 ref — 전부 테스트가 잡음. UPDATE의 md5 조건은 `FOR UPDATE` 뒤의 이중 방어라 정상 경로에서 드러나지 않음 |
| 운영(17.6 · pooler) | **미검증** |
| 이전 리허설 원본 | `~/.local/share/kayfabe-production-backups/rehearsal_20261103_isolated/`(SHA256SUMS 포함) |
