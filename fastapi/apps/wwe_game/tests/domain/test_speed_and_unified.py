"""스피드 챔피언십과 브랜드 통합 벨트 (하네스 §3-D72, 2026-08-13 사용자 스펙).

사용자가 벨트 사진 열여덟 장을 가져오며 목록이 바뀌었다. 이 파일이 잠그는 것은 셋이다.

1. **위민스 태그팀은 RAW·SD·NXT 공용**이다 — NXT 전용 위민스 태그 벨트는 없다.
2. **스피드는 3분 경기**이고, 못 끝내면 서든 데스로 이어진다.
3. **스피드는 급이 정하는 벨트**다 — 관문 15, 상한 50. 그 위로 올라가면 목록에서 빠진다.
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001
from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.services import contract_office
from wwe_game.domain.services.championship import eligible_titles, target_title
from wwe_game.domain.services.week_simulation import simulate_week, tournament_round_at
from wwe_game.domain.value_objects.match_kind import FORMATS, MatchKind
from wwe_game.domain.value_objects.team import Team
from wwe_game.domain.value_objects.title import (
    SPEED_POPULARITY_CEILING,
    SPEED_POPULARITY_REQUIRED,
    SPEED_TITLES,
    TITLES,
    Brand,
    Title,
    TitleTier,
    nxt_titles,
    titles_of,
)
from wwe_game.domain.value_objects.week_report import WeekKind
from wwe_game.domain.value_objects.wrestler_identity import Gender
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats


class _NeverChase:
    """그랜드슬램 우선을 끄고 순수 사다리만 잰다."""

    def chance(self, _probability: float) -> bool:
        return False


NEVER_CHASE = _NeverChase()
TEAM = Team("리버티 다이너스티", ("장상호", "행크 워커"))


# ── ① 위민스 태그팀은 세 브랜드 공용 ─────────────────────────


class TestTheWomensTagBeltIsOne:
    def test_there_is_no_nxt_only_womens_tag_belt(self) -> None:
        """사용자가 가져온 사진에도 없었다 — 통합 벨트 한 장이 폴더 바깥에 있었다."""
        tag_belts = [
            s
            for s in TITLES.values()
            if s.gender is Gender.FEMALE and s.tier is TitleTier.TAG
        ]
        assert len(tag_belts) == 1
        assert tag_belts[0].title is Title.WWE_WOMENS_TAG_TEAM_CHAMPIONSHIP

    @pytest.mark.parametrize("brand", list(Brand))
    def test_every_brand_can_chase_it(self, brand: Brand) -> None:
        assert Title.WWE_WOMENS_TAG_TEAM_CHAMPIONSHIP in titles_of(brand, Gender.FEMALE)

    def test_it_is_not_an_nxt_belt(self) -> None:
        """**NXT에서 걸리는 것과 NXT의 것은 다르다** (§3-D72).

        넓게 잡으면 콜업 때 반납되고(`call_up`), NXT 벨트 석권 조건에도 끼어든다.
        """
        assert Title.WWE_WOMENS_TAG_TEAM_CHAMPIONSHIP not in nxt_titles(Gender.FEMALE)
        assert nxt_titles(Gender.FEMALE) == {
            Title.NXT_WOMENS_CHAMPIONSHIP,
            Title.NXT_WOMENS_NORTH_AMERICAN_CHAMPIONSHIP,
        }

    def test_a_call_up_does_not_take_it_away(self) -> None:
        from wwe_game.domain.services.championship import call_up
        from wwe_game.domain.services.seeded_roll import SeededRoll

        belt = Title.WWE_WOMENS_TAG_TEAM_CHAMPIONSHIP
        run = make_run(gender=Gender.FEMALE, brand=Brand.NXT).evolve(
            titles_won=(belt, Title.NXT_WOMENS_CHAMPIONSHIP),
            titles_held=frozenset({belt, Title.NXT_WOMENS_CHAMPIONSHIP}),
        )
        after = call_up(run, SeededRoll(1, 1, "test"))
        assert belt in after.titles_held
        assert Title.NXT_WOMENS_CHAMPIONSHIP not in after.titles_held


# ── ② 3분 안에 끝내야 한다 ───────────────────────────────────


class TestTheThreeMinuteRule:
    def test_the_two_formats_exist(self) -> None:
        assert FORMATS[MatchKind.SPEED].label == "스피드 매치 (3분)"
        assert FORMATS[MatchKind.SUDDEN_DEATH].label == "서든 데스 매치"

    def test_three_minutes_leaves_less_damage_than_a_normal_match(self) -> None:
        """**3분이면 몸이 상할 틈이 없다.** 서든 데스는 그 반대다."""
        speed = FORMATS[MatchKind.SPEED]
        singles = FORMATS[MatchKind.SINGLES]
        sudden = FORMATS[MatchKind.SUDDEN_DEATH]
        assert speed.wear_factor < singles.wear_factor < sudden.wear_factor
        assert speed.injury_factor < singles.injury_factor < sudden.injury_factor

    def test_neither_format_tilts_the_odds(self) -> None:
        """시간 제한은 **누가 이기는지**를 바꾸지 않는다 — 형식만 바꾼다."""
        assert FORMATS[MatchKind.SPEED].win_factor == 1.0
        assert FORMATS[MatchKind.SUDDEN_DEATH].win_factor == 1.0
        assert FORMATS[MatchKind.SPEED].field == 2

    def test_a_speed_title_night_books_one_of_the_two(self) -> None:
        """스피드 벨트가 걸린 밤은 반드시 둘 중 하나다 — 사이는 없다."""
        seen: set[MatchKind] = set()
        for seed in range(300, 420):
            run = make_run(seed=seed, stats=WrestlerStats(popularity=30))
            for week in range(1, 220):
                report = simulate_week(run.evolve(week=week - 1))
                if report.title_at_stake in SPEED_TITLES:
                    seen.add(report.match_kind)
            if len(seen) == 2:
                break
        assert seen == {MatchKind.SPEED, MatchKind.SUDDEN_DEATH}

    def test_sudden_death_is_the_minority(self) -> None:
        """**3분을 넘기는 쪽이 예외다.** 절반이면 "3분 경기"가 아니게 된다."""
        assert 0.0 < rules.SPEED_TIME_UP_CHANCE < 0.5

    def test_the_night_is_decided_by_seed_not_by_luck_of_the_call(self) -> None:
        run = make_run(seed=99, stats=WrestlerStats(popularity=30))
        first = [simulate_week(run.evolve(week=w)).match_kind for w in range(1, 60)]
        again = [simulate_week(run.evolve(week=w)).match_kind for w in range(1, 60)]
        assert first == again


# ── ③ 급이 벨트를 정한다 ─────────────────────────────────────


class TestTheSpeedBeltBelongsToALevel:
    def test_it_is_a_singles_belt_not_a_team_belt(self) -> None:
        """**`TitleTier.TAG`는 둘이 드는 벨트라는 뜻이다** — 스피드는 혼자 든다."""
        for title in SPEED_TITLES:
            assert TITLES[title].tier is not TitleTier.TAG

    def test_a_solo_wrestler_can_hold_it(self) -> None:
        solo = make_run(brand=Brand.RAW, stats=WrestlerStats(popularity=20))
        assert Title.WWE_SPEED_CHAMPIONSHIP in eligible_titles(solo)

    @pytest.mark.parametrize("brand", list(Brand))
    def test_it_hangs_in_every_brand(self, brand: Brand) -> None:
        """NXT 2선 선수와 메인 로스터 하위 티어가 같은 벨트를 본다 (사용자 스펙)."""
        assert Title.WWE_SPEED_CHAMPIONSHIP in titles_of(brand, Gender.MALE)
        assert Title.WWE_WOMENS_SPEED_CHAMPIONSHIP in titles_of(brand, Gender.FEMALE)

    def test_below_the_gate_it_is_out_of_reach(self) -> None:
        run = make_run(stats=WrestlerStats(popularity=SPEED_POPULARITY_REQUIRED - 1))
        assert Title.WWE_SPEED_CHAMPIONSHIP not in eligible_titles(run)

    def test_at_the_gate_it_opens(self) -> None:
        run = make_run(stats=WrestlerStats(popularity=SPEED_POPULARITY_REQUIRED))
        assert Title.WWE_SPEED_CHAMPIONSHIP in eligible_titles(run)

    def test_growing_past_the_ceiling_closes_it(self) -> None:
        """**"하위 티어용"이라는 말이 여기 있다** — 위로 올라가면 더 안 쫓는다."""
        grown = make_run(stats=WrestlerStats(popularity=SPEED_POPULARITY_CEILING))
        assert Title.WWE_SPEED_CHAMPIONSHIP not in eligible_titles(grown)

    def test_the_ceiling_meets_the_secondary_gate(self) -> None:
        """상한과 2선 관문이 한 숫자다 — 스피드가 닫히는 순간 IC·US가 열린다."""
        assert (
            TITLES[Title.INTERCONTINENTAL_CHAMPIONSHIP].popularity_required
            == SPEED_POPULARITY_CEILING
        )

    def test_no_other_belt_has_a_ceiling(self) -> None:
        """상한은 §3-D20-3(정상에서 아래 벨트를 주우러 간다)과 부딪힌다 — 하나뿐이다."""
        capped = {t for t, s in TITLES.items() if s.popularity_ceiling is not None}
        assert capped == SPEED_TITLES

    def test_it_never_outranks_a_tag_belt_on_the_main_roster(self) -> None:
        """**여기가 원래 어긋났던 자리다.** 급으로 세우면 2선이라 태그 위로 올라간다.

        메인 로스터에서는 맨 아래여야 한다(태그 관문 30 > 스피드 15). NXT는 반대다 —
        NXT 태그 관문이 12라 스피드가 그 위에 선다. 순서를 정하는 것은 급이 아니라
        관문값이므로 두 결과가 모두 맞다.
        """
        for brand in (Brand.RAW, Brand.SMACKDOWN):
            for gender in Gender:
                ladder = titles_of(brand, gender)
                assert ladder[-1] in SPEED_TITLES
        for gender in Gender:
            ladder = titles_of(Brand.NXT, gender)
            speed = next(t for t in ladder if t in SPEED_TITLES)
            above = ladder[: ladder.index(speed)]
            assert all(
                TITLES[t].popularity_required > TITLES[speed].popularity_required
                for t in above
            )

    def test_a_midcarder_with_a_partner_still_picks_the_tag_belt(self) -> None:
        run = make_run(brand=Brand.RAW, stats=WrestlerStats(popularity=35)).evolve(
            team=TEAM
        )
        assert target_title(run, NEVER_CHASE) is Title.WORLD_TAG_TEAM_CHAMPIONSHIP

    def test_it_is_not_a_grand_slam_group(self) -> None:
        from wwe_game.domain.value_objects.title import GRAND_SLAM_GROUPS

        for groups in GRAND_SLAM_GROUPS.values():
            assert not {t for _, grp in groups for t in grp} & SPEED_TITLES

    def test_it_pays_less_than_any_other_belt(self) -> None:
        """관문이 낮아 자주 감기는 벨트다 — 2선 값을 주면 상한을 그것만으로 채운다."""
        assert contract_office.SPEED_PAY_WEIGHT < min(
            contract_office.TITLE_PAY_WEIGHT.values()
        )
        one_speed = make_run().evolve(titles_won=(Title.WWE_SPEED_CHAMPIONSHIP,))
        one_tag = make_run().evolve(titles_won=(Title.WORLD_TAG_TEAM_CHAMPIONSHIP,))
        assert contract_office.appraise(one_speed) < contract_office.appraise(one_tag)


# ── 곁들여: 그 밤이 실제로 서는지 ────────────────────────────


class TestItActuallyHappensInACareer:
    def test_a_career_meets_the_belt(self) -> None:
        """관문 15에 세 브랜드 공용이라, 어느 커리어든 한 번은 마주쳐야 한다."""
        met = 0
        for seed in range(700, 712):
            run = make_run(seed=seed, stats=WrestlerStats(popularity=25))
            for week in range(1, 160):
                report = simulate_week(run.evolve(week=week - 1))
                if report.title_at_stake in SPEED_TITLES:
                    met += 1
                    break
        assert met >= 6, f"12판 중 {met}판만 스피드 벨트를 봤다"

    def test_the_belt_photo_name_matches_the_code(self) -> None:
        """화면이 `/belts/<코드>.webp`로 찾는다 — 코드가 곧 파일명이다."""
        assert Title.WWE_SPEED_CHAMPIONSHIP.value == "wwe_speed_championship"
        assert (
            Title.WWE_WOMENS_SPEED_CHAMPIONSHIP.value == "wwe_womens_speed_championship"
        )

    def test_a_speed_night_never_becomes_a_signature_match(self) -> None:
        """럼블 주차에 스피드 벨트가 걸려도 30인 배틀로열로 3분 방어전을 하지는 않는다."""
        for seed in range(800, 830):
            run = make_run(seed=seed, stats=WrestlerStats(popularity=30))
            for week in range(1, 220):
                staged = run.evolve(week=week - 1)
                report = simulate_week(staged)
                # **토너먼트 주차는 예외다.** 그 밤의 형식은 대진표가 정한다
                # (§3-D33) — 스피드보다 앞선 규칙이고, 태그 벨트도 같다.
                # `report.tournament_round`가 아니라 달력에게 묻는다: 저쪽은
                # "이겨서 올라왔는가"이고 형식을 가르는 것은 "그 주차인가"다.
                if (
                    report.kind is WeekKind.PLE
                    and tournament_round_at(staged, week) == 0
                    and report.title_at_stake in SPEED_TITLES
                ):
                    assert report.match_kind in (
                        MatchKind.SPEED,
                        MatchKind.SUDDEN_DEATH,
                    )


# ── 그랜드슬램의 네 칸 (§3-D76) ──────────────────────────────


class TestTheTagBeltIsRequiredForTheSlam:
    """**태그팀은 그랜드슬램 필수다** (2026-08-13 사용자 확인).

    §3-D76에서 태그를 **폴백 사다리**에서 뺐다 — 싱글 자리에서 밀린 선수가 그 밤에
    흘러들어 갈 자리가 아니라서다. 뺀 것은 그 경로뿐이고 **필수 조건은 그대로**인데,
    둘을 헷갈리면 언젠가 "폴백에 없으니 그룹에서도 빼자"가 된다. 여기서 막는다.
    """

    @pytest.mark.parametrize("gender", list(Gender))
    def test_the_tag_group_is_one_of_the_four(self, gender: Gender) -> None:
        from wwe_game.domain.value_objects.title import GRAND_SLAM_GROUPS

        names = [name for name, _ in GRAND_SLAM_GROUPS[gender]]
        assert "태그팀" in names
        assert len(names) == 4

    @pytest.mark.parametrize("gender", list(Gender))
    def test_without_a_tag_belt_there_is_no_slam(self, gender: Gender) -> None:
        """나머지 셋을 다 감아도 태그가 비면 0이다 — 등급은 최솟값이 정한다."""
        from wwe_game.domain.value_objects.title import (
            GRAND_SLAM_GROUPS,
            grand_slam_level,
        )

        groups = dict(GRAND_SLAM_GROUPS[gender])
        without_tag = tuple(
            next(iter(sorted(belts, key=lambda t: t.value)))
            for name, belts in GRAND_SLAM_GROUPS[gender]
            if name != "태그팀"
        )
        assert grand_slam_level(without_tag, gender) == 0
        with_tag = (
            *without_tag,
            next(iter(sorted(groups["태그팀"], key=lambda t: t.value))),
        )
        assert grand_slam_level(with_tag, gender) == 1

    def test_the_tag_belt_is_still_reachable(self) -> None:
        """폴백에서 뺐다고 못 가는 벨트가 되면 그랜드슬램이 통째로 닫힌다."""
        from wwe_game.domain.services.championship import eligible_titles

        teamed = make_run(brand=Brand.RAW, stats=WrestlerStats(popularity=45)).evolve(
            team=TEAM
        )
        assert any(TITLES[t].tier is TitleTier.TAG for t in eligible_titles(teamed))
