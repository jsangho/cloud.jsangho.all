"""감사 엔드포인트 계약 테스트 (Phase 9).

프론트가 받는 JSON을 고정한다. 특히 둘:

1. **모델 이름이 응답 어디에도 없다** (하네스 §11-6). Phase 4가 그 값을 DB에
   남기기 시작했으므로, 경계에서 새지 않는다는 것을 여기서 못 박아야 한다.
2. **없는 예측은 404다.** 유스케이스는 `None`을 돌려주고 HTTP로 옮기는 것은
   라우터의 일이다 — 포트에서 `HTTPException`을 던지지 않는다(§4-6).

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest \\
        apps/kayfabe/tests/adapter/inbound/test_ai_lab_audit_router.py -q
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from fastapi import FastAPI
from kayfabe.adapter.inbound.api.v1.ai_lab_router import ai_lab_router
from kayfabe.app.dtos.ai_lab_dto import AuditReport, PredictionAuditResponse
from kayfabe.app.ports.input.ai_lab_use_case import AiLabUseCase
from kayfabe.app.services.ai_lab_evaluation import (
    RULES,
    EvaluationItem,
    EvidenceVerdict,
    RuleVerdict,
)
from kayfabe.app.services.ai_lab_replay import (
    PredictionReplay,
    ReplayMismatch,
    ReplayStatus,
)
from kayfabe.dependencies.ai_lab_provider import get_ai_lab

_GENERATED_AT = datetime(2026, 8, 9, 7, tzinfo=UTC)
_REVISED_AT = datetime(2026, 8, 1, 7, tzinfo=UTC)
_OWN = "https://en.wikipedia.org/wiki/SummerSlam_(2026)"

_AUDIT = PredictionAuditResponse(
    event_slug="summerslam",
    event_label="SummerSlam",
    match_key="ss26-n1-undisputed",
    match_title="Undisputed Championship",
    pick="left",
    pick_name="Cody Rhodes",
    win_probability=0.7,
    confidence=0.6,
    rationale="2/3 분석이 Cody Rhodes을(를) 골랐습니다.",
    source="agents",
    generated_at=_GENERATED_AT,
    result_recorded_at=None,
    event_start_date=date(2026, 8, 10),
    winner_name=None,
    correct=None,
    evaluation=EvaluationItem(
        event_slug="summerslam",
        event_label="SummerSlam",
        match_key="ss26-n1-undisputed",
        match_title="Undisputed Championship",
        generated_at=_GENERATED_AT,
        result_recorded_at=None,
        status="disqualified",
        eligible=False,
        verdicts=(
            RuleVerdict(
                code="self_reference",
                failed=True,
                applicable=True,
                detail="'SummerSlam' 대회 자체를 다룬 문서를 인용했습니다.",
            ),
        ),
    ),
    rules=RULES,
    reports=(
        AuditReport(
            agent="storyline",
            pick="left",
            weight=0.8,
            summary="명분이 도전자 쪽에 있다.",
            sources=(_OWN,),
            agent_version="storyline@1",
            prompt_version="f9b754e8b82ddb96",
        ),
    ),
    evidence=(
        EvidenceVerdict(
            rank=1,
            source_url=_OWN,
            source_revision_id="1367771",
            source_revised_at=_REVISED_AT,
            published_at=None,
            distance=0.12,
            temporal="before_event",
            revision_vs_prediction="before_prediction",
            self_reference=True,
        ),
    ),
    replay=PredictionReplay(
        status=ReplayStatus.DIVERGED,
        mismatches=(ReplayMismatch(field="confidence", stored="0.6", replayed="0.4"),),
        card_unchanged=True,
    ),
    knowledge_query="Undisputed WWE Championship Cody Rhodes Drew McIntyre",
)


class FakeUseCase(AiLabUseCase):
    """감사 조회만 답한다 — 나머지 경로는 이 테스트의 관심사가 아니다."""

    def __init__(self, *, found: bool = True) -> None:
        self._found = found
        self.calls: list[tuple[str, str]] = []

    async def get_audit(self, *, event_slug: str, match_key: str):
        self.calls.append((event_slug, match_key))
        return _AUDIT if self._found else None

    async def get_overview(self):
        raise NotImplementedError

    async def list_predictions(self, *, agent: str | None = None):
        raise NotImplementedError

    async def get_agents(self):
        raise NotImplementedError

    async def get_evaluation(self):
        raise NotImplementedError

    async def get_performance(self):
        raise NotImplementedError

    async def get_knowledge(self):
        raise NotImplementedError

    async def get_leakage(self):
        raise NotImplementedError

    async def get_readiness(self):
        raise NotImplementedError


def _client(use_case: FakeUseCase) -> TestClient:
    app = FastAPI()
    app.include_router(ai_lab_router, prefix="/api")
    app.dependency_overrides[get_ai_lab] = lambda: use_case
    return TestClient(app)


@pytest.fixture
def payload() -> dict:
    response = _client(FakeUseCase()).get(
        "/api/ai-lab/audit/summerslam/ss26-n1-undisputed"
    )
    assert response.status_code == 200
    return response.json()


def test_missing_prediction_is_404() -> None:
    response = _client(FakeUseCase(found=False)).get(
        "/api/ai-lab/audit/summerslam/없는-경기"
    )

    assert response.status_code == 404


def test_path_parameters_reach_the_use_case() -> None:
    use_case = FakeUseCase()

    _client(use_case).get("/api/ai-lab/audit/summerslam/ss26-n1-undisputed")

    assert use_case.calls == [("summerslam", "ss26-n1-undisputed")]


def test_response_is_camel_case(payload: dict) -> None:
    """프론트가 받는 키를 고정한다 — 스네이크가 섞이면 화면이 조용히 빈칸이 된다."""
    assert payload["eventSlug"] == "summerslam"
    assert payload["matchKey"] == "ss26-n1-undisputed"
    assert payload["pickName"] == "Cody Rhodes"
    assert payload["winProbability"] == 0.7
    assert payload["eventStartDate"] == "2026-08-10"
    # 결과가 없으면 `null`이다 — 오답(false)과 다른 상태다.
    assert payload["correct"] is None
    assert payload["resultRecordedAt"] is None
    # 무엇을 물었는가 (Phase 3). 증거 목록보다 한 단계 앞의 사실이다.
    assert (
        payload["knowledgeQuery"]
        == "Undisputed WWE Championship Cody Rhodes Drew McIntyre"
    )


def test_verdict_and_evidence_tell_the_same_story(payload: dict) -> None:
    """**판정과 증거가 한 화면에서 이어진다** (Phase 6).

    실격이라고만 적고 어느 조각 때문인지 못 짚으면, 그 설명은 근거가 아니라 주장이다.
    """
    assert payload["evaluation"]["status"] == "disqualified"
    [verdict] = payload["evaluation"]["verdicts"]
    assert verdict["code"] == "self_reference"

    [evidence] = payload["evidence"]
    assert evidence["selfReference"] is True
    assert evidence["sourceUrl"] == _OWN
    assert evidence["sourceRevisionId"] == "1367771"
    assert evidence["temporal"] == "before_event"


def test_rules_carry_definitions_without_counts(payload: dict) -> None:
    """**건수를 싣지 않는다.** 한 건짜리 화면에서 전체 집계는 오해만 만든다."""
    rules = payload["rules"]

    assert len(rules) == len(RULES)
    assert all("blocked" not in rule for rule in rules)
    assert all(rule["description"] for rule in rules)


def test_runtime_versions_are_exposed_but_the_model_is_not(payload: dict) -> None:
    """판은 보여 주고 **벤더는 감춘다** (하네스 §11-6).

    `agentVersion`·`promptVersion`은 불투명한 식별자라 모델을 드러내지 않는다.
    """
    [report] = payload["reports"]
    assert report["agentVersion"] == "storyline@1"
    assert report["promptVersion"] == "f9b754e8b82ddb96"
    assert "modelVersion" not in report
    assert "model" not in report


def test_no_model_name_anywhere_in_the_response(payload: dict) -> None:
    """응답 **전문**을 훑는다.

    키 이름만 보면 어딘가 문자열 값으로 섞여 나가는 경우를 놓친다. 모델 이름이
    실렸다면 벤더 접두사가 본문에 그대로 남는다.
    """
    raw = json.dumps(payload, ensure_ascii=False).lower()

    assert "gemini" not in raw
    assert "modelversion" not in raw
