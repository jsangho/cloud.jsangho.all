"""AI LAB 출력 포트 — **읽기만 한다** (Phase 3-0·3-1).

리포지토리는 행을 읽어 오는 일만 맡고, 세는 일과 판정은
`app/services/ai_lab_integrity.py`가 한다. 그래야 신뢰성 판정 규칙이 DB 없이
테스트된다 — 이 화면에서 가장 중요한 로직이 바로 그 판정이다.

지금 규모(예측 12 · 리포트 30)에서는 전부 읽어 메모리에서 접는다. 예측이 수천 건이
되면 SQL 집계로 옮긴다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.services.ai_lab_integrity import (
    CorpusFacts,
    PredictionRow,
    ReportRow,
)


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
    async def corpus_facts(self) -> CorpusFacts:
        """RAG 코퍼스 실측 — 청크·문서·도메인 수와 발행일 보유 수."""
        ...

    @abstractmethod
    async def count_events(self) -> int:
        """전체 대회 수. 예측 커버리지의 분모다."""
        ...
