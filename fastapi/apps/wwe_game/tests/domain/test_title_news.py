"""배경 벨트가 인박스에 흐른다 (하네스 §3-D65).

§3-D38이 벨트에 주인을 만들었지만 인박스만 보면 30년 내내 세계의 벨트가 멈춰 있었다 —
RAW 남성부만 30년에 146번 바뀌는데 뉴스는 내 벨트만 봤다.
"""

from __future__ import annotations

import pytest
from wwe_game.domain.services import title_news, title_scene
from wwe_game.domain.services.title_news import TitleBeat
from wwe_game.domain.value_objects.title import TITLES, Brand, Title, titles_of
from wwe_game.domain.value_objects.wrestler_identity import Gender

SEED = 7777
CAREER = 1560


def _news(**kwargs: object) -> tuple[title_news.TitleNews, ...]:
    return title_news.chronicle(
        SEED,
        CAREER,
        Gender.MALE,
        Brand.RAW,
        **kwargs,  # type: ignore[arg-type]
    )


class TestItReadsTheLineage:
    def test_it_is_the_same_every_time(self) -> None:
        assert _news() == _news()

    def test_it_runs_in_order(self) -> None:
        weeks = [item.week for item in _news()]
        assert weeks == sorted(weeks)

    def test_the_belt_actually_changed_hands_that_week(self) -> None:
        """뉴스의 주차는 **새 재위가 시작한 주차**여야 한다."""
        for item in _news():
            title = next(
                t
                for t in titles_of(Brand.RAW, Gender.MALE)
                if TITLES[t].display_name == item.title
            )
            starts = {r.start for r in title_scene.reigns_upto(SEED, CAREER, title)}
            assert item.week in starts

    def test_the_holder_is_the_new_champion(self) -> None:
        for item in _news():
            title = next(
                t
                for t in titles_of(Brand.RAW, Gender.MALE)
                if TITLES[t].display_name == item.title
            )
            now = title_scene.champion_at(SEED, item.week, title)
            assert item.holder == title_scene.holder_label(now or "", SEED)


class TestTheThreeWaysItChanges:
    def test_all_three_appear(self) -> None:
        """졌다·비웠다·이어받았다를 뭉치면 §3-D52·D58이 나눈 것이 도로 합쳐진다."""
        beats = {item.beat for item in _news()}
        assert TitleBeat.WON in beats
        assert TitleBeat.FILLED in beats

    def test_a_filled_belt_follows_a_vacancy(self) -> None:
        """**앞 재위가 어떻게 끝났는지**가 이 줄의 뜻이다 — 한 번 헷갈린 자리다."""
        for item in _news():
            if item.beat is not TitleBeat.FILLED:
                continue
            title = next(
                t
                for t in titles_of(Brand.RAW, Gender.MALE)
                if TITLES[t].display_name == item.title
            )
            reigns = title_scene.reigns_upto(SEED, CAREER, title)
            previous = next(r for r in reigns if r.ends == item.week)
            assert previous.vacated

    def test_the_headline_says_what_happened(self) -> None:
        for item in _news():
            assert item.holder in item.headline
            assert item.title in item.headline


class TestMyBeltIsNotTheirs:
    def test_a_belt_i_hold_is_skipped(self) -> None:
        """내가 감고 있는 벨트의 배경 계보를 흘리면 내 대관과 한 화면에서 부딪친다."""
        mine: Title = next(iter(titles_of(Brand.RAW, Gender.MALE)))
        skipped = _news(skip=frozenset({mine}))
        assert all(item.title != TITLES[mine].display_name for item in skipped)
        assert len(skipped) < len(_news())

    @pytest.mark.parametrize("brand", [Brand.RAW, Brand.SMACKDOWN, Brand.NXT])
    def test_only_that_brands_belts(self, brand: Brand) -> None:
        names = {TITLES[t].display_name for t in titles_of(brand, Gender.MALE)}
        for item in title_news.chronicle(SEED, CAREER, Gender.MALE, brand):
            assert item.title in names
