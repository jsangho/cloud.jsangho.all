"""AI LAB 입력 포트 (Phase 3-0·3-1).

**조회만 있다.** 이 화면은 LLM을 부르지 않는다 — 예측 생성은 관리자 전용 경로
(`POST /api/ple_events/{slug}/ai-predictions`)와 배치 스크립트의 몫이고, 화면 진입이
비용을 만드는 구조를 만들지 않는다(하네스 §3-D1).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.ai_lab_dto import AiLabOverviewResponse, AiLabPredictionsResponse


class AiLabUseCase(ABC):
    @abstractmethod
    async def get_overview(self) -> AiLabOverviewResponse:
        """예측 집계·신뢰성 판정·시스템 상태·에이전트 활동·최근 예측."""
        ...

    @abstractmethod
    async def list_predictions(self) -> AiLabPredictionsResponse:
        """저장된 예측 전체 + 에이전트 리포트 + 무결성 판정.

        **페이지네이션이 없다.** 지금 예측은 12건이고, 나눠 보낼 이유가 생기기 전에
        나누면 화면과 API 양쪽에 쓰이지 않는 구조만 남는다. 수백 건이 되면 그때
        `data_center`의 페이지 질의 패턴을 그대로 가져온다 — 그 경계를 여기 적어 둔다.
        """
        ...
