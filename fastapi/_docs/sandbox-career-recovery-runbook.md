# 커리어 세이브 v3 — 복구 Runbook

> 대상: 세이브 v3(`matches` · `match_records_since`) 전환 전후의 운영 장애.
> 도구: `apps/kayfabe/scripts/career_save_recovery.py`(격리 DB 전용) ·
> `apps/kayfabe/tests/scripts/career_save_audit.py`(오프라인 감사).
> 문서 검증: `apps/kayfabe/tests/scripts/test_career_recovery_runbook.py`.
> 2026-11-03 작성 · 2026-11-06 운영 기준 갱신. **복구 도구는 격리 PostgreSQL 16.2·17.6에서만
> 검증했다. 운영(Supabase 17.6)에서는 한 번도 실행하지 않았다.**

> 🛑 **`8c965da` 로 되돌리지 않는다.** Manager API 인증(`72437d6`)이 사라져
> `/api/manager/*` — 연락처 조회, 전체 삭제, 텔레그램 발송 — 가 인터넷에 **인증 없이**
> 다시 열린다. v3 세이브도 전부 500이 된다. 이 문서의 모든 되돌리기는 §1의 가드를 지난다.
> `rollback-8c965da` 이미지 태그도 쓰지 않는다.

> 🔴 **이 문서의 운영 명령을 승인 없이 복사해 실행하지 않는다.** 운영 세이브나 운영 프로세스를
> 바꾸는 모든 작업은 실행 직전에 §9의 승인 항목을 사용자에게 받는다. 승인은 한 번에 한
> 대상, 한 번의 실행에만 유효하다.

> 🔒 **복구 도구는 운영 DB에서 돌지 않는다 — 코드가 막는다.** 루프백이 아닌 호스트, 운영
> project ref가 들어 있는 DSN(원문은 공개 저장소에 두지 않고 SHA-256만 대조한다 · 앞 12자
> `5bd7917e6370` = 운영 백업 메타의 `project_ref_sha12`), `supabase`/`pooler`가 들어 있는 DSN,
> `supabase*` 역할이 있는 서버는 전부 거부한다(종료 코드 3). 그래서 **지금 운영 세이브를 고칠
> 수단은 없다.** 운영에서 쓰려면 가드를 여는 별도 커밋을 리뷰·승인받아야 한다(§10-3).

---

## 0. 지금 상태와 호환 — 무엇이 어디까지 안전한가

### 0-1. 운영 기준(2026-11-06)

| 항목 | 값 | 근거 |
|---|---|---|
| 운영 백엔드 | `e2fc44b` | `origin/aws` 일치 · 공개 API 동작 일치. **EC2 HEAD는 직접 못 봤다**(SSH 타임아웃 — IP 변경 추정) |
| Manager API 인증 | 적용됨(`72437d6` 포함) | 익명 `GET /api/manager/receiver/list` |
| Feature Flag | **운영에 없다** · 작업트리에만 있다 | 미커밋 |
| DB | Supabase PostgreSQL 17.6 | §8 |
| Alembic | `c3d57e9b14af` | `phase1c` 지문 파일 |
| DB 지문 | `2b2b33def0cb457d` | `phase1c` 지문 파일(2026-11-05) |
| 세이브 | 3행 · v1 2 · v2 1 · v3 0 · MatchRecord 0 · 영수증 17 | `phase1c` 백업 감사 |
| 최신 백업 | `phase1c`(2026-11-05 21:53 KST) | §7 |

🔴 **이 표는 쓰는 순간부터 낡는다.** 운영 작업 전에는 아래를 읽어서 다시 맞춘다(읽기 전용).

```bash
ssh aws-ec2 'cd /home/ec2-user/cloud.jsangho.all && git rev-parse --short HEAD && git status --short | wc -l'
curl -s https://api.jsangho.cloud/healthz
curl -s -o /dev/null -w '%{http_code}\n' https://api.jsangho.cloud/api/manager/receiver/list   # 401 이어야 한다
```

**예상 출력**: `e2fc44b` · `0` · `"ok": true` · `401`. Manager가 401이 아니면 **다른 작업을 멈추고** 그것부터 본다.

### 0-2. 되돌릴 수 있는 커밋

