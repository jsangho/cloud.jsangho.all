"""0주차의 챔피언들 (하네스 §3-D94 · 규칙 2).

*"무조건 시작할 때 이 명단인 걸로 해줘"* — 사용자가 준 열여덟 벨트의 현 챔피언이다.
그전까지는 첫 재위까지 시드로 굴려서, 같은 세계를 새로 시작할 때마다 주인이 달랐다.
"""

from __future__ import annotations

import pytest
from wwe_game.domain.constants import roster
from wwe_game.domain.constants.champions import OPENING_CHAMPIONS, PARTNER_JOIN
from wwe_game.domain.services import title_scene
from wwe_game.domain.value_objects.title import TITLES, Title, TitleTier

SEEDS = (0, 7, 42, 7777, 1234)


class TestTheListIsComplete:
    def test_every_belt_has_an_opening_champion(self) -> None:
        assert set(OPENING_CHAMPIONS) == set(Title)

    def test_the_join_matches_the_lineage(self) -> None:
        """태그 벨트의 두 이름을 잇는 문자열이 어긋나면 한 사람으로 읽힌다."""
        assert PARTNER_JOIN == title_scene.PARTNER_JOIN

    def test_tag_belts_are_held_by_two(self) -> None:
        for title, holder in OPENING_CHAMPIONS.items():
            if TITLES[title].tier is TitleTier.TAG:
                assert len(holder.split(PARTNER_JOIN)) == 2, holder

    def test_everyone_is_on_the_roster(self) -> None:
        """이름이 어긋나면 그 벨트만 조용히 굴림으로 떨어진다."""
        names = {m.name for m in roster.ROSTER} | {
            m.renamed_to for m in roster.ROSTER if m.renamed_to
        }
        for holder in OPENING_CHAMPIONS.values():
            for person in holder.split(PARTNER_JOIN):
                assert person in names, person


class TestEverySaveStartsTheSame:
    @pytest.mark.parametrize("seed", SEEDS)
    def test_week_zero_matches_the_list(self, seed: int) -> None:
        for title, holder in OPENING_CHAMPIONS.items():
            assert title_scene.champion_at(seed, 0, title) == holder

    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_gender_of_the_belt_is_respected(self, seed: int) -> None:
        """여성부 벨트를 남성부 선수가 들면 그 벨트가 무엇인지 사라진다."""
        for title in Title:
            holder = title_scene.champion_at(seed, 0, title)
            assert holder is not None
            for person in holder.split(PARTNER_JOIN):
                member = roster.member_of(person, seed)
                assert member is None or member.gender is TITLES[title].gender

    def test_later_reigns_still_vary(self) -> None:
        """**첫 재위만 못 박는다** — 그 뒤까지 정해 두면 계보가 아니라 각본이다."""
        later = {
            title_scene.champion_at(seed, 260, Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP)
            for seed in SEEDS
        }
        assert len(later) > 1

    def test_my_own_name_falls_back_to_the_roll(self) -> None:
        """내가 챔피언과 같은 이름을 쓰면 계보는 그 자리를 비켜 준다 (§3-D10-1)."""
        mine = OPENING_CHAMPIONS[Title.UNDISPUTED_WWE_CHAMPIONSHIP]
        holder = title_scene.champion_at(
            7, 0, Title.UNDISPUTED_WWE_CHAMPIONSHIP, exclude=mine
        )
        assert holder != mine
