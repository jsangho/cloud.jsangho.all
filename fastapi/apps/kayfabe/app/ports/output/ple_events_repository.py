from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.ple_events_dto import (
    MatchResultResponse,
    PleAiStatsResponse,
    PleEventReadQuery,
    PleEventSnapshotQuery,
    PleEventSummaryResponse,
    PleEventSyncCommand,
)


class PleEventsRepository(ABC):
    """PLE 조회 출력 포트."""

    @abstractmethod
    async def list_events(self) -> list[PleEventReadQuery]: ...

    @abstractmethod
    async def get_event_by_slug(self, slug: str) -> PleEventReadQuery | None: ...

    @abstractmethod
    async def get_prediction_pick_by_user(
        self, match_id: int, user_id: int
    ) -> str | None: ...

    @abstractmethod
    async def get_prediction_pick(
        self, match_id: int, client_id: str
    ) -> str | None: ...

    @abstractmethod
    async def aggregate_votes_for_match(
        self, *, match_id: int, fmt: str, card_json: str
    ) -> dict[str, int | list[int]]:
        """경기별 사이트 투표 집계."""
        ...

    @abstractmethod
    async def get_ai_stats(self) -> PleAiStatsResponse: ...

    @abstractmethod
    async def list_events_by_year(self, year: int) -> list[PleEventSummaryResponse]:
        """연도별 PLE 이벤트 목록."""
        ...

    @abstractmethod
    async def user_exists(self, *, user_id: int) -> bool:
        """예측 저장 전 로그인 회원 존재 여부 확인."""
        ...

    @abstractmethod
    async def flush(self) -> None:
        """현재 트랜잭션 변경 사항을 DB에 반영."""
        ...

    @abstractmethod
    async def upsert_event_from_sync(
        self, payload: PleEventSyncCommand
    ) -> PleEventSnapshotQuery:
        """프론트 매치 카드를 Neon에 upsert."""
        ...

    @abstractmethod
    async def upsert_prediction(
        self, match_id: int, client_id: str, pick: str, user_id: int
    ) -> None:
        """경기 예측 저장."""
        ...

    @abstractmethod
    async def set_match_result(
        self,
        slug: str,
        match_key: str,
        result: MatchResultResponse,
        status: str | None = None,
    ) -> bool:
        """경기 결과 저장. 성공 시 True."""
        ...

    @abstractmethod
    async def mark_event_finished(self, *, event_id: int, finished_at) -> None:
        """이벤트 상태를 finished로 갱신."""
        ...

    @abstractmethod
    async def refresh_all_match_point_values(self) -> int:
        """랭킹 집계 전 전체 매치 점수 재계산."""
        ...