코드는 저장소 bind mount다 — 커밋을 옮기고 재시작하면 코드가 바뀐다. 이미지는 그대로다.

| 커밋 | 코덱 | v3 읽기 | Manager 인증 | 쓰기 차단 | 복구 도구 | 되돌리기 |
|---|---|---|---|---|---|---|
| `8c965da` | 2 | **500** | **없음** | 없음 | 없음 | 🛑 금지 |
| `e4702c0` | 3 | 됨 | **없음** | 없음 | 있음 | 🛑 금지 |
| `79ae8d8` | 3 | 됨 | **없음** | 없음 | 있음 | 🛑 금지 |
| `e2fc44b` | 3 | 됨 | 있음 | **없음** | 있음 | ✅ 가장 낮은 허용선. 쓰기가 전부 열린다 |
| `7a3de79` | 3 | 됨 | 있음 | 있음 | 있음 | ✅ Flag 배포 후의 기준 |

`7a3de79` 은 Flag 커밋이고 **경기 기록 타입 검사는 다음 커밋 `1cbb205` 부터 있다.** 쓰기를 막은 채
타입 검사까지 유지하려면 `1cbb205` 이상으로 되돌린다.

격리 PG에서 세 코드를 같은 행에 돌린 실측(2026-11-06 · 상세·로그·쓰기):

| 행 | `8c965da` | `e2fc44b` | Flag 닫힘 |
|---|---|---|---|
| v1 · v2 | 200 · 쓰기가 **v2** 로 저장 | 200 · 쓰기가 **v3** 로 저장 | 조회 200 · 쓰기 503 · 판본 유지 |
| 정상 v3 | **상세·로그·쓰기 전부 500** | 200 | 조회 200 · 쓰기 503 |
| 경기 기록 API | **404**(경로 없음) | 200 | 200 |
| 목록(`GET /`) | 200 — 세이브를 열지 않는다 | 200 | 200 |

**첫 v3 쓰기 뒤에 구버전 백엔드는 호환되지 않는다.** v3 행의 소유자는 "커리어를 불러오지
못했습니다"만 보고 원인을 알 수 없다. 데이터가 지워지지는 않는다.

### 0-3. Feature Flag `CAREER_V3_WRITES_ENABLED`

| 상태 | 쓰기 | 조회 | v1·v2 행 |
|---|---|---|---|
| **Flag 배포 전**(지금) | 전부 열림 — **행동 한 번이 곧 첫 v3 쓰기** | 됨 | 쓰는 순간 v3 |
| 배포 후 · 닫힘(기본) | 생성·행동·진행·사건·결산·다음 시즌 전부 503 | 됨 | 그대로 보존 |
| 배포 후 · 열림 | 전부 열림 | 됨 | 쓰는 순간 v3 |

- 정확히 `true` 일 때만 열린다. `TRUE`·`1`·공백이 붙은 값은 닫힘이다.
- 서버 `fastapi/.env` 에 키가 없으므로 **배포 즉시 공개 화면의 커리어 쓰기가 멈춘다.** 의도다.
- 🔴 **닫을 때는 줄을 지우지 말고 `false` 를 쓴다.** compose `env_file` 은 컨테이너를 만들 때
  한 번 읽힌다. 그때 `true` 였다면 줄을 지워도 `load_dotenv(override=True)` 가 덮어쓸 값이
  없어 **`true` 가 살아남는다**(실측). 명시적 `false` 는 덮어쓴다.
- `e2fc44b` 로 되돌리면 게이트 자체가 사라져 **`.env` 값과 무관하게 쓰기가 열린다.**
  쓰기를 막은 채 되돌릴 방법은 없다 — 막아야 하면 Flag가 있는 커밋에 머문다.

닫기(`.env` 만 바꾼다 · 재시작 필요 · 이미지 재빌드 없음):

```bash
ssh aws-ec2 bash -s <<'EOF'
set -euo pipefail
cd /home/ec2-user/cloud.jsangho.all
if grep -q '^CAREER_V3_WRITES_ENABLED=' fastapi/.env; then
  sed -i 's/^CAREER_V3_WRITES_ENABLED=.*/CAREER_V3_WRITES_ENABLED=false/' fastapi/.env
else
  printf '\nCAREER_V3_WRITES_ENABLED=false\n' >> fastapi/.env
fi
docker compose restart backend </dev/null
grep -c '^CAREER_V3_WRITES_ENABLED=false$' fastapi/.env
EOF
```

