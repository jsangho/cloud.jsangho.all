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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    reports: Mapped[list[AgentReportModel]] = relationship(
        back_populates="prediction",
        cascade="all, delete-orphan",
        order_by="AgentReportModel.id",
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    prediction: Mapped[AgentPredictionModel] = relationship(back_populates="reports")


#: `sources` 컬럼 구분자. 코드 양쪽이 같은 값을 봐야 한다.
SOURCE_SEPARATOR = "\n"
