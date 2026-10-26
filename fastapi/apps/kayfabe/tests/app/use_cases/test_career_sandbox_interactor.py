"""커리어 샌드박스 조립. **규칙이 아니라 쓰기 경로를 본다.**

수치·판정은 도메인 테스트가 본다(`test_career_engine` · `test_career_season` ·
`test_career_retirement`). 여기서 고정하는 것은 유스케이스가 지켜야 할 다섯이다:

1. **쓰기는 잠그고 읽는다** — `load_for_update` 를 거치지 않는 쓰기 경로가 생기면
   동시 요청 둘이 같은 주차를 읽고 둘 다 쓴다(잃어버린 갱신).
2. **같은 요청 키는 한 번만 적용된다** — 잠금과 도메인 키가 못 막는 자리다.
   영수증 조회가 **잠금 뒤**에 있어야 동시 요청이 갈린다.
3. **실패는 아무것도 저장하지 않는다** — 도메인이 `ValueError` 를 내면 세이브도
   영수증도 그대로여야 한다. 포인트만 깎인 세이브가 남으면 사용자가 손해를 본다.
4. **소유권은 저장 계층이 지킨다** — 남의 커리어는 `None` 이고, 그 `None` 이
   유스케이스를 지나 404 가 된다. 영수증도 같은 범위로 갈린다.
5. **단계 오류 문구가 라우터의 409 분기와 맞는다** — 문구가 바뀌면 화면이
   "결산 버튼을 보여라" 와 "입력을 고쳐라" 를 구별하지 못한다.

## 가짜가 어디까지 진짜인가

`FakeRepository` 는 **고유 제약과 잠금 순서를 흉내 낸다** — 같은 (user, career,
request) 를 두 번 넣으면 `DuplicateRequestError` 를 내고, 영수증 조회는 잠금
뒤에만 의미가 있다. 흉내 내지 **못하는** 것은 트랜잭션 원자성과 진짜 행 잠금이다.
그 둘은 격리 PostgreSQL + 실제 HTTP 로 따로 쟀다(보고서의 §9 참조).
"""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import fields
from datetime import UTC, datetime

import pytest

from kayfabe.app.dtos.career_sandbox_dto import CareerViewDto
from kayfabe.app.ports.input.career_sandbox_use_case import RequestKeyConflictError
from kayfabe.app.ports.output.sandbox_career_repository import (
    RECEIPT_KEEP,
    CareerRow,
    DuplicateRequestError,
    RequestReceipt,
)
from kayfabe.app.use_cases.career_sandbox_interactor import CareerSandboxInteractor
from kayfabe.domain.services.career_world import Balance, Phase, WorldState

#: 라우터가 409 로 가르는 말머리. **복사본이 아니라 대조 대상이다** — 라우터의
#: `_PHASE_HINTS` 와 어긋나면 이 테스트가 깨져야 한다.
_PHASE_HINTS = ("단계가 아닙니다", "결산이 먼저", "다음 시즌을 시작할 수 없습니다")

_OWNER = 7
_STRANGER = 99

#: 짧은 시즌. 52주를 돌리지 않고 시즌 경계를 본다.
_BALANCE = Balance(season_weeks=3)

_counter = itertools.count(1)


def _rid(name: str = "k") -> str:
    """서로 **다른** 의도를 뜻하는 새 요청 키.

    기본값이 매번 새 키인 것은 의도다 — 멱등성을 보는 테스트만 키를 고정해서
    넘기므로, 키를 빼먹은 테스트가 조용히 중복 테스트가 되지 않는다.
    """
    return f"req-{name}-{next(_counter):04d}"