확인(읽기 전용 · **Flag가 있는 커밋에서만 돈다**). 인증된 쓰기로 시험하지 않는다 — 실제로
열려 있으면 그 시험이 첫 v3 쓰기가 된다.

```bash
ssh aws-ec2 bash -s <<'EOF'
cd /home/ec2-user/cloud.jsangho.all
docker compose exec -T backend sh -c 'cd /app/fastapi && PYTHONPATH=apps:. python -c "
from core.matrix.vault_keymaker_secret_manager import get_keymaker
get_keymaker().load_env()
from kayfabe.dependencies.career_sandbox_provider import career_v3_writes_enabled
print(\"v3_writes_enabled=\", career_v3_writes_enabled())"' </dev/null
docker inspect -f '{{.State.StartedAt}}' cloudjsanghoall-backend-1
stat -c '%y' fastapi/.env
EOF
```

**성공 기준**: `v3_writes_enabled= False` · 컨테이너 시작 시각이 `.env` 수정 시각보다 늦다.
늦지 않으면 돌고 있는 프로세스는 옛 값을 쥐고 있다.

### 0-4. 기존 v1·v2 데이터 보호 정책

- **일괄 변환을 하지 않는다.** 행은 자기가 쓰일 때만 v3가 된다. 그 변환은 메모리에서 시작해
  저장으로 끝나고 되돌리는 코드 경로가 없다.
- 닫힌 동안 v1·v2 행은 판본째 보존된다(`md5(world::text)`·`updated_at` 불변 실측).
- **열기 전에 그 시점의 백업을 새로 뜬다.** `phase1c` 뒤의 진행은 `phase1c`에 없다.
- 첫 쓰기는 사용자가 고른 **한 커리어**로 한다. 실사용자 행으로 시험하지 않는다.
- v2 행을 위한 별도 저장 경로를 만들지 않는다 — 기록을 버리는 두 번째 저장 경로가 된다.

### 0-5. 시간선

- **조회는 저장하지 않는다.** `view`·`log`·`matches`·`match`는 `repo.load`만 부른다.
- 세이브가 v3로 바뀌는 것은 **첫 쓰기**뿐이다. 그 전이면 코드만 움직여도 된다(§1).
- **그 뒤에는 앞으로 고친다**(§2). 쓰기를 멈춘 채 고친 코드를 올리고, 데이터는 건드리지 않는다.

상황별 판단은 §12.

---

## 1. 코드 되돌리기

**전제**

1. §0-1 재확인을 통과했다.
2. 되돌릴 대상이 §0-2의 ✅다. **v3 행이 있으면 대상은 `e2fc44b` 이상만 가능하다.**
3. Flag가 있는 커밋에서 내려오면 쓰기가 열린다는 것을 승인받았다(§0-3).

v3 행 수는 추측하지 말고 읽는다.

```bash
# 읽기 전용 추출. 운영 세이브 전체가 담긴다 — 700 디렉터리에 0600 으로.
# phase1b 이전 스크립트는 쓰지 않는다(ref 원문이 들어 있다).
umask 077
B=~/.local/share/kayfabe-production-backups
TS=$(date +%Y%m%d_%H%M)
ssh aws-ec2 'docker exec -i -w /app/fastapi -e PYTHONPATH=/app/fastapi/apps:/app/fastapi cloudjsanghoall-backend-1 python -' \
  < $B/extract_backup_phase1c_20261105_2153.py > $B/envelope_$TS.json 2> $B/envelope_$TS.err
cat $B/envelope_$TS.err       # read only · xid=None->None 이어야 한다
python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print([(r['id'],r['schema_version']) for r in d['careers']['rows']])" $B/envelope_$TS.json
```

**예상 출력**: 지금은 `[(1, 1), (2, 2), (3, 1)]`. 지문만 볼 때는 맨 끝을 `python - fp` 로 바꾼다.

**절차** — 가드가 인증 커밋 없는 대상을 거부한다. **가드를 빼고 실행하지 않는다.**

