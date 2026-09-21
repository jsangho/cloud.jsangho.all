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
class KnowledgeRetrieval:
    """예측을 만들 때 **실제로 프롬프트에 들어간 청크 하나**의 기록 (Phase 3-13).

    출처 URL은 이미 `AgentReport.sources`에 남는다. 그것으로 부족한 이유는 하나다 —
    **URL이 같아도 개정본이 다르면 다른 글이다.** 위키 문서는 경기 전후로 계속 고쳐지고,
    문서 단위 판정은 그 문서의 가장 늦은 개정본을 기준으로 잡을 수밖에 없다(최악 기준).
    여기에 그때 읽은 개정본을 적어 두면 "이 예측이 읽은 글"을 정확히 말할 수 있다.

    **청크를 FK로 걸지 않고 값을 베껴 둔다.** 재수집이 그 URL의 옛 청크를 통째로
    DELETE하기 때문이다(`replace_document_chunks`). 참조로 두면 코퍼스를 다시 모으는
    순간 이 기록이 가리키는 것이 사라지는데, 그러면 **증거가 필요한 바로 그 시점에**
    증거가 없다. `chunk_id`는 참조가 아니라 당시 식별자를 적어 둔 것뿐이다.
    """

    #: 프롬프트에 들어간 순서. 1부터다 — 검색 순위가 아니라 **에이전트가 읽은 순서**다.
    rank: int
    #: 당시 청크 행의 id. **참조가 아니다** — 재수집하면 그 행은 없을 수 있다.
    chunk_id: int | None = None
    source_url: str | None = None
    #: 본문 sha256. 재수집 뒤에도 같은 글인지 대조할 수 있는 유일한 값이다.
    content_hash: str | None = None
    source_revision_id: str | None = None
    source_revised_at: datetime | None = None
    published_at: datetime | None = None
    #: 코사인 거리. 작을수록 가깝다. 못 구하면 `None` — 0.0으로 채우지 않는다.
    distance: float | None = None

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError(f"rank는 1 이상이어야 합니다: {self.rank}")


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
    #: 이 예측을 만들 때 읽은 청크들 (Phase 3-13). **비어 있는 것은 정상이다** —
    #: 코퍼스에 맞는 글이 없었거나 검색이 실패한 경우이고, 옛 예측에는 아예 없다.
    retrievals: tuple[KnowledgeRetrieval, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.event_slug or not self.match_key:
            raise ValueError("event_slug·match_key는 비어 있을 수 없습니다.")
        if not self.pick:
            raise ValueError("pick은 비어 있을 수 없습니다.")
        _check_ratio(self.win_probability, "win_probability")
        _check_ratio(self.confidence, "confidence")
        if self.source is PredictionSource.AGENTS and not self.reports:
            raise ValueError("에이전트 예측에는 근거 리포트가 최소 1건 있어야 합니다.")
        ranks = [item.rank for item in self.retrievals]
        if len(set(ranks)) != len(ranks):
            # 순서가 곧 "무엇을 먼저 읽었는가"다. 중복되면 그 기록이 아무 말도 못 한다.
            raise ValueError(f"retrievals의 rank가 중복됐습니다: {sorted(ranks)}")

    @property
    def opinionated_reports(self) -> tuple[AgentReport, ...]:
        return tuple(report for report in self.reports if report.has_opinion)
