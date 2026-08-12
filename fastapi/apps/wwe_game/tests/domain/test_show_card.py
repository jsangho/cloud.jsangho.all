"""그 밤의 카드 (하네스 §3-D52).

이 파일이 잠그는 것은 **리포트 한 장 안에서 두 줄이 서로를 부정하지 않는다**는 것이다.
카드는 벨트 계보(§3-D38)·배경 대립(§3-D44) 위에 얹히는 층이라, 결과를 따로 굴리는
순간 "오늘 X가 벨트를 뺏었다"와 "그날의 벨트: Y"가 한 화면에 같이 뜬다.
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001
from wwe_game.domain.constants import roster
from wwe_game.domain.constants.ple_calendar import calendar_for
from wwe_game.domain.services import show_card, show_report, title_scene
from wwe_game.domain.value_objects.title import TITLES, Brand, Title, titles_of
from wwe_game.domain.value_objects.wrestler_identity import Gender

SEED = 7777
WORLD = Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP

_SHOW = next(s for s in calendar_for(Brand.RAW).shows if s.name == "백래시")
SHOW_WEEK = _SHOW.week_of_year + 52 * 7
"""대회가 보장된 주차. 아무 주차나 잡으면 그 브랜드의 대회 주차가 아니다."""


def _card(**kwargs: object) -> tuple[show_card.CardMatch, ...]:
    return show_card.card_for(
        SEED,
        SHOW_WEEK,
        Gender.MALE,
        Brand.RAW,
        is_major=False,
        **kwargs,  # type: ignore[arg-type]
    )


class TestItIsAlwaysTheSameNight:
    def test_the_same_seed_makes_the_same_card(self) -> None:
        # 저장하지 않으므로(§3-D45) 되짚을 때마다 같아야 한다. 다르면 리포트를 두 번
        # 열었을 때 그 밤이 바뀐다.
        assert _card() == _card()

    def test_another_week_is_another_night(self) -> None:
        first = _card()
        later = show_card.card_for(
            SEED, SHOW_WEEK + 52, Gender.MALE, Brand.RAW, is_major=False
        )
        assert first != later


class TestNobodyWrestlesTwice:
    def test_a_name_appears_once_a_night(self) -> None:
        names = [name for m in _card() for name in (m.left, m.right)]
        assert len(names) == len(set(names))

    def test_my_opponent_is_not_on_the_card(self) -> None:
        # 내 경기는 화면이 따로 그린다 — 여기 또 나오면 그가 그 밤에 두 경기를 뛴다.
        card = _card(player="장상호", busy=("코디 로즈",))
        names = {name for m in card for name in (m.left, m.right)}
        assert "장상호" not in names
        assert "코디 로즈" not in names

    def test_the_winner_is_one_of_the_two(self) -> None:
        assert all(m.winner in (m.left, m.right) for m in _card())


class TestTheCardAgreesWithTheBeltLineage:
    def test_a_belt_that_changed_hands_names_the_new_champion(self) -> None:
        """계보가 그날 바뀌었다면 카드의 승자가 **그 새 챔피언**이어야 한다."""
        checked = 0
        for week in range(1, 800):
            before = title_scene.champion_at(SEED, week - 1, WORLD)
            now = title_scene.champion_at(SEED, week, WORLD)
            if before == now or not calendar_for(Brand.RAW).is_show_week(week):
                continue
            card = show_card.card_for(
                SEED, week, Gender.MALE, Brand.RAW, is_major=False
            )
            bout = next(
                (m for m in card if m.left == before or m.right == before), None
            )
            if bout is None:
                continue
            assert bout.winner == now
            assert bout.changed_hands is True
            checked += 1
        if checked == 0:
            pytest.skip("800주 안에 대회 주차와 겹친 타이틀 이동이 없었다")

    def test_a_defence_keeps_the_champion(self) -> None:
        """벨트가 안 넘어간 밤의 타이틀전은 챔피언이 이긴다 — 계보가 그대로이므로."""
        holders = {
            title_scene.champion_at(SEED, SHOW_WEEK, title)
            for title in titles_of(Brand.RAW, Gender.MALE)
        }
        for match in _card():
            if match.title is None or match.changed_hands:
                continue
            assert match.left in holders, "타이틀전의 한쪽은 그 주차 챔피언이어야 한다"
            assert match.winner == match.left

    def test_a_vacant_belt_is_won_in_a_match(self) -> None:
        """떠난 챔피언의 벨트는 물려주는 것이 아니라 **경기로 채운다** (2026-08-12 사용자).

        30년을 훑어 공석 결정전을 모은다 — 링을 떠난 사람이 그 경기에 서 있으면 안 된다.
        """
        cal = calendar_for(Brand.RAW)
        found = 0
        for week in range(1, 1561):
            if not cal.is_show_week(week):
                continue
            for match in show_card.card_for(
                SEED, week, Gender.MALE, Brand.RAW, is_major=False
            ):
                if not match.vacant:
                    continue
                found += 1
                assert match.changed_hands is True
                assert match.title is not None
                for name in (match.left, match.right):
                    member = roster.member_of(name)
                    assert member is not None
                    assert member.is_active_at(week), f"{name}은 이미 링을 떠났다"
        assert found > 0, "30년에 공석이 한 번도 안 생겼다 — 은퇴가 계보에 안 닿는다"

    def test_the_new_champion_wins_the_vacant_match(self) -> None:
        cal = calendar_for(Brand.RAW)
        for week in range(1, 1561):
            if not cal.is_show_week(week):
                continue
            for match in show_card.card_for(
                SEED, week, Gender.MALE, Brand.RAW, is_major=False
            ):
                if match.title is None:
                    continue
                holder = next(
                    title_scene.champion_at(SEED, week, t)
                    for t in titles_of(Brand.RAW, Gender.MALE)
                    if TITLES[t].display_name == match.title
                )
                assert match.winner == holder

    def test_my_own_belt_is_not_defended_by_someone_else(self) -> None:
        # 내가 감고 있는 벨트를 카드가 다시 걸면 "그날의 벨트: 나"와 어긋난다.
        run = make_run(
            seed=SEED,
            week=SHOW_WEEK,
            titles_won=(WORLD,),
            titles_held=frozenset({WORLD}),
        )
        report = show_report.build_night(run, SHOW_WEEK)
        mine = next(c.title for c in report.champions if c.mine)
        assert all(m.title != mine for m in report.card)


class TestTheReportCarriesIt:
    def test_a_show_night_has_other_matches(self) -> None:
        run = make_run(seed=SEED, week=SHOW_WEEK)
        report = show_report.build_night(run, SHOW_WEEK)
        assert report.card, "그 밤에 나 말고 아무도 경기를 하지 않았다"

    def test_the_player_is_never_on_it(self) -> None:
        run = make_run(seed=SEED, week=SHOW_WEEK)
        report = show_report.build_night(run, SHOW_WEEK, busy=("코디 로즈",))
        names = {n for m in report.card for n in (m.left, m.right)}
        assert "장상호" not in names
        assert "코디 로즈" not in names
