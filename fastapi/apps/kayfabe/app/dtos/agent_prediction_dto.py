"""AI 승부예측 유스케이스 경계의 DTO. `_docs/ai-match-predictions-harness.md` §6.

도메인 엔티티(`AgentPrediction`)는 안쪽에서 쓰고, 이 DTO는 유스케이스가 밖(라우터)과
주고받는 모양이다. 벤더 응답 원형이나 ORM 행이 이 자리에 오지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class GeneratePredictionCommand:
    """예측 생성 요청.

    **비용이 드는 경로다**(하네스 §2-D7). 사용자 페이지 진입이 아니라 관리자·배치가
    명시적으로 부른다.
    """

    event_slug: str
    #: 비어 있으면 그 이벤트에서 아직 예측이 없는 경기 전부.
    match_keys: tuple[str, ...] = ()
    #: 이미 예측이 있는 경기도 다시 만든다.
    force: bool = False


@dataclass(frozen=True)
class MatchOption:
    """한 경기에서 고를 수 있는 선택지 하나.

    `pick`은 `ple_matches.winner_pick`과 **같은 형식**이어야 채점이 맞는다 —
    단일전은 `left`/`right`, 다인전은 인덱스 문자열(`"0"`).
    """

    pick: str
    name: str
    is_champion: bool = False


@dataclass(frozen=True)
class MatchContext:
    """에이전트에게 넘기는 경기 정보. 카드에서 뽑아낸 사실만 담는다."""

    event_slug: str
    event_label: str
    match_key: str
    title: str
    #: "singles" | "multi"
    match_format: str
    options: tuple[MatchOption, ...]
    #: 소수 배당. 카드에 없으면 `None` — 오즈 에이전트는 이때 의견 없음을 낸다.
    bookmaker_decimal: tuple[float, ...] | None = None


@dataclass(frozen=True)
class KnowledgeChunk:
    """RAG 검색 결과 한 조각.

    `source_url`이 없는 청크는 화면에서 출처를 붙일 수 없다 — 수집 단계에서 채운다.
    """

    text: str
    source_url: str | None = None
    published_at: datetime | None = None


@dataclass(frozen=True)
class AgentReportDto:
    agent: str
    pick: str | None
    weight: float
    summary: str
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentPredictionDto:
    """API로 나가는 예측 한 건. `source`로 폴백 여부가 드러난다(하네스 §3-D5)."""

    match_key: str
    pick: str
    pick_name: str
    win_probability: float
    confidence: float
    rationale: str
    source: str
    generated_at: datetime
    reports: tuple[AgentReportDto, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class GenerationSummary:
    """생성 결과 요약. 개별 실패가 전체를 실패시키지 않는다(하네스 §7.2)."""

    requested: int
    generated: int
    skipped: int
    failed: int
