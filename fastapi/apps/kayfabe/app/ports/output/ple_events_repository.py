from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

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
    async def set_event_schedule(
        self, *, slug: str, start_date: date | None, end_date: date | None
    ) -> bool:
        """**이미 있는 대회 행의 날짜 두 칸만** 고친다 (Phase 3-13 Stage 3-A).

        `upsert_event_from_sync`이 날짜를 쓰는 유일한 경로였는데, 그것은 날짜만 쓰지
        않는다 — 카드에 없는 경기를 지우고(`ple_predictions`가 CASCADE로 함께 사라진다),
        `status`를 갈아 끼우고, 페이로드에 결과가 있으면 `winner_pick`까지 덮어쓴다.
        날짜 하나 고치자고 그 폭을 감수할 수 없어 좁은 문을 따로 낸다.

        계약:

        - 없는 slug면 `False`. **행을 만들지 않는다**(Survivor Series를 만들지 않기로
          한 결정이 여기에 걸려 있다). `UPDATE`라 구조적으로 불가능하다.
        - 정확히 한 행이 바뀌면 `True`.
        - 두 행 이상이면 예외. `slug`에 UNIQUE 제약이 있어 일어날 수 없지만,
          제약이 사라진 것을 조용히 지나치는 것보다 멈추는 편이 낫다.
        - `ple_matches`·`ple_predictions`·`ple_agent_predictions`·`ple_agent_reports`
          를 읽지도 쓰지도 않는다.
        - `label`·`month`·`year`·`status`·`finished_at`은 건드리지 않는다.

        커밋하지 않는다 — 트랜잭션 경계는 부르는 쪽이 정한다(`flush`까지만 한다).
        """
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
