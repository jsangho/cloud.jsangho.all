"""라우터 계약 테스트 — 프론트가 받는 JSON과 권한 가드를 고정한다.

하네스 §10-T7의 완료 판정. 특히 **생성 경로가 관리자에게만 열려 있는지**를 본다 —
LLM 비용이 드는 입구라 인증만으로는 부족하다.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from fastapi.testclient import TestClient

from fastapi import FastAPI
from kayfabe.adapter.inbound.api.v1.ai_prediction_router import ai_prediction_router
from kayfabe.app.dtos.agent_prediction_dto import (
    AgentPredictionDto,
    AgentReportDto,
    GeneratePredictionCommand,
    GenerationSummary,
)
from kayfabe.app.ports.input.ai_prediction_use_case import AiPredictionUseCase
from kayfabe.app.ports.output.agent_prediction_repository import MatchNotFoundError
from kayfabe.dependencies.ai_prediction_provider import get_ai_prediction_use_case

_NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)

_PREDICTION = AgentPredictionDto(
    match_key="ss26-n2-whc",
    pick="left",
    pick_name="Roman Reigns",
    win_probability=0.78,
    confidence=0.67,
    rationale="2/3 분석이 Roman Reigns를 골랐습니다.",
    source="agents",
    generated_at=_NOW,
    reports=(
        AgentReportDto(
            agent="storyline",
            pick="left",
            weight=0.8,
            summary="타이틀 명분",
            sources=("https://www.wwe.com/",),
        ),
        AgentReportDto(
            agent="rumor", pick=None, weight=0.0, summary="참고할 소식 없음"
        ),
    ),
)


class FakeUseCase(AiPredictionUseCase):
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.commands: list[GeneratePredictionCommand] = []

    async def list_predictions(self, *, event_slug: str) -> list[AgentPredictionDto]:
        return [_PREDICTION]

    async def generate(self, command: GeneratePredictionCommand) -> GenerationSummary:
        if self.error is not None:
            raise self.error
        self.commands.append(command)
        return GenerationSummary(requested=3, generated=2, skipped=1, failed=0)


def _claims(roles: list[str]) -> TokenPayload:
    return TokenPayload(
        sub="1",
        aud="jsangho-api",
        exp=9999999999,
        iat=0,
        jti="jti",
        roles=roles,
        platform="web",
        device_id="d1",
    )


def _client(use_case: FakeUseCase, *, roles: list[str] | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(ai_prediction_router, prefix="/api")
    app.dependency_overrides[get_ai_prediction_use_case] = lambda: use_case
    if roles is not None:
        app.dependency_overrides[get_current_user] = lambda: _claims(roles)
    return TestClient(app)


def test_list_returns_camel_case_fields() -> None:
    response = _client(FakeUseCase()).get("/api/ple_events/summerslam/ai-predictions")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert set(item) == {
        "matchKey",
        "pick",
        "pickName",
        "winProbability",
        "confidence",
        "rationale",
        "source",
        "generatedAt",
        "reports",
    }
    assert item["winProbability"] == 0.78
    assert item["source"] == "agents"


def test_list_keeps_no_opinion_as_null() -> None:
    """의견 없음을 빈 문자열로 바꾸면 화면이 '아무개를 골랐다'로 오해한다."""
    response = _client(FakeUseCase()).get("/api/ple_events/summerslam/ai-predictions")

    reports = response.json()["items"][0]["reports"]
    assert reports[0]["sources"] == ["https://www.wwe.com/"]
    assert reports[1]["pick"] is None


def test_listing_needs_no_authentication() -> None:
    """조회는 저장된 값을 읽기만 하므로 로그인 없이 볼 수 있다."""
    response = _client(FakeUseCase()).get("/api/ple_events/summerslam/ai-predictions")

    assert response.status_code == 200


def test_generation_rejects_anonymous_callers() -> None:
    use_case = FakeUseCase()

    response = _client(use_case).post(
        "/api/ple_events/summerslam/ai-predictions", json={}
    )

    assert response.status_code == 401
    assert use_case.commands == []


def test_generation_rejects_non_admin_users() -> None:
    """LLM 비용이 드는 입구라 로그인만으로는 열리지 않는다."""
    use_case = FakeUseCase()

    response = _client(use_case, roles=["user"]).post(
        "/api/ple_events/summerslam/ai-predictions", json={}
    )

    assert response.status_code == 403
    assert use_case.commands == []


def test_admin_can_generate() -> None:
    use_case = FakeUseCase()

    response = _client(use_case, roles=["admin"]).post(
        "/api/ple_events/summerslam/ai-predictions",
        json={"matchKeys": ["ss26-n2-whc"], "force": True},
    )

    assert response.status_code == 200
    assert response.json() == {
        "requested": 3,
        "generated": 2,
        "skipped": 1,
        "failed": 0,
    }
    command = use_case.commands[0]
    assert command.event_slug == "summerslam"
    assert command.match_keys == ("ss26-n2-whc",)
    assert command.force is True


def test_missing_event_is_404() -> None:
    response = _client(
        FakeUseCase(error=MatchNotFoundError("summerslam")), roles=["admin"]
    ).post("/api/ple_events/summerslam/ai-predictions", json={})

    assert response.status_code == 404
    # 내부 사정(슬러그 원문·스택)이 그대로 새지 않는다
    assert response.json()["detail"] == "경기를 찾을 수 없습니다."


@pytest.mark.parametrize("body", [{}, {"force": False}])
def test_empty_body_means_all_pending_matches(body: dict[str, object]) -> None:
    use_case = FakeUseCase()

    _client(use_case, roles=["admin"]).post(
        "/api/ple_events/summerslam/ai-predictions", json=body
    )

    assert use_case.commands[0].match_keys == ()