```bash
ssh aws-ec2 "TARGET=<승인된_SHA> bash -s" <<'EOF'
set -euo pipefail
cd /home/ec2-user/cloud.jsangho.all
git fetch origin </dev/null
# >>> rollback-guard
MANAGER_AUTH_COMMIT=72437d6
if ! git cat-file -e "${TARGET}^{commit}" 2>/dev/null; then
  echo "REFUSED: 없는 커밋 ${TARGET}"; exit 1
fi
if ! git merge-base --is-ancestor "$MANAGER_AUTH_COMMIT" "$TARGET"; then
  echo "REFUSED: ${TARGET} 에는 Manager API 인증이 없다 — /api/manager/* 가 공개된다"; exit 1
fi
# <<< rollback-guard
git switch --detach "$TARGET" </dev/null
docker compose restart backend </dev/null
echo STEP=done
EOF
```

**성공 기준**: `STEP=done` · 재시작 직후 몇 초의 502가 지나면 `/healthz` 가 `"ok": true` ·
Manager 익명 요청 401 · 지문이 되돌리기 전과 같다.

Alembic은 돌리지 않는다 — `8c965da` 이후 마이그레이션 파일 변경이 없다(`versions/` 27개 동일).

---

## 2. Repair-forward — 첫 v3 쓰기 이후의 기본 경로

**원칙은 넷이다.** 쓰기를 먼저 멈춘다. 지우지 않는다. 고친 코드를 **앞으로** 올린다. 다시 여는
것은 별도 승인이다. 이 절에 운영 DB에 쓰는 단계는 **없다.** 데이터를 손으로 고치는 범용
도구는 일부러 만들지 않았다.

| 단계 | 할 일 | 멈출 조건 |
|---|---|---|
| R0 | 쓰기를 닫고 확인한다(§0-3) | 확인이 `False` 가 아니면 다음으로 가지 않는다 |
| R1 | 원본을 보존한다 | SHA256 불일치·추출 stderr 이상 |
| R2 | 손상을 찾는다(오프라인) | 입력을 못 읽음(종료 코드 2) |
| R3 | 원인을 분류한다 | 분류 불가면 사용자에게 올린다 |
| R4 | 격리 PG에서 재현하고 고친다 | 재현 안 되면 배포하지 않는다 |
| R5 | 고친 코드를 올린다 — **Flag는 닫힌 채** | CI 실패·병합 충돌 |
| R6 | 읽기 경로를 확인한다 | 조회가 행을 바꾸면 즉시 중단 |
| R7 | 무결성을 확인한다 | 지문·md5 불일치 |
| R8 | 별도 승인으로 쓰기를 재개한다 | 승인 없으면 닫힌 채 둔다 |

**Flag가 아직 배포되지 않았다면 R0이 불가능하다.** 쓰기를 막는 유일한 수단은
`docker compose stop backend` 이고 조회도 함께 죽는다. Flag 배포가 먼저인 이유다.

**R1 — 보존.** §1의 추출을 그대로 돌린다. 봉투 파일이 곧 백업이고 MatchRecord 전체가 들어 있다.

```bash
B=~/.local/share/kayfabe-production-backups
cd $B && sha256sum envelope_$TS.json > SHA256SUMS.envelope_$TS && chmod 600 SHA256SUMS.envelope_$TS
```

**R2 — 탐지.** API만으로는 모자란다. 세 층을 전부 본다.

| 손상 | 상세·로그 | `/matches` | 쓰기가 열려 있으면 | 찾는 법 |
|---|---|---|---|---|
| 구조·타입(칸 누락·배열 길이·판본·`rating` 문자열·`id` null) | **500** | 500 | 500 · 저장 안 됨 | 로그의 `세이브를 되살릴 수 없다` · 감사 `DECODE_FAILED` |
| 논리(승자 뒤집힘·중복·유실·순서·전적 불일치) | 200 | 200 | 🔴 200 · 손상째 저장 | **감사뿐이다** |

표는 하드닝 커밋 기준이다. **`e2fc44b` 에서는 타입 손상이 상세 200 · `/matches` 500 ·
쓰기 200(손상째 저장)이다**(2026-11-06 실측) — 그 커밋으로 내려가면 이 방어도 사라진다.