class FakeRepository:
    """세이브 한 칸을 들고 있는 가짜. **잠금 여부와 영수증을 기록한다.**"""

    def __init__(self) -> None:
        self.saves: dict[int, WorldState] = {}
        self.owner: dict[int, int] = {}
        self.reads: list[str] = []
        self.writes = 0
        #: `(user_id, career_id, request_id)` → 영수증. 키가 고유 제약이다.
        self.receipts: dict[tuple[int, int, str], RequestReceipt] = {}
        #: 영수증 조회가 **잠금 뒤**에 왔는지 본다.
        self.calls: list[str] = []
        self._next_id = 1

    async def create(
        self, *, user_id: int, player_name: str, seed: int, state: WorldState
    ) -> int:
        career_id = self._next_id
        self._next_id += 1
        self.saves[career_id] = state
        self.owner[career_id] = user_id
        return career_id

    async def list_for_user(self, user_id: int) -> list[CareerRow]:
        now = datetime(2026, 10, 21, tzinfo=UTC)
        return [
            CareerRow(
                id=cid,
                player_name=state.player,
                season=state.season,
                week=state.week,
                phase=str(state.phase),
                seed=state.seed,
                created_at=now,
                updated_at=now,
            )
            for cid, state in self.saves.items()
            if self.owner[cid] == user_id
        ]

    async def load(self, *, user_id: int, career_id: int) -> WorldState | None:
        self.reads.append("plain")
        self.calls.append("load")
        return self._mine(user_id=user_id, career_id=career_id)

    async def load_for_update(
        self, *, user_id: int, career_id: int
    ) -> WorldState | None:
        self.reads.append("locked")
        self.calls.append("lock")
        return self._mine(user_id=user_id, career_id=career_id)

    async def find_receipt(
        self, *, user_id: int, career_id: int, request_id: str
    ) -> RequestReceipt | None:
        self.calls.append("receipt")
        # **일부러 양보한다.** 가짜는 행 잠금을 흉내 내지 못하므로, 여기서 넘기지
        # 않으면 `asyncio.gather` 로 띄운 두 코루틴이 **차례로** 끝까지 돌아 동시
        # 요청 테스트가 조용히 순차 테스트가 된다(가짜 메서드에 진짜 await 가 없어
        # 코루틴이 멈출 자리가 없다). 여기서 넘기면 둘이 모두 "영수증 없음" 을 보고
        # 둘 다 적용을 시도하는 **최악의 순서**가 되고, 그걸 막는 것은 고유
        # 제약뿐이다 — 잠금이 풀린 경우까지 덮는 더 강한 조건이다.
        #
        # **읽은 뒤에** 양보한다. 순서가 뒤집히면(양보 → 읽기) 둘째가 첫째의 커밋을
        # 보게 되어 다시 순차 경로가 된다 — 실측으로 그랬다.
        if self._mine(user_id=user_id, career_id=career_id) is None:
            return None
        found = self.receipts.get((user_id, career_id, request_id))
        await asyncio.sleep(0)
        return found

    async def save(
        self,
        *,
        user_id: int,
        career_id: int,
        state: WorldState,
        receipt: RequestReceipt | None = None,
    ) -> None:
        if self._mine(user_id=user_id, career_id=career_id) is None:
            raise LookupError("커리어를 찾을 수 없습니다")
        if receipt is not None:
            scope = (user_id, career_id, receipt.request_id)
            if scope in self.receipts:
                # 고유 제약이 잡은 것과 같다. **세이브도 쓰지 않는다** — 진짜
                # 어댑터는 롤백하므로 여기서도 아무것도 바꾸지 않아야 한다.
                raise DuplicateRequestError(receipt.request_id)
            self.receipts[scope] = receipt
            self._prune(career_id)
        self.writes += 1
        self.saves[career_id] = state
        self.calls.append("save")

    def _prune(self, career_id: int) -> None:
        """보존 상한. 진짜 어댑터는 `id` 로 자르고 여기서는 삽입 순서로 자른다."""
        mine = [k for k in self.receipts if k[1] == career_id]
        for stale in mine[: max(0, len(mine) - RECEIPT_KEEP)]:
            del self.receipts[stale]

    def _mine(self, *, user_id: int, career_id: int) -> WorldState | None:
        if self.owner.get(career_id) != user_id:
            return None
        return self.saves.get(career_id)


async def _started() -> tuple[FakeRepository, CareerSandboxInteractor, int]:
    repository = FakeRepository()
    interactor = CareerSandboxInteractor(repository=repository, balance=_BALANCE)
    view = await interactor.create(
        user_id=_OWNER, name="Ho", style="테크니션", age=24, seed=11
    )
    repository.reads.clear()
    repository.calls.clear()
    return repository, interactor, view.id


# ── 쓰기 다섯을 부르는 헬퍼. `request_id` 를 빼먹을 수 없게 한다 ──────


def _only(outcome) -> CareerViewDto:
    """새로 처리된 결과. 재시도(`replayed`)였으면 테스트가 깨진다."""
    assert outcome.replayed is None, "재시도로 처리됐다 — 새 키를 기대한 자리다"
    assert outcome.view is not None
    return outcome.view


async def _act(
    interactor: CareerSandboxInteractor,
    career_id: int,
    action: str,
    *,
    target: str | None = None,
    user_id: int = _OWNER,
    key: str | None = None,
):
    return await interactor.act(
        user_id=user_id,
        career_id=career_id,
        action=action,
        target=target,
        request_id=key or _rid("act"),
    )


async def _advance(
    interactor: CareerSandboxInteractor,
    career_id: int,
    *,
    user_id: int = _OWNER,
    key: str | None = None,
):
    return await interactor.advance(
        user_id=user_id, career_id=career_id, request_id=key or _rid("adv")
    )


async def _settle(
    interactor: CareerSandboxInteractor,
    career_id: int,
    *,
    user_id: int = _OWNER,
    key: str | None = None,
):
    return await interactor.settle(
        user_id=user_id, career_id=career_id, request_id=key or _rid("settle")
    )


async def _next_season(
    interactor: CareerSandboxInteractor,
    career_id: int,
    *,
    user_id: int = _OWNER,
    key: str | None = None,
):
    return await interactor.next_season(
        user_id=user_id, career_id=career_id, request_id=key or _rid("next")
    )


