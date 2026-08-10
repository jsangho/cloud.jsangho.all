"""팀 세계와 뉴스 피드 (2026-08-10 사용자 지시 7·7-1·7-2·10번)."""

from __future__ import annotations

from _helpers import make_run  # noqa: I001  (tests 트리에 __init__.py가 없다)
from wwe_game.domain.constants.event_deck import DECK
from wwe_game.domain.constants.teams import KOREAN_TEAM_NAMES, SCRIPTED_ARCS
from wwe_game.domain.services import news_feed, team_engine
from wwe_game.domain.services.seeded_roll import TEAM, SeededRoll
from wwe_game.domain.services.week_simulation import apply_week, simulate_week
from wwe_game.domain.value_objects.week_report import (
    CallUpReason,
    OutcomeKind,
    WeekKind,
    WeekReport,
)
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

WEEKS_PER_YEAR = 52


def _chronicle(seed: int, weeks: int) -> list[team_engine.TeamNews]:
    news: list[team_engine.TeamNews] = []
    for week in range(1, weeks + 1):
        news.extend(team_engine.scripted_at(week))
        rolled = team_engine.roll_change(week, SeededRoll(seed, week, TEAM))
        if rolled is not None:
            news.append(rolled)
    return news


class TestTeamNames:
    def test_every_csv_team_has_a_korean_name(self) -> None:
        # 표에 없는 팀은 영문 그대로 화면에 나간다 — 조용히 섞이면 화면에서야 보인다.
        assert "The Tongans" in KOREAN_TEAM_NAMES
        assert "DarkState" in KOREAN_TEAM_NAMES
        assert team_engine.korean_name("Judgement Day") == "저지먼트 데이"

    def test_a_double_name_yields_its_short_form(self) -> None:
        assert team_engine.short_name("Latino World Order") == "LWO"
        assert team_engine.short_name("Out The Mud") == "아웃 더 머드"

    def test_an_unknown_team_keeps_its_source_name(self) -> None:
        assert team_engine.korean_name("Nonexistent Faction") == "Nonexistent Faction"


class TestScriptedArc:
    def test_los_americanos_splits_before_anyone_returns(self) -> None:
        # 셋이 동시에 돌아오면 "몇 년 더 활동하다가"라는 지시가 사라진다 (§7-1).
        split = next(a for a in SCRIPTED_ARCS if a.disband == "Los Americanos")
        formed = next(a for a in SCRIPTED_ARCS if a.form == "New Catch Republic")
        kaiser = next(
            a for a in SCRIPTED_ARCS if any("카이저" in new for _, new in a.renames)
        )
        assert split.week < formed.week < kaiser.week

    def test_new_catch_republic_is_dunne_and_bate(self) -> None:
        formed = next(a for a in SCRIPTED_ARCS if a.form == "New Catch Republic")
        assert set(formed.members) == {"피트 던", "타일러 베이트"}

    def test_the_gimmick_name_is_dropped_only_after_its_week(self) -> None:
        source = "엘 그란데 아메리카노 | 루드비히 카이저"
        arc = next(
            a for a in SCRIPTED_ARCS if any(old == source for old, _ in a.renames)
        )
        assert team_engine.ring_name_at(source, arc.week - 1) == source
        assert team_engine.ring_name_at(source, arc.week) == "루드비히 카이저"

    def test_the_arc_does_not_depend_on_the_seed(self) -> None:
        week = next(a for a in SCRIPTED_ARCS if a.disband).week
        assert team_engine.scripted_at(week) == team_engine.scripted_at(week)


