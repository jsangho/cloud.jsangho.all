"""AI LAB 입력 포트 (Phase 3-0·3-1).

**조회만 있다.** 이 화면은 LLM을 부르지 않는다 — 예측 생성은 관리자 전용 경로
(`POST /api/ple_events/{slug}/ai-predictions`)와 배치 스크립트의 몫이고, 화면 진입이
비용을 만드는 구조를 만들지 않는다(하네스 §3-D1).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.ai_lab_dto import (
    AiLabAgentsResponse,
    AiLabKnowledgeResponse,
    AiLabOverviewResponse,
    AiLabPerformanceResponse,
    AiLabPredictionsResponse,
)


class AiLabUseCase(ABC):
    @abstractmethod
    async def get_overview(self) -> AiLabOverviewResponse:
        """예측 집계·신뢰성 판정·시스템 상태·에이전트 활동·최근 예측."""
        ...

    @abstractmethod
    async def list_predictions(
        self, *, agent: str | None = None
    ) -> AiLabPredictionsResponse:
        """저장된 예측 전체 + 에이전트 리포트 + 무결성 판정.

        `agent`를 주면 **그 에이전트가 리포트를 낸 예측만** 남긴다. 모르는 이름이면
        빈 목록이다 — 없음은 예외가 아니다. 무결성·집계·대회 목록은 필터와 무관하게
        전체를 기준으로 낸다: 그것들은 *지금 보고 있는 목록*이 아니라 *저장된 예측 전체*를
        설명하는 값이라, 필터에 따라 흔들리면 무결성 경고가 약해진다.

        **페이지네이션이 없다.** 지금 예측은 12건이고, 나눠 보낼 이유가 생기기 전에
        나누면 화면과 API 양쪽에 쓰이지 않는 구조만 남는다. 수백 건이 되면 그때
        `data_center`의 페이지 질의 패턴을 그대로 가져온다 — 그 경계를 여기 적어 둔다.
        """
        ...

    @abstractmethod
    async def get_agents(self) -> AiLabAgentsResponse:
        """에이전트별 응답률·의견률·정확도·가중치·자기 참조 출처 (Phase 3-3)."""
        ...

    @abstractmethod
    async def get_performance(self) -> AiLabPerformanceResponse:
        """최종 승률이 세 의견에서 **어떻게 접혔는지** (Phase 3-5).

        **정확도를 재지 않는다.** 전체 적중률은 `get_overview()`가, 에이전트별
        정확도는 `get_agents()`가 이미 낸다. 여기서 또 세면 같은 숫자가 세 번 나온다.

        새 쿼리를 쓰지 않는다 — 이미 읽는 예측·리포트 목록을 잇는다.
        """
        ...

    @abstractmethod
    async def get_knowledge(self) -> AiLabKnowledgeResponse:
        """코퍼스 문서 목록 + **그중 실제로 프롬프트에 들어간 문서** (Phase 3-4).

        검색을 새로 돌리지 않는다 — 저장된 리포트의 출처와 문서 목록을 URL로 맞춰
        볼 뿐이다. 이 화면도 다른 AI LAB 화면처럼 LLM도 임베딩도 부르지 않는다.
        """
        ...