```bash
cd fastapi
PYTHONPATH=apps:. uv run python apps/kayfabe/tests/scripts/career_save_audit.py ~/.local/share/kayfabe-production-backups/envelope_$TS.json
ssh aws-ec2 'cd /home/ec2-user/cloud.jsangho.all && docker compose logs --tail 500 backend </dev/null' | grep -E 'CorruptSave|되살릴|저장 거부|ResponseValidationError'
```

감사기는 파일만 읽고 DB 드라이버를 import하지 않는다. 종료 코드 `0` 정상 · `1` 손상 · `2` 못 읽음.
출력은 career id·판본·문제 코드·경기 id뿐이다.

**R3 — 분류.**

| 분류 | 판단 | 수단 | 금지 |
|---|---|---|---|
| F1 코드 결함 | 데이터는 맞고 코드가 잘못 읽는다 | 코드 수정 | 데이터 변경 |
| F2 규칙적 오염 | 같은 코드 버그가 같은 모양을 남겼고 원래 값을 **계산으로** 알 수 있다 | `SCHEMA_VERSION = 4` + `_UPGRADES[3]` — 읽을 때 메모리에서 고치고 다음 저장이 새 판본으로 쓴다 | 원래 값을 추정해서 채우기 |
| F3 정보 유실 | 값이 없고 다시 만들 수 없다 | 세이브에 칸을 더해 깨진 기록을 **원문째 격리**하고 화면에 "기록 손상"을 표시 | 깨진 기록을 빼고 저장 |

**MatchRecord는 다시 만들 수 없다** — 그 주의 인기도·컨디션이 세이브에 남지 않는다. 그래서:

- F2는 v3 코드로 되돌릴 수 없는 새 경계를 만든다. v4로 저장된 행은 `e2fc44b` 에서 500이다.
  **검증이 끝날 때까지 닫아 둔다**는 뜻이다.
- F3의 관대한 읽기는 **닫힌 동안만** 안전하다. 지금 `dump` 에는 못 읽은 기록을 담을 칸이
  없어서, 열면 다음 저장이 그 기록을 조용히 없앤다. 격리 칸 없이 관대한 읽기만 배포하지 않는다.
- F2·F3는 설계만 있다. 구현된 것은 없다.

**R4 — 재현.** 그 행의 `world`를 격리 PG에 넣고(테스트의 `_put_raw`) 현재 코드로 `repo.load`
를 부른다. 재현되면 코덱·도메인을 고치고 **그 행의 모양을 테스트로 남긴다.** 운영 사본은
커밋하지 않는다.

**R5 — 배포 순서.**

1. `ho`에서 게이트(ruff·format·lint-imports·`pytest apps`, PG 테스트 포함) → 푸시 → CI 초록
2. `git merge-tree --write-tree aws ho` 로 충돌을 먼저 본다 → `aws` 병합 → 푸시
3. 서버 `git merge --ff-only origin/aws` → `docker compose restart backend` (**backend만**)
4. **`fastapi/.env` 는 건드리지 않는다.** Flag는 `false` 그대로다
5. 스키마가 안 바뀌었으면 Alembic을 돌리지 않는다. 이미지도 재빌드하지 않는다

배포 스킬(`.claude/skills/deploy/SKILL.md`)을 그대로 쓰면 Alembic·auth 재시작이 함께 간다.
이 절차에서는 위 줄만 쓴다.

**R6 — 읽기 경로 보호.** 세이브 하나의 고장은 그 커리어에서 멈춘다 — 목록은 세이브를 열지
않아 200이고 다른 커리어도 정상이다(실측). 확인: 영향받은 커리어의 상세·로그·`/matches` 가
200이고, **GET 전후로 지문이 같다.** `/healthz` 는 앱과 DB만 본다 — 세이브 손상은 안 보인다.

**R7 — 무결성.**

1. §1의 추출을 다시 돌려 감사 종료 코드 `0`
2. R1 봉투와 비교: 영향 없는 행의 `world_jsonb_md5` 동일 · 행 수·영수증 수 동일 · v3 행 수 동일
3. F2면 메모리 판본만 올라갔으므로 저장된 `world_jsonb_md5` 는 **그대로여야** 한다

