"""데이터 센터 코디네이터 — 가짜 포트만 쓴다. DB 호출 0회 (Phase 2).

여기서 잠그는 것은 **필터와 페이지 자르기**다. 세는 규칙은
`test_data_center_stats.py`가 따로 지킨다.
"""

from __future__ import annotations

import json

import pytest

# 순환 임포트 회피 — 사연은 `test_data_center_stats.py` 상단 주석에 있다.
import kayfabe.adapter.inbound.api  # noqa: F401
from kayfabe.app.dtos.data_center_dto import MatchPageQuery, WrestlerPageQuery
from kayfabe.app.ports.output.data_center_repository import DataCenterRepository
from kayfabe.app.services.data_center_stats import MatchRow, TitleRow, WrestlerRow
from kayfabe.app.use_cases.data_center_interactor import DataCenterInteractor


def _card(left: str, right: str) -> str:
    return json.dumps(
        {"format": "singles", "left": {"name": left}, "right": {"name": right}}
    )


def _match(
    slug: str, key: str, left: str, right: str, month: int | None = 1
) -> MatchRow:
    return MatchRow(
        event_slug=slug,
        event_label=slug.title(),
        month=month,
        year=2026,
        event_status="finished",
        match_key=key,
        title="Single Match",
        format="singles",
        card_json=_card(left, right),
        winner_pick="left",
        winner_name=None,
        status="finished",
    )


class FakeRepository(DataCenterRepository):
    """포트 페이크. **읽어 준 것만 돌려준다.**"""

    def __init__(
        self,
        *,
        wrestlers: list[WrestlerRow] | None = None,
        matches: list[MatchRow] | None = None,
        titles: list[TitleRow] | None = None,
        events: tuple[int, int] = (2, 1),
        belts: int = 18,
    ) -> None:
        self._wrestlers = wrestlers or []
        self._matches = matches or []
        self._titles = titles or []
        self._events = events
        self._belts = belts

    async def list_wrestlers(self) -> list[WrestlerRow]:
        return list(self._wrestlers)

    async def list_matches(self) -> list[MatchRow]:
        return list(self._matches)

    async def list_title_acquisitions(self) -> list[TitleRow]:
        return list(self._titles)

    async def count_events(self) -> tuple[int, int]:
        return self._events

    async def count_championship_belts(self) -> int:
        return self._belts


WRESTLERS = [
    WrestlerRow(name="Cody Rhodes", brand="RAW", real_name="Cody Runnels"),
    WrestlerRow(name="Seth Rollins", brand="RAW"),
    WrestlerRow(name="Liv Morgan", brand="SmackDown"),
]
MATCHES = [
    _match("royal-rumble", "rr1", "Cody Rhodes", "Seth Rollins"),
    _match("summerslam", "ss1", "Liv Morgan", "Seth Rollins", month=8),
]
TITLES = [
    TitleRow("Cody Rhodes", "Undisputed WWE Championship", "WrestleMania 40"),
    TitleRow("Cody Rhodes", "Intercontinental Championship", "Raw 2016"),
]


@pytest.fixture
def interactor() -> DataCenterInteractor:
    return DataCenterInteractor(
        data_center_repository=FakeRepository(
            wrestlers=WRESTLERS, matches=MATCHES, titles=TITLES
        )
    )


class TestOverviewCountsWhatItRead:
    @pytest.mark.asyncio
    async def test_counts_come_from_the_repository(
        self, interactor: DataCenterInteractor
    ) -> None:
        overview = await interactor.get_overview()
        assert overview.counts.wrestlers == 3
        assert overview.counts.matches == 2
        assert overview.counts.finished_matches == 2
        assert overview.counts.events == 2
        assert overview.counts.title_acquisitions == 2

    @pytest.mark.asyncio
    async def test_recent_matches_are_finished_ones(
        self, interactor: DataCenterInteractor
    ) -> None:
        overview = await interactor.get_overview()
        assert overview.recent_matches
        assert all(m.status == "finished" for m in overview.recent_matches)


