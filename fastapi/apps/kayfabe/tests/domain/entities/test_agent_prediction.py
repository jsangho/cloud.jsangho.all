"""엔티티 불변식 테스트 — 근거 없는 예측을 만들 수 없어야 한다."""

from __future__ import annotations

from datetime import datetime

import pytest

from kayfabe.domain.entities.agent_prediction import (
    AgentKind,
    AgentPrediction,
    AgentReport,
    KnowledgeRetrieval,
    PredictionSource,
)

_NOW = datetime(2026, 8, 4, 12, 0, 0)


def _report() -> AgentReport:
    return AgentReport(
        agent=AgentKind.STORYLINE,
        pick="left",
        weight=0.8,
        summary="타이틀 명분이 도전자 쪽에 있다.",
        sources=("https://www.wwe.com/shows/raw",),
    )


def _prediction(**overrides: object) -> AgentPrediction:
    kwargs: dict[str, object] = {
        "event_slug": "summerslam",
        "match_key": "ss26-n2-whc",
        "pick": "left",
        "pick_name": "Roman Reigns",
        "win_probability": 0.78,
        "confidence": 0.67,
        "rationale": "세 분석 중 둘이 같은 쪽을 골랐습니다.",
        "source": PredictionSource.AGENTS,
        "generated_at": _NOW,
        "reports": (_report(),),
    }
    kwargs.update(overrides)
    return AgentPrediction(**kwargs)  # type: ignore[arg-type]


def test_prediction_keeps_its_reports() -> None:
    prediction = _prediction()

    assert prediction.opinionated_reports == (_report(),)
    assert prediction.source is PredictionSource.AGENTS


def test_agent_prediction_requires_at_least_one_report() -> None:
    """근거 없이 'AI가 골랐다'만 남는 상태를 타입 수준에서 막는다."""
    with pytest.raises(ValueError):
        _prediction(reports=())


def test_bookmaker_fallback_may_have_no_reports() -> None:
    """에이전트가 전부 죽어도 화면은 예측을 보여줘야 한다 — 대신 출처를 밝힌다."""
    prediction = _prediction(source=PredictionSource.BOOKMAKER_FALLBACK, reports=())

    assert prediction.source is PredictionSource.BOOKMAKER_FALLBACK
    assert prediction.reports == ()


@pytest.mark.parametrize("field", ["win_probability", "confidence"])
@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_ratios_must_stay_within_zero_and_one(field: str, value: float) -> None:
    with pytest.raises(ValueError):
        _prediction(**{field: value})


@pytest.mark.parametrize("field", ["event_slug", "match_key", "pick"])
def test_identifiers_cannot_be_empty(field: str) -> None:
    with pytest.raises(ValueError):
        _prediction(**{field: ""})


def test_report_without_opinion_is_not_a_failure() -> None:
    """의견 없음(None)은 실패도 아니고 반반도 아니다."""
    silent = AgentReport(
        agent=AgentKind.RUMOR, pick=None, weight=0.0, summary="참고할 소식 없음"
    )

    assert silent.has_opinion is False


def test_report_pick_cannot_be_empty_string() -> None:
    """빈 문자열은 '의견 없음'과 혼동된다 — None만 허용한다."""
    with pytest.raises(ValueError):
        AgentReport(agent=AgentKind.ODDS, pick="", weight=0.5, summary="")


def test_report_weight_is_a_ratio() -> None:
    with pytest.raises(ValueError):
        AgentReport(agent=AgentKind.ODDS, pick="left", weight=1.5, summary="")


class TestKnowledgeRetrieval:
    """검색 기록의 불변식 (Phase 3-13).

    이 값 객체가 붙드는 것은 하나다 — **순서가 곧 기록의 의미**다. 어느 글을 먼저
    읽었는지를 적는 자리이므로, 순서가 없거나 겹치면 적어 둔 것이 아무 말도 못 한다.
    """

    def test_rank_starts_at_one(self) -> None:
        assert KnowledgeRetrieval(rank=1).rank == 1

    @pytest.mark.parametrize("rank", [0, -1])
    def test_rank_below_one_is_rejected(self, rank: int) -> None:
        with pytest.raises(ValueError):
            KnowledgeRetrieval(rank=rank)

    def test_everything_but_rank_may_be_unknown(self) -> None:
        """레거시 청크는 계보도 해시도 없다 — 그 사실을 0이나 빈 문자열로 덮지 않는다."""
        item = KnowledgeRetrieval(rank=3)

        assert (item.chunk_id, item.source_url, item.content_hash) == (None, None, None)
        assert (item.source_revision_id, item.source_revised_at) == (None, None)
        assert (item.published_at, item.distance) == (None, None)

    def test_duplicate_ranks_are_rejected(self) -> None:
        with pytest.raises(ValueError):
            _prediction(
                retrievals=(KnowledgeRetrieval(rank=1), KnowledgeRetrieval(rank=1))
            )

    def test_a_prediction_may_have_read_nothing(self) -> None:
        """코퍼스에 맞는 글이 없으면 빈 것이 정직하다 — 옛 예측도 이 상태다."""
        assert _prediction().retrievals == ()
