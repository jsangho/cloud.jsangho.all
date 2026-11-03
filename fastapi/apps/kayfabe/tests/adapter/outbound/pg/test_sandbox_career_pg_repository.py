"""커리어 세이브 어댑터 — **진짜 PostgreSQL 이어야 의미가 있는 것들.**

## 왜 가짜로는 안 되는가

`test_career_sandbox_interactor` 의 `FakeRepository` 는 고유 제약과 잠금 **순서**를
흉내 낸다. 흉내 내지 못하는 것이 넷이고, 넷 다 이 파일이 본다.

    1. `SELECT … FOR UPDATE` 가 두 번째 읽기를 **실제로 멈추는가**
    2. 고유 제약 위반이 `IntegrityError` 로 올라와 `DuplicateRequestError` 가 되는가
    3. 그 롤백이 **세이브 변경까지** 되돌리는가 (원자성)
    4. `ON DELETE CASCADE` 가 영수증을 데려가는가

여기에 보존 상한의 **실제 SQL**(`id DESC LIMIT 8`)을 더한다. 가짜는 파이썬 dict 의
삽입 순서로 자르므로 `notin_(scalar_subquery())` 가 맞는지는 아무도 모른다.

## 실행 — DSN 을 주지 않으면 전부 skip 된다

```bash
cd fastapi
KAYFABE_TEST_DATABASE_URL='postgresql+psycopg://user:pw@127.0.0.1:5432/kayfabe_test' \
  PYTHONPATH=apps uv run pytest apps/kayfabe/tests/adapter/outbound/pg/test_sandbox_career_pg_repository.py -v
```

**드라이버는 `psycopg`(v3) 다.** 이 저장소에 `asyncpg` 는 없다 — `postgresql+asyncpg://`
를 주면 import 에서 죽는다.

## 안전 규칙 — 버려도 되는 DB 에만 댄다

- 전용 환경변수 **`KAYFABE_TEST_DATABASE_URL`** 만 읽는다. **`DATABASE_URL` 은 보지
  않는다** — 앱 설정을 그대로 집으면 운영에 테스트를 돌리는 길이 열린다.
- 그 둘이 **같으면 거부한다**(`UsageError`). 실수로 같은 값을 넣는 경우를 막는다.
- 표 셋을 `checkfirst=True` 로 만들고(이미 있으면 건드리지 않는다), 끝나면 **이
  테스트가 만든 유저 행만** 지운다. CASCADE 가 그 유저의 커리어·영수증을 데려간다.
  **남의 행은 손대지 않고, DROP TABLE 도 하지 않는다.**
- `alembic` 을 부르지 않는다. 이 파일은 마이그레이션 적용 수단이 아니다
  (절차는 `fastapi/_docs/sandbox-career-migration.md`).
"""

from __future__ import annotations

import asyncio
import copy
import importlib.util
import json
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from core.entities.user_model import UserModel
from kayfabe.adapter.outbound.orm.career_sandbox_orm import (
    SandboxCareerModel,
    SandboxCareerRequestModel,
)
from kayfabe.adapter.outbound.pg.career_world_codec import (
    SCHEMA_VERSION,
)
from kayfabe.adapter.outbound.pg.career_world_codec import (
    load as decode,
)
from kayfabe.adapter.outbound.pg.sandbox_career_pg_repository import (
    SandboxCareerPgRepository,
)
from kayfabe.app.ports.input.career_sandbox_use_case import RequestKeyConflictError
from kayfabe.app.ports.output.sandbox_career_repository import (
    RECEIPT_KEEP,
    CorruptSaveError,
    DuplicateRequestError,
    RequestReceipt,
)
from kayfabe.app.use_cases.career_sandbox_interactor import CareerSandboxInteractor
from kayfabe.domain.services import career_engine as engine
from kayfabe.domain.services import career_season as season_rules
from kayfabe.domain.services.career_world import Balance, WorldState

#: 이 파일만의 DSN. 비어 있으면 전부 skip 이다.
_DSN = os.getenv("KAYFABE_TEST_DATABASE_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not _DSN,
    reason="KAYFABE_TEST_DATABASE_URL 이 없다 — 버려도 되는 PostgreSQL 을 가리켜야 한다",
)