class TestWrestlerPage:
    @pytest.mark.asyncio
    async def test_records_ride_along(self, interactor: DataCenterInteractor) -> None:
        page = await interactor.list_wrestlers(WrestlerPageQuery())
        by_name = {row.name: row for row in page.items}
        assert by_name["Cody Rhodes"].wins == 1
        assert by_name["Seth Rollins"].losses == 2
        assert by_name["Cody Rhodes"].titles == 2

    @pytest.mark.asyncio
    async def test_a_wrestler_without_matches_has_no_win_rate(self) -> None:
        """**0%가 아니라 빈칸이다** — 안 뛴 것과 다 진 것은 다르다."""
        repo = FakeRepository(wrestlers=[WrestlerRow(name="새 얼굴")], matches=[])
        page = await DataCenterInteractor(data_center_repository=repo).list_wrestlers(
            WrestlerPageQuery()
        )
        assert page.items[0].win_rate is None
        assert page.items[0].matches == 0

    @pytest.mark.asyncio
    async def test_search_matches_ring_name_and_real_name(
        self, interactor: DataCenterInteractor
    ) -> None:
        by_ring = await interactor.list_wrestlers(WrestlerPageQuery(q="cody"))
        by_real = await interactor.list_wrestlers(WrestlerPageQuery(q="runnels"))
        assert [r.name for r in by_ring.items] == ["Cody Rhodes"]
        assert [r.name for r in by_real.items] == ["Cody Rhodes"]

    @pytest.mark.asyncio
    async def test_brand_filter_uses_real_values(
        self, interactor: DataCenterInteractor
    ) -> None:
        page = await interactor.list_wrestlers(WrestlerPageQuery(brand="SmackDown"))
        assert [r.name for r in page.items] == ["Liv Morgan"]
        assert page.brands == ["RAW", "SmackDown"]

    @pytest.mark.asyncio
    async def test_pagination_slices_without_losing_the_total(
        self, interactor: DataCenterInteractor
    ) -> None:
        page = await interactor.list_wrestlers(WrestlerPageQuery(page=2, size=2))
        assert page.total == 3
        assert len(page.items) == 1
        assert (page.page, page.size) == (2, 2)

    @pytest.mark.asyncio
    async def test_a_page_past_the_end_is_empty_not_an_error(
        self, interactor: DataCenterInteractor
    ) -> None:
        page = await interactor.list_wrestlers(WrestlerPageQuery(page=99, size=10))
        assert page.items == []
        assert page.total == 3


class TestMatchPage:
    @pytest.mark.asyncio
    async def test_event_filter(self, interactor: DataCenterInteractor) -> None:
        page = await interactor.list_matches(MatchPageQuery(event="summerslam"))
        assert [m.match_key for m in page.items] == ["ss1"]
        assert page.total == 1

    @pytest.mark.asyncio
    async def test_competitor_filter_looks_at_participants(
        self, interactor: DataCenterInteractor
    ) -> None:
        page = await interactor.list_matches(MatchPageQuery(competitor="Liv"))
        assert [m.match_key for m in page.items] == ["ss1"]

    @pytest.mark.asyncio
    async def test_event_options_always_come_along(
        self, interactor: DataCenterInteractor
    ) -> None:
        """필터 후보는 **DB에 있는 대회만**이다 — 목록을 화면에 박지 않는다."""
        page = await interactor.list_matches(MatchPageQuery(event="summerslam"))
        assert {e.slug for e in page.events} == {"royal-rumble", "summerslam"}

    @pytest.mark.asyncio
    async def test_winner_is_derived_for_the_row(
        self, interactor: DataCenterInteractor
    ) -> None:
        page = await interactor.list_matches(MatchPageQuery())
        assert page.items[0].winner_name in {"Cody Rhodes", "Liv Morgan"}


class TestChampionshipStats:
    @pytest.mark.asyncio
    async def test_belts_and_holders_are_counted(
        self, interactor: DataCenterInteractor
    ) -> None:
        stats = await interactor.get_championship_stats()
        assert stats.total_acquisitions == 2
        assert stats.belt_count == 2
        assert stats.holder_count == 1
        assert stats.top_holders[0].name == "Cody Rhodes"
        assert stats.top_holders[0].reigns == 2

    @pytest.mark.asyncio
    async def test_no_reign_length_is_reported(
        self, interactor: DataCenterInteractor
    ) -> None:
        """§9 — `won_at`이 자유 텍스트라 최장 재위는 만들지 않는다."""
        stats = await interactor.get_championship_stats()
        assert not any("longest" in field for field in vars(stats.belts[0]))


class TestAnalytics:
    @pytest.mark.asyncio
    async def test_distributions_add_up_to_the_matches(
        self, interactor: DataCenterInteractor
    ) -> None:
        analytics = await interactor.get_analytics()
        assert analytics.singles_matches + analytics.multi_matches == 2
        assert analytics.title_matches + analytics.non_title_matches == 2

    @pytest.mark.asyncio
    async def test_brand_counts_come_from_the_wrestler_rows(
        self, interactor: DataCenterInteractor
    ) -> None:
        analytics = await interactor.get_analytics()
        assert {b.brand: b.wrestlers for b in analytics.brands} == {
            "RAW": 2,
            "SmackDown": 1,
        }

    @pytest.mark.asyncio
    async def test_the_sample_threshold_is_published(
        self, interactor: DataCenterInteractor
    ) -> None:
        """화면이 "N경기 이상"이라고 적을 수 있어야 순위가 읽힌다."""
        analytics = await interactor.get_analytics()
        assert analytics.min_matches_for_rate >= 1
