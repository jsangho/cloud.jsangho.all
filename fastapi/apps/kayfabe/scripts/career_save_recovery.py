"""커리어 세이브 비상 복구 — v3→v2 다운그레이드 · 선택 career 백업 복원.

## 왜 있는가

Phase 1 은 세이브를 v3(`matches` · `match_records_since`)로 올린다. 구버전 백엔드
(`8c965da` · SCHEMA_VERSION 2)는 v3 를 `CorruptSaveError` → 500 으로 거부하므로,
첫 v3 쓰기 이후의 코드 롤백은 데이터 조치가 함께 가야 한다. 이 파일이 그 조치다.
절차·승인 항목·중단 조건은 `fastapi/_docs/sandbox-career-recovery-runbook.md`.

**우선 정책은 repair-forward(새 코드를 고쳐 다시 배포)다.** 이 도구는 그게 안 될 때만.

## 하는 일

- `downgrade-v3` — 한 career 의 v3 세이브에서 두 칸을 지우고 판본을 2 로 내린다.
  **MatchRecord 는 영구 삭제된다.** 같은 트랜잭션에서 그 career 의 영수증만 지운다.
- `restore` — 백업 파일에서 **한 career 만** 골라 원래 id 로 upsert 한다. 같은
  트랜잭션에서 그 career 의 영수증만 지운다. **백업의 영수증은 복원하지 않는다**
  (복원하면 옛 `Idempotency-Key` 재전송이 지워진 시간선의 응답을 돌려준다).
- `fingerprint` — 두 표의 지문만 읽는다(읽기 전용).

## 안전장치

- **기본이 드라이런이다.** 드라이런은 `READ ONLY` 트랜잭션이라 UPDATE/DELETE 를
  보내지 않는다(보내도 DB 가 거부한다).
- 쓰기에는 `--execute` + `--confirm <op>:career=<id>:user=<uid>` + 드라이런이
  보여 준 기대값(`--expect-*`)이 **모두** 필요하다. 하나라도 어긋나면 아무것도 안 바꾼다.
- **격리 DB 에서만 돈다.** DSN 은 전용 환경변수 `KAYFABE_RECOVERY_DATABASE_URL`
  에서만 읽고(`DATABASE_URL` 은 안 본다), 루프백 호스트가 아니거나 운영 project
  ref·Supabase 흔적이 있으면 **접속 전에** 거부한다. 접속 뒤에도 서버 주소와
  `supabase*` 역할 유무를 다시 본다(SSH 터널 대비).
  운영에서 쓰려면 이 가드를 여는 **별도 승인 커밋**이 필요하다 — 의도된 마찰이다.
- 쓰기 전에 대상 행과 영수증의 **사전 이미지**를 파일로 남긴다(0600, 덮어쓰기 금지).
  파일을 못 쓰면 커밋하지 않는다.
- 전부 한 트랜잭션. 검증 하나라도 어긋나면 rollback.
- DSN·비밀번호를 출력하지 않는다.

이 파일은 **psycopg 와 표준 라이브러리만** 쓴다. 앱 모듈을 import 하지 않으므로
구버전 코드가 도는 컨테이너에서도 같은 도구로 돌 수 있다.

## 종료 코드

- `0` — 드라이런 완료 또는 커밋 완료.
- `2` — 사용법 오류.
- `3` — 가드 거부(격리 DB 가 아니다). DB 에 접속하지 않았거나 즉시 끊었다.
- `4` — 사전 조건 불일치로 중단. **아무것도 바꾸지 않았다.**
- `5` — 실행 중 예외. **트랜잭션 전체를 rollback 했다.**

실행 예 (격리 PG):

    cd fastapi
    KAYFABE_RECOVERY_DATABASE_URL='postgresql://pgtest@127.0.0.1:55433/kayfabe_test' \\
      uv run python apps/kayfabe/scripts/career_save_recovery.py \\
      downgrade-v3 --career-id 2 --user-id 6
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import ipaddress
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb

DSN_ENV = "KAYFABE_RECOVERY_DATABASE_URL"
#: 운영 Supabase project ref 의 **SHA-256**. 원문은 공개 저장소에 두지 않는다.
#: DSN 의 모든 `REF_LEN` 글자 구간을 해시해 대조한다 — 어디에 붙어 있든 걸린다.
#: 앞 12자(`5bd7917e6370`)가 운영 백업 메타의 `project_ref_sha12` 와 같다.
PRODUCTION_REF_SHA256 = frozenset(
    {"5bd7917e6370c657e08445ba0ba78969d5a3aeaeab3f9b4b5793ee7c392150b0"}
)
REF_LEN = 20
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
V3_KEYS = ("matches", "match_records_since")
#: 앱이 그 career 를 잡고 있으면 기다리지 않고 멈춘다(종료 코드 5 · rollback).
LOCK_TIMEOUT_MS = 5000

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_GUARD = 3
EXIT_ABORT = 4
EXIT_ERROR = 5

Hook = Callable[[str], None]


class GuardRefusedError(Exception):
    """격리 DB 가 아니다."""


class RecoveryAbortError(Exception):
    """사전 조건 불일치. 쓰기 전에(또는 rollback 으로) 멈춘다."""


# ── 가드 ──────────────────────────────────────────────────────────


def _sha12(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def guard_dsn(dsn: str, *, environ: dict[str, str] | None = None) -> str:
    """접속 **전** 가드. 통과하면 psycopg 에 줄 conninfo 를 돌려준다."""
    env = os.environ if environ is None else environ
    raw = (dsn or "").strip()
    if not raw:
        raise GuardRefusedError(f"{DSN_ENV} 가 비어 있다")
    lowered = raw.lower()
    if _contains_production_ref(lowered):
        raise GuardRefusedError("운영 project ref 가 들어 있다 — 접속하지 않는다")
    if "supabase" in lowered or "pooler" in lowered:
        raise GuardRefusedError("Supabase/pooler 주소다 — 격리 DB 가 아니다")
    app = (env.get("DATABASE_URL") or "").strip()
    if app and app == raw:
        raise GuardRefusedError(
            "앱의 DATABASE_URL 과 같다 — 격리 DB 를 따로 가리켜야 한다"
        )
    conninfo = raw.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        params = conninfo_to_dict(conninfo)
    except psycopg.ProgrammingError as e:
        raise GuardRefusedError("DSN 을 해석할 수 없다") from e
    hosts = [h for h in (params.get("host") or "").split(",") if h]
    if not hosts or any(h not in LOOPBACK_HOSTS for h in hosts):
        raise GuardRefusedError(
            f"루프백이 아닌 호스트다(sha12={_sha12(','.join(hosts))}) — 격리 DB 만 허용"
        )
    for addr in (params.get("hostaddr"), env.get("PGHOSTADDR")):
        if addr and not _is_loopback(addr):
            raise GuardRefusedError("hostaddr 가 루프백이 아니다")
    return conninfo


def _contains_production_ref(text: str) -> bool:
    return any(
        hashlib.sha256(text[i : i + REF_LEN].encode()).hexdigest()
        in PRODUCTION_REF_SHA256
        for i in range(len(text) - REF_LEN + 1)
    )


def _is_loopback(addr: str) -> bool:
    try:
        return ipaddress.ip_address(addr.split("/")[0]).is_loopback
    except ValueError:
        return False


def guard_server(cur: psycopg.Cursor) -> dict[str, Any]:
    """접속 **후** 가드. 터널로 운영에 닿은 경우를 여기서 잡는다."""
    cur.execute(
        "SELECT inet_server_addr()::text, current_database(), "
        "split_part(version(), ' ', 2), "
        "(SELECT count(*) FROM pg_roles WHERE rolname LIKE 'supabase%%')"
    )
    addr, db, version, supabase_roles = cur.fetchone()
    if addr is not None and not _is_loopback(addr):
        raise GuardRefusedError("서버 주소가 루프백이 아니다")
    if supabase_roles:
        raise GuardRefusedError("supabase 역할이 있는 서버다 — 격리 DB 가 아니다")
    return {"server_addr": addr or "unix-socket", "database": db, "version": version}


# ── 읽기 ──────────────────────────────────────────────────────────

_ROW_SQL = (
    "SELECT id, user_id, player_name, seed, season, week, phase, world, "
    "md5(world::text), created_at, updated_at FROM sandbox_careers WHERE id = %s"
)
_ROW_KEYS = (
    "id",
    "user_id",
    "player_name",
    "seed",
    "season",
    "week",
    "phase",
    "world",
    "world_jsonb_md5",
    "created_at",
    "updated_at",
)


def _target(cur: psycopg.Cursor, career_id: int, *, lock: bool) -> list[dict]:
    if lock:
        cur.execute(f"SET LOCAL lock_timeout = {int(LOCK_TIMEOUT_MS)}")
    cur.execute(_ROW_SQL + (" FOR UPDATE" if lock else ""), (career_id,))
    out = []
    for r in cur.fetchall():
        row = dict(zip(_ROW_KEYS, r, strict=True))
        row["created_at"] = row["created_at"].isoformat()
        row["updated_at"] = row["updated_at"].isoformat()
        out.append(row)
    return out


def _receipts(cur: psycopg.Cursor, career_id: int) -> list[dict]:
    cur.execute(
        "SELECT row_to_json(r) FROM sandbox_career_requests r "
        "WHERE r.career_id = %s ORDER BY r.id",
        (career_id,),
    )
    return [r[0] for r in cur.fetchall()]


def fingerprint(cur: psycopg.Cursor) -> dict[str, Any]:
    """두 표의 지문. career 별 md5·판본 + career 별 영수증 묶음 md5 + 시퀀스."""
    cur.execute(
        "SELECT id, user_id, md5(world::text), world->>'version', updated_at::text "
        "FROM sandbox_careers ORDER BY id"
    )
    careers = {str(r[0]): list(r[1:]) for r in cur.fetchall()}
    cur.execute(
        "SELECT career_id, count(*), md5(string_agg(row_to_json(r)::text, ',' "
        "ORDER BY r.id)) FROM sandbox_career_requests r GROUP BY career_id "
        "ORDER BY career_id"
    )
    receipts = {str(r[0]): [r[1], r[2]] for r in cur.fetchall()}
    seqs = {}
    for tb in ("sandbox_careers", "sandbox_career_requests"):
        cur.execute("SELECT pg_get_serial_sequence(%s, 'id')", (f"public.{tb}",))
        seq = cur.fetchone()[0]
        cur.execute(f"SELECT last_value, is_called FROM {seq}")  # noqa: S608 - 카탈로그 값
        seqs[tb] = list(cur.fetchone())
    body = {"careers": careers, "receipts": receipts, "sequences": seqs}
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    return {"digest": digest, **body}


def _others_unchanged(before: dict, after: dict, career_id: int) -> bool:
    key = str(career_id)

    def strip(fp: dict, part: str) -> dict:
        return {k: v for k, v in fp[part].items() if k != key}

    return all(strip(before, p) == strip(after, p) for p in ("careers", "receipts"))


# ── 공통 ──────────────────────────────────────────────────────────


def _token(op: str, career_id: int, user_id: int) -> str:
    return f"{op}:career={career_id}:user={user_id}"


def _write_pre_image(directory: Path, op: str, career_id: int, body: dict) -> dict:
    """대상의 현재 상태를 파일로. **덮어쓰지 않는다**(O_EXCL).

    다운그레이드 뒤 MatchRecord 가 남는 곳은 이 파일뿐이다. 그래서 `os.write` 의
    부분 쓰기(디스크가 거의 찼을 때 등)를 끝까지 이어 쓰고, 파일과 디렉터리를 fsync
    한 뒤 **다시 읽어 SHA256 을 대조한다.** 하나라도 어긋나면 예외 → 커밋하지 않는다.
    """
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"preimage_{op}_career{career_id}_{stamp}.json"
    data = json.dumps(body, ensure_ascii=False, default=str, indent=1).encode()
    digest = hashlib.sha256(data).hexdigest()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("사전 이미지를 끝까지 쓰지 못했다")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    dir_fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise OSError("사전 이미지 SHA256 이 쓴 내용과 다르다")
    return {"path": str(path), "sha256": digest}


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise RecoveryAbortError(message)


def _check_v3_shape(world: Any) -> tuple[int, Any]:
    _require(isinstance(world, dict), "world 가 객체가 아니다")
    version = world.get("version")
    _require(
        type(version) is int and version == 3, f"판본이 3 이 아니다(지금 {version!r})"
    )
    matches = world.get("matches")
    _require(isinstance(matches, list), "matches 가 배열이 아니다")
    for m in matches:
        _require(
            isinstance(m, dict)
            and isinstance(m.get("id"), str)
            and type(m.get("season")) is int
            and type(m.get("week")) is int
            and isinstance(m.get("participants"), list),
            "MatchRecord 모양이 예상과 다르다",
        )
    since = world.get("match_records_since", "missing")
    _require(
        since is None
        or (
            isinstance(since, list)
            and len(since) == 2
            and all(type(x) is int for x in since)
        ),
        "match_records_since 모양이 예상과 다르다",
    )
    return len(matches), since


# ── downgrade-v3 ──────────────────────────────────────────────────


def downgrade_v3(
    conn: psycopg.Connection, args: argparse.Namespace, hook: Hook
) -> dict[str, Any]:
    execute = args.execute
    with conn.transaction(), conn.cursor() as cur:
        rows = _target(cur, args.career_id, lock=execute)
        _require(len(rows) == 1, f"대상 행이 1개가 아니다({len(rows)}개)")
        row = rows[0]
        _require(row["user_id"] == args.user_id, "user_id 가 예상과 다르다")
        n_matches, since = _check_v3_shape(row["world"])
        receipts = _receipts(cur, args.career_id)
        fp_before = fingerprint(cur)
        planned = {k: v for k, v in row["world"].items() if k not in V3_KEYS}
        planned["version"] = 2
        report: dict[str, Any] = {
            "op": "downgrade-v3",
            "mode": "execute" if execute else "dry-run",
            "career_id": args.career_id,
            "user_id": args.user_id,
            "before": {
                "version": 3,
                "world_jsonb_md5": row["world_jsonb_md5"],
                "match_records": n_matches,
                "match_records_since": since,
                "season_week": [row["season"], row["week"]],
            },
            "planned": {
                "version": 2,
                "removed_keys": list(V3_KEYS),
                "match_records_lost": n_matches,
                "receipts_to_delete": [r["id"] for r in receipts],
            },
            "fingerprint_before": fp_before["digest"],
            "execute_flags": (
                f"--execute --confirm {_token('downgrade-v3', args.career_id, args.user_id)}"
                f" --expect-md5 {row['world_jsonb_md5']} --expect-matches {n_matches}"
                f" --expect-receipts {len(receipts)} --pre-image-dir <DIR>"
            ),
        }
        if not execute:
            return report

        _require(
            args.expect_md5 == row["world_jsonb_md5"], "현재 md5 가 기대값과 다르다"
        )
        _require(args.expect_matches == n_matches, "MatchRecord 수가 기대값과 다르다")
        _require(args.expect_receipts == len(receipts), "영수증 수가 기대값과 다르다")
        report["pre_image"] = _write_pre_image(
            args.pre_image_dir,
            "downgrade-v3",
            args.career_id,
            {"row": row, "receipts": receipts, "fingerprint": fp_before},
        )
        hook("pre_image_written")

        cur.execute(
            "UPDATE sandbox_careers SET world = (world - 'matches' - "
            "'match_records_since') || jsonb_build_object('version', 2) "
            "WHERE id = %s AND user_id = %s AND md5(world::text) = %s "
            "RETURNING world, md5(world::text)",
            (args.career_id, args.user_id, row["world_jsonb_md5"]),
        )
        updated = cur.fetchall()
        _require(len(updated) == 1, f"UPDATE 대상이 1행이 아니다({len(updated)}행)")
        new_world, new_md5 = updated[0]
        _require(new_world == planned, "변경 결과가 계획과 다르다")
        hook("updated")

        cur.execute(
            "DELETE FROM sandbox_career_requests WHERE career_id = %s RETURNING id",
            (args.career_id,),
        )
        deleted = sorted(r[0] for r in cur.fetchall())
        _require(
            deleted == [r["id"] for r in receipts], "삭제된 영수증이 예상 범위와 다르다"
        )
        hook("receipts_deleted")

        fp_after = fingerprint(cur)
        _require(
            _others_unchanged(fp_before, fp_after, args.career_id),
            "다른 career 가 바뀌었다",
        )
        after_row = _target(cur, args.career_id, lock=False)[0]
        _require(
            after_row["world"].get("version") == 2
            and not any(k in after_row["world"] for k in V3_KEYS)
            and after_row["world_jsonb_md5"] == new_md5,
            "변경 후 구조 확인 실패",
        )
        hook("before_commit")
    report.update(
        after={"version": 2, "world_jsonb_md5": new_md5},
        receipts_deleted=deleted,
        fingerprint_after=fp_after["digest"],
        committed=True,
    )
    return report


# ── restore ───────────────────────────────────────────────────────


def _load_backup(path: Path, sums: Path) -> list[dict]:
    """SHA256SUMS 로 백업 파일을 검증하고 career 행 목록을 돌려준다."""
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    listed = {}
    for line in sums.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2:
            listed[parts[1].lstrip("*")] = parts[0]
    _require(path.name in listed, "SHA256SUMS 에 백업 파일이 없다")
    _require(listed[path.name] == digest, "백업 파일 SHA256 이 맞지 않는다")
    doc = json.loads(data)
    if isinstance(doc, dict) and "careers" in doc:
        doc = doc["careers"]
    rows = doc.get("rows") if isinstance(doc, dict) else None
    _require(isinstance(rows, list), "백업에서 career 행 목록을 찾을 수 없다")
    return rows


_UPSERT = (
    "INSERT INTO sandbox_careers (id, user_id, player_name, seed, season, week, "
    "phase, world, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, "
    "%s, %s) ON CONFLICT (id) DO UPDATE SET player_name = EXCLUDED.player_name, "
    "seed = EXCLUDED.seed, season = EXCLUDED.season, week = EXCLUDED.week, "
    "phase = EXCLUDED.phase, world = EXCLUDED.world, "
    "updated_at = EXCLUDED.updated_at WHERE sandbox_careers.user_id = EXCLUDED.user_id "
    "RETURNING md5(world::text)"
)


def restore(
    conn: psycopg.Connection, args: argparse.Namespace, hook: Hook
) -> dict[str, Any]:
    execute = args.execute
    picked = [
        r
        for r in _load_backup(args.backup, args.sha256sums)
        if r.get("id") == args.career_id
    ]
    _require(len(picked) == 1, f"백업에 대상 career 가 1행이 아니다({len(picked)}행)")
    src = picked[0]
    _require(src.get("user_id") == args.user_id, "백업의 user_id 가 예상과 다르다")
    src_version = (src.get("world") or {}).get("version")
    _require(
        type(src_version) is int and src_version in (1, 2, 3), "백업 판본을 알 수 없다"
    )
    _require(
        isinstance(src.get("world_jsonb_md5"), str), "백업 행에 world_jsonb_md5 가 없다"
    )

    with conn.transaction(), conn.cursor() as cur:
        rows = _target(cur, args.career_id, lock=execute)
        _require(len(rows) <= 1, "대상 행 수가 예상과 다르다")
        current = rows[0] if rows else None
        if current is not None:
            _require(
                current["user_id"] == args.user_id, "현재 행의 user_id 가 예상과 다르다"
            )
        receipts = _receipts(cur, args.career_id)
        fp_before = fingerprint(cur)
        seq_last, seq_called = fp_before["sequences"]["sandbox_careers"]
        seq_needed = args.career_id > seq_last or (
            args.career_id == seq_last and not seq_called
        )
        cur_desc = (
            None
            if current is None
            else {
                "version": current["world"].get("version"),
                "world_jsonb_md5": current["world_jsonb_md5"],
                "season_week": [current["season"], current["week"]],
                "updated_at": current["updated_at"],
            }
        )
        expect = (
            "--expect-absent"
            if current is None
            else f"--expect-current-md5 {current['world_jsonb_md5']}"
        )
        report: dict[str, Any] = {
            "op": "restore",
            "mode": "execute" if execute else "dry-run",
            "career_id": args.career_id,
            "user_id": args.user_id,
            "backup": {
                "file": args.backup.name,
                "version": src_version,
                "world_jsonb_md5": src["world_jsonb_md5"],
                "season_week": [src.get("season"), src.get("week")],
                "updated_at": src.get("updated_at"),
            },
            "current": cur_desc,
            "planned": {
                "receipts_to_delete": [r["id"] for r in receipts],
                "backup_receipts_restored": 0,
                "sequence_setval": seq_needed,
                "progress_after_backup_is_lost": current is not None
                and current["world_jsonb_md5"] != src["world_jsonb_md5"],
            },
            "fingerprint_before": fp_before["digest"],
            "execute_flags": (
                f"--execute --confirm {_token('restore', args.career_id, args.user_id)}"
                f" {expect} --expect-receipts {len(receipts)} --pre-image-dir <DIR>"
            ),
        }
        if not execute:
            return report

        if current is None:
            _require(args.expect_absent, "현재 행이 없는데 --expect-absent 가 없다")
        else:
            _require(
                args.expect_current_md5 == current["world_jsonb_md5"],
                "현재 md5 가 기대값과 다르다",
            )
        _require(args.expect_receipts == len(receipts), "영수증 수가 기대값과 다르다")
        report["pre_image"] = _write_pre_image(
            args.pre_image_dir,
            "restore",
            args.career_id,
            {"row": current, "receipts": receipts, "fingerprint": fp_before},
        )
        hook("pre_image_written")

        cur.execute(
            _UPSERT,
            (
                src["id"],
                src["user_id"],
                src["player_name"],
                src["seed"],
                src["season"],
                src["week"],
                src["phase"],
                Jsonb(src["world"]),
                datetime.datetime.fromisoformat(src["created_at"]),
                datetime.datetime.fromisoformat(src["updated_at"]),
            ),
        )
        upserted = cur.fetchall()
        _require(len(upserted) == 1, "upsert 대상이 1행이 아니다")
        _require(
            upserted[0][0] == src["world_jsonb_md5"],
            "복원한 world md5 가 백업과 다르다",
        )
        hook("upserted")

        cur.execute(
            "DELETE FROM sandbox_career_requests WHERE career_id = %s RETURNING id",
            (args.career_id,),
        )
        deleted = sorted(r[0] for r in cur.fetchall())
        _require(
            deleted == [r["id"] for r in receipts], "삭제된 영수증이 예상 범위와 다르다"
        )
        hook("receipts_deleted")

        if seq_needed:
            # 근거: 복원 id 가 시퀀스 뒤에 있으면 다음 create 가 그 id 를 다시 뽑아
            # PK 충돌이 난다. 표의 max(id) 로 맞춘다(뒤로 감기지 않는다 — 조건부).
            cur.execute(
                "SELECT setval(pg_get_serial_sequence('public.sandbox_careers', 'id'), "
                "(SELECT max(id) FROM sandbox_careers), true)"
            )
        fp_after = fingerprint(cur)
        _require(
            _others_unchanged(fp_before, fp_after, args.career_id),
            "다른 career 가 바뀌었다",
        )
        after_row = _target(cur, args.career_id, lock=False)[0]
        _require(after_row["world"] == src["world"], "복원 후 world 가 백업과 다르다")
        hook("before_commit")
    report.update(
        after={
            "version": src_version,
            "world_jsonb_md5": after_row["world_jsonb_md5"],
            "sequence": fp_after["sequences"]["sandbox_careers"],
        },
        receipts_deleted=deleted,
        fingerprint_after=fp_after["digest"],
        committed=True,
    )
    return report


# ── CLI ───────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="career_save_recovery", description=__doc__.split("\n")[0]
    )
    sub = p.add_subparsers(dest="op", required=True)
    sub.add_parser("fingerprint", help="두 표의 지문(읽기 전용)")
    for name in ("downgrade-v3", "restore"):
        s = sub.add_parser(name)
        s.add_argument("--career-id", type=int, required=True)
        s.add_argument("--user-id", type=int, required=True)
        s.add_argument("--execute", action="store_true", help="없으면 드라이런")
        s.add_argument("--confirm", default="")
        s.add_argument("--expect-receipts", type=int)
        s.add_argument("--pre-image-dir", type=Path)
        if name == "downgrade-v3":
            s.add_argument("--expect-md5")
            s.add_argument("--expect-matches", type=int)
        else:
            s.add_argument("--backup", type=Path, required=True)
            s.add_argument("--sha256sums", type=Path, required=True)
            g = s.add_mutually_exclusive_group()
            g.add_argument("--expect-current-md5")
            g.add_argument("--expect-absent", action="store_true")
    return p


def _check_execute_args(args: argparse.Namespace) -> str | None:
    if args.confirm != _token(args.op, args.career_id, args.user_id):
        return "--confirm 이 대상과 맞지 않는다"
    if args.expect_receipts is None:
        return "--expect-receipts 가 필요하다"
    if args.op == "downgrade-v3" and (
        args.expect_md5 is None or args.expect_matches is None
    ):
        return "--expect-md5 와 --expect-matches 가 필요하다"
    if args.op == "restore" and not (args.expect_current_md5 or args.expect_absent):
        return "--expect-current-md5 또는 --expect-absent 가 필요하다"
    d = args.pre_image_dir
    if d is None or not d.is_dir():
        return "--pre-image-dir 가 존재하는 디렉터리여야 한다"
    return None


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, default=str, indent=1) + "\n")


def main(argv: list[str] | None = None, *, hook: Hook | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as e:
        return EXIT_USAGE if e.code else EXIT_OK
    if getattr(args, "execute", False):
        problem = _check_execute_args(args)
        if problem:
            print(f"USAGE {problem}", file=sys.stderr)
            return EXIT_USAGE
    try:
        conninfo = guard_dsn(os.environ.get(DSN_ENV, ""))
    except GuardRefusedError as e:
        print(f"GUARD {e}", file=sys.stderr)
        return EXIT_GUARD

    step = hook or (lambda _name: None)
    try:
        with psycopg.connect(conninfo, connect_timeout=10, autocommit=False) as conn:
            with conn.cursor() as cur:
                server = guard_server(cur)
            conn.rollback()
            if args.op == "fingerprint" or not args.execute:
                conn.read_only = True  # 드라이런은 쓰기를 보낼 수 없다
            if args.op == "fingerprint":
                with conn.transaction(), conn.cursor() as cur:
                    report = {"op": "fingerprint", **fingerprint(cur)}
            elif args.op == "downgrade-v3":
                report = downgrade_v3(conn, args, step)
            else:
                report = restore(conn, args, step)
    except GuardRefusedError as e:
        print(f"GUARD {e}", file=sys.stderr)
        return EXIT_GUARD
    except RecoveryAbortError as e:
        print(f"ABORT {e} — 아무것도 바꾸지 않았다", file=sys.stderr)
        return EXIT_ABORT
    except Exception as e:  # noqa: BLE001 - 어떤 예외든 rollback 으로 끝난다
        print(f"ERROR {type(e).__name__} — 트랜잭션을 rollback 했다", file=sys.stderr)
        return EXIT_ERROR
    _emit({"server": server, **report})
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