# ── 생성·조회 ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_stores_the_save_and_returns_the_dashboard() -> None:
    repository, _, career_id = await _started()

    assert career_id in repository.saves
    assert repository.saves[career_id].player == "Ho"


@pytest.mark.asyncio
async def test_season_weeks_comes_from_balance_not_a_constant() -> None:
    """화면이 `2 / 3` 를 **서버 값으로** 적는다. 52를 프론트에 박지 않기 위해서다."""
    _, interactor, career_id = await _started()

    view = await interactor.view(user_id=_OWNER, career_id=career_id)

    assert view is not None
    assert view.season_weeks == _BALANCE.season_weeks
    assert view.max_action_points == _BALANCE.action_points


@pytest.mark.asyncio
async def test_seed_is_stored_so_the_world_survives_reconnect() -> None:
    repository, _, career_id = await _started()

    assert repository.saves[career_id].seed == 11


@pytest.mark.asyncio
async def test_a_seedless_create_still_stores_a_seed() -> None:
    """시드를 안 주면 서버가 만들어 **저장한다** — 재접속해도 같은 세계여야 한다.

    화면은 시드 칸 없이 만들기 때문에 이 경로가 기본값이다.
    """
    repository = FakeRepository()
    interactor = CareerSandboxInteractor(repository=repository, balance=_BALANCE)

    view = await interactor.create(user_id=_OWNER, name="Ho", style="파워", age=24)

    assert isinstance(repository.saves[view.id].seed, int)


@pytest.mark.asyncio
async def test_risk_has_a_band_and_reasons_but_no_score() -> None:
    """점수 칸이 없다 — 검증되지 않은 퍼센트를 화면에 흘리지 않기 위해서다."""
    _, interactor, career_id = await _started()

    view = await interactor.view(user_id=_OWNER, career_id=career_id)

    assert view is not None
    assert view.player.risk is not None
    assert view.player.risk.band
    names = {f.name for f in fields(view.player.risk)}
    assert names == {"band", "reasons"}


@pytest.mark.asyncio
async def test_npcs_carry_no_risk_band() -> None:
    """위험 평가는 플레이어만 내보낸다. 로스터 전원에 붙이면 화면이 못 쓸 소음이 된다."""
    _, interactor, career_id = await _started()

    view = await interactor.view(user_id=_OWNER, career_id=career_id)

    assert view is not None
    assert view.roster
    assert all(w.risk is None for w in view.roster)


@pytest.mark.asyncio
async def test_list_only_returns_my_careers() -> None:
    repository = FakeRepository()
    interactor = CareerSandboxInteractor(repository=repository, balance=_BALANCE)
    await interactor.create(user_id=_OWNER, name="Ho", style="파워", age=24, seed=1)
    await interactor.create(user_id=_STRANGER, name="Dex", style="파워", age=24, seed=2)

    mine = await interactor.list_careers(_OWNER)

    assert [row.player_name for row in mine] == ["Ho"]


# ── 소유권 ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_strangers_view_is_none_not_an_error() -> None:
    """**있는지 없는지 알려 주지 않는다.** 구별하면 id 의 존재가 새어 나간다."""
    _, interactor, career_id = await _started()

    assert await interactor.view(user_id=_STRANGER, career_id=career_id) is None


@pytest.mark.asyncio
async def test_stranger_cannot_advance_someone_elses_career() -> None:
    repository, interactor, career_id = await _started()
    before = repository.saves[career_id]

    with pytest.raises(LookupError):
        await _advance(interactor, career_id, user_id=_STRANGER)

    assert repository.saves[career_id] is before
    assert repository.writes == 0


# ── 쓰기 경로 ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_every_write_locks_the_row_first() -> None:
    """쓰기 넷이 전부 잠긴 읽기를 거친다. **멱등 키만으로는 경쟁을 막지 못한다.**"""
    repository, interactor, career_id = await _started()

    await _act(interactor, career_id, "프로모")
    await _advance(interactor, career_id)
    await _advance(interactor, career_id)
    await _advance(interactor, career_id)
    await _settle(interactor, career_id)
    await _next_season(interactor, career_id)

    assert repository.reads == ["locked"] * 6


@pytest.mark.asyncio
async def test_read_paths_do_not_lock() -> None:
    repository, interactor, career_id = await _started()

    await interactor.view(user_id=_OWNER, career_id=career_id)
    await interactor.log(
        user_id=_OWNER, career_id=career_id, season=None, limit=10, offset=0
    )

    assert repository.reads == ["plain", "plain"]


@pytest.mark.asyncio
async def test_action_spends_a_point_and_the_server_decides_the_effect() -> None:
    repository, interactor, career_id = await _started()
    before = repository.saves[career_id].hero.popularity

    view = _only(await _act(interactor, career_id, "프로모"))

    assert view.action_points == _BALANCE.action_points - 1
    assert view.player.popularity > before


