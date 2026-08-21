"""데이터 센터 출력 포트 — **읽기만 한다** (Phase 2).

리포지토리는 행을 읽어 오는 일만 맡고, 세는 일은 `app/services/data_center_stats.py`가
한다. 그래야 집계 규칙이 DB 없이 테스트된다.

**지금 규모에서는 전부 읽어 메모리에서 접는다** (경기 68 · 선수 178 · 타이틀 367).
선수별 전적은 어차피 모든 경기를 훑어야 나오므로 부분만 읽어도 이득이 없다.
경기가 수천 건이 되면 집계 테이블이나 SQL 집계로 옮긴다 — 그 경계를 여기 적어 둔다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.services.data_center_stats import MatchRow, TitleRow, WrestlerRow


class DataCenterRepository(ABC):
    """`/data-center/*` 라우터가 쓰는 읽기 포트."""

    @abstractmethod
    async def list_wrestlers(self) -> list[WrestlerRow]:
        """`wrestlers` 전체. **데이터 센터의 선수 원본은 이 표다** (§1)."""
        ...

    @abstractmethod
    async def list_matches(self) -> list[MatchRow]:
        """`ple_matches` 전체 + 그 대회 정보(월·연도·상태)."""
        ...

    @abstractmethod
    async def list_title_acquisitions(self) -> list[TitleRow]:
        """`title_acquisitions` 전체."""
        ...

    @abstractmethod
    async def count_events(self) -> tuple[int, int]:
        """(전체 대회 수, 종료된 대회 수)."""
        ...

    @abstractmethod
    async def count_championship_belts(self) -> int:
        """현 챔피언 보드에 올라 있는 벨트 수 (`championship_titles`)."""
        ...