#: 짧은 시즌. 52주를 돌리지 않고 경계를 본다.
_BALANCE = Balance(season_weeks=3)

#: 잠금이 **실제로 멈추는지** 보는 시간. 짧으면 느린 DB 에서 거짓 실패가 나고, 길면
#: 테스트가 느려진다. 0.4초는 로컬 PG 의 `FOR UPDATE` 획득(수 ms)보다 두 자릿수 크다.
_BLOCK_WAIT = 0.4


def _guard_dsn() -> str:
    """앱이 쓰는 DB 와 같으면 거부한다. **운영에 테스트를 돌리는 길을 막는다.**"""
    configured = (os.getenv("DATABASE_URL") or "").strip()
    if configured and configured == _DSN:
        raise pytest.UsageError(
            "KAYFABE_TEST_DATABASE_URL 이 앱의 DATABASE_URL 과 같다 — "
            "버려도 되는 DB 를 따로 가리켜야 한다"
        )
    return _DSN


@dataclass
class Harness:
    """한 테스트가 쓰는 연결 묶음. 세션은 **테스트가 직접 연다** — 동시성을 보려면
    세션이 둘 이상 필요하고, 하나를 공유하면 그게 곧 직렬화다."""

    session_factory: async_sessionmaker[AsyncSession]
    user_id: int

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    @asynccontextmanager
    async def repo(self) -> AsyncIterator[SandboxCareerPgRepository]:
        async with self.session() as session:
            yield SandboxCareerPgRepository(session)


@asynccontextmanager
async def _harness() -> AsyncIterator[Harness]:
    """표 셋을 보장하고 테스트 유저 하나를 만든다. 끝나면 그 유저만 지운다."""
    engine_ = create_async_engine(_guard_dsn(), poolclass=NullPool)
    factory = async_sessionmaker(bind=engine_, expire_on_commit=False)
    user_id: int | None = None
    try:
        async with engine_.begin() as conn:
            # 순서가 규칙이다 — FK 대상이 먼저 있어야 한다.
            await conn.run_sync(UserModel.__table__.create, checkfirst=True)
            await conn.run_sync(SandboxCareerModel.__table__.create, checkfirst=True)
            await conn.run_sync(
                SandboxCareerRequestModel.__table__.create, checkfirst=True
            )

        tag = uuid.uuid4().hex[:12]
        async with factory() as session:
            user = UserModel(
                login_id=f"pgtest-{tag}",
                nickname=f"pgtest-{tag}",
                email=f"pgtest-{tag}@example.invalid",
                password_hash="x",
                role="user",
            )
            session.add(user)
            await session.commit()
            user_id = user.id

        yield Harness(session_factory=factory, user_id=user_id)
    finally:
        if user_id is not None:
            async with factory() as session:
                # CASCADE 가 커리어와 영수증을 데려간다. **이 유저 행만** 지운다.
                await session.execute(delete(UserModel).where(UserModel.id == user_id))
                await session.commit()
        await engine_.dispose()


def _world(seed: int = 11) -> WorldState:
    return engine.create_world(
        player="Ho", style="테크니션", seed=seed, age=24, balance=_BALANCE
    )


async def _career(h: Harness, *, seed: int = 11) -> int:
    async with h.repo() as repo:
        return await repo.create(
            user_id=h.user_id, player_name="Ho", seed=seed, state=_world(seed)
        )


def _receipt(request_id: str, *, fingerprint: str = "f" * 64) -> RequestReceipt:
    return RequestReceipt(
        request_id=request_id, fingerprint=fingerprint, response={"week": 1}
    )


# ── 1. 보존 상한의 실제 SQL ───────────────────────────────────────


@pytest.mark.asyncio
async def test_receipts_are_pruned_to_the_newest_eight() -> None:
    """`id DESC LIMIT 8`. **가짜는 dict 순서로 자르므로 이 SQL 을 검증하지 못한다.**"""
    async with _harness() as h:
        career_id = await _career(h)
        world = _world()

        for n in range(RECEIPT_KEEP + 4):
            async with h.repo() as repo:
                await repo.save(
                    user_id=h.user_id,
                    career_id=career_id,
                    state=world,
                    receipt=_receipt(f"req-{n:04d}"),
                )

        async with h.session() as session:
            rows = (
                (
                    await session.execute(
                        select(SandboxCareerRequestModel.request_id)
                        .where(SandboxCareerRequestModel.career_id == career_id)
                        .order_by(SandboxCareerRequestModel.id)
                    )
                )
                .scalars()
                .all()
            )

        assert len(rows) == RECEIPT_KEEP
        # 남은 것이 **최신** 여덟이다 — 앞의 넷이 떨어졌다.
        assert list(rows) == [f"req-{n:04d}" for n in range(4, RECEIPT_KEEP + 4)]


