"""커리어 경기 기록 화면의 **브라우저 E2E 용 API 서버.** 테스트 전용 — 운영에 올리지 않는다.

`www/e2e/career-matches.spec.ts`(Playwright)가 띄운다. 프로덕션 코드는 **그대로**
쓴다 — 라우터(`career_sandbox_router`) · 유스케이스(`CareerSandboxInteractor`) ·
세이브 코덱(`career_world_codec`)이 진짜이고, 바꾼 것은 둘뿐이다.

    저장소   PostgreSQL 대신 메모리. 세이브는 **코덱으로 눕힌 dict** 로 들고 매번
             되살린다 — PG 어댑터와 같은 경로라서 응답이 운영과 같은 모양이다.
    인증     JWT 대신 **테스트 쿠키** `kayfabe_e2e_user=<회원 id>`. 비밀값이 없다.
             진짜 토큰 검증은 백엔드 테스트가 본다 — 이 서버는 화면을 보는 곳이다.

`/auth/me` 는 인증 게이트웨이의 자리표시자다(프론트 `fetchMyProfile` 이 부른다).
`/__e2e/reset` 은 세이브를 처음 상태로 되돌린다 — 테스트가 주차를 진행하므로.

## 데이터 — 엔진이 실제로 만든 것만

골든 궤적(`test_career_golden.run_trajectory`, 시드 11)으로 시즌 1(경기 기록 40건:
싱글 · 태그 18 · 타이틀, 핀폴 · 비핀폴, 부상 3, 관계 변화)을 만들고, 이어서 시즌 2 를
**기록이 정확히 20건이 될 때까지** 진행한다. 그래서 「시즌 2」 필터는 한 쪽이 꽉 차고
다음 쪽이 비어 「마지막 쪽 빈 결과」 를 재현한다. 손으로 지은 기록은 없다 — 아래
`trimmed` 커리어만 기록 배열의 앞을 잘라 보존 상한 상태를 흉내 낸다.

    회원 1 · 커리어 1   본 커리어(시즌 1·2, 기록 60)
    회원 1 · 커리어 2   새 커리어(기록 0) — 빈 상태
    회원 1 · 커리어 3   커리어 1 에서 앞 5건을 자른 것 — `trimmed`
    회원 1 · 커리어 4   다음 주가 **결장 주**인 커리어 — 보고에 경기 링크가 없어야 한다
    회원 1 · 커리어 5   다음 주가 **경기 주**인 커리어 — 보고 링크를 누른다
    회원 2 · 커리어 9   남의 커리어

실행(저장소 루트에서)::

    cd fastapi && PYTHONPATH=apps:. uv run python \
        apps/kayfabe/tests/e2e/career_match_e2e_server.py --port 8765 --origin http://127.0.0.1:3100
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from kayfabe.adapter.inbound.api.v1.career_sandbox_router import career_sandbox_router
from kayfabe.adapter.outbound.pg.career_world_codec import dump, load
from kayfabe.app.ports.output.sandbox_career_repository import (
    CareerRow,
    RequestReceipt,
)
from kayfabe.app.use_cases.career_sandbox_interactor import CareerSandboxInteractor
from kayfabe.dependencies.career_sandbox_provider import get_career_use_case
from kayfabe.domain.services import career_engine as engine
from kayfabe.domain.services import career_events as events
from kayfabe.domain.services import career_season as season_rules
from kayfabe.domain.services.career_world import Balance, Phase, WorldState

#: 쿠키 이름. 값은 회원 id 숫자 하나다.
SESSION_COOKIE = "kayfabe_e2e_user"

_GOLDEN = (
    Path(__file__).resolve().parents[1]
    / "domain"
    / "services"
    / "test_career_golden.py"
)
_BALANCE = Balance()


# ── 데이터 ────────────────────────────────────────────────────────


def _golden_world() -> WorldState:
    spec = importlib.util.spec_from_file_location("_career_golden_e2e", _GOLDEN)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _, world = module.run_trajectory()
    return world


def _resolve_all(world: WorldState) -> WorldState:
    """열린 사건을 골든과 같은 규칙으로 닫는다(은퇴는 고르지 않는다)."""
    for event in list(world.pending):
        code = next(
            (c.code for c in event.choices if c.enabled and c.code != "retire"), None
        )
        if code is not None:
            world = events.resolve(
                world, event_id_=event.id, choice_code=code, balance=_BALANCE
            )
    return world


def _next_report(world: WorldState):
    """다음 주를 **복사본으로** 돌려 본다 — 엔진이 결정론적이라 예측이 곧 결과다."""
    return engine.advance_week(_resolve_all(world), balance=_BALANCE).report


def _season_two(world: WorldState) -> WorldState:
    """시즌 2 를 기록이 20 건이 될 때까지 진행한다."""
    world = season_rules.start_next_season(world, balance=_BALANCE)
    while sum(1 for m in world.matches if m.season == 2) < 20:
        world = engine.advance_week(_resolve_all(world), balance=_BALANCE).state
        if world.phase != Phase.IN_SEASON:
            raise RuntimeError("시즌 2 가 기록 20 건 전에 끝났다")
    return world


def _until_next_week_is(world: WorldState, *, match: bool) -> WorldState:
    """다음 주가 경기(또는 무경기) 주가 될 때까지 한 주씩 넘긴다."""
    for _ in range(30):
        if (_next_report(world).opponent is not None) == match:
            return _resolve_all(world)
        world = engine.advance_week(_resolve_all(world), balance=_BALANCE).state
    raise RuntimeError("조건에 맞는 주를 찾지 못했다")


def _out_next_week(world: WorldState) -> WorldState:
    """플레이어를 두 주 결장시킨다 — 다음 보고가 무경기 주가 된다."""
    hero = replace(world.hero, out_weeks=2)
    roster = tuple(hero if w.is_player else w for w in world.roster)
    out = replace(world, roster=roster)
    if _next_report(out).opponent is not None:
        raise RuntimeError("결장시켰는데 다음 주에 경기가 있다")
    return out


def build_saves() -> dict[int, tuple[int, dict[str, Any]]]:
    """career_id → (owner, 코덱으로 눕힌 세이브)."""
    main = _season_two(_golden_world())
    fresh = engine.create_world(player="Rookie Ho", style="테크니션", seed=7, age=24)
    trimmed = replace(main, matches=main.matches[5:])
    rest = _out_next_week(main)
    report = _until_next_week_is(main, match=True)
    stranger = engine.create_world(player="Stranger", style="파워", seed=3, age=25)
    return {
        1: (1, dump(main)),
        2: (1, dump(fresh)),
        3: (1, dump(trimmed)),
        4: (1, dump(rest)),
        5: (1, dump(report)),
        9: (2, dump(stranger)),
    }


# ── 저장소 ────────────────────────────────────────────────────────


class MemoryRepository:
    """`SandboxCareerRepository` 의 메모리판. 세이브를 **dict 로** 들고 코덱으로 되살린다."""

    def __init__(self, store: dict[int, tuple[int, dict[str, Any]]]) -> None:
        self.store = store
        self.receipts: dict[tuple[int, int, str], RequestReceipt] = {}

    async def create(self, **_: Any) -> int:
        raise HTTPException(status_code=405, detail="E2E 서버는 커리어를 만들지 않는다")

    async def list_for_user(self, user_id: int) -> list[CareerRow]:
        from datetime import UTC, datetime

        now = datetime(2026, 11, 3, tzinfo=UTC)
        rows = []
        for cid, (owner, raw) in sorted(self.store.items()):
            if owner != user_id:
                continue
            rows.append(
                CareerRow(
                    id=cid,
                    player_name=raw["player"],
                    season=raw["season"],
                    week=raw["week"],
                    phase=raw["phase"],
                    seed=raw["seed"],
                    created_at=now,
                    updated_at=now,
                )
            )
        return rows

    async def load(self, *, user_id: int, career_id: int) -> WorldState | None:
        found = self.store.get(career_id)
        if found is None or found[0] != user_id:
            return None
        return load(found[1])

    async def load_for_update(
        self, *, user_id: int, career_id: int
    ) -> WorldState | None:
        return await self.load(user_id=user_id, career_id=career_id)

    async def find_receipt(
        self, *, user_id: int, career_id: int, request_id: str
    ) -> RequestReceipt | None:
        return self.receipts.get((user_id, career_id, request_id))

    async def save(
        self,
        *,
        user_id: int,
        career_id: int,
        state: WorldState,
        receipt: RequestReceipt | None = None,
    ) -> None:
        found = self.store.get(career_id)
        if found is None or found[0] != user_id:
            raise LookupError("커리어를 찾을 수 없습니다")
        self.store[career_id] = (user_id, dump(state))
        if receipt is not None:
            self.receipts[(user_id, career_id, receipt.request_id)] = receipt


# ── 앱 ────────────────────────────────────────────────────────────


def _user_from_cookie(request: Request) -> int:
    raw = request.cookies.get(SESSION_COOKIE, "")
    if not raw.isdigit():
        raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다.")
    return int(raw)


def build_app(origin: str) -> FastAPI:
    pristine = build_saves()
    repo = MemoryRepository(copy.deepcopy(pristine))

    app = FastAPI(title="career-match-e2e")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(career_sandbox_router, prefix="/api")

    def current_user(request: Request) -> TokenPayload:
        return TokenPayload(
            sub=str(_user_from_cookie(request)),
            aud="jsangho-api",
            exp=9999999999,
            iat=0,
            jti="e2e",
            roles=["user"],
            platform="web",
            device_id="e2e",
        )

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_career_use_case] = lambda: CareerSandboxInteractor(
        repository=repo, balance=_BALANCE
    )

    @app.get("/auth/me")
    def me(request: Request) -> dict[str, Any]:
        user_id = _user_from_cookie(request)
        return {"userId": user_id, "nickname": f"e2e-{user_id}", "role": "user"}

    @app.post("/__e2e/reset")
    def reset() -> dict[str, bool]:
        repo.store = copy.deepcopy(pristine)
        repo.receipts.clear()
        return {"ok": True}

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--origin", default="http://127.0.0.1:3100")
    args = parser.parse_args()
    # 루프백에만 묶는다 — 테스트 서버를 네트워크에 내놓지 않는다.
    uvicorn.run(
        build_app(args.origin), host="127.0.0.1", port=args.port, log_level="warning"
    )


if __name__ == "__main__":
    main()
