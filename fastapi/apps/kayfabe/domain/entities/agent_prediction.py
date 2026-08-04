"""AI 멀티 에이전트 승부예측 — 도메인 엔티티.

`_docs/ai-match-predictions-harness.md` §5. 순수 파이썬이고 LLM·DB·HTTP를 모른다.

**예측은 근거와 함께만 존재한다.** 에이전트 리포트 없이 만들어진 예측을 이 엔티티로
표현할 수 없게 두는 것이 목적이다 — "AI가 골랐다"는 말만 있고 왜 골랐는지 없는 상태를
만들지 않는다(하네스 §3-D6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class AgentKind(StrEnum):
    """리포트를 낸 전문 에이전트. 하네스 §5의 세 축이다."""

    STORYLINE = "storyline"
    ODDS = "odds"
    RUMOR = "rumor"


class PredictionSource(StrEnum):
    """예측이 무엇으로 만들어졌는지.

    에이전트가 전부 실패하면 기존 북메이커 파생으로 강등하는데, 그 사실을 응답까지
    끌고 가야 화면이 구분해 표시할 수 있다(하네스 §3-D5). 조용히 같은 얼굴로
    내보내지 않기 위한 필드다.
    """

    AGENTS = "agents"
    BOOKMAKER_FALLBACK = "bookmaker_fallback"


def _check_ratio(value: float, name: str) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name}은(는) 0.0~1.0이어야 합니다: {value}")
    return value


@dataclass(frozen=True)
class AgentReport:
    """에이전트 한 명의 의견.

    `pick`이 `None`이면 **의견 없음**이다 — 실패와 다르고, 반반이라는 뜻도 아니다.
    루머 에이전트처럼 참고할 소식이 없으면 정상적으로 의견 없음을 낸다.
    """

    agent: AgentKind
    pick: str | None
    weight: float
    summary: str
    sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _check_ratio(self.weight, "weight")
        if self.pick is not None and not self.pick:
            raise ValueError("pick은 빈 문자열일 수 없습니다. 의견 없음은 None입니다.")

    @property
    def has_opinion(self) -> bool:
        return self.pick is not None


@dataclass(frozen=True)
class AgentPrediction:
    """경기 하나에 대한 최종 예측(애그리거트 루트).

    `win_probability`와 `confidence`는 **다른 축**이다. 전자는 고른 쪽이 이길
    것으로 본 비중이고, 후자는 에이전트들이 얼마나 합의했는지다. 한쪽이 높다고
    다른 쪽이 높지 않다 — 한 에이전트만 강하게 밀어도 승률은 높지만 합의는 낮다.
    """

    event_slug: str
    match_key: str
    pick: str
    pick_name: str
    win_probability: float
    confidence: float
    rationale: str
    source: PredictionSource
    generated_at: datetime
    reports: tuple[AgentReport, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.event_slug or not self.match_key:
            raise ValueError("event_slug·match_key는 비어 있을 수 없습니다.")
        if not self.pick:
            raise ValueError("pick은 비어 있을 수 없습니다.")
        _check_ratio(self.win_probability, "win_probability")
        _check_ratio(self.confidence, "confidence")
        if self.source is PredictionSource.AGENTS and not self.reports:
            raise ValueError("에이전트 예측에는 근거 리포트가 최소 1건 있어야 합니다.")

    @property
    def opinionated_reports(self) -> tuple[AgentReport, ...]:
        return tuple(report for report in self.reports if report.has_opinion)