class TestTeamsComeAndGo:
    def test_teams_form_and_disband_over_thirty_years(self) -> None:
        news = _chronicle(seed=99, weeks=30 * WEEKS_PER_YEAR)
        changes = {n.change for n in news}
        assert team_engine.TeamChange.FORMED in changes
        assert team_engine.TeamChange.DISBANDED in changes
        assert len(news) >= 20, "서른 해에 스무 건도 안 되면 세계가 멈춰 있다"

    def test_the_chronicle_is_reproducible(self) -> None:
        assert _chronicle(7, 520) == _chronicle(7, 520)

    def test_some_tag_teams_are_just_two_names(self) -> None:
        # 이름을 짓지 않고 "A & B"로 부르는 경우가 있어야 한다 (§7-2).
        news = _chronicle(seed=5, weeks=30 * WEEKS_PER_YEAR)
        assert any(" & " in n.team.label for n in news if len(n.team.members) == 2)

    def test_a_stable_always_gets_a_name(self) -> None:
        news = _chronicle(seed=5, weeks=30 * WEEKS_PER_YEAR)
        stables = [n.team for n in news if len(n.team.members) >= 3]
        assert stables, "서른 해에 스테이블이 하나도 안 생겼다"
        assert all(team.name for team in stables)

    def test_nobody_teams_up_with_themselves(self) -> None:
        news = _chronicle(seed=13, weeks=30 * WEEKS_PER_YEAR)
        for item in news:
            assert len(set(item.team.members)) == len(item.team.members)


class TestTheDeckOffersTeams:
    def test_declining_an_offer_raises_the_heat(self) -> None:
        # 거절은 손해가 아니라 이야기다 (§7-2).
        offers = [c for c in DECK if c.code.startswith("team_")]
        assert offers, "팀 권유 카드가 없다"
        declines = [ch for c in offers for ch in c.choices if ch.heat > 0]
        assert declines, "거절이 아무 흔적도 남기지 않는다"

    def test_both_a_tag_team_and_a_stable_can_be_joined(self) -> None:
        flags = {f for c in DECK for ch in c.choices for f in ch.flags}
        assert {"in_tag_team", "in_stable"} <= flags


class TestCrowdReactions:
    def test_a_heel_gets_jeered_for_the_same_title(self) -> None:
        face = WrestlerStats(popularity=50, alignment=60)
        heel = WrestlerStats(popularity=50, alignment=-60)
        assert news_feed.mood_for(news_feed.NewsKind.TITLE_WON, face) is (
            news_feed.CrowdMood.ROAR
        )
        assert news_feed.mood_for(news_feed.NewsKind.TITLE_WON, heel) is (
            news_feed.CrowdMood.JEER
        )

    def test_no_alignment_reads_as_a_split_crowd(self) -> None:
        blank = WrestlerStats(popularity=50, alignment=0)
        assert news_feed.mood_for(news_feed.NewsKind.TITLE_WON, blank) is (
            news_feed.CrowdMood.SPLIT
        )

    def test_bad_news_is_always_quiet(self) -> None:
        heel = WrestlerStats(popularity=90, alignment=-80)
        for kind in (
            news_feed.NewsKind.INJURY,
            news_feed.NewsKind.CURSED,
            news_feed.NewsKind.TITLE_LOST,
        ):
            assert news_feed.mood_for(kind, heel) is news_feed.CrowdMood.HUSH

    def test_a_star_gets_chanted_at(self) -> None:
        star = WrestlerStats(popularity=90, alignment=70)
        assert news_feed.mood_for(news_feed.NewsKind.CALL_UP, star) is (
            news_feed.CrowdMood.CHANT
        )

    def test_every_mood_has_a_line(self) -> None:
        assert set(news_feed.MOOD_LINES) == set(news_feed.CrowdMood)
        assert all(len(v) >= 3 for v in news_feed.MOOD_LINES.values())