**R8 — 쓰기 재개(별도 승인).** R0~R7 결과를 보여 주고 승인을 받는다.

1. 새 백업(§7)을 뜨고 `sha256sum -c` 를 통과시킨다
2. `.env` 를 `true` 로 → `docker compose restart backend` → §0-3 확인에서 `True`
3. 승인받은 **커리어 하나**로 쓰기 한 번 → 추출·감사 → 그 행만 바뀌었는지 비교
4. 이상이 있으면 즉시 §0-3으로 닫는다. 이상이 없으면 사용자에게 공개 재개를 묻는다

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

**이 절은 기본 경로가 아니다.** `e2fc44b` 이상은 v3를 읽으므로 코드가 정상이면 다운그레이드할
이유가 없다. 필요한 경우는 하나뿐이다 — v3 코덱 자체를 쓸 수 없어 코덱 2 백엔드로 가야 할 때.

🛑 **그런 코덱 2 커밋은 지금 없다.** 있는 것은 `8c965da` 뿐이고 Manager 인증이 없다. 먼저
`8c965da` 에 `heyman/adapter/inbound/api/__init__.py` 의 인증을 얹은 핫픽스를 만들어 리뷰하고
시험해야 한다(`git merge-tree` 시험에서 충돌은 `fastapi/CLAUDE.md`·`www/package.json` 둘뿐이었다
· 핫픽스는 빌드·시험하지 않았다). **운영에서는 도구도 가드에 막힌다**(§10-3).

**순서** — 새 백엔드가 도는 채로 내리면 다음 쓰기에 다시 v3가 된다. 그래서:

1. 사전 백업(§7) → 2. `docker compose stop backend` → 3. 다운그레이드 드라이런 → 4. 실행 →
5. 인증이 있는 코덱 2 핫픽스로 §1(가드 통과 필수) → 6. `docker compose start backend` →
7. 그 career GET 200.

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
  --backup $B/kayfabe_production_phase1c_predeploy_careers_20261105_2153.json \
  --sha256sums $B/SHA256SUMS.phase1c_predeploy_20261105_2153
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
| §1 코드 되돌리기 | 보존 — `e2fc44b` 이상으로만 간다 |
| §2 repair-forward | **보존** — 운영 쓰기 단계가 없다 |
| §3 다운그레이드 | **영구 삭제** — 사전 이미지에만 남는다 |
| §4 v1/v2 백업 복원 | **삭제**(백업에 없던 것) — 사전 이미지에만 남는다 |
| §4 v3 백업 복원 | 백업 시점까지 |

---

## 7. 백업과 SHA256 검증

```bash
B=~/.local/share/kayfabe-production-backups     # 700 · 파일 600 · ext4(재부팅에 남는다)
cd $B && sha256sum -c SHA256SUMS.phase1c_predeploy_20261105_2153
stat -c '%a %n' . *                              # 700 / 600
```

**예상 출력**: 파일마다 `OK`. 하나라도 `FAILED`면 **그 백업으로 복원하지 않는다**(도구도
`백업 파일 SHA256 이 맞지 않는다`로 멈춘다).

새 백업은 §1의 추출로 만든다. 봉투 파일 하나가 그대로 백업이고 `restore --backup` 이 읽는다.
`sha256sum` 은 §2 R1대로 만든다. 기존 파일은 덮어쓰지 않는다. 추출 전후 지문(`… python - fp`)이
같아야 한다.

**`phase1c` 는 첫 v3 쓰기 전 상태다.** 그 뒤의 진행과 MatchRecord는 들어 있지 않다. 쓰기를 열기
직전과 첫 쓰기 직후에 새로 뜬다. 백업은 이 PC 한 곳에만 있고 암호화하지 않았다.

---

## 8. 운영 DB와 격리 DB 식별

| | 운영 | 격리(테스트) |
|---|---|---|
| 호스트 | `aws-0-ap-northeast-2.pooler.supabase.com:5432` | `127.0.0.1:55433` |
| 사용자명 | `postgres.<운영 ref>`(20자 · 원문은 서버 `.env`에만) | `pgtest` |
| 버전 | 17.6 | 16.2(pgserver 번들) · 17.6(`postgres:17.6` 컨테이너) |
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

