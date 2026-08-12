"""태그 벨트와 스테이블 (하네스 §3-D58).

사용자가 정한 규칙 셋을 잠근다.

1. 스테이블 소속은 **같은 스테이블 안에서만** 짝을 짠다
2. 한 사람이 빠지면 **스테이블의 남은 동성 선수가 이어받는다**
3. 스테이블이 둘을 못 채우면 **벨트를 반납한다**

독립 선수는 스테이블이 없는 사람들끼리만 짠다 — 스테이블 밖과 손을 잡으면 그 스테이블이
무엇인지가 사라지기 때문이다.
"""

from __future__ import annotations

import pytest
from wwe_game.domain.constants import roster
from wwe_game.domain.services import title_scene
from wwe_game.domain.value_objects.title import TITLES, Title, TitleTier

SEEDS = (42, 7777, 1234)
TAG_TITLES = tuple(
    sorted(
        (t for t, spec in TITLES.items() if spec.tier is TitleTier.TAG),
        key=lambda t: t.value,
    )
)
WEEKS = range(0, 1561, 26)


def _pair(seed: int, week: int, title: Title) -> tuple[roster.RosterMember, ...]:
    holder = title_scene.champion_at(seed, week, title)
    assert holder is not None
    people = tuple(
        member
        for name in title_scene.members_of(holder)
        if (member := roster.member_of(name, seed)) is not None
    )
    return people


class TestTheRosterKnowsItsStables:
    def test_the_real_stables_are_there(self) -> None:
        """원본 CSV의 `Stable&Team`이 그대로 들어와야 한다 — 지어내지 않았다."""
        stables = {m.stable for m in roster.ROSTER if m.stable}
        assert "Pretty Deadly" in stables
        assert "The Tongans" in stables
        assert "Bloodline" in stables

    def test_a_stable_is_never_split_by_the_separator(self) -> None:
        # "Bloodline | The Usos"는 한 스테이블이다 — 둘로 세면 한 무리가 갈린다.
        assert all("|" not in m.stable for m in roster.ROSTER)

    def test_the_made_up_wrestlers_have_no_stable(self) -> None:
        # 가상 선수에게 스테이블을 지어 주지 않는다 — 원본에 없는 사실이다.
        assert any(m.stable == "" for m in roster.ROSTER)


class TestTagBeltsAreHeldByTwo:
    @pytest.mark.parametrize("seed", SEEDS)
    @pytest.mark.parametrize("title", TAG_TITLES)
    def test_two_people_hold_it(self, seed: int, title: Title) -> None:
        for week in WEEKS:
            assert len(_pair(seed, week, title)) == 2

    @pytest.mark.parametrize("seed", SEEDS)
    @pytest.mark.parametrize("title", TAG_TITLES)
    def test_both_are_active(self, seed: int, title: Title) -> None:
        for week in WEEKS:
            assert all(m.is_active_at(week) for m in _pair(seed, week, title))

    @pytest.mark.parametrize("seed", SEEDS)
    @pytest.mark.parametrize("title", TAG_TITLES)
    def test_partners_share_a_stable(self, seed: int, title: Title) -> None:
        """**규칙 1** — 스테이블 소속은 같은 스테이블끼리, 독립은 독립끼리."""
        for week in WEEKS:
            stables = {m.stable for m in _pair(seed, week, title)}
            assert len(stables) == 1, f"{seed}/{title}/{week}주: {stables}"

    @pytest.mark.parametrize("seed", SEEDS)
    @pytest.mark.parametrize("title", TAG_TITLES)
    def test_the_pair_matches_the_division(self, seed: int, title: Title) -> None:
        for week in WEEKS:
            assert all(
                m.gender is TITLES[title].gender for m in _pair(seed, week, title)
            )


class TestWhenSomeoneDropsOut:
    def test_a_stable_can_inherit(self) -> None:
        """**규칙 2** — 남은 사람 옆에 같은 스테이블의 선수가 선다."""
        found = 0
        for seed in SEEDS:
            for title in TAG_TITLES:
                for reign in title_scene._reigns(seed, 1560, title, ""):
                    if not reign.inherited:
                        continue
                    found += 1
                    stables = {
                        member.stable
                        for name in title_scene.members_of(reign.holder)
                        if (member := roster.member_of(name, seed)) is not None
                    }
                    assert stables and "" not in stables, (
                        "독립 선수에게는 이어받을 스테이블이 없다"
                    )
                    assert len(stables) == 1
        assert found > 0, "30년 세 판에 이어받기가 한 번도 없었다"

    def test_an_independent_pair_vacates(self) -> None:
        """**규칙 3의 짝** — 스테이블이 없으면 이어받지 못하고 벨트가 빈다."""
        for seed in SEEDS:
            for title in TAG_TITLES:
                for reign in title_scene._reigns(seed, 1560, title, ""):
                    if not reign.inherited:
                        continue
                    for name in title_scene.members_of(reign.holder):
                        member = roster.member_of(name, seed)
                        assert member is not None and member.stable

    def test_a_vacated_belt_is_never_held_by_a_lone_wrestler(self) -> None:
        """**규칙 3** — 둘을 못 채우면 반납이다. 한 명이 든 태그 벨트는 없다."""
        for seed in SEEDS:
            for title in TAG_TITLES:
                for week in WEEKS:
                    holder = title_scene.champion_at(seed, week, title)
                    assert holder is not None
                    assert len(title_scene.members_of(holder)) == 2
