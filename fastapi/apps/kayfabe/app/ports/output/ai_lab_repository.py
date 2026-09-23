"""AI LAB 출력 포트 — **읽기만 한다** (Phase 3-0·3-1).

리포지토리는 행을 읽어 오는 일만 맡고, 세는 일과 판정은
`app/services/ai_lab_integrity.py`가 한다. 그래야 신뢰성 판정 규칙이 DB 없이
테스트된다 — 이 화면에서 가장 중요한 로직이 바로 그 판정이다.

지금 규모(예측 12 · 리포트 30)에서는 전부 읽어 메모리에서 접는다. 예측이 수천 건이
되면 SQL 집계로 옮긴다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.agent_prediction_dto import MatchOption
from kayfabe.app.services.ai_lab_evaluation import RetrievalRow
from kayfabe.app.services.ai_lab_integrity import (
    CorpusFacts,
    PredictionRow,
    ReportRow,
)
from kayfabe.app.services.ai_lab_knowledge import DocumentRow
from kayfabe.app.services.ai_lab_readiness import EventRow


class AiLabRepository(ABC):
    """`/ai-lab/*` 라우터가 쓰는 읽기 포트."""

    @abstractmethod
    async def list_predictions(self) -> list[PredictionRow]:
        """저장된 예측 전체 + 그 경기의 실제 결과(`winner_pick`)."""
        ...

    @abstractmethod
    async def list_reports(self) -> list[ReportRow]:
        """에이전트 리포트 전체. 인용 출처가 여기 실려 온다."""
        ...

    @abstractmethod
    async def list_retrievals(self) -> list[RetrievalRow]:
        """예측이 **그때 읽은** 청크 기록 (Phase 3-13 Stage 4-B).

        옛 예측에는 행이 없다. 비어 있는 것이 정상이고, 판정은 그때 문서 단위
        계보로 되돌아간다.
        """
        ...

    @abstractmethod
    async def corpus_facts(self) -> CorpusFacts:
        """RAG 코퍼스 실측 — 청크·문서·도메인 수와 발행일 보유 수."""
        ...

    @abstractmethod
    async def list_documents(self) -> list[DocumentRow]:
        """지식 청크를 출처 URL로 묶은 문서 목록 (Phase 3-4).

        **여기서만 묶는다.** `corpus_facts()`도 문서 수를 세지만 그것은 개요의
        한 줄짜리 값이고, 이쪽은 문서마다 청크·임베딩·발행일을 함께 낸다.
        """
        ...

    @abstractmethod
    async def count_events(self) -> int:
        """전체 대회 수. 예측 커버리지의 분모다."""
        ...

    @abstractmethod
    async def list_events(self) -> list[EventRow]:
        """대회 전체 + 그 카드의 경기 수 (Phase 8).

        **다른 화면은 대회를 예측을 통해서만 본다** — `list_predictions()`가 조인으로
        끌어오는 것은 예측이 있는 대회뿐이다. 준비도는 그 반대편, **아직 예측이 없는
        대회**를 묻기 때문에 대회 쪽에서 읽어야 한다. 그래서 쿼리가 하나 는다.

        거르지 않고 전부 준다 — "아직 열리지 않았는가"는 오늘이 입력인 판정이라
        `summarize_readiness`가 `as_of`를 받아서 한다. 여기서 `WHERE`로 걸러 버리면
        그 판정을 시험할 수 없다.
        """
        ...

    @abstractmethod
    async def load_match_options(
        self, *, event_slug: str, match_key: str
    ) -> tuple[MatchOption, ...]:
        """그 경기의 **지금 카드** 선택지 (Phase 5).

        **그때 카드의 스냅샷이 아니다.** 카드는 판본을 남기지 않으므로 여기서 오는
        것은 언제나 최신 하나이고, 재현은 그 사실을 감추지 않고 함께 내보낸다.

        경기 행이 사라졌거나 카드에서 선택지를 읽지 못하면 빈 튜플이다 — 예외가
        아니다. 카드가 없는 것은 오류가 아니라 재현할 수 없는 상태다.
        """
        ...