1. 작업 종류(§1/§2 R8/§3/§4)와 대상 `career_id`·`user_id`(테스트 계정인지 실사용자인지) ·
   되돌리기라면 대상 커밋과 §1 가드 통과 · 쓰기가 열리는지 여부
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
| 코드 호환표(2026-11-06) | `8c965da`·`e2fc44b`·작업트리(Flag 닫힘·열림)를 격리 PG 16.2에서 같은 17개 세이브(v1·v2·정상 v3·손상 14종)에 돌렸다. 시드는 골든과 엔진 출력 — 운영 데이터 아님. 루프백만 있는 네트워크 네임스페이스 |
| 명령 리허설(2026-11-06) | 같은 격리 환경에서 이 문서의 명령으로 `fingerprint` · `phase1c` 3행 `restore`(md5 전부 일치) · v3→v2 `downgrade-v3` 실행 · 재실행 종료 코드 4 · 운영 형식 DSN 종료 코드 3. 사본은 끝나고 지웠다 |
| 오프라인 감사 | `phase1c`: 3행 · v1 2 · v2 1 · 기록 0 · 손상 0. 골든 궤적(기록 40건)과 시드 40개 오탐 0. 손상 22종 전부 탐지 |
| 문서 검증 | 가드·`.env` 닫기 명령·CLI 인자를 이 문서에서 꺼내 실행한다(`test_career_recovery_runbook.py`). 판본표는 전체 git 이력이 있을 때만 검증된다 |
| 운영 커밋 대조 | `origin/aws` = `e2fc44b` · 익명 Manager 401 · `/healthz` 정상. **EC2의 `git rev-parse` 는 SSH 타임아웃으로 못 봤다** |
| 미검증 | `7a3de79` 운영 동작 · §0-3 닫기·확인 명령의 서버 실행 · 봉투 파일을 `restore --backup` 으로 쓰는 경로 · 컨테이너 없는 추출 · 인증 핫픽스 · **운영 pooler 위의 복구 도구 실행** |
| PostgreSQL 17.6(2026-11-06) | `postgres:17.6`(`17.6-2.pgdg13+1`) 격리 컨테이너 — internal 네트워크 · 포트 공개 없음 · `.env` 없는 사본. 같은 사본·같은 명령으로 16.2와 대조: 테스트 701건 결과 전부 동일, 고정 입력의 `md5(world::text)`·`pg_column_size` 전부 동일. 구버전 코덱 테스트는 실제 `git archive` 출력을 돌려주는 대역을 썼다 |
| 이전 리허설 원본 | `~/.local/share/kayfabe-production-backups/rehearsal_20261103_isolated/`(SHA256SUMS 포함) |

---

## 12. 시나리오별 복구 판단

표의 ✅는 지금 실행할 수 있는 것, ⛔는 할 수 없거나 해서는 안 되는 것이다. **운영 데이터를 바꾸는
수단은 모든 시나리오에서 ⛔다** — 복구 도구가 운영을 거부한다.

### A. Flag 배포 직후 · v3 쓰기 0건

- ✅ Flag 커밋 유지: 조회 정상 · 쓰기 503 · v1·v2 보존
- ✅ `e2fc44b` 로 되돌리기(§1) — 데이터 영향 없음. **단 쓰기가 다시 열리고 첫 v3 쓰기를 막을 수 없다**
- ✅ `phase1c` 는 유효하다(지문이 `2b2b33def0cb457d` 면 그 뒤 변화 없음)
- ⛔ `8c965da`: 데이터는 괜찮지만 Manager 인증이 사라진다
- ⛔ 조치 없이 `.env` 를 `true` 로: 별도 승인 사항이다(§2 R8)

### B. 첫 v3 쓰기 직후

- ✅ 즉시 닫기(§0-3) · 조회 유지 · §2로 앞으로 고치기
- ✅ `e2fc44b` 이상으로 되돌리기 — v3를 읽는다. 쓰기가 열리는 것은 승인 사항
- ⛔ `8c965da`: 그 행이 상세·로그·쓰기 500 + Manager 인증 소실
- ⛔ v3를 v2로 내리기: 도구가 운영을 거부한다(종료 코드 3). 가능해져도 그 경기의 MatchRecord가 사라진다
- ⛔ `phase1c` 로 복원: 도구가 거부한다. 가능해져도 백업 뒤의 진행이 사라진다