@pytest.mark.asyncio
async def test_pruning_is_scoped_to_one_career() -> None:
    """상한은 커리어당이다. 한 커리어의 쓰기가 다른 커리어의 영수증을 지우면 안 된다."""
    async with _harness() as h:
        first = await _career(h, seed=11)
        second = await _career(h, seed=12)
        world = _world()

        async with h.repo() as repo:
            await repo.save(
                user_id=h.user_id,
                career_id=first,
                state=world,
                receipt=_receipt("keep-me"),
            )
        for n in range(RECEIPT_KEEP + 3):
            async with h.repo() as repo:
                await repo.save(
                    user_id=h.user_id,
                    career_id=second,
                    state=world,
                    receipt=_receipt(f"other-{n:04d}"),
                )

        async with h.repo() as repo:
            survived = await repo.find_receipt(
                user_id=h.user_id, career_id=first, request_id="keep-me"
            )
        assert survived is not None


# ── 2. FOR UPDATE 가 실제로 멈춘다 ────────────────────────────────


@pytest.mark.asyncio
async def test_a_second_locked_read_waits_for_the_first_transaction() -> None:
    """**이것이 가짜로 흉내 낼 수 없는 바로 그것이다.**

    잠금이 없으면 두 요청이 같은 주차를 읽고 둘 다 쓴다(잃어버린 갱신). 멱등 키는
    **같은** 요청의 재전송만 막으므로 이 자리를 대신하지 못한다.
    """
    async with _harness() as h:
        career_id = await _career(h)

        async with h.session() as first:
            held = SandboxCareerPgRepository(first)
            assert (
                await held.load_for_update(user_id=h.user_id, career_id=career_id)
            ) is not None

            async def second_read() -> WorldState | None:
                async with h.session() as other:
                    return await SandboxCareerPgRepository(other).load_for_update(
                        user_id=h.user_id, career_id=career_id
                    )

            waiting = asyncio.create_task(second_read())
            # 첫 트랜잭션이 열려 있는 동안에는 끝나지 못한다.
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.shield(waiting), timeout=_BLOCK_WAIT)

            # 잠금을 풀면 통과한다.
            await first.commit()
            assert (await asyncio.wait_for(waiting, timeout=10)) is not None


@pytest.mark.asyncio
async def test_a_plain_read_does_not_wait() -> None:
    """읽기 전용 조회는 잠그지 않는다 — 대시보드가 쓰기 뒤에 줄 서면 안 된다."""
    async with _harness() as h:
        career_id = await _career(h)

        async with h.session() as first:
            await SandboxCareerPgRepository(first).load_for_update(
                user_id=h.user_id, career_id=career_id
            )

            async with h.session() as other:
                plain = await asyncio.wait_for(
                    SandboxCareerPgRepository(other).load(
                        user_id=h.user_id, career_id=career_id
                    ),
                    timeout=_BLOCK_WAIT,
                )
            assert plain is not None
            await first.rollback()


# ── 3·4. 고유 제약과 그 뒤의 롤백 ─────────────────────────────────


