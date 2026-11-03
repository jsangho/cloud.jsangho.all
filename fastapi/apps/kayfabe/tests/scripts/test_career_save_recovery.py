"""`scripts/career_save_recovery.py` — 비상 복구 도구의 가드와 실제 PG 시나리오.

## 두 묶음

1. **가드(DB 없음)** — 운영 ref·Supabase·비루프백 DSN 을 **접속 전에** 거부하는지,
   승인 플래그 없이 쓰기 경로로 들어가지 않는지. CI 에서도 돈다.
2. **PG 시나리오** — `KAYFABE_TEST_DATABASE_URL` 이 없으면 skip(CI 기본). 하네스·안전
   규칙은 `test_sandbox_career_pg_repository` 의 것을 그대로 쓴다. 각 테스트는 **실제
   변경 전후의 DB 상태**(`world::text`·영수증·시퀀스)를 비교한다.

## 실행

```bash
cd fastapi
KAYFABE_TEST_DATABASE_URL='postgresql+psycopg://pgtest@127.0.0.1:55433/kayfabe_test' \\
  PYTHONPATH=apps uv run pytest apps/kayfabe/tests/scripts/test_career_save_recovery.py -v
```

구버전 코덱 호환 검사(`test_downgraded_save_is_read_by_the_aws_codec`)는 git 에
`8c965da` 객체가 있어야 돈다(얕은 클론이면 skip).
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

import psycopg
import pytest

_HERE = Path(__file__).resolve()
_SCRIPT = _HERE.parents[2] / "scripts" / "career_save_recovery.py"
_PG_TESTS = (
    _HERE.parents[1]
    / "adapter"
    / "outbound"
    / "pg"
    / "test_sandbox_career_pg_repository.py"
)
_REPO_ROOT = _HERE.parents[5]
#: 구버전 백엔드(Phase 0/0.5 · SCHEMA_VERSION 2). 다운그레이드 결과를 이 코덱이 읽어야 한다.
_AWS_COMMIT = "8c965da"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = _load("_career_save_recovery", _SCRIPT)

_TEST_DSN = os.getenv("KAYFABE_TEST_DATABASE_URL", "").strip()
_SYNC_DSN = _TEST_DSN.replace("postgresql+psycopg://", "postgresql://", 1)
needs_pg = pytest.mark.skipif(
    not _TEST_DSN,
    reason="KAYFABE_TEST_DATABASE_URL 이 없다 — 버려도 되는 PostgreSQL 을 가리켜야 한다",
)


# ── 1. 가드 — DB 없이 ─────────────────────────────────────────────

#: 가짜 운영 ref. **진짜 ref 는 공개 저장소에 두지 않는다** — 도구는 해시만 들고 있고,
#: 테스트는 이 가짜의 해시를 주입해 같은 차단 경로를 본다.
_FAKE_REF = "qwertyuiopasdfghjklz"
assert len(_FAKE_REF) == tool.REF_LEN


@pytest.fixture
def fake_production_ref(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(
        tool,
        "PRODUCTION_REF_SHA256",
        frozenset({hashlib.sha256(_FAKE_REF.encode()).hexdigest()}),
    )
    return _FAKE_REF


def test_the_real_production_ref_is_kept_only_as_a_hash() -> None:
    assert tool.PRODUCTION_REF_SHA256
    assert all(len(h) == 64 and int(h, 16) >= 0 for h in tool.PRODUCTION_REF_SHA256)
    # 이 파일의 가짜는 진짜가 아니다(우연히 같으면 아래 테스트가 진짜를 검증하지 않는다).
    assert (
        hashlib.sha256(_FAKE_REF.encode()).hexdigest() not in tool.PRODUCTION_REF_SHA256
    )


@pytest.mark.parametrize(
    "template",
    [
        "postgresql://postgres.{ref}:pw@127.0.0.1:5432/postgres",
        "postgresql://u:pw@127.0.0.1:5432/{ref}",
        "postgresql://u:pw@127.0.0.1:5432/x{ref}y",  # 다른 글자와 붙어 있어도
        "postgresql://u:pw@127.0.0.1:5432/X?application_name={REF}",  # 대문자여도
    ],
)
def test_guard_refuses_a_production_ref_even_on_loopback(
    fake_production_ref: str, template: str
) -> None:
    dsn = template.format(ref=fake_production_ref, REF=fake_production_ref.upper())
    with pytest.raises(tool.GuardRefusedError, match="운영 project ref"):
        tool.guard_dsn(dsn, environ={})


@pytest.mark.parametrize(
    "dsn",
    [
        "",
        "postgresql+psycopg://postgres.abc:pw@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres",
        "postgresql://u:pw@db.example.com:5432/x",
        "postgresql://u:pw@10.0.0.5:5432/x",
        "postgresql://u:pw@/x",
        "postgresql://u:pw@127.0.0.1:5432/x?hostaddr=10.0.0.5",
        "postgresql://u:pw@127.0.0.1,db.example.com:5432/x",
    ],
)
def test_guard_refuses_anything_but_a_loopback_isolated_db(dsn: str) -> None:
    with pytest.raises(tool.GuardRefusedError):
        tool.guard_dsn(dsn, environ={})


def test_guard_refuses_the_apps_own_database_url() -> None:
    dsn = "postgresql://u:pw@127.0.0.1:5432/x"
    with pytest.raises(tool.GuardRefusedError):
        tool.guard_dsn(dsn, environ={"DATABASE_URL": dsn})


def test_guard_refuses_a_non_loopback_pghostaddr() -> None:
    with pytest.raises(tool.GuardRefusedError):
        tool.guard_dsn(
            "postgresql://u:pw@127.0.0.1:5432/x", environ={"PGHOSTADDR": "10.0.0.5"}
        )


def test_guard_accepts_loopback() -> None:
    out = tool.guard_dsn("postgresql+psycopg://u:pw@127.0.0.1:5432/x", environ={})
    assert out.startswith("postgresql://")


def _no_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a, **_k):
        raise AssertionError("가드가 막아야 할 접속이 시도됐다")

    monkeypatch.setattr(tool.psycopg, "connect", boom)


@pytest.mark.parametrize("op", ["fingerprint", "downgrade-v3"])
@pytest.mark.parametrize(
    "host", ["aws-0-ap-northeast-2.pooler.supabase.com", "127.0.0.1"]
)
def test_production_ref_is_blocked_before_connecting_and_leaks_nothing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_production_ref: str,
    op: str,
    host: str,
) -> None:
    secret = "Sup3r-S3cret-Pw"
    monkeypatch.setenv(
        tool.DSN_ENV,
        f"postgresql+psycopg://postgres.{fake_production_ref}:{secret}"
        f"@{host}:5432/postgres",
    )
    _no_connect(monkeypatch)
    argv = [op] if op == "fingerprint" else [op, "--career-id", "1", "--user-id", "2"]
    assert tool.main(argv) == tool.EXIT_GUARD
    out = capsys.readouterr()
    assert secret not in out.out + out.err
    assert fake_production_ref not in out.out + out.err


@pytest.mark.parametrize(
    "extra",
    [
        [],  # --confirm 없음
        ["--confirm", "downgrade-v3:career=1:user=999"],  # 다른 대상
        ["--confirm", "restore:career=1:user=2"],  # 다른 작업
        ["--confirm", "downgrade-v3:career=1:user=2"],  # 기대값 없음
        [
            "--confirm",
            "downgrade-v3:career=1:user=2",
            "--expect-md5",
            "x",
            "--expect-matches",
            "0",
            "--expect-receipts",
            "0",
        ],  # 사전 이미지 디렉터리 없음
    ],
)
def test_execute_without_full_approval_never_connects(
    monkeypatch: pytest.MonkeyPatch, extra: list[str]
) -> None:
    monkeypatch.setenv(tool.DSN_ENV, "postgresql://u@127.0.0.1:1/x")
    _no_connect(monkeypatch)
    argv = ["downgrade-v3", "--career-id", "1", "--user-id", "2", "--execute", *extra]
    assert tool.main(argv) == tool.EXIT_USAGE


# ── 2. PG 시나리오 ────────────────────────────────────────────────


def _pg():
    return _load("_career_pg_recovery", _PG_TESTS)


@pytest.fixture
def pg():
    return _pg()


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    """도구를 같은 프로세스에서 부른다. (종료 코드, 보고서 dict|None, stderr)."""
    monkeypatch.setenv(tool.DSN_ENV, _SYNC_DSN)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    def _run(*argv: str, hook=None) -> tuple[int, dict | None, str]:
        code = tool.main(list(argv), hook=hook)
        out = capsys.readouterr()
        report = (
            json.loads(out.out) if code == tool.EXIT_OK and out.out.strip() else None
        )
        return code, report, out.err

    return _run


def _db() -> psycopg.Connection:
    return psycopg.connect(_SYNC_DSN, autocommit=True)


def _snapshot(*career_ids: int) -> dict[str, Any]:
    """대상 career 들의 실제 행(`world::text` 포함) + 영수증 전부 + 시퀀스."""
    with _db() as c, c.cursor() as cur:
        cur.execute(
            "SELECT id, user_id, season, week, phase, world::text, updated_at::text "
            "FROM sandbox_careers WHERE id = ANY(%s) ORDER BY id",
            (list(career_ids),),
        )
        rows = cur.fetchall()
        cur.execute(
            "SELECT id, career_id, request_id, response::text FROM sandbox_career_requests "
            "WHERE career_id = ANY(%s) ORDER BY id",
            (list(career_ids),),
        )
        receipts = cur.fetchall()
        cur.execute("SELECT last_value, is_called FROM sandbox_careers_id_seq")
        seq = cur.fetchone()
    return {"rows": rows, "receipts": receipts, "seq": seq}


def _raw(career_id: int) -> tuple[dict, str]:
    with _db() as c, c.cursor() as cur:
        cur.execute(
            "SELECT world, md5(world::text) FROM sandbox_careers WHERE id = %s",
            (career_id,),
        )
        return cur.fetchone()


def _add_receipts(user_id: int, career_id: int, *keys: str) -> None:
    with _db() as c, c.cursor() as cur:
        for k in keys:
            cur.execute(
                "INSERT INTO sandbox_career_requests "
                "(user_id, career_id, request_id, fingerprint, response) "
                "VALUES (%s, %s, %s, %s, '{\"week\": 1}'::jsonb)",
                (user_id, career_id, k, "f" * 64),
            )


def _put_raw(career_id: int, world: dict) -> None:
    with _db() as c, c.cursor() as cur:
        cur.execute(
            "UPDATE sandbox_careers SET world = %s WHERE id = %s",
            (psycopg.types.json.Jsonb(world), career_id),
        )


async def _v3_career(pg, h, *, with_records: bool) -> int:
    """v3 행. 기록 40건(골든 궤적) 또는 0건(새 커리어)."""
    career_id = await pg._career(h)
    if with_records:
        _, world = pg._golden().run_trajectory()
        assert len(world.matches) == 40
        async with h.repo() as repo:
            await repo.save(user_id=h.user_id, career_id=career_id, state=world)
    raw, _ = _raw(career_id)
    assert raw["version"] == 3
    return career_id


def _flags(report: dict, pre_dir: Path) -> list[str]:
    return report["execute_flags"].replace("<DIR>", str(pre_dir)).split()


def _write_backup(
    tmp_path: Path, rows: list[dict], name: str = "backup.json"
) -> tuple[Path, Path]:
    path = tmp_path / name
    data = json.dumps(
        {"meta": {"table": "sandbox_careers"}, "rows": rows}, ensure_ascii=False
    )
    path.write_text(data, encoding="utf-8")
    sums = tmp_path / f"SHA256SUMS.{name}"
    sums.write_text(
        f"{hashlib.sha256(data.encode()).hexdigest()}  {name}\n", encoding="utf-8"
    )
    return path, sums


def _backup_rows(*career_ids: int) -> list[dict]:
    """운영 추출(`extract_backup_phase1b`)과 같은 모양 — 서버 md5 를 함께 싣는다."""
    with _db() as c, c.cursor() as cur:
        cur.execute(
            "SELECT id, user_id, player_name, seed, season, week, phase, created_at, "
            "updated_at, world, md5(world::text) FROM sandbox_careers WHERE id = ANY(%s) "
            "ORDER BY id",
            (list(career_ids),),
        )
        keys = ("id", "user_id", "player_name", "seed", "season", "week", "phase")
        return [
            {
                **dict(zip(keys, r[:7], strict=True)),
                "created_at": r[7].isoformat(),
                "updated_at": r[8].isoformat(),
                "world": r[9],
                "world_jsonb_md5": r[10],
            }
            for r in cur.fetchall()
        ]


# ── 2-1. 다운그레이드 ─────────────────────────────────────────────


@needs_pg
@pytest.mark.asyncio
@pytest.mark.parametrize("with_records", [False, True], ids=["0-records", "40-records"])
async def test_downgrade_v3_to_v2_drops_only_the_two_keys_and_this_careers_receipts(
    pg, run, tmp_path: Path, with_records: bool
) -> None:
    async with pg._harness() as h:
        target = await _v3_career(pg, h, with_records=with_records)
        other = await _v3_career(pg, h, with_records=False)
        _add_receipts(h.user_id, target, "t-1", "t-2", "t-3")
        _add_receipts(h.user_id, other, "o-1", "o-2")
        before_world, before_md5 = _raw(target)
        other_before = _snapshot(other)

        code, plan, _ = run(
            "downgrade-v3", "--career-id", str(target), "--user-id", str(h.user_id)
        )
        assert code == 0 and plan["mode"] == "dry-run"
        assert plan["planned"]["match_records_lost"] == (40 if with_records else 0)
        assert len(plan["planned"]["receipts_to_delete"]) == 3

        pre = tmp_path / "pre"
        pre.mkdir()
        code, rep, err = run(
            "downgrade-v3", "--career-id", str(target), "--user-id", str(h.user_id),
            *_flags(plan, pre),
        )  # fmt: skip
        assert code == 0, err
        assert rep["committed"] is True

        after_world, after_md5 = _raw(target)
        expected = {k: v for k, v in before_world.items() if k not in tool.V3_KEYS}
        expected["version"] = 2
        assert after_world == expected
        assert after_md5 == rep["after"]["world_jsonb_md5"] != before_md5
        assert _snapshot(target)["receipts"] == []
        assert _snapshot(other) == other_before  # 다른 career 와 그 영수증은 그대로

        files = list(pre.iterdir())
        assert len(files) == 1 and oct(files[0].stat().st_mode & 0o777) == "0o600"
        image = json.loads(files[0].read_text(encoding="utf-8"))
        assert (
            image["row"]["world"] == before_world
        )  # MatchRecord 는 사전 이미지에만 남는다
        assert len(image["receipts"]) == 3
        assert (
            hashlib.sha256(files[0].read_bytes()).hexdigest()
            == rep["pre_image"]["sha256"]
        )

        # 현재 코드도 읽는다(v2 → v3 메모리 업그레이드). DB 는 v2 그대로다.
        async with h.repo() as repo:
            world = await repo.load(user_id=h.user_id, career_id=target)
        assert world is not None and world.matches == ()
        assert _raw(target)[1] == after_md5

        # 재실행은 안전하다 — 판본이 이미 2 라 쓰기 전에 멈춘다.
        snap = _snapshot(target, other)
        code, _, err = run(
            "downgrade-v3", "--career-id", str(target), "--user-id", str(h.user_id),
            *_flags(plan, pre),
        )  # fmt: skip
        assert code == tool.EXIT_ABORT and "판본이 3 이 아니다" in err
        assert _snapshot(target, other) == snap
        assert len(list(pre.iterdir())) == 1


@needs_pg
@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2])
async def test_downgrade_refuses_v1_and_v2_rows(pg, run, version: int) -> None:
    async with pg._harness() as h:
        target = await pg._career(h)
        _put_raw(target, pg._v1_raw() if version == 1 else pg._v2_raw())
        snap = _snapshot(target)
        code, _, err = run(
            "downgrade-v3", "--career-id", str(target), "--user-id", str(h.user_id)
        )
        assert code == tool.EXIT_ABORT and "판본이 3 이 아니다" in err
        assert _snapshot(target) == snap


@needs_pg
@pytest.mark.asyncio
async def test_downgrade_refuses_missing_career_and_wrong_user(
    pg, run, tmp_path: Path
) -> None:
    async with pg._harness() as h:
        target = await _v3_career(pg, h, with_records=True)
        snap = _snapshot(target)
        code, _, err = run(
            "downgrade-v3", "--career-id", "2147483000", "--user-id", str(h.user_id)
        )
        assert code == tool.EXIT_ABORT and "1개가 아니다(0개)" in err
        code, _, err = run(
            "downgrade-v3",
            "--career-id",
            str(target),
            "--user-id",
            str(h.user_id + 10_000),
        )
        assert code == tool.EXIT_ABORT and "user_id" in err
        assert _snapshot(target) == snap


@needs_pg
@pytest.mark.asyncio
async def test_downgrade_stops_when_the_row_changed_since_the_dry_run(
    pg, run, tmp_path: Path
) -> None:
    """드라이런 뒤 사용자가 한 주를 더 진행했다 — 기대값이 어긋나 아무것도 안 바뀐다."""
    async with pg._harness() as h:
        target = await _v3_career(pg, h, with_records=True)
        _add_receipts(h.user_id, target, "t-1")
        _, plan, _ = run(
            "downgrade-v3", "--career-id", str(target), "--user-id", str(h.user_id)
        )
        world, _ = _raw(target)
        world["week"] += 1
        _put_raw(target, world)
        snap = _snapshot(target)
        pre = tmp_path / "pre"
        pre.mkdir()
        code, _, err = run(
            "downgrade-v3", "--career-id", str(target), "--user-id", str(h.user_id),
            *_flags(plan, pre),
        )  # fmt: skip
        assert code == tool.EXIT_ABORT and "md5" in err
        _add_receipts(h.user_id, target, "t-2")  # 영수증 수 기대값도 어긋난다
        snap = _snapshot(target)
        flags = _flags(plan, pre)
        flags[flags.index("--expect-md5") + 1] = _raw(target)[1]
        code, _, err = run(
            "downgrade-v3",
            "--career-id",
            str(target),
            "--user-id",
            str(h.user_id),
            *flags,
        )
        assert code == tool.EXIT_ABORT and "영수증 수" in err
        assert _snapshot(target) == snap
        assert list(pre.iterdir()) == []


@needs_pg
@pytest.mark.asyncio
async def test_downgrade_refuses_unexpected_match_record_shape(pg, run) -> None:
    async with pg._harness() as h:
        target = await _v3_career(pg, h, with_records=True)
        world, _ = _raw(target)
        world["matches"][0] = {"id": 7}
        _put_raw(target, world)
        snap = _snapshot(target)
        code, _, err = run(
            "downgrade-v3", "--career-id", str(target), "--user-id", str(h.user_id)
        )
        assert code == tool.EXIT_ABORT and "MatchRecord 모양" in err
        assert _snapshot(target) == snap


@needs_pg
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "step", ["pre_image_written", "updated", "receipts_deleted", "before_commit"]
)
async def test_downgrade_rolls_back_everything_on_a_mid_transaction_failure(
    pg, run, tmp_path: Path, step: str
) -> None:
    async with pg._harness() as h:
        target = await _v3_career(pg, h, with_records=True)
        other = await _v3_career(pg, h, with_records=False)
        _add_receipts(h.user_id, target, "t-1", "t-2")
        _add_receipts(h.user_id, other, "o-1")
        _, plan, _ = run(
            "downgrade-v3", "--career-id", str(target), "--user-id", str(h.user_id)
        )
        snap = _snapshot(target, other)

        def hook(name: str) -> None:
            if name == step:
                raise RuntimeError(f"주입한 실패: {name}")

        pre = tmp_path / "pre"
        pre.mkdir()
        code, _, err = run(
            "downgrade-v3", "--career-id", str(target), "--user-id", str(h.user_id),
            *_flags(plan, pre), hook=hook,
        )  # fmt: skip
        assert code == tool.EXIT_ERROR and "rollback" in err
        assert _snapshot(target, other) == snap


@needs_pg
@pytest.mark.asyncio
async def test_downgraded_save_is_read_by_the_aws_codec(
    pg, run, tmp_path: Path
) -> None:
    """**구버전 백엔드가 읽을 수 있는가** — `8c965da` 의 코덱을 별도 프로세스로 띄워 본다."""
    if subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "cat-file", "-e", f"{_AWS_COMMIT}^{{commit}}"],
        capture_output=True,
    ).returncode:
        pytest.skip(f"git 에 {_AWS_COMMIT} 가 없다(얕은 클론)")
    async with pg._harness() as h:
        target = await _v3_career(pg, h, with_records=True)
        _, plan, _ = run(
            "downgrade-v3", "--career-id", str(target), "--user-id", str(h.user_id)
        )
        pre = tmp_path / "pre"
        pre.mkdir()
        code, _, err = run(
            "downgrade-v3", "--career-id", str(target), "--user-id", str(h.user_id),
            *_flags(plan, pre),
        )  # fmt: skip
        assert code == 0, err
        v3_before = json.loads(next(pre.iterdir()).read_text(encoding="utf-8"))["row"][
            "world"
        ]
        downgraded, _ = _raw(target)

    archive = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "archive", _AWS_COMMIT, "fastapi/apps/kayfabe", "fastapi/core"],
        capture_output=True, check=True,
    ).stdout  # fmt: skip
    old_tree = tmp_path / "aws"
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(old_tree, filter="data")
    (tmp_path / "v2.json").write_text(json.dumps(downgraded), encoding="utf-8")
    (tmp_path / "v3.json").write_text(json.dumps(v3_before), encoding="utf-8")
    probe = (
        "import json, sys\n"
        "from kayfabe.adapter.outbound.pg import career_world_codec as old\n"
        "from kayfabe.app.ports.output.sandbox_career_repository import CorruptSaveError\n"
        f"assert {str(old_tree)!r} in old.__file__, old.__file__\n"
        "assert old.SCHEMA_VERSION == 2\n"
        "v2 = json.load(open(sys.argv[1])); v3 = json.load(open(sys.argv[2]))\n"
        "assert old.dump(old.load(dict(v2))) == v2, 'round trip'\n"
        "try:\n    old.load(dict(v3)); print('V3_READ')\n"
        "except CorruptSaveError:\n    print('V3_REFUSED')\n"
        "print('OK')\n"
    )
    env = {
        **os.environ,
        "PYTHONPATH": f"{old_tree}/fastapi/apps{os.pathsep}{old_tree}/fastapi",
    }
    env.pop("PYTHONSTARTUP", None)
    res = subprocess.run(
        [sys.executable, "-c", probe, str(tmp_path / "v2.json"), str(tmp_path / "v3.json")],
        capture_output=True, text=True, env=env, cwd=tmp_path,
    )  # fmt: skip
    assert res.returncode == 0, res.stderr[-2000:]
    assert res.stdout.split() == ["V3_REFUSED", "OK"]


# ── 2-2. 복원 ─────────────────────────────────────────────────────


@needs_pg
@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2])
async def test_restore_brings_back_a_v1_or_v2_backup_over_a_v3_row(
    pg, run, tmp_path: Path, version: int
) -> None:
    async with pg._harness() as h:
        target = await pg._career(h)
        other = await _v3_career(pg, h, with_records=False)
        _put_raw(target, pg._v1_raw() if version == 1 else pg._v2_raw())
        backup, sums = _write_backup(tmp_path, _backup_rows(target, other))
        backed_world, backed_md5 = _raw(target)
        backed_snapshot = _snapshot(target)

        # 백업 뒤 진행: 현재 코드가 v3 로 저장하고 영수증이 쌓였다.
        _, world = pg._golden().run_trajectory()
        async with h.repo() as repo:
            await repo.save(user_id=h.user_id, career_id=target, state=world)
        _add_receipts(h.user_id, target, "t-1", "t-2")
        _add_receipts(h.user_id, other, "o-1")
        assert _raw(target)[0]["version"] == 3
        other_before = _snapshot(other)

        base = ["restore", "--career-id", str(target), "--user-id", str(h.user_id),
                "--backup", str(backup), "--sha256sums", str(sums)]  # fmt: skip
        code, plan, _ = run(*base)
        assert code == 0 and plan["mode"] == "dry-run"
        assert plan["current"]["version"] == 3 and plan["backup"]["version"] == version
        assert plan["planned"]["progress_after_backup_is_lost"] is True
        assert plan["planned"]["backup_receipts_restored"] == 0
        assert plan["planned"]["sequence_setval"] is False

        pre = tmp_path / "pre"
        pre.mkdir()
        code, rep, err = run(*base, *_flags(plan, pre))
        assert code == 0, err
        world_now, md5_now = _raw(target)
        assert world_now == backed_world and md5_now == backed_md5
        assert md5_now == rep["backup"]["world_jsonb_md5"]
        after = _snapshot(target)
        assert after["rows"] == backed_snapshot["rows"]  # updated_at 까지 백업 값
        assert after["receipts"] == []
        assert after["seq"] == backed_snapshot["seq"]
        assert _snapshot(other) == other_before

        image = json.loads(next(pre.iterdir()).read_text(encoding="utf-8"))
        assert image["row"]["world"]["version"] == 3  # 지운 시간선은 사전 이미지에 있다
        assert len(image["receipts"]) == 2

        async with h.repo() as repo:
            assert await repo.load(user_id=h.user_id, career_id=target) is not None

        # 재시도: 낡은 기대값이면 멈추고, 새 드라이런 값으로 다시 하면 같은 결과다.
        snap = _snapshot(target, other)
        code, _, err = run(*base, *_flags(plan, pre))
        assert code == tool.EXIT_ABORT and "md5" in err
        assert _snapshot(target, other) == snap
        code, plan2, _ = run(*base)
        assert plan2["planned"]["progress_after_backup_is_lost"] is False
        code, rep2, err = run(*base, *_flags(plan2, pre))
        assert code == 0, err
        assert _snapshot(target, other) == snap
        assert rep2["receipts_deleted"] == []


@needs_pg
@pytest.mark.asyncio
async def test_restore_refuses_mismatched_ids_tampered_files_and_multiple_rows(
    pg, run, tmp_path: Path
) -> None:
    async with pg._harness() as h:
        target = await _v3_career(pg, h, with_records=False)
        rows = _backup_rows(target)
        snap = _snapshot(target)

        def attempt(
            rows_: list[dict], *, user: int, name: str, tamper: bool = False
        ) -> tuple[int, str]:
            backup, sums = _write_backup(tmp_path, rows_, name)
            if tamper:
                backup.write_text(
                    backup.read_text(encoding="utf-8") + " ", encoding="utf-8"
                )
            code, _, err = run(
                "restore", "--career-id", str(target), "--user-id", str(user),
                "--backup", str(backup), "--sha256sums", str(sums),
            )  # fmt: skip
            return code, err

        code, err = attempt(rows, user=h.user_id + 10_000, name="a.json")
        assert code == tool.EXIT_ABORT and "백업의 user_id" in err
        code, err = attempt(
            [dict(rows[0], user_id=h.user_id + 10_000)],
            user=h.user_id + 10_000,
            name="b.json",
        )
        assert code == tool.EXIT_ABORT and "현재 행의 user_id" in err
        code, err = attempt([], user=h.user_id, name="c.json")
        assert code == tool.EXIT_ABORT and "0행" in err
        code, err = attempt(rows + rows, user=h.user_id, name="d.json")
        assert code == tool.EXIT_ABORT and "2행" in err
        code, err = attempt(rows, user=h.user_id, name="e.json", tamper=True)
        assert code == tool.EXIT_ABORT and "SHA256" in err
        assert _snapshot(target) == snap


@needs_pg
@pytest.mark.asyncio
async def test_restore_of_a_missing_row_moves_the_sequence_only_when_needed(
    pg, run, tmp_path: Path
) -> None:
    async with pg._harness() as h:
        source = await _v3_career(pg, h, with_records=False)
        row = _backup_rows(source)[0]
        with _db() as c, c.cursor() as cur:
            cur.execute("SELECT last_value FROM sandbox_careers_id_seq")
            last = cur.fetchone()[0]
        far = dict(
            row, id=last + 50
        )  # 시퀀스보다 뒤의 id — 복원하면 다음 create 와 충돌한다
        backup, sums = _write_backup(tmp_path, [far])
        base = ["restore", "--career-id", str(far["id"]), "--user-id", str(h.user_id),
                "--backup", str(backup), "--sha256sums", str(sums)]  # fmt: skip
        code, plan, _ = run(*base)
        assert plan["current"] is None and plan["planned"]["sequence_setval"] is True
        pre = tmp_path / "pre"
        pre.mkdir()
        code, rep, err = run(*base, *_flags(plan, pre))
        assert code == 0, err
        assert rep["after"]["sequence"][0] >= far["id"]
        assert _raw(far["id"])[1] == row["world_jsonb_md5"]
        nxt = await pg._career(h)  # 다음 create 는 충돌하지 않는다
        assert nxt > far["id"]


@needs_pg
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "step", ["pre_image_written", "upserted", "receipts_deleted", "before_commit"]
)
async def test_restore_rolls_back_everything_on_a_mid_transaction_failure(
    pg, run, tmp_path: Path, step: str
) -> None:
    async with pg._harness() as h:
        target = await pg._career(h)
        _put_raw(target, pg._v2_raw())
        backup, sums = _write_backup(tmp_path, _backup_rows(target))
        _, world = pg._golden().run_trajectory()
        async with h.repo() as repo:
            await repo.save(user_id=h.user_id, career_id=target, state=world)
        _add_receipts(h.user_id, target, "t-1")
        base = ["restore", "--career-id", str(target), "--user-id", str(h.user_id),
                "--backup", str(backup), "--sha256sums", str(sums)]  # fmt: skip
        _, plan, _ = run(*base)
        snap = _snapshot(target)

        def hook(name: str) -> None:
            if name == step:
                raise RuntimeError(name)

        pre = tmp_path / "pre"
        pre.mkdir()
        code, _, err = run(*base, *_flags(plan, pre), hook=hook)
        assert code == tool.EXIT_ERROR and "rollback" in err
        assert _snapshot(target) == snap


# ── 2-3. 안전성 ───────────────────────────────────────────────────


@needs_pg
@pytest.mark.asyncio
async def test_dry_runs_change_nothing_and_cannot_write(
    pg, run, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with pg._harness() as h:
        target = await _v3_career(pg, h, with_records=True)
        _add_receipts(h.user_id, target, "t-1")
        backup, sums = _write_backup(tmp_path, _backup_rows(target))
        code, fp1, _ = run("fingerprint")
        assert code == 0
        snap = _snapshot(target)
        for _ in range(2):  # 두 번 돌려도 같다
            code, rep, _ = run(
                "downgrade-v3", "--career-id", str(target), "--user-id", str(h.user_id)
            )
            assert code == 0 and rep["mode"] == "dry-run" and "committed" not in rep
            code, rep, _ = run(
                "restore", "--career-id", str(target), "--user-id", str(h.user_id),
                "--backup", str(backup), "--sha256sums", str(sums),
            )  # fmt: skip
            assert code == 0 and rep["mode"] == "dry-run" and "committed" not in rep
        _, fp2, _ = run("fingerprint")
        assert fp1["digest"] == fp2["digest"]
        assert _snapshot(target) == snap

    # 드라이런 연결은 READ ONLY 다 — 쓰기가 섞여 들어가도 DB 가 거부한다.
    seen: dict[str, bool] = {}
    real_downgrade, real_restore = tool.downgrade_v3, tool.restore

    def spy(real, name):
        def wrapped(conn, args, hook):
            seen[name] = conn.read_only
            return real(conn, args, hook)

        return wrapped

    monkeypatch.setattr(tool, "downgrade_v3", spy(real_downgrade, "downgrade"))
    monkeypatch.setattr(tool, "restore", spy(real_restore, "restore"))
    async with pg._harness() as h:
        target = await _v3_career(pg, h, with_records=False)
        backup, sums = _write_backup(tmp_path, _backup_rows(target), "ro.json")
        run("downgrade-v3", "--career-id", str(target), "--user-id", str(h.user_id))
        run(
            "restore", "--career-id", str(target), "--user-id", str(h.user_id),
            "--backup", str(backup), "--sha256sums", str(sums),
        )  # fmt: skip
    assert seen == {"downgrade": True, "restore": True}
    with psycopg.connect(_SYNC_DSN) as conn:
        conn.read_only = True
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction), conn.cursor() as cur:
            cur.execute("DELETE FROM sandbox_career_requests WHERE false")


@needs_pg
@pytest.mark.asyncio
@pytest.mark.parametrize("op", ["downgrade-v3", "restore"])
async def test_a_career_locked_by_the_app_makes_the_tool_stop_not_wait(
    pg, run, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, op: str
) -> None:
    """앱의 `_mutate` 가 그 행을 `FOR UPDATE` 로 쥐고 있다 — 도구는 기다리지 않고 rollback."""
    monkeypatch.setattr(tool, "LOCK_TIMEOUT_MS", 200)
    async with pg._harness() as h:
        target = await _v3_career(pg, h, with_records=True)
        _add_receipts(h.user_id, target, "t-1")
        backup, sums = _write_backup(tmp_path, _backup_rows(target))
        base = ["--career-id", str(target), "--user-id", str(h.user_id)]
        if op == "restore":
            base += ["--backup", str(backup), "--sha256sums", str(sums)]
        _, plan, _ = run(op, *base)
        snap = _snapshot(target)
        pre = tmp_path / "pre"
        pre.mkdir()
        async with h.repo() as repo:  # 앱 쪽 잠금
            await repo.load_for_update(user_id=h.user_id, career_id=target)
            code, _, err = run(op, *base, *_flags(plan, pre))
        assert code == tool.EXIT_ERROR and "LockNotAvailable" in err
        assert _snapshot(target) == snap
        assert list(pre.iterdir()) == []  # 잠금 전이라 사전 이미지도 없다


@needs_pg
@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["short-writes", "write-stalls", "readback-differs"])
async def test_pre_image_is_complete_or_nothing_is_committed(
    pg, run, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """사전 이미지가 MatchRecord 의 유일한 사본이다 — 잘린 파일을 남기고 커밋하면 안 된다."""
    async with pg._harness() as h:
        target = await _v3_career(pg, h, with_records=True)
        _add_receipts(h.user_id, target, "t-1")
        _, plan, _ = run(
            "downgrade-v3", "--career-id", str(target), "--user-id", str(h.user_id)
        )
        snap = _snapshot(target)
        real_write, real_read = tool.os.write, Path.read_bytes
        if mode == "short-writes":  # 한 번에 1000바이트씩만 — 이어 쓰면 성공해야 한다
            monkeypatch.setattr(
                tool.os, "write", lambda fd, b: real_write(fd, b[:1000])
            )
        elif mode == "write-stalls":  # 0바이트 반환 — 무한 루프가 아니라 실패
            monkeypatch.setattr(tool.os, "write", lambda fd, b: 0)
        else:  # 디스크가 다른 내용을 돌려준다
            monkeypatch.setattr(
                Path,
                "read_bytes",
                lambda p: (
                    real_read(p)[:-1]
                    if p.name.startswith("preimage_")
                    else real_read(p)
                ),
            )
        pre = tmp_path / "pre"
        pre.mkdir()
        code, rep, err = run(
            "downgrade-v3", "--career-id", str(target), "--user-id", str(h.user_id),
            *_flags(plan, pre),
        )  # fmt: skip
        monkeypatch.undo()
        if mode == "short-writes":
            assert code == 0, err
            image = next(pre.iterdir())
            assert (
                hashlib.sha256(image.read_bytes()).hexdigest()
                == rep["pre_image"]["sha256"]
            )
            assert (
                len(
                    json.loads(image.read_text(encoding="utf-8"))["row"]["world"][
                        "matches"
                    ]
                )
                == 40
            )
        else:
            assert code == tool.EXIT_ERROR and "OSError" in err
            assert _snapshot(target) == snap


@needs_pg
def test_no_secret_reaches_the_output(
    run, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    secret = "Pw-Never-Print-Me"
    if "@" not in _SYNC_DSN:
        pytest.skip("DSN 형식을 알 수 없다")
    scheme, rest = _SYNC_DSN.split("://", 1)
    userinfo, hostpart = rest.split("@", 1)
    user = userinfo.split(":", 1)[0]
    monkeypatch.setenv(tool.DSN_ENV, f"{scheme}://{user}:{secret}@{hostpart}")
    code = tool.main(["fingerprint"])
    out = capsys.readouterr()
    assert code == 0, out.err
    assert secret not in out.out + out.err
    assert user + ":" not in out.out + out.err
