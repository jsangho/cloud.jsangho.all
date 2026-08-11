"""턴 — 성향이 반대편으로 넘어가는 사건 (하네스 §3-D39).

성향은 카드 169개가 조금씩 움직여 왔지만, **그 값이 0을 넘어가는 순간에는 아무 일도
일어나지 않았다.** 어느 밤에 등을 돌렸는지가 화면 어디에도 없었다.
"""

from __future__ import annotations

from wwe_game.domain.services import news_feed
from wwe_game.domain.value_objects.week_report import WeekKind, WeekReport
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

PLAYER = "장상호"


def feed_of(*alignments: int) -> tuple[news_feed.NewsItem, ...]:
    """성향만 바꿔 가며 주차를 세운다 — 나머지는 뉴스가 안 읽는다."""
    entries = tuple(
        (
            WeekReport(week=i + 1, kind=WeekKind.WEEKLY_SHOW),
            WrestlerStats(alignment=a),
        )
        for i, a in enumerate(alignments)
    )
    return news_feed.compile_feed(entries, (), PLAYER)


def turns(*alignments: int) -> list[news_feed.NewsItem]:
    return [i for i in feed_of(*alignments) if i.kind is news_feed.NewsKind.TURN]


class TestATurnIsCrossingSides:
    def test_face_to_heel_is_a_turn(self) -> None:
        moments = turns(40, 40, -40, -40)
        assert len(moments) == 1
        assert moments[0].week == 3
        assert "등을 돌렸다" in moments[0].headline
        assert moments[0].mood is news_feed.CrowdMood.JEER

    def test_heel_to_face_is_a_turn(self) -> None:
        moments = turns(-40, -40, 40)
        assert len(moments) == 1
        assert "관중 쪽으로" in moments[0].headline
        assert moments[0].mood is news_feed.CrowdMood.ROAR

    def test_the_first_commitment_is_not_a_turn(self) -> None:
        """**뒤집을 앞면이 없었다.** 데뷔하고 처음 한쪽에 서는 것은 턴이 아니다."""
        assert turns(0, 5, 10, 40, 40) == []

    def test_drifting_through_the_middle_is_not_a_turn(self) -> None:
        """중립 구간(-19~19)은 관중이 갈린 상태다. 드나드는 것을 세면 턴이 수십 번 난다."""
        assert turns(40, 10, 40, 5, 30, 0, 25) == []

    def test_crossing_all_the_way_after_a_pause_still_counts(self) -> None:
        """가운데를 지나 반대편까지 갔으면 턴이다 — 몇 주에 걸쳐 갔더라도."""
        moments = turns(40, 10, 0, -10, -40)
        assert len(moments) == 1
        assert moments[0].week == 5

    def test_turning_back_and_forth_counts_twice(self) -> None:
        moments = turns(40, -40, 40)
        assert [m.week for m in moments] == [2, 3]


class TestTheFeedSeesEachWeekAsItWas:
    def test_a_turn_and_a_title_can_share_a_week(self) -> None:
        """같은 주에 대관과 턴이 겹칠 수 있다. 한 줄만 남기면 둘 중 하나가 사라진다."""
        from wwe_game.domain.value_objects.title import Title
        from wwe_game.domain.value_objects.week_report import OutcomeKind

        entries = (
            (WeekReport(week=1, kind=WeekKind.PLE), WrestlerStats(alignment=40)),
            (
                WeekReport(
                    week=2,
                    kind=WeekKind.PLE,
                    result=OutcomeKind.WIN,
                    title_at_stake=Title.INTERCONTINENTAL_CHAMPIONSHIP,
                    opponent="세스 롤린스",
                ),
                WrestlerStats(alignment=-40),
            ),
        )
        feed = news_feed.compile_feed(entries, (), PLAYER)
        kinds = {i.kind for i in feed}
        assert news_feed.NewsKind.TURN in kinds
        assert news_feed.NewsKind.TITLE_WON in kinds
