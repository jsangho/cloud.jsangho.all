"""v3 쓰기 게이트 — **진짜 행이 그대로인가.**

`test_career_v3_write_gate` 는 가짜 세션이 호출을 받지 않았는지를 본다. 가짜가 못 보는
것은 실제 커밋이다 — 503 뒤에 `get_db` 가 커밋해도 행이 그대로인지, 잠금이 풀리는지,
옛 판본 행이 그 판본 그대로 남는지. 그래서 **실제 `get_db`** 를 지나게 하고 `world::text`
(JSONB 정규형)의 md5·`updated_at`·영수증을 전후로 비교한다.

DSN·안전 규칙·하네스는 `test_sandbox_career_pg_repository` 의 것을 그대로 쓴다
(`KAYFABE_TEST_DATABASE_URL` 이 없으면 전부 skip — CI 기본 동작).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from collections.abc import Awaitable, Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select, text

from core.matrix import grid_oracle_database_manager as database
from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from kayfabe.adapter.inbound.api.v1.career_sandbox_router import career_sandbox_router
from kayfabe.adapter.outbound.orm.career_sandbox_orm import (
    SandboxCareerModel,
    SandboxCareerRequestModel,
)
from kayfabe.adapter.outbound.pg.career_world_codec import SCHEMA_VERSION, dump, load
from kayfabe.adapter.outbound.pg.sandbox_career_pg_repository import (
    SandboxCareerPgRepository,
)
from kayfabe.app.ports.output.sandbox_career_repository import (
    CareerV3WritesDisabledError,
)
from kayfabe.dependencies.career_sandbox_provider import CAREER_V3_WRITES_ENV
from kayfabe.dependencies.data_center_provider import get_data_center_repository
from kayfabe.domain.services import career_engine as engine
from kayfabe.domain.services import career_season as season_rules
from kayfabe.domain.services.career_world import Balance, Phase

pytestmark = pytest.mark.skipif(
    not os.getenv("KAYFABE_TEST_DATABASE_URL", "").strip(),
    reason="KAYFABE_TEST_DATABASE_URL 이 없다 — 버려도 되는 PostgreSQL 을 가리켜야 한다",
)

_REPO_TESTS = Path(__file__).resolve().parent / "test_sandbox_career_pg_repository.py"
_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
_BASE = "/api/sandbox/careers"
_ACT = {"action": "휴식"}


def _pg():
    spec = importlib.util.spec_from_file_location("_career_pg_gate", _REPO_TESTS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pg = _pg()


def _fixture(version: int) -> dict[str, Any]:
    """시즌 중으로 돌린다 — 그래야 주차 진행이 저장 직전까지 간다."""
    path = _FIXTURES / f"career_golden_v{version}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))[f"final_v{version}"]
    return {**raw, "phase": str(Phase.IN_SEASON)}


def _fresh_world():
    return engine.create_world(player="Ho", style="테크니션", seed=7, age=24)


def _pending() -> dict[str, Any]:
    raw = dump(_fresh_world())
    raw["pending"] = [
        {
            "id": "evt",
            "kind": "retirement_thought",
            "season": 1,
            "week": 1,
            "subject": "Ho",
            "other": None,
            "headline": "거취를 묻는다",
            "detail": "",
            "choices": [
                {"code": "stay", "label": "계속한다", "enabled": True, "note": ""}
            ],
        }
    ]
    return raw


def _settlement() -> dict[str, Any]:
    return dump(replace(_fresh_world(), phase=Phase.SETTLEMENT))


def _settled() -> dict[str, Any]:
    return dump(season_rules.settle(load(_settlement()), balance=Balance()))


class _NoRoster:
    async def list_wrestlers(self) -> list:
        return []

    async def list_title_acquisitions(self) -> list:
        return []


async def _seed(h: Any, raw: dict[str, Any]) -> int:
    async with h.session() as session:
        row = SandboxCareerModel(
            user_id=h.user_id,
            player_name=raw["player"],
            seed=raw["seed"],
            season=raw["season"],
            week=raw["week"],
            phase=raw["phase"],
            world=raw,
        )
        session.add(row)
        await session.commit()
        return row.id


async def _snapshot(h: Any) -> dict[str, list[tuple]]:
    """그 사용자의 행 전부. **`updated_at` 을 넣는다** — 내용이 같아도 쓰면 움직인다."""
    async with h.session() as session:
        careers = await session.execute(
            text(
                "SELECT id, md5(world::text), world->>'version', season, week, "
                "phase, updated_at FROM sandbox_careers WHERE user_id = :u ORDER BY id"
            ),
            {"u": h.user_id},
        )
        receipts = await session.execute(
            text(
                "SELECT id, career_id, request_id, md5(response::text) "
                "FROM sandbox_career_requests WHERE user_id = :u ORDER BY id"
            ),
            {"u": h.user_id},
        )
        return {
            "careers": [tuple(r) for r in careers],
            "receipts": [tuple(r) for r in receipts],
        }


Client = Callable[[str, str], Awaitable[httpx.Response]]


def _app(h: Any, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """**`get_db` 는 오버라이드하지 않는다** — 세션 공장만 시험 DB 로 돌린다."""
    monkeypatch.setattr(database, "AsyncSessionLocal", h.session_factory)
    app = FastAPI()
    app.include_router(career_sandbox_router, prefix="/api")
    app.dependency_overrides[get_data_center_repository] = _NoRoster
    app.dependency_overrides[get_current_user] = lambda: TokenPayload(
        sub=str(h.user_id),
        aud="jsangho-api",
        exp=9999999999,
        iat=0,
        jti="jti",
    )
    return app


def _http(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def _key(suffix: str) -> dict[str, str]:
    return {"Idempotency-Key": f"gate-pg-request-{suffix}"}


def _assert_blocked(response: httpx.Response) -> None:
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "career_v3_writes_disabled"


@pytest.fixture(autouse=True)
def _closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(CAREER_V3_WRITES_ENV, raising=False)


@pytest.mark.asyncio
async def test_every_write_is_blocked_and_rows_stay_identical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with pg._harness() as h:
        v1 = await _seed(h, _fixture(1))
        v2 = await _seed(h, _fixture(2))
        v3 = await _seed(h, dump(_fresh_world()))
        pending = await _seed(h, _pending())
        settlement = await _seed(h, _settlement())
        settled = await _seed(h, _settled())
        before = await _snapshot(h)
        assert [row[2] for row in before["careers"]] == ["1", "2", "3", "3", "3", "3"]

        requests = [
            (_BASE, {"name": "Ho", "style": "테크니션", "age": 24}),
            (f"{_BASE}/{v1}/actions", _ACT),
            (f"{_BASE}/{v1}/advance", None),
            (f"{_BASE}/{v2}/actions", _ACT),
            (f"{_BASE}/{v2}/advance", None),
            (f"{_BASE}/{v3}/actions", _ACT),
            (f"{_BASE}/{v3}/advance", None),
            (f"{_BASE}/{pending}/events/evt", {"choice": "stay"}),
            (f"{_BASE}/{settlement}/settle", None),
            (f"{_BASE}/{settled}/next-season", None),
        ]
        async with _http(_app(h, monkeypatch)) as client:
            for index, (url, body) in enumerate(requests):
                response = await client.post(url, json=body, headers=_key(str(index)))
                _assert_blocked(response)

        assert await _snapshot(h) == before

        # 503 이 행 잠금을 쥔 채 끝나지 않았다.
        async with h.session() as session:
            await session.execute(
                select(SandboxCareerModel.id)
                .where(SandboxCareerModel.user_id == h.user_id)
                .with_for_update(nowait=True)
            )
            await session.rollback()


@pytest.mark.asyncio
async def test_reads_work_and_old_rows_stay_old(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with pg._harness() as h:
        ids = [await _seed(h, _fixture(1)), await _seed(h, _fixture(2))]
        before = await _snapshot(h)

        async with _http(_app(h, monkeypatch)) as client:
            listing = await client.get(_BASE)
            assert listing.status_code == 200, listing.text
            assert {c["id"] for c in listing.json()} == set(ids)
            for career_id in ids:
                for path in ("", "/log", "/matches"):
                    response = await client.get(f"{_BASE}/{career_id}{path}")
                    assert response.status_code == 200, response.text

        assert await _snapshot(h) == before


@pytest.mark.asyncio
async def test_a_direct_repository_call_cannot_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """라우터도 배선도 거치지 않는 길. 값을 안 주면 닫힘이다."""
    async with pg._harness() as h:
        career_id = await _seed(h, _fixture(2))
        before = await _snapshot(h)

        async with h.session() as session:
            repository = SandboxCareerPgRepository(session)
            state = await repository.load_for_update(
                user_id=h.user_id, career_id=career_id
            )
            assert state is not None
            with pytest.raises(CareerV3WritesDisabledError):
                await repository.save(
                    user_id=h.user_id, career_id=career_id, state=state
                )
            with pytest.raises(CareerV3WritesDisabledError):
                await repository.create(
                    user_id=h.user_id, player_name="Ho", seed=1, state=state
                )
            await session.commit()

        assert await _snapshot(h) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("version", (1, 2))
async def test_opening_the_gate_converts_exactly_the_row_touched(
    monkeypatch: pytest.MonkeyPatch, version: int
) -> None:
    """같은 하네스에서 열면 쓰인다 — 위 테스트들이 헛돈 것이 아니라는 짝."""
    async with pg._harness() as h:
        touched = await _seed(h, _fixture(version))
        untouched = await _seed(h, _fixture(version))
        before = await _snapshot(h)

        monkeypatch.setenv(CAREER_V3_WRITES_ENV, "true")
        async with _http(_app(h, monkeypatch)) as client:
            first = await client.post(
                f"{_BASE}/{touched}/actions", json=_ACT, headers=_key("open")
            )
            assert first.status_code == 200, first.text

            # 다시 닫아도 끝난 요청의 재전송은 같은 답이고, 새 요청은 막힌다.
            monkeypatch.delenv(CAREER_V3_WRITES_ENV)
            after_open = await _snapshot(h)
            replay = await client.post(
                f"{_BASE}/{touched}/actions", json=_ACT, headers=_key("open")
            )
            assert replay.status_code == 200 and replay.json() == first.json()
            _assert_blocked(
                await client.post(
                    f"{_BASE}/{touched}/actions", json=_ACT, headers=_key("next")
                )
            )

        assert await _snapshot(h) == after_open
        rows = {row[0]: row for row in after_open["careers"]}
        assert rows[touched][2] == str(SCHEMA_VERSION)
        assert rows[untouched] == before["careers"][1]
        assert len(after_open["receipts"]) == 1
        async with h.session() as session:
            count = await session.execute(
                select(SandboxCareerRequestModel.id).where(
                    SandboxCareerRequestModel.career_id == touched
                )
            )
            assert len(count.all()) == 1