@pytest.mark.asyncio
async def test_a_rejected_action_saves_nothing() -> None:
    """포인트만 깎인 세이브가 남지 않는다 — 검증이 쓰기보다 앞선다."""
    repository, interactor, career_id = await _started()
    before = repository.saves[career_id]

    with pytest.raises(ValueError):
        await _act(interactor, career_id, "춤")

    assert repository.saves[career_id] is before
    assert repository.writes == 0
    # **영수증도 남지 않는다** — 실패를 성공으로 재사용하지 않기 위해서다.
    assert repository.receipts == {}


@pytest.mark.asyncio
async def test_training_needs_a_known_stat() -> None:
    _, interactor, career_id = await _started()

    with pytest.raises(ValueError, match="훈련 대상"):
        await _act(interactor, career_id, "훈련", target="춤솜씨")


@pytest.mark.asyncio
async def test_points_run_out_within_a_week() -> None:
    _, interactor, career_id = await _started()
    for _ in range(_BALANCE.action_points):
        await _act(interactor, career_id, "프로모")

    with pytest.raises(ValueError, match="행동 포인트"):
        await _act(interactor, career_id, "프로모")


@pytest.mark.asyncio
async def test_advance_returns_the_week_report() -> None:
    """화면이 "그 주에 무슨 일이 있었나" 를 쓰려면 보고가 응답에 있어야 한다."""
    _, interactor, career_id = await _started()

    view = _only(await _advance(interactor, career_id))

    assert view.week == 2
    assert view.last_report is not None
    assert view.last_report.week == 1


@pytest.mark.asyncio
async def test_a_fresh_career_has_no_report_yet() -> None:
    _, interactor, career_id = await _started()

    view = await interactor.view(user_id=_OWNER, career_id=career_id)

    assert view is not None
    assert view.last_report is None


# ── 단계 ──────────────────────────────────────────────────────────


async def _to_settlement(interactor: CareerSandboxInteractor, career_id: int) -> None:
    for _ in range(_BALANCE.season_weeks):
        await _advance(interactor, career_id)


@pytest.mark.asyncio
async def test_season_end_blocks_advance_with_a_409_shaped_message() -> None:
    _, interactor, career_id = await _started()
    await _to_settlement(interactor, career_id)

    with pytest.raises(ValueError) as caught:
        await _advance(interactor, career_id)

    assert any(hint in str(caught.value) for hint in _PHASE_HINTS)


@pytest.mark.asyncio
async def test_settle_before_the_season_ends_is_a_phase_error() -> None:
    _, interactor, career_id = await _started()

    with pytest.raises(ValueError) as caught:
        await _settle(interactor, career_id)

    assert any(hint in str(caught.value) for hint in _PHASE_HINTS)


@pytest.mark.asyncio
async def test_next_season_before_settlement_is_a_phase_error() -> None:
    _, interactor, career_id = await _started()
    await _to_settlement(interactor, career_id)

    with pytest.raises(ValueError) as caught:
        await _next_season(interactor, career_id)

    assert any(hint in str(caught.value) for hint in _PHASE_HINTS)


@pytest.mark.asyncio
async def test_settle_then_next_season_returns_to_week_one() -> None:
    _, interactor, career_id = await _started()
    await _to_settlement(interactor, career_id)

    settled = _only(await _settle(interactor, career_id))
    started = _only(await _next_season(interactor, career_id))

    assert settled.phase == Phase.OFFSEASON
    assert len(settled.seasons) == 1
    assert (started.season, started.week) == (2, 1)
    assert started.phase == Phase.IN_SEASON


@pytest.mark.asyncio
async def test_settlement_is_idempotent_across_calls() -> None:
    """같은 결산을 두 번 불러도 시즌 장이 하나다 — 나이도 한 번만 오른다.

    **요청 키를 서로 다르게 준다.** 같은 키면 영수증이 막아서 도메인의 멱등 키를
    못 보게 된다 — 여기서 보려는 것은 그 아래층(`career_season` 의 `applied`)이다.
    """
    _, interactor, career_id = await _started()
    await _to_settlement(interactor, career_id)

    first = _only(await _settle(interactor, career_id))
    second = _only(await _settle(interactor, career_id))

    assert len(first.seasons) == len(second.seasons) == 1
    assert first.player.age == second.player.age


# ── 기록 ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_log_is_newest_first_and_pages() -> None:
    _, interactor, career_id = await _started()
    await _to_settlement(interactor, career_id)

    page = await interactor.log(
        user_id=_OWNER, career_id=career_id, season=None, limit=2, offset=0
    )
    nxt = await interactor.log(
        user_id=_OWNER, career_id=career_id, season=None, limit=2, offset=2
    )

    assert [e.week for e in page] == sorted((e.week for e in page), reverse=True)
    assert page and nxt
    assert page[-1].week >= nxt[0].week


