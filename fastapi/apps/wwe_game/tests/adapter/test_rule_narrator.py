"""T6 서술 생성기 — 시드 재현 · 다양성(§11-6) · 조사 · 비트 우선순위."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import replace

import pytest
from _helpers import make_run  # noqa: I001  (tests 트리에 __init__.py가 없다)
from wwe_game.adapter.outbound.narration.rule_narrator import (
    MIN_RIVAL_FREE_TEMPLATES,
    RuleNarrator,
    beat_of,
    josa_for,
    stage_region,
)
from wwe_game.adapter.outbound.narration.templates import (
    INDIE_VENUES,
    MOVES,
    REACTIONS_HIGH,
    REACTIONS_LOW,
    STADIUMS,
    TEMPLATES,
    VENUES,
    Beat,
)
from wwe_game.domain.constants.countries import Region
from wwe_game.domain.constants.ple_calendar import calendar_for
from wwe_game.domain.entities.career_run import Rivalry, RivalryStage
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.services.week_simulation import simulate_week
from wwe_game.domain.value_objects.condition import Condition, InjuryGrade
from wwe_game.domain.value_objects.title import Brand, Title
from wwe_game.domain.value_objects.week_report import (
    CallUpReason,
    OutcomeKind,
    WeekKind,
    WeekReport,
)
from wwe_game.domain.value_objects.wrestler_identity import PlayStyle
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

NARRATOR = RuleNarrator()

DIVERSITY_WEEKS = 30
"""§11-6이 정한 반복 구간. 이만큼 돌려서 같은 문장이 3회를 넘으면 실패다."""

DIVERSITY_LIMIT = 3


def report(
    week: int,
    kind: WeekKind = WeekKind.WEEKLY_SHOW,
    result: OutcomeKind | None = OutcomeKind.WIN,
    **extra: object,
) -> WeekReport:
    return WeekReport(week=week, kind=kind, result=result, **extra)  # type: ignore[arg-type]


def rival(name: str = "로만 레인즈", heat: int = 60) -> Rivalry:
    return Rivalry(
        rival_name=name, stage=RivalryStage.HEATED, heat=heat, started_week=1
    )


def _from_bank(line: str, beat: Beat) -> bool:
    """슬롯을 걷어낸 고정 문구가 전부 들어 있으면 그 비트의 뱅크에서 나온 문장이다."""
    for template in TEMPLATES[beat]:
        chunks = [c for c in re.split(r"\{[^}]*\}", template) if c.strip()]
        if all(chunk in line for chunk in chunks):
            return True
    return False


class TestJosa:
    @pytest.mark.parametrize(
        ("word", "spec", "expected"),
        [
            ("장상호", "이", "장상호가"),  # 받침 없음
            ("건서", "이", "건서가"),
            ("CM 펑크", "이", "CM 펑크가"),  # '크'는 받침 없음
            ("로만 레인즈", "은", "로만 레인즈는"),
            ("파워밤", "은", "파워밤은"),  # 받침 있음
            ("초크슬램", "을", "초크슬램을"),
            ("토페", "을", "토페를"),
            ("건서", "과", "건서와"),
            ("파워밤", "과", "파워밤과"),
            ("헤드벗", "으로", "헤드벗으로"),
            ("롤업", "으로", "롤업으로"),
            ("토페", "으로", "토페로"),
            ("서울", "으로", "서울로"),  # ㄹ 받침은 '으로'가 아니라 '로'
        ],
    )
    def test_josa_follows_the_final_consonant(
        self, word: str, spec: str, expected: str
    ) -> None:
        assert word + josa_for(word, spec) == expected

    def test_latin_names_fall_back_to_the_last_letter(self) -> None:
        # 링 네임은 자유 입력이라 영문이 들어온다. 모음이면 받침 없는 쪽으로 본다.
        assert josa_for("Cody", "이") == "가"
        assert josa_for("Punk", "이") == "이"


class TestDeterminism:
    def test_the_same_week_narrates_the_same_line(self) -> None:
        run = make_run(seed=11, stats=WrestlerStats(popularity=50))
        first = NARRATOR.narrate(run, report(12))
        assert first == NARRATOR.narrate(run, report(12))

    def test_a_different_seed_tells_a_different_story(self) -> None:
        a = make_run(seed=11, stats=WrestlerStats(popularity=50))
        b = make_run(seed=99, stats=WrestlerStats(popularity=50))
        lines = {NARRATOR.narrate(a, report(w)) for w in range(1, 30)}
        other = {NARRATOR.narrate(b, report(w)) for w in range(1, 30)}
        assert lines != other

    def test_no_slot_is_left_unfilled(self) -> None:
        run = make_run(stats=WrestlerStats(popularity=80), rivalries=(rival(),))
        for week in range(1, 60):
            line = NARRATOR.narrate(run, report(week))
            assert "{" not in line and "}" not in line


class TestDiversity:
    @pytest.mark.parametrize(
        ("kind", "result"),
        [
            (WeekKind.WEEKLY_SHOW, OutcomeKind.WIN),
            (WeekKind.WEEKLY_SHOW, OutcomeKind.LOSS),
            (WeekKind.PLE, OutcomeKind.WIN),
            (WeekKind.PLE, OutcomeKind.LOSS),
            (WeekKind.PROMO, None),
            (WeekKind.OFF, None),
        ],
    )
    def test_thirty_weeks_of_the_same_kind_do_not_repeat(
        self, kind: WeekKind, result: OutcomeKind | None
    ) -> None:
        run = make_run(seed=5, stats=WrestlerStats(popularity=55))
        lines = Counter(
            NARRATOR.narrate(run, report(w, kind, result))
            for w in range(1, DIVERSITY_WEEKS + 1)
        )
        assert lines.most_common(1)[0][1] <= DIVERSITY_LIMIT

    def test_a_career_without_rivals_still_has_room(self) -> None:
        # 커리어 초반은 대립이 없다. {rival} 문장이 빠져도 후보가 마르면 안 된다 (§11-6).
        run = make_run(seed=8, stats=WrestlerStats(popularity=20), rivalries=())
        lines = Counter(
            NARRATOR.narrate(run, report(w)) for w in range(1, DIVERSITY_WEEKS + 1)
        )
        assert lines.most_common(1)[0][1] <= DIVERSITY_LIMIT

    def test_every_beat_keeps_rival_free_templates(self) -> None:
        for beat in Beat:
            free = [t for t in TEMPLATES[beat] if "{rival" not in t]
            assert len(free) >= MIN_RIVAL_FREE_TEMPLATES, beat


class TestSlots:
    def test_a_rivalless_run_never_names_a_rival(self) -> None:
        run = make_run(seed=3, stats=WrestlerStats(popularity=60), rivalries=())
        for week in range(1, 80):
            assert "로만 레인즈" not in NARRATOR.narrate(run, report(week))

    def test_the_stage_is_north_america_most_weeks(self) -> None:
        # 단체는 미국에 있다. 선수 국적이 한국이어도 대부분의 주차는 북미다 (§3-D14-1).
        run = make_run(seed=4, stats=WrestlerStats(popularity=45))
        lines = [NARRATOR.narrate(run, report(w)) for w in range(1, 500)]
        seen = Counter(
            region
            for line in lines
            for region, venues in VENUES.items()
            if any(venue in line for venue in venues)
        )
        assert seen[Region.NA] / sum(seen.values()) > 0.80

    def test_the_tour_goes_abroad_and_stops_by_home(self) -> None:
        run = make_run(seed=4, stats=WrestlerStats(popularity=45))
        lines = [NARRATOR.narrate(run, report(w)) for w in range(1, 500)]
        seen = Counter(
            region
            for line in lines
            for region, venues in VENUES.items()
            if any(venue in line for venue in venues)
        )
        assert seen[Region.KR] > 0, "고향 개선 경기가 한 번도 없다"
        away = {r: n for r, n in seen.items() if r not in (Region.NA, Region.KR)}
        assert away, "해외 투어가 한 번도 없다"
        # 고향이 다른 해외 권역보다 잦다 — 국적을 고른 의미가 화면에 남아야 한다.
        assert seen[Region.KR] > max(away.values())

    @pytest.mark.parametrize("home", list(Region))
    def test_every_home_region_can_stage_a_week(self, home: Region) -> None:
        seen = {
            stage_region(home, SeededRoll(seed, 1, "narration")) for seed in range(400)
        }
        assert Region.NA in seen
        if home is not Region.NA:
            assert home in seen

    def test_the_play_style_picks_the_move(self) -> None:
        run = make_run(seed=6, style=PlayStyle.POWERHOUSE)
        lines = [NARRATOR.narrate(run, report(w)) for w in range(1, 80)]
        assert any(m in line for line in lines for m in MOVES[PlayStyle.POWERHOUSE])
        others = [
            m
            for style, moves in MOVES.items()
            if style is not PlayStyle.POWERHOUSE
            for m in moves
        ]
        assert not any(m in line for line in lines for m in others)

    def test_popularity_sets_the_temperature(self) -> None:
        cold = " ".join(
            NARRATOR.narrate(
                make_run(seed=2, stats=WrestlerStats(popularity=10)), report(w)
            )
            for w in range(1, 150)
        )
        hot = " ".join(
            NARRATOR.narrate(
                make_run(seed=2, stats=WrestlerStats(popularity=95)), report(w)
            )
            for w in range(1, 150)
        )
        assert any(r in cold for r in REACTIONS_LOW)
        assert not any(r in cold for r in REACTIONS_HIGH)
        assert any(r in hot for r in REACTIONS_HIGH)
        assert not any(r in hot for r in REACTIONS_LOW)


class TestBeatPriority:
    def test_a_call_up_outranks_everything(self) -> None:
        assert (
            beat_of(
                report(
                    30,
                    injury=InjuryGrade.MINOR,
                    injury_weeks=3,
                    draft_night=True,
                    call_up=CallUpReason.EMERGENCY,
                )
            )
            is Beat.CALL_UP_EMERGENCY
        )

    def test_winning_a_new_belt_beats_getting_hurt(self) -> None:
        # 부상은 다음 주 결장 문장에서 이어지지만, 벨트가 오가는 장면은 이 주에만 있다.
        assert (
            beat_of(
                report(
                    40,
                    kind=WeekKind.PLE,
                    title_at_stake=Title.INTERCONTINENTAL_CHAMPIONSHIP,
                    injury=InjuryGrade.SERIOUS,
                    injury_weeks=10,
                )
            )
            is Beat.TITLE_WON
        )

    def test_defending_is_not_winning_a_new_belt(self) -> None:
        assert (
            beat_of(
                report(
                    40,
                    kind=WeekKind.PLE,
                    title_at_stake=Title.INTERCONTINENTAL_CHAMPIONSHIP,
                    title_defended=True,
                )
            )
            is Beat.TITLE_DEFENDED
        )

    def test_a_failed_defence_is_a_loss_of_the_belt(self) -> None:
        assert (
            beat_of(
                report(
                    41,
                    kind=WeekKind.PLE,
                    result=OutcomeKind.LOSS,
                    title_at_stake=Title.INTERCONTINENTAL_CHAMPIONSHIP,
                    title_defended=True,
                )
            )
            is Beat.TITLE_LOST
        )

    @pytest.mark.parametrize(
        ("kind", "result", "expected"),
        [
            (WeekKind.OFF, None, Beat.OFF),
            (WeekKind.PROMO, None, Beat.PROMO),
            (WeekKind.PLE, OutcomeKind.DRAW, Beat.PLE_DRAW),
            (WeekKind.WEEKLY_SHOW, OutcomeKind.LOSS, Beat.SHOW_LOSS),
        ],
    )
    def test_a_plain_week_reads_from_its_kind(
        self, kind: WeekKind, result: OutcomeKind | None, expected: Beat
    ) -> None:
        assert beat_of(report(20, kind, result)) is expected

    def test_the_belt_name_reaches_the_sentence(self) -> None:
        run = make_run(stats=WrestlerStats(popularity=80))
        lines = [
            NARRATOR.narrate(
                run,
                report(
                    week,
                    kind=WeekKind.PLE,
                    title_at_stake=Title.INTERCONTINENTAL_CHAMPIONSHIP,
                ),
            )
            for week in range(1, 40)
        ]
        assert any("인터컨티넨탈 챔피언십" in line for line in lines)
        assert all("{" not in line for line in lines)

    @pytest.mark.parametrize(
        ("kind", "result", "beat"),
        [
            (WeekKind.OFF, None, Beat.OFF),
            (WeekKind.PROMO, None, Beat.PROMO),
            (WeekKind.PLE, OutcomeKind.WIN, Beat.PLE_WIN),
        ],
    )
    def test_the_line_comes_from_that_beats_bank(
        self, kind: WeekKind, result: OutcomeKind | None, beat: Beat
    ) -> None:
        run = make_run(
            seed=13,
            condition=Condition(grade=InjuryGrade.SERIOUS, weeks_left=8)
            if kind is WeekKind.OFF
            else None,
        )
        for week in range(1, 40):
            line = NARRATOR.narrate(run, report(week, kind, result))
            assert _from_bank(line, beat), line


class TestTheVenueIsOneNight:
    """리포트 머리와 서술이 **같은 경기장**을 말한다 (§3-D69).

    무대는 서술의 슬롯이라(§3-D14-1) 그쪽이 이미 뽑고 있었다 — 리포트가 따로 뽑으면
    같은 밤이 두 곳에서 열린다.
    """

    def test_the_same_week_gives_the_same_venue(self) -> None:
        narrator = RuleNarrator()
        run = make_run(seed=7777)
        assert narrator.venue_of(run, 40) == narrator.venue_of(run, 40)

    def test_another_week_is_another_venue(self) -> None:
        narrator = RuleNarrator()
        run = make_run(seed=7777)
        found = {narrator.venue_of(run, week) for week in range(1, 60)}
        assert len(found) > 1

    def test_it_is_the_venue_the_sentence_used(self) -> None:
        narrator = RuleNarrator()
        run = make_run(seed=7777, week=0)
        checked = 0
        for week in range(1, 80):
            current = replace(run, week=week - 1)
            report = simulate_week(current)
            text = narrator.narrate(current, report)
            venue = narrator.venue_of(current, report.week)
            if venue not in text:
                continue  # 그 템플릿이 무대를 안 쓴 주차다
            checked += 1
        assert checked > 0, "무대를 쓴 문장이 한 번도 없었다"

    def test_the_home_crowd_still_comes_around(self) -> None:
        """국적이 무대에 드러나는 자리는 그대로다 (§3-D14-1)."""
        narrator = RuleNarrator()
        run = make_run(seed=7777)
        venues = {narrator.venue_of(run, week) for week in range(1, 1560)}
        assert len(venues) > 10


class TestTheStageMatchesTheStature:
    """무대의 급이 그 사람의 처지를 말한다 (§3-D70, 2026-08-12 사용자 지적).

    "탬파의 물류창고 링"에 세우면 세계 최대 단체의 주간 투어가 인디로 읽힌다. 반대로
    방출된 선수를 아레나에 세우면 방출이 아무 일도 아닌 것이 된다(§3-D50).
    """

    def test_a_signed_wrestler_stands_in_an_arena(self) -> None:
        narrator = RuleNarrator()
        run = make_run(seed=7777)
        stages = {narrator.venue_of(run, week) for week in range(1, 400)}
        assert stages
        assert not (stages & set(INDIE_VENUES))

    def test_an_unsigned_wrestler_works_the_indies(self) -> None:
        narrator = RuleNarrator()
        run = replace(make_run(seed=7777), contract=None, titles_held=frozenset())
        stages = {narrator.venue_of(run, week) for week in range(1, 400)}
        assert stages <= set(INDIE_VENUES)

    def test_a_major_night_stands_in_a_stadium(self) -> None:
        """레슬매니아가 주간 방송과 같은 곳에 서면 그 밤이 커지지 않는다 (§3-D70)."""
        narrator = RuleNarrator()
        run = replace(make_run(seed=7777), brand=Brand.RAW)
        calendar = calendar_for(Brand.RAW)
        checked = 0
        for show in calendar.shows:
            if not show.is_major:
                continue
            for year in range(1, 6):
                week = show.week_of_year + 52 * year
                assert narrator.venue_of(run, week) in STADIUMS[Region.NA] or any(
                    narrator.venue_of(run, week) in bank for bank in STADIUMS.values()
                )
                checked += 1
        assert checked > 0

    def test_an_ordinary_night_does_not(self) -> None:
        narrator = RuleNarrator()
        run = replace(make_run(seed=7777), brand=Brand.RAW)
        calendar = calendar_for(Brand.RAW)
        stadiums = {name for bank in STADIUMS.values() for name in bank}
        for week in range(1, 300):
            if calendar.is_show_week(week) and calendar.show_for(week).is_major:
                continue
            assert narrator.venue_of(run, week) not in stadiums

    def test_the_three_banks_never_share_a_name(self) -> None:
        """한 이름이 두 뱅크에 있으면 급이 섞인다 — 고척스카이돔이 실제로 그랬다."""
        arenas = {name for bank in VENUES.values() for name in bank}
        stadiums = {name for bank in STADIUMS.values() for name in bank}
        assert not (arenas & stadiums)
        assert not (arenas & set(INDIE_VENUES))
        assert not (stadiums & set(INDIE_VENUES))
