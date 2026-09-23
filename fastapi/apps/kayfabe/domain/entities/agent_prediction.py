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
class AgentRuntime:
    """리포트 하나가 **어떤 조건에서 만들어졌는가** (Phase 4).

    의견(`AgentReport`)과 분리해 두는 이유는 둘이 다른 것을 말하기 때문이다. 의견은
    "누가 이긴다고 봤는가"이고, 이 값은 "그 의견을 낸 것이 무엇이었는가"다. 프롬프트를
    고치거나 모델을 갈아 끼우면 같은 경기에서 다른 의견이 나오는데, 그 기록이 없으면
    **두 예측이 왜 다른지 사후에 물을 수 없다.**

    세 칸의 성격이 서로 다르다. 그 차이를 감추지 않는다:

    * `model` — 그 호출이 **실제로 지정한** 모델 이름. 벤더가 따로 주는 버전 문자열이
      아니라 모델 id 자체다(Gemini는 그런 값을 주지 않으므로 지어내지 않는다).
      LLM을 쓰지 않는 오즈 에이전트, 그리고 모델을 지정하지 않아 허브 기본값
      (`GEMINI_MODEL`)에 맡긴 호출은 `None`이다 — **`None`은 "모른다"가 아니라
      "우리가 고정하지 않았다"는 사실이다.** 예비 모델로 넘어간 호출은 예비 쪽
      이름이 들어간다. 주 모델 이름을 적으면 그 기록이 거짓이 된다.
    * `prompt_version` — 지시문에서 **파생된** 해시라 손으로 못 속인다.
      덮는 범위는 페르소나 · 조립 틀 · 출력 규칙이다. 모델을 부르지 않았으면 `None`.
    * `agent_version` — **사람이 선언하는** 값이다. 판독·의견 강등·무게 계산처럼
      해시로 잡히지 않는 로직의 판을 가리킨다. 파생값이 아니므로 올리는 것을 잊으면
      **틀린 값이 된다** — 그 한계를 알고 쓴다. 대신 항상 존재한다.
    """

    agent_version: str
    model: str | None = None
    prompt_version: str | None = None

    def __post_init__(self) -> None:
        if not self.agent_version:
            raise ValueError("agent_version은 비어 있을 수 없습니다.")


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
    #: 이 의견을 만든 조건 (Phase 4). **`None`은 기록이 없다는 뜻이다** — Phase 4
    #: 이전에 저장된 리포트가 그렇다. 사후에 지금 값으로 채우지 않는다. 그때 어떤
    #: 프롬프트였는지는 아무도 모르고, 지금 것을 적으면 거짓 기록이 된다.
    runtime: AgentRuntime | None = None

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