@pytest.mark.asyncio
async def test_log_can_be_filtered_by_season() -> None:
    _, interactor, career_id = await _started()
    await _to_settlement(interactor, career_id)
    await _settle(interactor, career_id)
    await _next_season(interactor, career_id)
    await _advance(interactor, career_id)

    season_two = await interactor.log(
        user_id=_OWNER, career_id=career_id, season=2, limit=50, offset=0
    )

    assert season_two
    assert {e.season for e in season_two} == {2}


@pytest.mark.asyncio
async def test_log_of_a_missing_career_raises() -> None:
    _, interactor, career_id = await _started()

    with pytest.raises(LookupError):
        await interactor.log(
            user_id=_STRANGER, career_id=career_id, season=None, limit=10, offset=0
        )


@pytest.mark.asyncio
async def test_dashboard_keeps_the_recent_log_short() -> None:
    """긴 기록이 대시보드를 점령하지 않는다 — 전체는 `/log` 로 따로 읽는다."""
    from kayfabe.app.use_cases.career_sandbox_interactor import RECENT_LOG

    _, interactor, career_id = await _started()
    await _to_settlement(interactor, career_id)

    view = await interactor.view(user_id=_OWNER, career_id=career_id)

    assert view is not None
    assert len(view.recent_log) <= RECENT_LOG


@pytest.mark.asyncio
async def test_view_marks_boiling_rivalries_so_the_screen_need_not_know_the_threshold() -> (
    None
):
    """`feud` 가 라이벌을 가른다. **`kind` 로는 못 가른다.**

    `after_match` 가 경기마다 진 쪽을 라이벌 kind 로 올리므로, 화면이 그 칸으로
    라이벌전을 세면 상대 거의 전원이 걸린다(실측으로 경기 30건 중 30건이 걸렸다).
    임계값(`FEUD_HEAT`)을 화면에 복사하는 대신 판정을 내보내는 이유가 이것이다 —
    서버 설정을 바꿨을 때 화면만 거짓말하는 길을 막는다.
    """
    from kayfabe.domain.services import career_relations as relations
    from kayfabe.domain.services.career_world import RelationKind

    repository, interactor, career_id = await _started()
    state = repository.saves[career_id]
    hero = state.hero.name
    cool = state.roster[1].name
    hot = state.roster[2].name
    state = relations.upsert(
        state,
        a=hero,
        b=cool,
        kind=RelationKind.RIVAL,
        heat_delta=relations.FEUD_HEAT - 1,
        week=1,
    )
    state = relations.upsert(
        state,
        a=hero,
        b=hot,
        kind=RelationKind.RIVAL,
        heat_delta=relations.FEUD_HEAT,
        week=1,
    )
    repository.saves[career_id] = state

    view = await interactor.view(user_id=_OWNER, career_id=career_id)

    assert view is not None
    by_other = {r.b: r for r in view.relationships if r.a == hero}
    # 둘 다 라이벌 kind 다 — 그래서 kind 만으로는 갈리지 않는다.
    assert by_other[cool].kind == str(RelationKind.RIVAL)
    assert by_other[hot].kind == str(RelationKind.RIVAL)
    # 갈리는 것은 `feud` 하나다.
    assert by_other[cool].feud is False
    assert by_other[hot].feud is True


# ── 중복·동시 요청 ────────────────────────────────────────────────
#
# **아래는 "지금 이렇게 동작한다" 가 아니라 "이렇게 동작해야 한다" 를 고정한다.**
#
# 2026-10-21 에 실제 스택(격리 PostgreSQL + 두 FastAPI 프로세스 + httpx)으로 네
# 경우를 재서 **전부 중복 적용**되는 것을 먼저 확인했다:
#
#     A /actions 순차 2회 : 포인트 2→0 · 인기도 +6 (두 번 적용)
#     B /actions 동시 2개 : 같음 — 행 잠금은 중복을 막지 못한다
#     C /advance 순차 2회 : 주차 1→3
#     D /advance 동시 2개 : 주차 1→3
#
# 원인은 둘이다. 행 잠금(`load_for_update`)은 **잃어버린 갱신**을 막을 뿐 두 요청이
# 같은 연산인지 모른다. 도메인의 멱등 키도 못 막는다 — 행동 키의 순번이 남은
# 포인트에서 나와서(`slot = 최대 - 남음`) 재시도가 **다음 순번**을 쓴다.
#
# 그 빈칸을 메우는 것이 **클라이언트가 만든 요청 키**다. 아래 테스트들이 그 계약을
# 고정한다 — 앞 판본의 경보 넷은 기대값을 뒤집어 여기 흡수됐다.


