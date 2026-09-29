"""위키 동기화 계획 테스트.

**기준선과 위키 행은 2026-09-29 실측값이다** — 왼쪽은 운영 `championship_titles`,
오른쪽은 `List of current champions in WWE`(개정본 1374648912)가 그날 말한 것이다.
그날 22개 벨트 중 13개가 어긋나 있었다.

고정하는 계약 일곱:

1. 이름만 다른 벨트는 별칭표로 이어 붙인다 (`WWE Evolve Men's` = `WWE Evolve`)
2. 위키에 없는 보드 벨트는 **지우지 않고** 알린다 (Speed 벨트 둘이 그렇게 걸렸다)
3. 보드에 없는 위키 벨트는 **추가하지 않고** 알린다
4. 같은 재위면 줄을 손대지 않는다 — 나열 순서만 다른 것도 같은 재위다
5. 바뀐 줄의 `won_event`는 위키 값으로 덮고, 위키가 못 준 줄은 **비운다**
6. 획득일을 못 읽은 위키 행으로는 챔피언도 바꾸지 않는다
7. 줄 순서는 기준선 그대로이고, 기준일은 **아무것도 안 바뀌어도** 올라간다

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/kayfabe/tests -q
"""

from __future__ import annotations

from kayfabe.app.services.wiki_belt_names import WIKI_BELT_ALIASES
from kayfabe.domain.services.champion_board_sync import plan_wiki_sync
from kayfabe.domain.services.champion_table_parser import WikiChampionRow
from kayfabe.domain.services.championship_succession import TitleReign

AS_OF = "2026-09-29"

_BASELINE = (
    TitleReign(
        belt_name="World Heavyweight Championship",
        champions=("Roman Reigns",),
        won_at="2026-04-19",
        won_event="WrestleMania 42",
    ),
    TitleReign(
        belt_name="Undisputed WWE Championship",
        champions=("CM Punk",),
        won_at="2026-07-06",
        won_event="Raw",
    ),
    TitleReign(
        belt_name="Women's United States Championship",
        champions=("Tiffany Stratton",),
        won_at="2026-04-24",
        won_event="SmackDown",
    ),
    TitleReign(
        belt_name="World Tag Team Championship",
        champions=("Austin Theory", "Bron Breakker"),
        team_name="The Vision",
        won_at="2026-07-06",
        won_event="Raw",
    ),
    # **카탈로그에서 지워지기 전 상태다.** 이 줄이 `missing_on_wiki`로 걸린 것이
    # Speed 벨트 둘의 폐지를 확인한 계기였다(2026-09-29). 결정이 끝난 뒤에도 계약은
    # 남는다 — 위키가 벨트를 빼는 일은 또 생기고, 그때 보드를 조용히 지워선 안 된다.
    TitleReign(
        belt_name="WWE Speed Championship",
        champions=("Lexis King",),
        won_at="2026-04-21",
        won_event="NXT Revenge",
    ),
)

_WIKI = (
    WikiChampionRow(
        belt_name="World Heavyweight Championship",
        champions=("Roman Reigns",),
        team_name=None,
        won_at="2026-04-19",
        won_event="WrestleMania 42",
    ),
    WikiChampionRow(
        belt_name="Undisputed WWE Championship",
        champions=("Sami Zayn",),
        team_name=None,
        won_at="2026-09-11",
        won_event="SmackDown",
    ),
    WikiChampionRow(
        belt_name="WWE Women's United States Championship",
        champions=("Jacy Jayne",),
        team_name=None,
        won_at="2026-08-14",
        won_event="SmackDown",
    ),
    WikiChampionRow(
        belt_name="World Tag Team Championship",
        champions=("Bron Breakker", "Austin Theory"),
        team_name="The Vision",
        won_at="2026-07-06",
        won_event="Raw",
    ),
    WikiChampionRow(
        belt_name="NXT Championship",
        champions=("Grayson Waller",),
        team_name=None,
        won_at="2026-08-30",
        won_event="Heatwave",
    ),
)


def _plan(baseline=_BASELINE, wiki=_WIKI, *, as_of=AS_OF):
    return plan_wiki_sync(baseline, wiki, as_of=as_of, aliases=WIKI_BELT_ALIASES)