@pytest.mark.asyncio
async def test_a_duplicate_receipt_raises_and_rolls_the_save_back() -> None:
    """같은 (user, career, request) 는 DB 가 거부한다 — 그리고 **세이브도 안 바뀐다.**"""
    async with _harness() as h:
        career_id = await _career(h)
        first_state = _world()

        async with h.repo() as repo:
            await repo.save(
                user_id=h.user_id,
                career_id=career_id,
                state=first_state,
                receipt=_receipt("same-key"),
            )

        # 두 번째가 **다른 상태**를 쓰려 한다. 거부되면 그 상태도 남지 않아야 한다.
        moved = engine.advance_week(first_state, balance=_BALANCE).state
        assert moved.week != first_state.week

        async with h.repo() as repo:
            with pytest.raises(DuplicateRequestError):
                await repo.save(
                    user_id=h.user_id,
                    career_id=career_id,
                    state=moved,
                    receipt=_receipt("same-key"),
                )

        # 원자성: 거울 칼럼과 JSON 둘 다 첫 상태다.
        async with h.session() as session:
            row = (
                await session.execute(
                    select(SandboxCareerModel).where(SandboxCareerModel.id == career_id)
                )
            ).scalar_one()
            assert row.week == first_state.week
            assert row.season == first_state.season
            assert row.world["week"] == first_state.week

        # 그리고 최초 영수증을 다시 읽을 수 있다 — 호출자가 그 응답을 재생한다.
        async with h.repo() as repo:
            stored = await repo.find_receipt(
                user_id=h.user_id, career_id=career_id, request_id="same-key"
            )
        assert stored is not None
        assert stored.response == {"week": 1}


@pytest.mark.asyncio
async def test_concurrent_identical_receipts_let_exactly_one_through() -> None:
    """잠금을 **일부러 건너뛴** 동시 쓰기. 남는 방어선이 고유 제약뿐인 경로다."""
    async with _harness() as h:
        career_id = await _career(h)
        world = _world()

        async def write() -> str:
            async with h.repo() as repo:
                try:
                    await repo.save(
                        user_id=h.user_id,
                        career_id=career_id,
                        state=world,
                        receipt=_receipt("race-key"),
                    )
                except DuplicateRequestError:
                    return "rejected"
                return "applied"

        results = await asyncio.gather(write(), write())

        assert sorted(results) == ["applied", "rejected"]
        async with h.session() as session:
            count = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM sandbox_career_requests "
                        "WHERE career_id = :cid AND request_id = 'race-key'"
                    ),
                    {"cid": career_id},
                )
            ).scalar_one()
        assert count == 1


# ── 5·6. 유스케이스가 진짜 저장소 위에서 멱등한가 ─────────────────


@pytest.mark.asyncio
async def test_the_same_key_replays_the_stored_response() -> None:
    """같은 키·같은 payload → **한 번만 적용되고 같은 답**이 온다."""
    async with _harness() as h:
        career_id = await _career(h)

        async def advance(key: str):
            async with h.repo() as repo:
                return await CareerSandboxInteractor(
                    repository=repo, balance=_BALANCE
                ).advance(user_id=h.user_id, career_id=career_id, request_id=key)

        first = await advance("replay-key-1")
        second = await advance("replay-key-1")

        assert first.replayed is None
        assert first.view is not None
        # **dict 끼리 비교한다.** `body` 는 최초에 DTO · 재시도에 dict 를 주므로 그대로
        # 비교하면 타입이 달라 늘 거짓이다. 영수증에 들어간 것이 `asdict(view)` 다.
        #
        # 그리고 **JSON 을 한 번 왕복시킨 뒤** 비교한다. 영수증 칸은 `JSONB` 라
        # `asdict` 가 낸 tuple(`roster`·`pending`)이 list 로 돌아온다 — 가짜 저장소는
        # 파이썬 객체를 그대로 들고 있어 이 차이를 못 본다. 클라이언트가 받는 것은
        # 양쪽 다 JSON 이므로, **같아야 하는 지점도 JSON 이다.**
        assert second.replayed == json.loads(json.dumps(asdict(first.view)))

        async with h.session() as session:
            week = (
                await session.execute(
                    select(SandboxCareerModel.week).where(
                        SandboxCareerModel.id == career_id
                    )
                )
            ).scalar_one()
        assert week == 2, "재시도가 주차를 한 번만 넘겨야 한다"


@pytest.mark.asyncio
async def test_the_same_key_with_a_different_payload_conflicts() -> None:
    """같은 키에 다른 내용 → 거부(라우터가 409 로 번역한다)."""
    async with _harness() as h:
        career_id = await _career(h)

        async def act(action: str, target: str | None, key: str):
            async with h.repo() as repo:
                return await CareerSandboxInteractor(
                    repository=repo, balance=_BALANCE
                ).act(
                    user_id=h.user_id,
                    career_id=career_id,
                    action=action,
                    target=target,
                    request_id=key,
                )

        await act("훈련", "in_ring", "conflict-key-1")
        with pytest.raises(RequestKeyConflictError):
            await act("훈련", "mic", "conflict-key-1")


