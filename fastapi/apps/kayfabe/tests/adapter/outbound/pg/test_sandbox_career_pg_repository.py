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
import json
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from core.entities.user_model import UserModel
from kayfabe.adapter.outbound.orm.career_sandbox_orm import (
    SandboxCareerModel,
    SandboxCareerRequestModel,
)
from kayfabe.adapter.outbound.pg.sandbox_career_pg_repository import (
    SandboxCareerPgRepository,
)
from kayfabe.app.ports.input.career_sandbox_use_case import RequestKeyConflictError
from kayfabe.app.ports.output.sandbox_career_repository import (
    RECEIPT_KEEP,
    DuplicateRequestError,
    RequestReceipt,
)
from kayfabe.app.use_cases.career_sandbox_interactor import CareerSandboxInteractor
from kayfabe.domain.services import career_engine as engine
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
