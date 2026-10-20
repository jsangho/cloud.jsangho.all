"""장난감 시뮬레이터 조립.

읽는 것은 둘뿐이다 — 로스터(나이)와 타이틀 획득 수. **`DataCenterRepository` 를
재사용한다.** 읽기 전용 포트라 새로 낼 이유가 없고, 쓰기가 딸려 오지도 않는다.

승률을 읽지 않는 이유는 `domain/services/match_sim` 독스트링에 적혀 있다(표본이
없다 — 5경기 이상이 169명 중 11명).
"""

from __future__ import annotations

import logging
from datetime import date

from kayfabe.app.dtos.sandbox_dto import SimContenderResponse, SimResultResponse
from kayfabe.app.ports.input.sandbox_use_case import SandboxUseCase
from kayfabe.app.ports.output.data_center_repository import DataCenterRepository
from kayfabe.app.services.competitor_roster import normalize_name
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


def _to_response(contender: Contender) -> SimContenderResponse:
    return SimContenderResponse(
        name=contender.name,
        titles=contender.titles,
        age=contender.age,
        score=contender_score(contender),
    )
