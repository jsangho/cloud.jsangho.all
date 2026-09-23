"""AI 멀티 에이전트 예측 저장 테이블 — `_docs/ai-match-predictions-harness.md` §6.

기존 `ple_matches.ai_pick`(20자) 3컬럼으로는 승률·근거·에이전트별 리포트를 담을
자리가 없어 별도 테이블을 둔다(§2-D5). 기존 컬럼은 그대로 살려 적중률 집계
(`get_ai_stats`)의 연속성을 지킨다.
"""

from __future__ import annotations

from datetime import datetime

from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


class AgentPredictionModel(Base):
    """경기 하나에 대한 최종 예측."""

    __tablename__ = "ple_agent_predictions"
    __table_args__ = (
        # 경기당 예측은 하나다. 재생성은 기존 행을 대체한다.
        UniqueConstraint("event_id", "match_key", name="uq_agent_prediction_match"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("ple_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    match_key: Mapped[str] = mapped_column(String(80), nullable=False)
    #: "left" | "right" | 다인전 인덱스 문자열. `ple_matches.winner_pick`과 같은 형식이어야 채점된다.
    pick: Mapped[str] = mapped_column(String(20), nullable=False)
    pick_name: Mapped[str] = mapped_column(String(200), nullable=False)
    #: 0.0~1.0. 화면에서만 %로 바꾼다(하네스 §3-D4).
    win_probability: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    #: "agents" | "bookmaker_fallback" — 폴백으로 만들어졌는지 화면이 구분해야 한다(§3-D5).
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    #: 생성 시점에 결과가 **시스템 밖에서** 이미 알려져 있었는가 (Phase 3-7).
    #: `NULL`은 모른다가 아니라 **아무도 선언하지 않았다**는 뜻이다 — 그 행은
    #: Phase 3-6의 판정 경로를 그대로 지난다. "모른다"는 `False`로 명시한다.
    outcome_known_externally: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
    #: 위 선언의 근거. **사실만 적는다** — 추정한 경기 날짜나 승자를 넣지 않는다.
    provenance_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: 지식 검색에 실제로 쓴 질의 (Phase 3). 경기 제목 + 선택지 이름으로 만들어지므로
    #: 파생값처럼 보이지만, **카드가 바뀌면 재료가 사라진다** — 경기 행이 없어진
    #: 예측이 이미 있다. `NULL`은 기록 전이며 백필하지 않는다.
    knowledge_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    reports: Mapped[list[AgentReportModel]] = relationship(
        back_populates="prediction",
        cascade="all, delete-orphan",
        order_by="AgentReportModel.id",
        lazy="selectin",
    )
    retrievals: Mapped[list[PredictionRetrievalModel]] = relationship(
        back_populates="prediction",
        cascade="all, delete-orphan",
        order_by="PredictionRetrievalModel.rank",
        lazy="selectin",
    )


class AgentReportModel(Base):
    """에이전트 한 명의 의견. 근거가 없으면 예측을 만들지 않으므로 이 행이 곧 근거다."""

    __tablename__ = "ple_agent_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("ple_agent_predictions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: "storyline" | "odds" | "rumor"
    agent: Mapped[str] = mapped_column(String(30), nullable=False)
    #: 의견 없음은 NULL이다 — 빈 문자열과 구분한다.
    pick: Mapped[str | None] = mapped_column(String(20), nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: 출처 URL 목록. 줄바꿈으로 잇는다 — 조회 시 통째로 읽고 쓰기만 해서 배열 타입이 필요 없다.
    sources: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: 아래 셋은 **이 의견이 만들어진 조건**이다 (Phase 4). 셋 다 nullable인 이유가
    #: 서로 다르므로 한 덩어리로 읽지 않는다 — 자세한 것은 `AgentRuntime` 독스트링.
    #:
    #: 실제로 답한 모델 이름. 예비 모델로 넘어갔으면 예비 쪽이 들어간다. LLM을 쓰지
    #: 않는 오즈 에이전트와, 모델을 고정하지 않아 허브 기본값에 맡긴 호출은 `NULL`이다.
    model_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    #: 지시문 sha256 앞 16자리. **프롬프트 원문은 저장하지 않는다** — 되돌릴 수 없는
    #: 해시만 남긴다(§11-6). 모델을 부르지 않았으면 `NULL`.
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: 에이전트 로직의 판. 사람이 선언하는 값이라 해시와 달리 틀릴 수 있다.
    #: **Phase 4 이전 행은 `NULL`이고 백필하지 않는다** — 그 리포트가 어느 판에서
    #: 나왔는지 아무도 모르고, 지금 값을 적으면 없던 사실을 만드는 것이 된다.
    agent_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    prediction: Mapped[AgentPredictionModel] = relationship(back_populates="reports")


class PredictionRetrievalModel(Base):
    """예측을 만들 때 프롬프트에 들어간 청크 하나 (Phase 3-13).

    **청크에 FK를 걸지 않는다.** 재수집이 그 URL의 옛 청크를 통째로 DELETE하므로
    (`replace_document_chunks`), 참조로 두면 코퍼스를 다시 모으는 순간 이 기록이
    가리키는 것이 사라진다. 그래서 당시 값을 그대로 베껴 둔다 — 비정규화가 아니라
    **스냅샷**이다. `chunk_id`도 참조가 아니라 당시 식별자를 적어 둔 것뿐이다.

    예측이 지워지면 이 기록도 함께 지운다. 재생성은 예측 행을 갈아 끼우므로
    (`AgentPredictionPgRepository.save`), 옛 생성의 기록이 새 예측에 붙지 않는다.
    """

    __tablename__ = "ple_prediction_retrievals"
    __table_args__ = (
        # 한 예측 안에서 읽은 순서는 하나뿐이다. 중복은 기록을 무의미하게 만든다.
        UniqueConstraint("prediction_id", "rank", name="uq_prediction_retrieval_rank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("ple_agent_predictions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: 프롬프트에 들어간 순서(1부터). 검색 순위가 아니라 **읽은 순서**다.
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    #: 당시 청크 행의 id. **참조가 아니다** — 재수집하면 그 행은 없을 수 있다.
    chunk_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: 본문 sha256. 재수집 뒤에도 같은 글인지 대조할 수 있는 유일한 값이다.
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: 그때 프롬프트에 들어간 **본문 그대로** (Phase 3). 해시는 *대조*만 되고
    #: 복원은 안 된다 — 재수집이 옛 청크를 지우면 그 글은 어디에도 없다.
    #: `NULL`은 기록 전이다. 허용 도메인 글만 코퍼스에 들어오므로 §4-8과 무관하다.
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: 그때 읽은 개정본. **URL이 같아도 개정본이 다르면 다른 글이다.**
    source_revision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_revised_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: 코사인 거리. 작을수록 가깝다. 못 구하면 NULL — 0.0으로 채우지 않는다.
    distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    prediction: Mapped[AgentPredictionModel] = relationship(back_populates="retrievals")


#: `sources` 컬럼 구분자. 코드 양쪽이 같은 값을 봐야 한다.
SOURCE_SEPARATOR = "\n"