class TestFeedIsReadable:
    def test_an_ordinary_week_makes_no_news(self) -> None:
        quiet = WeekReport(week=4, kind=WeekKind.WEEKLY_SHOW, result=OutcomeKind.WIN)
        assert news_feed.from_report(quiet, WrestlerStats(), "장상호") is None

    def test_a_call_up_makes_news(self) -> None:
        moment = WeekReport(week=90, kind=WeekKind.PROMO, call_up=CallUpReason.EARNED)
        item = news_feed.from_report(moment, WrestlerStats(), "장상호")
        assert item is not None
        assert "장상호" in item.headline
        assert item.crowd_line

    def test_the_feed_is_far_shorter_than_the_log(self) -> None:
        run = make_run(seed=21)
        entries: list[tuple[WeekReport, WrestlerStats]] = []
        for _ in range(300):
            if run.is_blocked or not run.is_active:
                break
            report = simulate_week(run)
            run = apply_week(run, report)
            entries.append((report, run.stats))
        feed = news_feed.compile_feed(tuple(entries), (), "장상호")
        assert len(feed) < len(entries) / 3, "뉴스가 로그만큼 길면 읽을 수 없다"

    def test_my_week_comes_before_the_background(self) -> None:
        mine = WeekReport(week=52, kind=WeekKind.PROMO, call_up=CallUpReason.EARNED)
        background = team_engine.TeamNews(
            week=52,
            change=team_engine.TeamChange.FORMED,
            team=team_engine.Team("", ("가", "나")),
            headline="새 태그팀이 나왔다 — 가 & 나.",
        )
        feed = news_feed.compile_feed(
            ((mine, WrestlerStats()),), (background,), "장상호"
        )
        assert feed[0].kind is news_feed.NewsKind.CALL_UP
        assert feed[1].kind is news_feed.NewsKind.TEAM


class TestThePlayerJoinsATeam:
    def test_accepting_forms_a_team_on_the_next_week(self) -> None:
        from wwe_game.domain.constants.career_flags import TEAM_PENDING

        run = make_run(seed=4).evolve(flags=frozenset({"in_tag_team", TEAM_PENDING}))
        assert run.team is None
        after = apply_week(run, simulate_week(run))
        assert after.team is not None, "수락해 놓고 팀이 안 생겼다"
        assert str(run.identity.name) in after.team.members
        assert len(after.team.members) >= 2

    def test_the_signal_is_spent_but_the_state_remains(self) -> None:
        # `team_pending`은 한 번의 신호, `in_tag_team`은 후속 카드가 읽는 상태다.
        from wwe_game.domain.constants.career_flags import TEAM_PENDING

        run = make_run(seed=8).evolve(flags=frozenset({"in_tag_team", TEAM_PENDING}))
        after = apply_week(run, simulate_week(run))
        assert TEAM_PENDING not in after.flags
        assert "in_tag_team" in after.flags

    def test_a_team_is_not_rebuilt_every_week(self) -> None:
        from wwe_game.domain.constants.career_flags import TEAM_PENDING

        run = make_run(seed=12).evolve(flags=frozenset({"in_tag_team", TEAM_PENDING}))
        run = apply_week(run, simulate_week(run))
        formed = run.team
        for _ in range(6):
            run = apply_week(run, simulate_week(run))
        assert run.team == formed, "같은 팀이 매주 다시 만들어졌다"

    def test_a_solo_career_has_no_team(self) -> None:
        run = make_run(seed=2)
        for _ in range(10):
            run = apply_week(run, simulate_week(run))
        assert run.team is None

    def test_a_nameless_team_falls_back_to_the_members(self) -> None:
        from wwe_game.domain.value_objects.team import Team

        assert Team("", ("장상호", "행크 워커")).label == "장상호 & 행크 워커"
        assert Team("다크스테이트", ("장상호",)).label == "다크스테이트"

    def test_losing_a_partner_below_two_ends_the_team(self) -> None:
        from wwe_game.domain.value_objects.team import Team

        pair = Team("리버티 다이너스티", ("장상호", "행크 워커"))
        assert pair.without("행크 워커") is None
        trio = Team("더 컬링", ("장상호", "행크 워커", "케일 딕슨"))
        assert trio.without("케일 딕슨") is not None
