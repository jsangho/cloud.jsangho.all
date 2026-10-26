"""무상태 장난감의 주차 진행. **시즌 길이가 한 곳에서만 나온다.**

이 테스트가 있는 이유는 실제로 갈라졌기 때문이다 — 서버의 `MAX_WEEKS` 가 40에서
52로 올라간 뒤에도 화면은 `40` 을 박아 두고 `19 / 40` 을 그리고 있었다
(2026-10-21 발견). 숫자를 두 곳에 적으면 한쪽만 고쳐지고, 고쳐지지 않은 쪽이
거짓말을 한다.

그래서 응답이 `maxWeeks` 를 들고 나가고 화면은 그 값만 쓴다. 아래 테스트는 그
칸이 **도메인 상수와 같은 값**임을 고정한다.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kayfabe.adapter.inbound.api.v1.sandbox_router import sandbox_router
from kayfabe.app.services.data_center_stats import WrestlerRow
from kayfabe.app.use_cases.sandbox_interactor import SandboxInteractor
from kayfabe.dependencies.sandbox_provider import get_sandbox
from kayfabe.domain.services.career_run import MAX_WEEKS

_URL = "/api/sandbox/career/step"

_ROSTER = [
    WrestlerRow(name="Dex Harlow", brand="NXT"),
    WrestlerRow(name="Marcus Vane", brand="NXT"),
]


class FakeRepository:
    """읽기 포트의 일부만 흉내 낸다 — 장난감이 쓰는 것은 로스터 하나다."""

    async def list_wrestlers(self) -> list[WrestlerRow]:
        return list(_ROSTER)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(sandbox_router, prefix="/api")
    app.dependency_overrides[get_sandbox] = lambda: SandboxInteractor(
        data_center_repository=FakeRepository()
    )
    return TestClient(app)


def _step(client: TestClient, state: dict, choice: str = "경기") -> dict:
    response = client.post(_URL, json={"state": state, "choice": choice})
    assert response.status_code == 200, response.text
    return response.json()


def test_step_reports_the_season_length_from_the_server() -> None:
    body = _step(_client(), {"name": "Ho", "style": "파워"})

    assert body["maxWeeks"] == MAX_WEEKS


def test_the_season_is_52_weeks_not_40() -> None:
    """사용자 요구 §1 — "한 시즌은 정확히 52주". 화면 표시만 바꾼 것이 아니다."""
    assert MAX_WEEKS == 52
    assert _step(_client(), {"name": "Ho", "style": "파워"})["maxWeeks"] == 52


def test_an_unknown_choice_is_422() -> None:
    client = _client()

    response = client.post(
        _URL, json={"state": {"name": "Ho", "style": "파워"}, "choice": "춤"}
    )

    assert response.status_code == 422