### C. 일부 커리어만 v3인 혼합 상태

- ✅ 닫아 둔 채 그대로 운영: 판본이 섞여도 세 판본 모두 조회 200 · 쓰기 503
- ✅ §2 — 복구 단위는 **행 하나**다. 한 행의 문제가 다른 행으로 번지지 않는다
- ⛔ 일괄 처리: 여러 career를 한 번에 바꾸는 수단은 없고 만들지 않는다
- ⛔ `8c965da`: v1·v2는 쓰기가 돌고 v3만 500이 되어 **사용자마다 다른 시간선**이 생긴다.
  v1이 v2로 오르는 쓰기가 계속되므로 다시 올라와도 그 사이 상태가 섞인다
- ⛔ `e2fc44b` 로 내려가 닫힌 효과 기대: 게이트가 없다 — 남은 행도 쓰이는 순간 v3가 된다

### D. MatchRecord 데이터 손상

먼저 닫는다. **논리 손상은 쓰기가 열려 있으면 손상째 계속 저장된다.** 타입 손상도 하드닝
커밋 이전 코드에서는 그렇다.

- ✅ 원본 보존 → 오프라인 감사 → F1/F2/F3 분류(§2 R1~R3)
- ✅ 손상 범위 확인 — 구조·타입 손상은 그 커리어만 500, 나머지는 정상. 기록 한 건이 깨져도
  커리어 전체를 못 연다(부분 표시 없음 — 의도)
- ✅ `career_save_rejected`(500) 는 저장이 거부된 것이다 — 세이브는 마지막 정상 상태 그대로다
- ✅ F1 코드 수정 배포 · F2 읽기 업그레이드 · F3 격리 칸 추가 — **F2·F3는 설계뿐**이라 구현과 검증이 먼저다
- ⛔ MatchRecord 재계산: 그 주의 상태가 남지 않아 시드로도 만들 수 없다
- ⛔ 깨진 기록을 빼고 저장: 지우는 일이다. 격리 칸 없는 관대한 읽기도 같은 결과가 된다(§2 R3)
- ⛔ 운영 행 직접 UPDATE: 금지 · 도구 없음
- ⛔ `/healthz` 나 API 200으로 "정상" 판단: 논리 손상은 어디에도 안 보인다

### E. 백엔드 장애로 읽기까지 실패

**세이브 문제로 단정하지 않는다.** 데이터 조치는 원인이 세이브로 확인되기 전에 하지 않는다.

| 관찰 | 뜻 | 할 일 |
|---|---|---|
| `/healthz` 응답 없음 · 502 | 프로세스가 안 떴다 | `docker compose logs --tail 200 backend` · 기동 오류면 §1 |
| `"ok": false` · `db` 가 `ok` 아님 | DB·pooler 문제 | Supabase 상태 확인 · 앱을 되돌려도 안 낫는다 |
| `/healthz` 정상 · 목록 200 · 상세 500 | 세이브·코덱 문제 | 행 하나면 D · 전체면 코덱 회귀 → §1 |
| 익명 401만 정상 | 판단 근거 아님 | 401은 인증 전에 나가고 DB를 안 탄다 |

- ✅ §1로 `e2fc44b` 이상으로 되돌리기 — 코드 문제면 이것으로 충분하고 데이터는 그대로다
- ✅ 로컬 백업 조회·감사(백엔드가 없어도 된다)
- ⛔ 지금 시점 추출: §1 추출은 **백엔드 컨테이너가 떠 있어야** 돈다. 컨테이너 없이 뜨는 경로는 시험하지 않았다
- ⛔ 복구 도구로 복원: 읽기 장애의 답이 아니고 도구가 거부한다
- ⛔ `8c965da`: 장애 중의 급한 손이 가장 쉽게 치는 명령이다. v3가 있으면 고쳐지지도 않는다
- ⛔ `rollback-8c965da` 태그: 코드는 마운트라 태그는 Python·패키지만 바꾼다. 코드 장애에 효과가 없다
- ⛔ Supabase 시점 복구를 수단으로 계산: 플랜·보존 기간을 확인한 적 없다