@pytest.mark.asyncio
async def test_a_rejected_write_stores_nothing() -> None:
    """도메인이 거부하면 세이브도 영수증도 남지 않는다 — 같은 키를 다시 쓸 수 있다."""
    async with _harness() as h:
        career_id = await _career(h)

        async with h.repo() as repo:
            interactor = CareerSandboxInteractor(repository=repo, balance=_BALANCE)
            with pytest.raises(ValueError):
                await interactor.act(
                    user_id=h.user_id,
                    career_id=career_id,
                    action="없는행동",
                    target=None,
                    request_id="rejected-key-1",
                )

        async with h.repo() as repo:
            assert (
                await repo.find_receipt(
                    user_id=h.user_id,
                    career_id=career_id,
                    request_id="rejected-key-1",
                )
            ) is None


# ── 7. 소유권이 쿼리에 있다 ───────────────────────────────────────


@pytest.mark.asyncio
async def test_a_stranger_sees_nothing_and_cannot_write() -> None:
    """남의 커리어는 `None` 이고 쓰기는 `LookupError` 다 — 403 과 404 를 가르지 않는다."""
    async with _harness() as h:
        career_id = await _career(h)
        stranger = h.user_id + 10_000_000

        async with h.repo() as repo:
            assert (await repo.load(user_id=stranger, career_id=career_id)) is None
            assert (
                await repo.find_receipt(
                    user_id=stranger, career_id=career_id, request_id="x" * 8
                )
            ) is None
            with pytest.raises(LookupError):
                await repo.save(user_id=stranger, career_id=career_id, state=_world())