@pytest.mark.asyncio
async def test_repeating_the_same_action_applies_it_once() -> None:
    """A. 응답을 못 받아 다시 눌러도 **한 번만 적용된다.**"""
    repository, interactor, career_id = await _started()
    before = await interactor.view(user_id=_OWNER, career_id=career_id)
    assert before is not None
    key = "req-same-action"

    first = await _act(interactor, career_id, "프로모", key=key)
    second = await _act(interactor, career_id, "프로모", key=key)

    after = await interactor.view(user_id=_OWNER, career_id=career_id)
    assert after is not None
    assert after.action_points == before.action_points - 1
    # 둘째는 세이브까지 가지 않았다.
    assert repository.writes == 1
    # 그리고 **최초 응답의 본문**을 그대로 받았다.
    assert second.replayed is not None
    assert second.replayed["action_points"] == _only(first).action_points
    assert second.replayed["player"]["popularity"] == _only(first).player.popularity


@pytest.mark.asyncio
async def test_concurrent_identical_actions_apply_once() -> None:
    """B. 더블클릭(동시 두 요청)도 **한 번만 적용된다.**

    가짜가 `find_receipt` 에서 양보하므로(위 주석) 둘 다 "영수증 없음" 을 보고 둘 다
    적용을 시도한다 — **잠금이 전혀 없는 최악의 순서**다. 여기서 통과하는 관문은
    고유 제약(`DuplicateRequestError`)이고, 그 경로도 예외가 아니라 재시도 응답으로
    끝나야 한다. 진짜 행 잠금 경로는 격리 PostgreSQL + 실제 HTTP 로 따로 쟀다.
    """
    repository, interactor, career_id = await _started()
    before = await interactor.view(user_id=_OWNER, career_id=career_id)
    assert before is not None
    key = "req-concurrent-action"

    results = await asyncio.gather(
        _act(interactor, career_id, "프로모", key=key),
        _act(interactor, career_id, "프로모", key=key),
    )

    after = await interactor.view(user_id=_OWNER, career_id=career_id)
    assert after is not None
    assert after.action_points == before.action_points - 1
    assert repository.writes == 1
    # 둘 중 하나는 새로 처리되고 하나는 재시도로 갈린다 — **둘 다 200 이다.**
    assert sum(r.replayed is not None for r in results) == 1


@pytest.mark.asyncio
async def test_repeating_advance_moves_one_week() -> None:
    """C. 같은 키로 주차 진행을 두 번 보내면 **한 주만 간다.**"""
    _, interactor, career_id = await _started()
    before = await interactor.view(user_id=_OWNER, career_id=career_id)
    assert before is not None
    key = "req-same-advance"

    first = await _advance(interactor, career_id, key=key)
    second = await _advance(interactor, career_id, key=key)

    after = await interactor.view(user_id=_OWNER, career_id=career_id)
    assert after is not None
    assert after.week == before.week + 1
    # 재시도도 **그 주의 보고**를 받는다. 세이브에 없는 값이라 영수증에 담겨 있다.
    assert second.replayed is not None
    assert second.replayed["last_report"]["week"] == before.week
    assert _only(first).last_report is not None


@pytest.mark.asyncio
async def test_concurrent_advances_move_one_week() -> None:
    """D. 동시 두 요청도 **한 주만 간다.**"""
    repository, interactor, career_id = await _started()
    key = "req-concurrent-advance"

    results = await asyncio.gather(
        _advance(interactor, career_id, key=key),
        _advance(interactor, career_id, key=key),
    )

    after = await interactor.view(user_id=_OWNER, career_id=career_id)
    assert after is not None
    assert after.week == 2
    assert repository.writes == 1
    assert sum(r.replayed is not None for r in results) == 1


@pytest.mark.asyncio
async def test_the_row_lock_is_taken_before_the_receipt_is_read() -> None:
    """**순서가 규칙이다.** 영수증을 잠금 앞에서 읽으면 동시 요청 둘이 다 통과한다."""
    repository, interactor, career_id = await _started()

    await _act(interactor, career_id, "프로모")

    assert repository.calls == ["lock", "receipt", "save"]


@pytest.mark.asyncio
async def test_a_replay_touches_the_save_only_to_lock_it() -> None:
    """재시도는 **쓰기로 가지 않는다** — 잠그고 영수증을 보고 끝난다."""
    repository, interactor, career_id = await _started()
    key = "req-replay-shape"
    await _act(interactor, career_id, "프로모", key=key)
    repository.calls.clear()

    await _act(interactor, career_id, "프로모", key=key)

    assert repository.calls == ["lock", "receipt"]


# ── 같은 키 · 다른 payload ────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_same_key_with_a_different_action_is_rejected() -> None:
    """돌려줄 응답이 다른 요청의 것이다 — 통과시키면 하지 않은 행동의 답을 받는다."""
    repository, interactor, career_id = await _started()
    key = "req-clashing"
    await _act(interactor, career_id, "프로모", key=key)

    with pytest.raises(RequestKeyConflictError):
        await _act(interactor, career_id, "휴식", key=key)

    assert repository.writes == 1


