from __future__ import annotations

from abc import ABC, abstractmethod

from pandas import DataFrame

from titanic.app.dtos.crew_hartley_violin_dto import (
    HartleyViolinQuery,
    HartleyViolinResponse,
)


class HartleyViolinUseCase(ABC):
    """`/titanic/hartley/*` inbound(hartley_violin_router) 입력 포트."""

    @abstractmethod
    async def introduce_myself(
        self, query: HartleyViolinQuery
    ) -> HartleyViolinResponse:
        """하틀리 자기소개 메소드 (`GET /myself`)."""
        ...

    @abstractmethod
    def get_correlation_heatmap(self, df: DataFrame) -> bytes:
        """수치형 컬럼 간 상관관계 히트맵을 PNG 바이트로 반환."""
        ...

    @abstractmethod
    def get_survival_rate_chart(self, df: DataFrame) -> bytes:
        """pclass·sex·embarked 별 생존율 바 차트를 PNG 바이트로 반환."""
        ...
