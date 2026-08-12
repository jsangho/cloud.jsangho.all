"""명부의 들고 남 (하네스 §3-D61).

명부에는 시간 축이 있는데(§3-D13-1) 그 사실이 인박스에 한 줄도 없었다 — 30년이면 오늘의
얼굴이 전부 사라지는데 언제 떠났는지를 알 길이 없었다.

**분량은 화면이 정한다**(2026-08-12 사용자 결정). 그래서 여기서 잠그는 것은 "적게
흘린다"가 아니라 **말이 되는 것만 흘린다**이다 — 없는 사람의 은퇴, 두 번 세는 이동,
남의 브랜드 소식.
"""

from __future__ import annotations

import pytest
from wwe_game.domain.constants import roster
from wwe_game.domain.constants.roster import RivalTier
from wwe_game.domain.services import roster_scene
from wwe_game.domain.services.roster_scene import RosterBeat
from wwe_game.domain.value_objects.title import Brand
from wwe_game.domain.value_objects.wrestler_identity import Gender

SEED = 7777
CAREER = 1560


def _news(gender: Gender = Gender.MALE, brand: Brand = Brand.RAW):
    return roster_scene.chronicle(CAREER, gender, brand, SEED)


class TestItReadsTheRosterAsItIs:
    def test_it_is_the_same_every_time(self) -> None:
        # 굴림이 없다 — 명부가 아는 사실을 읽을 뿐이다.
        assert _news() == _news()

    def test_it_runs_in_order(self) -> None:
        weeks = [item.week for item in _news()]
        assert weeks == sorted(weeks)

    def test_nothing_happens_at_week_zero(self) -> None:
        """0주차 명부는 데뷔가 아니라 시작이다."""
        assert all(item.week > 0 for item in _news())

    def test_it_stops_at_the_week_asked(self) -> None:
        early = roster_scene.chronicle(300, Gender.MALE, Brand.RAW, SEED)
        assert all(item.week <= 300 for item in early)
        assert len(early) < len(_news())


class TestEveryLineIsTrue:
    @pytest.mark.parametrize("brand", list(Brand))
    def test_the_person_is_on_that_brand(self, brand: Brand) -> None:
        """남의 브랜드 소식은 그 세계선의 일이 아니다 (§3-D53)."""
        for item in roster_scene.chronicle(CAREER, Gender.MALE, brand, SEED):
            member = roster.member_of(item.name, SEED)
            assert member is not None
            week = item.week if item.beat is not RosterBeat.RETIRE else item.week - 1
            assert roster.brand_at(member, week, SEED) is brand

    @pytest.mark.parametrize("gender", list(Gender))
    def test_the_person_is_in_that_division(self, gender: Gender) -> None:
        for item in roster_scene.chronicle(CAREER, gender, Brand.RAW, SEED):
            member = roster.member_of(item.name, SEED)
            assert member is not None
            assert member.gender is gender

    def test_a_debut_is_their_first_week(self) -> None:
        for item in _news():
            if item.beat is not RosterBeat.DEBUT:
                continue
            member = roster.member_of(item.name, SEED)
            assert member is not None
            assert member.debut_week == item.week

    def test_a_retirement_is_their_last_week(self) -> None:
        for item in _news():
            if item.beat is not RosterBeat.RETIRE:
                continue
            member = roster.member_of(item.name, SEED)
            assert member is not None
            assert member.retire_week == item.week
            # 떠나기 직전에는 아직 링에 있었다.
            assert member.is_active_at(item.week - 1)

    def test_only_main_eventers_retire_in_the_news(self) -> None:
        """등급이 낮은 사람의 퇴장까지 세면 명부 388명이 전부 흐른다."""
        for item in _news():
            if item.beat is not RosterBeat.RETIRE:
                continue
            member = roster.member_of(item.name, SEED)
            assert member is not None
            assert roster.tier_at(member, item.week - 1) is RivalTier.MAIN_EVENT

    def test_a_call_up_lands_on_the_main_roster(self) -> None:
        for item in _news():
            if item.beat is not RosterBeat.CALL_UP:
                continue
            member = roster.member_of(item.name, SEED)
            assert member is not None
            assert roster.call_up_week(member) == item.week
            assert roster.brand_at(member, item.week, SEED) is not Brand.NXT

    def test_nobody_moves_twice_for_one_move(self) -> None:
        """콜업은 **도착한 브랜드에서만** 기사가 된다 — 양쪽에 흘리면 한 이동이 두 줄이다."""
        moves = [
            (item.name, item.week)
            for brand in Brand
            for item in roster_scene.chronicle(CAREER, Gender.MALE, brand, SEED)
            if item.beat is RosterBeat.CALL_UP
        ]
        assert len(moves) == len(set(moves))


class TestItFollowsThatRunsCast:
    def test_the_names_are_of_that_run(self) -> None:
        """가상 선수 이름은 판마다 다르다 (§3-D59) — 뉴스도 그 판의 이름을 써야 한다."""
        other = roster_scene.chronicle(CAREER, Gender.MALE, Brand.RAW, 1234)
        assert {item.name for item in _news()} != {item.name for item in other}

    def test_every_name_resolves_in_that_run(self) -> None:
        for seed in (0, SEED, 1234):
            for item in roster_scene.chronicle(CAREER, Gender.MALE, Brand.RAW, seed):
                assert roster.member_of(item.name, seed) is not None