@pytest.mark.asyncio
async def test_the_same_key_with_a_different_target_is_rejected() -> None:
    """지문이 행동 코드만 보면 `훈련:mic` 과 `훈련:stamina` 가 같아진다."""
    _, interactor, career_id = await _started()
    key = "req-clashing-target"
    await _act(interactor, career_id, "훈련", target="mic", key=key)

    with pytest.raises(RequestKeyConflictError):
        await _act(interactor, career_id, "훈련", target="stamina", key=key)


@pytest.mark.asyncio
async def test_the_same_key_on_a_different_operation_is_rejected() -> None:
    """**연산 이름이 지문에 들어간다.** 빼면 payload 가 빈 쓰기 셋이 서로 섞인다."""
    _, interactor, career_id = await _started()
    key = "req-cross-operation"
    await _advance(interactor, career_id, key=key)

    with pytest.raises(RequestKeyConflictError):
        await _settle(interactor, career_id, key=key)


@pytest.mark.asyncio
async def test_an_empty_request_key_is_a_value_error() -> None:
    """라우터가 먼저 막지만(422) 유스케이스도 혼자 서야 한다."""
    _, interactor, career_id = await _started()

    with pytest.raises(ValueError, match="요청 키"):
        await _advance(interactor, career_id, key="   ")


# ── 정상적인 연속 요청 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_different_keys_apply_each_action() -> None:
    """멱등성이 진행을 막지 않는다 — 다른 키는 다른 의도다."""
    repository, interactor, career_id = await _started()
    before = await interactor.view(user_id=_OWNER, career_id=career_id)
    assert before is not None

    await _act(interactor, career_id, "프로모", key="req-promo-1")
    await _act(interactor, career_id, "프로모", key="req-promo-2")

    after = await interactor.view(user_id=_OWNER, career_id=career_id)
    assert after is not None
    assert after.action_points == before.action_points - 2
    assert repository.writes == 2


@pytest.mark.asyncio
async def test_different_keys_advance_each_week() -> None:
    _, interactor, career_id = await _started()

    await _advance(interactor, career_id, key="req-week-1")
    await _advance(interactor, career_id, key="req-week-2")

    after = await interactor.view(user_id=_OWNER, career_id=career_id)
    assert after is not None
    assert after.week == 3


# ── 실패와 재시도 ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_failed_request_leaves_the_key_reusable() -> None:
    """실패는 영수증을 남기지 않는다 — **같은 키로 다시 보내면 적용된다.**

    트랜잭션이 되돌려져 바뀐 것이 없으므로 재시도가 안전하다. 실패 응답을 성공
    응답으로 재사용하지 않는 쪽을 고른 결과다.
    """
    repository, interactor, career_id = await _started()
    key = "req-failed-then-ok"
    # 포인트를 다 써서 거부되게 만든다.
    for _ in range(_BALANCE.action_points):
        await _act(interactor, career_id, "프로모")
    with pytest.raises(ValueError, match="행동 포인트"):
        await _act(interactor, career_id, "프로모", key=key)
    assert all(k[2] != key for k in repository.receipts)

    # 주차를 넘겨 포인트를 되살리고 **같은 키로** 다시 보낸다.
    await _advance(interactor, career_id)
    retried = await _act(interactor, career_id, "프로모", key=key)

    assert retried.replayed is None
    assert _only(retried).action_points == _BALANCE.action_points - 1


@pytest.mark.asyncio
async def test_a_failed_request_can_be_corrected_under_the_same_key() -> None:
    """거부된 뒤 입력을 고쳐 같은 키로 보내도 통과한다 — 지문을 비교할 영수증이 없다."""
    _, interactor, career_id = await _started()
    key = "req-corrected"
    with pytest.raises(ValueError, match="훈련 대상"):
        await _act(interactor, career_id, "훈련", target="춤솜씨", key=key)

    fixed = await _act(interactor, career_id, "훈련", target="mic", key=key)

    assert fixed.replayed is None


@pytest.mark.asyncio
async def test_a_unique_constraint_hit_replays_instead_of_failing() -> None:
    """고유 제약이 잡힌 경로도 **200 으로 끝난다.**

    잠금이 못 막은 순서에서 DB 가 거부하면, 호출자는 되돌리고 저장된 응답을 읽어야
    한다. 이 경로가 500 이 되면 사용자가 "실패했다" 를 보고 또 누른다.
    """
    repository, interactor, career_id = await _started()
    key = "req-constraint"
    # 영수증만 먼저 꽂아 둔다 — `find_receipt` 가 못 보게 다른 사용자 범위로
    # 넣을 수는 없으므로, 유스케이스가 조회한 **뒤에** 생기는 상황을 만든다.
    original = await _act(interactor, career_id, "프로모", key=key)
    stored = repository.receipts[(_OWNER, career_id, key)]
    found: list[int] = []

    real_find = repository.find_receipt

    async def blind_once(**kwargs):
        """첫 조회는 못 본 척한다 — 잠금이 풀린 경쟁을 흉내 낸다."""
        found.append(1)
        if len(found) == 1:
            return None
        return await real_find(**kwargs)

    repository.find_receipt = blind_once  # type: ignore[method-assign]
    raced = await _act(interactor, career_id, "프로모", key=key)

    assert raced.replayed == stored.response
    assert raced.replayed is not None
    assert raced.replayed["action_points"] == _only(original).action_points
    # 세이브는 한 번만 바뀌었다.
    assert repository.writes == 1


