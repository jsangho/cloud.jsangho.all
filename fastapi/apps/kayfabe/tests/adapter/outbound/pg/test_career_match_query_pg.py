"""경기 기록 조회 — **진짜 JSONB 에서 읽고, 행을 한 바이트도 바꾸지 않는가.**

라우터 테스트(`test_career_match_router`)는 가짜 저장소로 저장·잠금 호출이 0회인
것을 본다. 가짜가 못 보는 것은 실제 행이다 — 세션이 닫힐 때 무언가 커밋되는지,
옛 판본 행이 조회만으로 v3 가 되는지. 그래서 `world::text`(JSONB 정규형)를 조회
전후로 비교한다.

DSN·안전 규칙·하네스는 `test_sandbox_career_pg_repository` 의 것을 그대로 쓴다
(`KAYFABE_TEST_DATABASE_URL` 이 없으면 전부 skip — CI 기본 동작).
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

from kayfabe.app.ports.input.career_sandbox_use_case import MatchNotFoundError
from kayfabe.app.use_cases.career_sandbox_interactor import CareerSandboxInteractor
from kayfabe.domain.services import career_match_record as records
from kayfabe.domain.services.career_world import Balance

pytestmark = pytest.mark.skipif(
    not os.getenv("KAYFABE_TEST_DATABASE_URL", "").strip(),
    reason="KAYFABE_TEST_DATABASE_URL 이 없다 — 버려도 되는 PostgreSQL 을 가리켜야 한다",
)

_REPO_TESTS = Path(__file__).resolve().parent / "test_sandbox_career_pg_repository.py"


def _pg():
    spec = importlib.util.spec_from_file_location("_career_pg_p1", _REPO_TESTS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # 그 모듈의 `@dataclass`(Harness)가 `sys.modules` 에서 자기 모듈을 찾는다 —
    # 등록하지 않으면 수집 단계에서 죽는다(DSN 이 없어도).
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pg = _pg()


async def _read_everything(h, career_id: int, user_id: int) -> tuple[list, list]:
    """목록 두 번과 상세를 전부 — 각자 **새 세션**에서. 세션 종료가 커밋하면 드러난다."""
    async with h.repo() as repo:
        use_case = CareerSandboxInteractor(repository=repo, balance=Balance())
        listed = await use_case.matches(
            user_id=user_id, career_id=career_id, season=None, limit=200, offset=0
        )
    details = []
    for item in listed:
        async with h.repo() as repo:
            use_case = CareerSandboxInteractor(repository=repo, balance=Balance())
            details.append(
                await use_case.match(
                    user_id=user_id, career_id=career_id, match_id=item.id
                )
            )
    return listed, details


@pytest.mark.asyncio
async def test_reading_v3_records_from_jsonb_changes_nothing() -> None:
    _, world = pg._golden().run_trajectory()
    async with pg._harness() as h:
        career_id = await pg._career(h)
        async with h.repo() as repo:
            await repo.save(user_id=h.user_id, career_id=career_id, state=world)
        _, text_before = await pg._raw(h, career_id)

        listed, details = await _read_everything(h, career_id, h.user_id)

        _, text_after = await pg._raw(h, career_id)
        assert text_after == text_before
        assert [m.id for m in listed] == [m.id for m in reversed(world.matches)]
        assert len(details) == 40
        tag = next(d for d in details if d.kind == "tag")
        assert [p.side for p in tag.participants] == [0, 0, 1, 1]


@pytest.mark.asyncio
async def test_reading_a_v2_row_neither_saves_nor_upgrades_it() -> None:
    async with pg._harness() as h:
        career_id = await pg._career(h)
        raw = pg._v2_raw()
        await pg._put_raw(h, career_id, raw)
        _, text_before = await pg._raw(h, career_id)
        played = next(e for e in pg.decode(raw).log if e.kind == "match")

        async with h.repo() as repo:
            use_case = CareerSandboxInteractor(repository=repo, balance=Balance())
            listed = await use_case.matches(
                user_id=h.user_id, career_id=career_id, season=None, limit=50, offset=0
            )
            with pytest.raises(MatchNotFoundError) as caught:
                await use_case.match(
                    user_id=h.user_id,
                    career_id=career_id,
                    match_id=records.match_id(season=played.season, week=played.week),
                )

        stored, text_after = await pg._raw(h, career_id)
        assert listed == []
        assert caught.value.reason == records.BEFORE_RECORDS
        assert stored["version"] == 2
        assert text_after == text_before


@pytest.mark.asyncio
async def test_a_stranger_cannot_read_matches() -> None:
    async with pg._harness() as h:
        career_id = await pg._career(h)
        async with h.repo() as repo:
            use_case = CareerSandboxInteractor(repository=repo, balance=Balance())
            with pytest.raises(LookupError) as listed:
                await use_case.matches(
                    user_id=h.user_id + 10_000,
                    career_id=career_id,
                    season=None,
                    limit=50,
                    offset=0,
                )
            with pytest.raises(LookupError) as detail:
                await use_case.match(
                    user_id=h.user_id + 10_000, career_id=career_id, match_id="s1w1:p"
                )

        assert not isinstance(listed.value, MatchNotFoundError)
        assert not isinstance(detail.value, MatchNotFoundError)
