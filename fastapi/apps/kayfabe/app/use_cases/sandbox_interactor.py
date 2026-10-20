"""장난감 시뮬레이터 조립.

읽는 것은 둘뿐이다 — 로스터(나이)와 타이틀 획득 수. **`DataCenterRepository` 를
재사용한다.** 읽기 전용 포트라 새로 낼 이유가 없고, 쓰기가 딸려 오지도 않는다.

승률을 읽지 않는 이유는 `domain/services/match_sim` 독스트링에 적혀 있다(표본이
없다 — 5경기 이상이 169명 중 11명).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date

from kayfabe.app.dtos.sandbox_dto import (
    CareerStateResponse,
    CareerStepResponse,
    SimContenderResponse,
    SimResultResponse,
)
from kayfabe.app.ports.input.sandbox_use_case import SandboxUseCase
from kayfabe.app.ports.output.data_center_repository import DataCenterRepository
from kayfabe.app.services.competitor_roster import normalize_name
from kayfabe.domain.services.career_run import (
    CareerState,
    advance,
    is_defense,
    next_belt,
)
from kayfabe.domain.services.match_sim import Contender, contender_score, simulate

logger = logging.getLogger("uvicorn.error")


def _age_on(birth_date: str | None, today: date) -> int | None:
    """만 나이. 생일이 `????-07-16` 꼴이면 `None` — 연도를 모르면 못 센다."""
    raw = (birth_date or "").strip()
    try:
        born = date.fromisoformat(raw)
    except ValueError:
        return None
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


class SandboxInteractor(SandboxUseCase):
    def __init__(self, *, data_center_repository: DataCenterRepository) -> None:
        self._repo = data_center_repository

    async def simulate(self, *, a: str, b: str) -> SimResultResponse | None:
        left, right = normalize_name(a), normalize_name(b)
        wrestlers = await self._repo.list_wrestlers()
        by_name = {w.name: w for w in wrestlers}
        if left not in by_name or right not in by_name:
            logger.info("[SandboxInteractor] 로스터에 없음 | a=%s b=%s", left, right)
            return None

        titles = await self._repo.list_title_acquisitions()
        counts: dict[str, int] = {}
        for row in titles:
            counts[row.competitor_name] = counts.get(row.competitor_name, 0) + 1

        today = date.today()
        contenders = {
            name: Contender(
                name=name,
                titles=counts.get(name, 0),
                age=_age_on(by_name[name].birth_date, today),
            )
            for name in (left, right)
        }
        verdict = simulate(contenders[left], contenders[right])
        logger.info(
            "[SandboxInteractor] %s vs %s -> %s (p=%.3f)",
            left,
            right,
            verdict.winner,
            verdict.probability_a,
        )
        return SimResultResponse(
            a=_to_response(contenders[left]),
            b=_to_response(contenders[right]),
            winner=verdict.winner,
            probability_a=verdict.probability_a,
            roll=verdict.roll,
        )

    async def career_step(
        self, *, state: CareerState, choice: str
    ) -> CareerStepResponse:
        """한 주를 넘긴다. **읽기만 한다** — 상대 선수 이름을 뽑으려고 로스터를 본다.

        상대를 로스터에서 뽑는 이유는 재미뿐이다. 판정에는 들어가지 않는다 —
        들어가면 `advance` 가 순수 함수가 아니게 되고 결정론이 깨진다.
        """
        opponent = await self._pick_opponent(state)
        result = advance(state, choice=choice, opponent=opponent)
        nxt = result.state
        report = result.report
        belt = next_belt(nxt) if nxt.outcome is None else None
        return CareerStepResponse(
            state=_state_to_response(nxt),
            week=report.week,
            kind=report.kind,
            won=report.won,
            opponent=report.opponent,
            belt=report.belt,
            promoted_to=report.promoted_to,
            injured_weeks=report.injured_weeks,
            popularity_delta=report.popularity_delta,
            next_belt=belt,
            defending=is_defense(nxt) and belt is not None,
        )

    async def _pick_opponent(self, state: CareerState) -> str | None:
        """같은 브랜드에서 한 명. **상태에서 파생**하므로 같은 주차면 같은 상대다."""
        wrestlers = await self._repo.list_wrestlers()
        pool = [w.name for w in wrestlers if (w.brand or "") == state.brand]
        if not pool:
            pool = [w.name for w in wrestlers]
        if not pool:
            return None
        pool.sort()
        index = _stable_index(f"{state.name}:{state.week}:{state.brand}", len(pool))
        return pool[index]


def _stable_index(key: str, size: int) -> int:
    """문자열에서 고정 인덱스. `hash()` 는 프로세스마다 달라 쓸 수 없다."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % size


def _state_to_response(state: CareerState) -> CareerStateResponse:
    return CareerStateResponse(
        name=state.name,
        style=state.style,
        week=state.week,
        brand=state.brand,
        popularity=state.popularity,
        wins=state.wins,
        losses=state.losses,
        reigns=list(state.reigns),
        held=state.held,
        out_weeks=state.out_weeks,
        outcome=state.outcome,
    )


def _to_response(contender: Contender) -> SimContenderResponse:
    return SimContenderResponse(
        name=contender.name,
        titles=contender.titles,
        age=contender.age,
        score=contender_score(contender),
    )
