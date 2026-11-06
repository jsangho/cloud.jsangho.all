"""경기 기록 상한(104건)에서 **진짜 JSONB 왕복과 API 가 버티는가.**

절댓값은 크기만 회귀 경보로 둔다. 시간은 기계에 달려 있어 단언하지 않는다.

## 실측 (2026-11-06 · PostgreSQL 16.2 · 로컬 TCP · 중앙값 25회)

17.6 에서 같은 입력을 재면 크기는 바이트까지 같고 시간은 오차 범위 안이었다.

입력은 셋이다. `real` 은 102명 세계를 엔진으로 돌려 104건을 채운 세이브(5시즌), `all_tag`
는 가장 큰 태그 기록을 복제해 전부 태그로 만든 합성 최악, `14시즌` 은 로그가 상한(1,200줄)에
닿은 세이브다.

                      real      all_tag     14시즌
    세이브 JSON       334 KB    385 KB      522 KB
    기록 구역          82 KB    132 KB       83 KB
    JSONB 칸(압축)     49 KB     36 KB       74 KB
    dump              0.8 ms    1.0 ms      1.4 ms
    load              2.9 ms    3.4 ms      4.5 ms
    verify_matches    1.1 ms    1.4 ms      1.1 ms
    INSERT·UPDATE      10 ms     11 ms       17 ms
    SELECT              5 ms      7 ms        9 ms
    POST 행동(저장까지) 55 ms     60 ms     미측정  (14시즌 세이브가 비시즌이라 422)
    GET 상세 응답      61 KB     61 KB       75 KB
    GET /matches 50건  12 KB     13 KB       12 KB
    GET /matches 200   24 KB     27 KB       24 KB   (건수가 104 라 104건)
    GET 경기 한 장    1.1 KB    1.7 KB      1.1 KB

**상한은 지금 값으로 충분하다.** 저장 전 검사는 쓰기 시간의 약 10분의 1이다. 세이브가
계속 자라는 원인은 기록이 아니라 상한이 없는 `applied` 다(시즌당 약 120칸) — 14시즌에서도
쓰기가 20 ms 안쪽이라 지금 고칠 이유는 없다. 영수증은 한 건에 응답 전문(약 70 KB)이 들어가고
커리어당 8건까지만 남는다. 숫자에는 **Supabase pooler 왕복이 들어 있지 않다.**

DSN·안전 규칙·하네스는 `test_sandbox_career_pg_repository` 의 것을 그대로 쓴다.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import text

from kayfabe.adapter.inbound.api.schemas.career_sandbox_schema import (
    MatchSummarySchema,
)
from kayfabe.adapter.outbound.pg.career_world_codec import dump, load
from kayfabe.app.use_cases.career_sandbox_interactor import _match_summary_dto
from kayfabe.domain.services import career_match_record as records
from kayfabe.domain.services import career_season as season_rules
from kayfabe.domain.services.career_world import Balance, Phase, WorldState

pytestmark = pytest.mark.skipif(
    not os.getenv("KAYFABE_TEST_DATABASE_URL", "").strip(),
    reason="KAYFABE_TEST_DATABASE_URL 이 없다 — 버려도 되는 PostgreSQL 을 가리켜야 한다",
)

_HERE = Path(__file__).resolve().parent

#: 회귀 경보. 실측보다 넉넉하다 — 넘으면 무엇이 커졌는지 본다.
_SAVE_LIMIT = 450_000
_MATCHES_RESPONSE_LIMIT = 80_000


def _module(name: str) -> object:
    spec = importlib.util.spec_from_file_location(
        f"_career_max_{name}", _HERE / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pg = _module("test_sandbox_career_pg_repository")
size = _module("test_career_save_size")


def real_world() -> WorldState:
    """엔진이 실제로 104건을 채운 세계."""
    balance = Balance()
    world = size._world()
    while len(world.matches) < records.MAX_MATCH_RECORDS:
        world = size._play_season(world, balance)
        assert world.phase == Phase.OFFSEASON
        world = season_rules.start_next_season(world, balance=balance)
    assert len(world.matches) == records.MAX_MATCH_RECORDS
    return world


def all_tag_world(world: WorldState) -> WorldState:
    """가장 큰 태그 기록으로 104건을 채운다. **크기의 최악을 재려는 합성 입력이다.**

    102명 세계는 동맹이 안 생겨 태그가 나오지 않으므로 기록은 골든 궤적에서 가져온다.
    """
    spec = importlib.util.spec_from_file_location(
        "_career_max_golden",
        _HERE.parents[2] / "domain" / "services" / "test_career_golden.py",
    )
    assert spec is not None and spec.loader is not None
    golden = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = golden
    spec.loader.exec_module(golden)
    _, source = golden.run_trajectory()
    tag = max(
        (m for m in source.matches if m.kind == "tag"),
        key=lambda m: len(json.dumps(dump(replace(source, matches=(m,)))["matches"])),
    )
    filled = tuple(
        replace(
            tag,
            id=records.match_id(season=world.season, week=i + 1),
            season=world.season,
            week=i + 1,
        )
        for i in range(records.MAX_MATCH_RECORDS)
    )
    return replace(world, matches=filled)


@pytest.fixture(scope="module")
def world() -> WorldState:
    return real_world()


@pytest.mark.asyncio
@pytest.mark.parametrize("shape", ("real", "all_tag"))
async def test_the_cap_round_trips_through_jsonb(world: WorldState, shape: str) -> None:
    state = world if shape == "real" else all_tag_world(world)
    async with pg._harness() as h:
        async with h.repo() as repo:
            career_id = await repo.create(
                user_id=h.user_id, player_name="Hero", seed=7, state=state
            )
        async with h.repo() as repo:
            loaded = await repo.load(user_id=h.user_id, career_id=career_id)
        assert loaded == state
        assert len(loaded.matches) == records.MAX_MATCH_RECORDS

        async with h.session() as session:
            stored = (
                await session.execute(
                    text("SELECT world::text FROM sandbox_careers WHERE id = :i"),
                    {"i": career_id},
                )
            ).scalar_one()
        assert load(json.loads(stored)) == state
        assert len(stored.encode("utf-8")) < _SAVE_LIMIT


@pytest.mark.asyncio
async def test_the_cap_does_not_grow_on_the_next_write(world: WorldState) -> None:
    """상한에서 또 경기를 해도 건수는 그대로고 가장 오래된 기록부터 빠진다."""
    balance = Balance()
    later = size._play_season(world, balance)
    assert later.matches[-1].id != world.matches[-1].id
    async with pg._harness() as h:
        async with h.repo() as repo:
            career_id = await repo.create(
                user_id=h.user_id, player_name="Hero", seed=7, state=world
            )
        async with h.repo() as repo:
            await repo.load_for_update(user_id=h.user_id, career_id=career_id)
            await repo.save(user_id=h.user_id, career_id=career_id, state=later)
        async with h.repo() as repo:
            after = await repo.load(user_id=h.user_id, career_id=career_id)

    assert after == later
    assert len(after.matches) == records.MAX_MATCH_RECORDS
    assert world.matches[0].id not in {m.id for m in after.matches}


def test_the_first_page_of_matches_stays_small(world: WorldState) -> None:
    """`/matches` 의 기본 쪽(50건)이 경보 안에 있는가 — 스키마를 지난 값으로 잰다."""
    page = [
        MatchSummarySchema.model_validate(
            _match_summary_dto(m), from_attributes=True
        ).model_dump(by_alias=True)
        for m in world.matches[-50:]
    ]
    assert len(json.dumps(page, ensure_ascii=False).encode()) < _MATCHES_RESPONSE_LIMIT