class TestUpdates:
    """위키가 고치는 줄."""

    def test_only_changed_rows_are_updated(self) -> None:
        plan = _plan()

        assert [update.belt_name for update in plan.updated] == [
            "Undisputed WWE Championship",
            "Women's United States Championship",
        ]
        updated = {reign.belt_name: reign for reign in plan.reigns}
        assert updated["Undisputed WWE Championship"].champions == ("Sami Zayn",)
        assert updated["Undisputed WWE Championship"].won_at == "2026-09-11"

    def test_alias_links_a_differently_named_belt(self) -> None:
        """이 계약이 없으면 `Women's United States`가 '위키에 없는 벨트'로 빠진다."""
        plan = _plan()

        assert "Women's United States Championship" not in plan.missing_on_wiki
        updated = {reign.belt_name: reign for reign in plan.reigns}
        assert updated["Women's United States Championship"].champions == (
            "Jacy Jayne",
        )
        # **보드 이름을 지킨다** — PLE 경기 제목이 이 이름과 정확 일치해야 한다.
        assert "WWE Women's United States Championship" not in updated

    def test_listing_order_alone_is_not_a_change(self) -> None:
        """순서를 변경으로 세면 매번 같은 줄을 다시 쓰고 `won_event`가 그때마다 갈린다."""
        plan = _plan()

        assert "World Tag Team Championship" in plan.unchanged
        tag = {reign.belt_name: reign for reign in plan.reigns}[
            "World Tag Team Championship"
        ]
        assert tag.champions == ("Austin Theory", "Bron Breakker")

    def test_won_event_is_cleared_when_wiki_has_none(self) -> None:
        """옛 대회명을 남기면 보드가 새 챔피언·새 날짜에 옛 대회를 붙여 거짓을 말한다."""
        wiki = (
            WikiChampionRow(
                belt_name="Undisputed WWE Championship",
                champions=("Sami Zayn",),
                team_name=None,
                won_at="2026-09-11",
                won_event=None,
            ),
        )
        plan = _plan(wiki=wiki)

        assert plan.updated[0].after.won_event is None


class TestGates:
    """고치지 않고 알리기만 하는 경우."""

    def test_belt_missing_from_wiki_is_kept_and_reported(self) -> None:
        """지우는 것은 사람이 한다 — 여기서 지우면 문서 누락이 보드를 비운다."""
        plan = _plan()

        assert plan.missing_on_wiki == ("WWE Speed Championship",)
        speed = {reign.belt_name: reign for reign in plan.reigns}[
            "WWE Speed Championship"
        ]
        assert speed.champions == ("Lexis King",)
        assert speed.won_event == "NXT Revenge"

    def test_wiki_belt_missing_from_board_is_reported(self) -> None:
        plan = _plan()

        assert plan.unmatched_wiki == ("NXT Championship",)
        assert all(reign.belt_name != "NXT Championship" for reign in plan.reigns)

    def test_row_without_a_date_changes_nothing(self) -> None:
        wiki = (
            WikiChampionRow(
                belt_name="Undisputed WWE Championship",
                champions=("Sami Zayn",),
                team_name=None,
                won_at="",
            ),
        )
        plan = _plan(wiki=wiki)

        assert plan.updated == ()
        assert "Undisputed WWE Championship" in plan.missing_on_wiki
        kept = {reign.belt_name: reign for reign in plan.reigns}[
            "Undisputed WWE Championship"
        ]
        assert kept.champions == ("CM Punk",)


class TestBoardShape:
    """보드의 모양과 기준일."""

    def test_board_order_is_preserved(self) -> None:
        plan = _plan()

        assert [reign.belt_name for reign in plan.reigns] == [
            reign.belt_name for reign in _BASELINE
        ]

    def test_as_of_advances_without_changes(self) -> None:
        """갱신된 것은 값이 아니라 '언제까지 확인했는가'다 — PLE 관문이 그 날짜를 본다."""
        plan = _plan(baseline=_BASELINE[:1], wiki=_WIKI[:1])

        assert plan.updated == ()
        assert plan.unchanged == ("World Heavyweight Championship",)
        assert plan.as_of == AS_OF