# ── 8. ON DELETE CASCADE ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_deleting_a_career_takes_its_receipts() -> None:
    """영수증은 세이브에 매달려 있다. 남겨 둘 이유가 없다."""
    async with _harness() as h:
        career_id = await _career(h)

        async with h.repo() as repo:
            await repo.save(
                user_id=h.user_id,
                career_id=career_id,
                state=_world(),
                receipt=_receipt("cascade-key"),
            )

        async with h.session() as session:
            await session.execute(
                delete(SandboxCareerModel).where(SandboxCareerModel.id == career_id)
            )
            await session.commit()

            left = (
                (
                    await session.execute(
                        select(SandboxCareerRequestModel).where(
                            SandboxCareerRequestModel.career_id == career_id
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert left == []


@pytest.mark.asyncio
async def test_deleting_the_user_takes_careers_and_receipts() -> None:
    """회원 탈퇴가 세이브를 데려간다. 고아 세이브가 남으면 소유자 없는 행이 된다."""
    async with _harness() as h:
        career_id = await _career(h)
        async with h.repo() as repo:
            await repo.save(
                user_id=h.user_id,
                career_id=career_id,
                state=_world(),
                receipt=_receipt("user-cascade"),
            )

        async with h.session() as session:
            await session.execute(delete(UserModel).where(UserModel.id == h.user_id))
            await session.commit()

            careers = (
                (
                    await session.execute(
                        select(SandboxCareerModel).where(
                            SandboxCareerModel.user_id == h.user_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            receipts = (
                (
                    await session.execute(
                        select(SandboxCareerRequestModel).where(
                            SandboxCareerRequestModel.career_id == career_id
                        )
                    )
                )
                .scalars()
                .all()
            )

        assert careers == []
        assert receipts == []


# ── 7. 세이브 판본 v1 → v2 가 진짜 JSONB 위에서도 지켜지는가 ───────
#
# 코덱 단위 테스트(`test_career_world_codec_upgrade`)는 파이썬 dict 를 본다. 여기서는
# **JSONB 를 한 번 거친 값**을 본다 — JSONB 는 키 순서를 버리고 튜플을 배열로
# 돌려주며(2026-10-22 실측), 읽기 경로가 실수로 쓰기를 하면 DB 에만 흔적이 남는다.
#
# v1 행은 **배포 전 운영 행의 모양**을 흉내 낸다 — `create` 로 행을 만든 뒤
# `world` 칸을 변경 전 코드가 실제로 쓴 v1 세이브(골든 픽스처 `final_v1`)로 덮는다.

_GOLDEN_PATH = (
    Path(__file__).resolve().parents[3]
    / "domain"
    / "services"
    / "test_career_golden.py"
)

#: 골든 v1 세이브는 52주 시즌으로 만들었다. 인터랙터도 같은 밸런스여야 한다.
_V1_BALANCE = Balance()


def _golden():
    spec = importlib.util.spec_from_file_location("_career_golden_pg", _GOLDEN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _v1_raw() -> dict[str, Any]:
    return _golden().load_fixture()["final_v1"]


async def _put_raw(h: Harness, career_id: int, raw: dict[str, Any]) -> None:
    """`world` 칸을 날것으로 덮는다. **코덱을 거치지 않는다** — 옛 판본 행을 만든다."""
    async with h.session() as session:
        await session.execute(
            update(SandboxCareerModel)
            .where(SandboxCareerModel.id == career_id)
            .values(world=raw)
        )
        await session.commit()


async def _raw(h: Harness, career_id: int) -> tuple[dict[str, Any], str]:
    """DB 에 실제로 있는 값. dict 와 `world::text`(JSONB 정규형) 둘 다."""
    async with h.session() as session:
        row = (
            await session.execute(
                select(SandboxCareerModel.world, text("world::text")).where(
                    SandboxCareerModel.id == career_id
                )
            )
        ).one()
    return row[0], row[1]


async def _v1_career(h: Harness) -> tuple[int, dict[str, Any]]:
    career_id = await _career(h)
    raw = _v1_raw()
    await _put_raw(h, career_id, raw)
    return career_id, raw


@pytest.mark.asyncio
async def test_v1_row_is_stored_and_read_back_as_v1() -> None:
    """출발점 확인 — JSONB 에 넣은 v1 이 값 그대로 남는다(키 순서는 JSONB 가 버린다)."""
    async with _harness() as h:
        career_id, raw = await _v1_career(h)

        stored, _ = await _raw(h, career_id)

        assert stored == raw
        assert stored["version"] == 1


@pytest.mark.asyncio
async def test_reading_a_v1_row_upgrades_in_memory_only() -> None:
    """**조회는 DB 를 바꾸지 않는다.** 저장소 `load` · `load_for_update`(커밋 없이 닫음) ·
    목록 · 유스케이스 `view` · `log` 를 다 지나도 행은 v1 바이트 그대로다."""
    async with _harness() as h:
        career_id, raw = await _v1_career(h)
        _, text_before = await _raw(h, career_id)

        async with h.repo() as repo:
            world = await repo.load(user_id=h.user_id, career_id=career_id)
            locked = await repo.load_for_update(user_id=h.user_id, career_id=career_id)
            await repo.list_for_user(h.user_id)
        async with h.repo() as repo:
            use_case = CareerSandboxInteractor(repository=repo, balance=_V1_BALANCE)
            view = await use_case.view(user_id=h.user_id, career_id=career_id)
            await use_case.log(
                user_id=h.user_id, career_id=career_id, season=None, limit=50, offset=0
            )

        stored, text_after = await _raw(h, career_id)

        assert world is not None and locked == world
        assert view is not None
        # 메모리에서는 v2 칸이 있다.
        assert world.hero.streaks_since is None
        assert world.hero.best_win_streak > 0
        # DB 는 v1 그대로다.
        assert stored["version"] == 1
        assert stored == raw
        assert text_after == text_before


@pytest.mark.asyncio
async def test_first_save_writes_v2_and_keeps_every_v1_field() -> None:
    """같은 세계를 **그대로** 저장하면 DB 에 v2 가 쓰이고, v1 칸은 하나도 안 바뀐다."""
    golden = _golden()
    async with _harness() as h:
        career_id, raw = await _v1_career(h)

        async with h.repo() as repo:
            world = await repo.load_for_update(user_id=h.user_id, career_id=career_id)
            assert world is not None
            await repo.save(user_id=h.user_id, career_id=career_id, state=world)

        stored, _ = await _raw(h, career_id)

        assert stored["version"] == SCHEMA_VERSION == 3
        assert golden.strip_v2(stored) == golden.strip_v2(raw)
        hero = next(w for w in stored["roster"] if w["is_player"])
        assert {"win_streak", "best_win_streak", "streaks_since"} <= set(hero)
        # 부분 집계 표시는 JSON 배열로 들어간다(튜플은 JSONB 에 없다).
        npc_partial = [w for w in stored["roster"] if w["streaks_since"] is not None]
        assert npc_partial
        assert all(isinstance(w["streaks_since"], list) for w in npc_partial)


@pytest.mark.asyncio
async def test_v2_reload_restores_the_same_world_and_resave_is_stable() -> None:
    """저장 → 조회 → 재저장. **같은 `WorldState`, 같은 JSONB** 다."""
    async with _harness() as h:
        career_id, raw = await _v1_career(h)
        expected = decode(copy.deepcopy(raw))

        async with h.repo() as repo:
            first = await repo.load_for_update(user_id=h.user_id, career_id=career_id)
            assert first is not None
            await repo.save(user_id=h.user_id, career_id=career_id, state=first)
        dict_1, text_1 = await _raw(h, career_id)

        async with h.repo() as repo:
            second = await repo.load_for_update(user_id=h.user_id, career_id=career_id)
            assert second is not None
            await repo.save(user_id=h.user_id, career_id=career_id, state=second)
        dict_2, text_2 = await _raw(h, career_id)

        assert first == expected
        assert second == expected
        assert dict_2 == dict_1
        assert text_2 == text_1
        assert json.dumps(dict_2, sort_keys=True, ensure_ascii=False) == json.dumps(
            dict_1, sort_keys=True, ensure_ascii=False
        )


@pytest.mark.asyncio
async def test_a_use_case_write_on_a_v1_row_persists_v2() -> None:
    """실제 쓰기 경로(`_mutate`: 잠금 → 영수증 → 도메인 → 저장)를 지나면 v2 로 남는다.

    결과 세계는 **메모리에서 같은 연산을 한 것과 같다** — 업그레이드가 쓰기 경로에서
    다른 값을 만들지 않는다.
    """
    async with _harness() as h:
        career_id, raw = await _v1_career(h)
        expected = season_rules.start_next_season(
            decode(copy.deepcopy(raw)), balance=_V1_BALANCE
        )

        async with h.repo() as repo:
            outcome = await CareerSandboxInteractor(
                repository=repo, balance=_V1_BALANCE
            ).next_season(
                user_id=h.user_id, career_id=career_id, request_id="phase05-next-1"
            )
        stored, _ = await _raw(h, career_id)
        async with h.repo() as repo:
            reloaded = await repo.load(user_id=h.user_id, career_id=career_id)

        assert outcome.view is not None and outcome.view.season == raw["season"] + 1
        assert stored["version"] == SCHEMA_VERSION
        assert reloaded == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [99, 0, "2", None])
async def test_corrupt_version_row_is_refused_and_left_untouched(version) -> None:
    """모르는 판본은 읽기·쓰기 모두 `CorruptSaveError`. **실패한 쓰기는 행을 안 바꾼다.**"""
    async with _harness() as h:
        career_id, raw = await _v1_career(h)
        broken = {**raw, "version": version}
        await _put_raw(h, career_id, broken)
        _, text_before = await _raw(h, career_id)

        async with h.repo() as repo:
            with pytest.raises(CorruptSaveError):
                await repo.load(user_id=h.user_id, career_id=career_id)
        async with h.repo() as repo:
            with pytest.raises(CorruptSaveError):
                await CareerSandboxInteractor(
                    repository=repo, balance=_V1_BALANCE
                ).next_season(
                    user_id=h.user_id, career_id=career_id, request_id="phase05-bad-1"
                )

        stored, text_after = await _raw(h, career_id)
        assert stored == broken
        assert text_after == text_before


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["win_streak", "best_win_streak", "streaks_since"])
async def test_v2_row_missing_a_new_field_is_refused(key: str) -> None:
    """v2 행에서 새 칸이 빠지면 손상이다 — 기본값으로 메워 읽지 않는다."""
    async with _harness() as h:
        career_id, _ = await _v1_career(h)
        async with h.repo() as repo:
            world = await repo.load_for_update(user_id=h.user_id, career_id=career_id)
            assert world is not None
            await repo.save(user_id=h.user_id, career_id=career_id, state=world)
        stored, _ = await _raw(h, career_id)
        del stored["roster"][0][key]
        await _put_raw(h, career_id, stored)

        async with h.repo() as repo:
            with pytest.raises(CorruptSaveError):
                await repo.load(user_id=h.user_id, career_id=career_id)


# ── 8. 세이브 v3(경기 기록)가 진짜 JSONB 위에서도 지켜지는가 ─────────
#
# v3 는 세이브에 **처음으로 부동소수**(승률 · 경기력 세 항)를 넣는다. JSONB 는 숫자를
# numeric 으로 들고 있다가 돌려주므로, 끝자리까지 같은 float 로 돌아오는지가 여기서
# 처음 검증된다.

_V2_FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "career_golden_v2.json"


def _v2_raw() -> dict[str, Any]:
    return json.loads(_V2_FIXTURE.read_text(encoding="utf-8"))["final_v2"]


@pytest.mark.asyncio
async def test_v3_records_survive_jsonb_bit_for_bit() -> None:
    """골든 궤적의 기록 40건(태그 18건 포함)을 저장하고 다시 읽으면 같은 세계다."""
    golden = _golden()
    _, world = golden.run_trajectory()
    assert len(world.matches) == 40
    async with _harness() as h:
        career_id = await _career(h)
        async with h.repo() as repo:
            await repo.save(user_id=h.user_id, career_id=career_id, state=world)
        stored, text_1 = await _raw(h, career_id)
        async with h.repo() as repo:
            again = await repo.load(user_id=h.user_id, career_id=career_id)
            assert again is not None
            await repo.save(user_id=h.user_id, career_id=career_id, state=again)
        _, text_2 = await _raw(h, career_id)

        assert stored["version"] == SCHEMA_VERSION == 3
        assert again == world
        assert text_2 == text_1
        assert [m.probability for m in again.matches] == [
            m.probability for m in world.matches
        ]
        assert [p.power for m in again.matches for p in m.participants] == [
            p.power for m in world.matches for p in m.participants
        ]


@pytest.mark.asyncio
async def test_v2_row_reads_as_v3_and_first_save_keeps_v2_fields() -> None:
    """v2 행 — 조회는 DB 를 안 바꾸고, 첫 저장이 v3 를 쓰며 v2 칸은 전부 그대로다."""
    async with _harness() as h:
        career_id = await _career(h)
        raw = _v2_raw()
        await _put_raw(h, career_id, raw)
        _, text_before = await _raw(h, career_id)

        async with h.repo() as repo:
            world = await repo.load(user_id=h.user_id, career_id=career_id)
        after_read, text_after_read = await _raw(h, career_id)
        assert world is not None
        assert after_read["version"] == 2 and text_after_read == text_before

        async with h.repo() as repo:
            locked = await repo.load_for_update(user_id=h.user_id, career_id=career_id)
            assert locked is not None
            await repo.save(user_id=h.user_id, career_id=career_id, state=locked)
        stored, _ = await _raw(h, career_id)

        assert stored["version"] == 3
        assert stored["matches"] == []
        assert stored["match_records_since"] == [raw["season"], raw["week"]]
        assert {
            k: v
            for k, v in stored.items()
            if k not in ("version", "matches", "match_records_since")
        } == {k: v for k, v in raw.items() if k != "version"}


@pytest.mark.asyncio
async def test_advancing_through_the_use_case_records_matches_in_jsonb() -> None:
    """유스케이스로 주차를 넘기면 기록이 **같은 커밋**에 들어간다(원자성)."""
    async with _harness() as h:
        career_id = await _career(h)
        async with h.repo() as repo:
            use_case = CareerSandboxInteractor(repository=repo, balance=_BALANCE)
            for i in range(_BALANCE.season_weeks):
                await use_case.advance(
                    user_id=h.user_id, career_id=career_id, request_id=f"p0-adv-{i:04d}"
                )
        stored, _ = await _raw(h, career_id)
        async with h.repo() as repo:
            world = await repo.load(user_id=h.user_id, career_id=career_id)
        assert world is not None

        played = [e for e in world.log if e.kind == "match"]
        assert len(stored["matches"]) == len(played) == len(world.matches) >= 1
        assert stored["match_records_since"] is None