# ── 격리 ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_same_key_in_two_careers_of_one_user_is_isolated() -> None:
    """키 범위에 커리어가 들어간다 — 안 들어가면 둘째 커리어가 첫째 응답을 받는다."""
    repository = FakeRepository()
    interactor = CareerSandboxInteractor(repository=repository, balance=_BALANCE)
    one = await interactor.create(
        user_id=_OWNER, name="Ho", style="파워", age=24, seed=1
    )
    two = await interactor.create(
        user_id=_OWNER, name="Dex", style="파워", age=24, seed=2
    )
    key = "req-shared-across-careers"

    first = await _advance(interactor, one.id, key=key)
    second = await _advance(interactor, two.id, key=key)

    assert first.replayed is None
    assert second.replayed is None
    assert _only(second).id == two.id
    assert repository.writes == 2


@pytest.mark.asyncio
async def test_the_same_key_for_two_users_is_isolated() -> None:
    repository = FakeRepository()
    interactor = CareerSandboxInteractor(repository=repository, balance=_BALANCE)
    mine = await interactor.create(
        user_id=_OWNER, name="Ho", style="파워", age=24, seed=1
    )
    theirs = await interactor.create(
        user_id=_STRANGER, name="Dex", style="파워", age=24, seed=2
    )
    key = "req-shared-across-users"

    await _advance(interactor, mine.id, key=key)
    other = await _advance(interactor, theirs.id, user_id=_STRANGER, key=key)

    assert other.replayed is None
    assert repository.writes == 2


@pytest.mark.asyncio
async def test_a_stranger_cannot_replay_my_receipt() -> None:
    """남의 영수증은 보이지 않는다 — 보이면 세이브 내용이 새어 나간다."""
    _, interactor, career_id = await _started()
    key = "req-not-yours"
    await _advance(interactor, career_id, key=key)

    with pytest.raises(LookupError):
        await _advance(interactor, career_id, user_id=_STRANGER, key=key)


# ── 재시작과 보존 ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_restarted_process_still_recognises_the_request() -> None:
    """영수증이 **DB 에** 있다 — 프로세스 메모리에 있으면 재시작이 보호를 지운다.

    유스케이스 객체를 새로 만들어 재시작을 흉내 낸다. 저장소만 같다.
    """
    repository, interactor, career_id = await _started()
    key = "req-survives-restart"
    first = await _advance(interactor, career_id, key=key)

    restarted = CareerSandboxInteractor(repository=repository, balance=_BALANCE)
    second = await restarted.advance(
        user_id=_OWNER, career_id=career_id, request_id=key
    )

    assert second.replayed is not None
    assert second.replayed["week"] == _only(first).week
    assert repository.writes == 1


@pytest.mark.asyncio
async def test_receipts_are_capped_per_career() -> None:
    """**무한히 쌓이지 않는다.** 영수증에는 응답 본문이 통째로 들어간다."""
    repository, interactor, career_id = await _started()

    for week in range(RECEIPT_KEEP + 3):
        await _advance(interactor, career_id, key=f"req-week-{week}")
        if repository.saves[career_id].phase != Phase.IN_SEASON:
            await _settle(interactor, career_id, key=f"req-settle-{week}")
            await _next_season(interactor, career_id, key=f"req-next-{week}")

    mine = [k for k in repository.receipts if k[1] == career_id]
    assert len(mine) == RECEIPT_KEEP


@pytest.mark.asyncio
async def test_a_pruned_receipt_stops_deduplicating() -> None:
    """상한의 **대가를 적어 둔다** — 잘린 뒤 도착한 재시도는 새 요청이 된다.

    감수한 트레이드오프다(`RECEIPT_KEEP` 주석). 재시도 창은 요청 하나이고 그
    사이에 같은 커리어로 여덟 번 더 쓰는 경로는 없다. 이 성질이 **의도**라는 것을
    테스트로 적어 두지 않으면 나중에 버그로 보고된다.
    """
    repository, interactor, career_id = await _started()
    key = "req-will-be-pruned"
    await _act(interactor, career_id, "프로모", key=key)

    for n in range(RECEIPT_KEEP):
        await _act(interactor, career_id, "프로모", key=f"req-filler-{n}")
        if repository.saves[career_id].action_points == 0:
            await _advance(interactor, career_id, key=f"req-adv-{n}")
            if repository.saves[career_id].phase != Phase.IN_SEASON:
                await _settle(interactor, career_id, key=f"req-set-{n}")
                await _next_season(interactor, career_id, key=f"req-nxt-{n}")

    assert (_OWNER, career_id, key) not in repository.receipts
