"""도메인이 만든 것이 응답까지 나오는가 (하네스 §3-D73, 3차 평가).

**이 파일이 잠그는 것은 "만들었는데 안 보인다"이다.** 계약·돈 축은 2026-08-11에
도메인이 완성됐는데 2026-08-13까지 응답에 한 필드도 안 나갔다 — 테스트가 전부
도메인 안에서만 돌아서 아무도 안 잡았다. 그랜드슬램도 같은 자리였다.

그래서 여기는 **어댑터 경계**를 잰다: 도메인 값 → 스키마 → camelCase 응답.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "domain"))

from _helpers import make_run  # noqa: E402, I001
from wwe_game.adapter.inbound.api.schemas.career_schema import (  # noqa: E402
    BriefcaseSchema,
    OfferOptionSchema,
    to_briefcase,
    to_grand_slam,
    to_money,
    to_offer_options,
    to_week,
)
from wwe_game.app.dtos.career_dto import WeekReportView  # noqa: E402
from wwe_game.domain.constants import career_rules as rules  # noqa: E402
from wwe_game.domain.services.week_simulation import simulate_week  # noqa: E402
from wwe_game.domain.value_objects.condition import InjuryGrade  # noqa: E402
from wwe_game.domain.value_objects.body_part import BodyPart  # noqa: E402
from wwe_game.domain.value_objects.contract_offer import OfferChoice  # noqa: E402
from wwe_game.domain.value_objects.title import Title  # noqa: E402
from wwe_game.domain.value_objects.week_report import (  # noqa: E402
    CallUpReason,
    WeekKind,
    WeekReport,
)


def view_of(report: WeekReport, run) -> WeekReportView:
    return WeekReportView(
        report=report, narration="", stats=run.stats, match_summary=None
    )


# ── 계약·돈 (§3-D47·D50) ─────────────────────────────────────


class TestTheContractReachesTheScreen:
    def test_a_signed_run_reports_its_deal(self) -> None:
        run = make_run(week=100)
        money = to_money(run)
        assert money.contract is not None
        assert money.contract.weekly_pay > 0
        # **연봉은 도메인이 곱한다** — 화면이 52를 곱하면 두 곳이 갈린다.
        assert money.contract.annual_pay == money.contract.weekly_pay * 52

    def test_the_balance_is_carried(self) -> None:
        assert to_money(make_run().evolve(money=1_234_567)).balance == 1_234_567

    def test_market_value_comes_along(self) -> None:
        """**주급과 몸값이 갈리는 폭이 재계약의 긴장이다** — 둘을 함께 낸다."""
        assert to_money(make_run(week=500)).market_value > 0

    def test_weeks_left_never_goes_negative(self) -> None:
        """만료 주차를 부상으로 건너뛸 수 있다(`Contract.expires_at`)."""
        run = make_run(week=100)
        assert run.contract is not None
        late = run.evolve(week=run.contract.ends_week + 30)
        assert to_money(late).contract is not None
        assert to_money(late).contract.weeks_left == 0

    def test_an_unsigned_run_has_no_contract_but_has_a_clock(self) -> None:
        """**무소속 구간의 유일한 시계다** (§3-D50). 없으면 2년 반이 통째로 깜깜하다."""
        run = make_run(week=600).evolve(contract=None, unsigned_weeks=70)
        money = to_money(run)
        assert money.contract is None
        assert money.unsigned_weeks == 70
        assert money.fade_in_weeks == rules.FADE_GRACE_WEEKS - 70

    def test_a_signed_run_has_no_fade_clock(self) -> None:
        assert to_money(make_run(week=100)).fade_in_weeks is None

    def test_the_fade_clock_stops_at_zero(self) -> None:
        run = make_run(week=900).evolve(
            contract=None, unsigned_weeks=rules.FADE_GRACE_WEEKS + 20
        )
        assert to_money(run).fade_in_weeks == 0


# ── 재계약 협상 (§3-D84) ─────────────────────────────────────


class TestTheOfferReachesTheScreen:
    """**협상은 화면이 없으면 존재하지 않는 것과 같다.** 도메인만 만들어 두고
    응답에 안 실은 채 하루를 보낸 것이 바로 이 파일이 생긴 이유다(§3-D73)."""

    @staticmethod
    def opened():
        return make_run(week=300).evolve(offer_week=300)

    def test_an_open_offer_sends_all_five_choices(self) -> None:
        options = to_offer_options(self.opened())
        assert len(options) == len(OfferChoice), "다섯이 다 가야 선택이 된다"
        assert {o.code for o in options} == {c.value for c in OfferChoice}

    def test_a_quiet_week_sends_none(self) -> None:
        """**비어 있으면 협상 중이 아니다** — 화면은 목록의 길이만 본다."""
        assert to_offer_options(make_run(week=300)) == []

    def test_each_choice_carries_its_terms(self) -> None:
        by_code = {o.code: o for o in to_offer_options(self.opened())}
        assert by_code[OfferChoice.ACCEPT.value].weekly_pay > 0
        assert by_code[OfferChoice.LONG.value].years == 5
        # 나가는 길에는 조건이 없다 — 0이 그 사실을 말한다.
        assert by_code[OfferChoice.WALK.value].years == 0
        assert by_code[OfferChoice.WALK.value].weekly_pay == 0

    def test_the_refusal_odds_never_leave_the_domain(self) -> None:
        """**거절 확률은 안 나간다** (§11-14). 보이면 '더 부른다'가 계산이 된다."""
        fields = set(OfferOptionSchema.model_fields)
        assert "refusal" not in fields
        assert not fields & {"pay_factor", "risk", "chance"}


# ── 가방 (§3-D85) ────────────────────────────────────────────


class TestTheBriefcaseReachesTheScreen:
    """**상시 행동은 보이지 않으면 없는 것과 같다.** 멈춤과 달리 게임이 물어보지
    않으므로, 화면이 자리를 안 내주면 플레이어는 가방을 든 줄도 모른다."""

    @staticmethod
    def carrying():
        return make_run(week=300).evolve(briefcase_week=283)

    def test_it_carries_the_clock_and_the_target(self) -> None:
        card = to_briefcase(self.carrying())
        assert card is not None
        assert card.weeks_left == rules.BRIEFCASE_WEEKS - 17
        assert card.title and card.champion, "겨누는 벨트와 그 주인이 함께 와야 고른다"
        assert card.can_cash_in is True
        assert card.pending is False

    def test_no_briefcase_no_card(self) -> None:
        assert to_briefcase(make_run(week=300)) is None

    def test_the_champions_numbers_never_leave_the_domain(self) -> None:
        """**챔피언의 인기도는 안 나간다** (§11-14) — 나가면 승률의 힌트가 된다."""
        fields = set(BriefcaseSchema.model_fields)
        assert not fields & {"popularity", "champion_popularity", "odds", "chance"}


# ── 그랜드슬램 (§3-D20) ──────────────────────────────────────


class TestTheGrandSlamReachesTheScreen:
    def test_four_groups_always(self) -> None:
        slam = to_grand_slam(make_run())
        assert [g.name for g in slam.groups] == ["월드", "인터컨티넨탈", "US", "태그팀"]

    def test_an_empty_career_is_level_zero_with_four_empty_boxes(self) -> None:
        """**빈 칸을 숨기지 않는다** — 비어 있는 것이 정보다."""
        slam = to_grand_slam(make_run())
        assert slam.level == 0
        assert all(g.count == 0 for g in slam.groups)

    def test_the_lowest_group_sets_the_level(self) -> None:
        """월드를 다섯 번 감아도 US가 없으면 0이다."""
        run = make_run().evolve(titles_won=(Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP,) * 5)
        slam = to_grand_slam(run)
        assert slam.level == 0
        assert slam.groups[0].count == 5

    def test_all_four_filled_is_a_slam(self) -> None:
        run = make_run().evolve(
            titles_won=(
                Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP,
                Title.INTERCONTINENTAL_CHAMPIONSHIP,
                Title.UNITED_STATES_CHAMPIONSHIP,
                Title.WORLD_TAG_TEAM_CHAMPIONSHIP,
            )
        )
        assert to_grand_slam(run).level == 1

    def test_the_womens_groups_use_womens_belts(self) -> None:
        from wwe_game.domain.value_objects.wrestler_identity import Gender

        run = make_run(gender=Gender.FEMALE).evolve(
            titles_won=(Title.WWE_WOMENS_TAG_TEAM_CHAMPIONSHIP,)
        )
        slam = to_grand_slam(run)
        assert slam.groups[3].name == "태그팀"
        assert slam.groups[3].count == 1


# ── 주차 리포트의 잃어버린 사건들 ────────────────────────────


class TestTheWeekReportsWhatItMade:
    def test_pay_reaches_the_row(self) -> None:
        run = make_run(week=300)
        report = simulate_week(run)
        assert to_week(view_of(report, run), seed=run.seed).pay == report.pay

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("title_defended", True),
            ("draft_night", True),
        ],
    )
    def test_flags_reach_the_row(self, field: str, value: bool) -> None:
        run = make_run(week=300)
        report = WeekReport(week=300, kind=WeekKind.PLE, **{field: value})
        assert getattr(to_week(view_of(report, run), seed=1), field) is value

    def test_a_vacated_belt_leaves_a_line(self) -> None:
        """**지금까지 로그에 한 줄도 없었다** — 다음에 목록을 보면 그냥 사라져 있다."""
        run = make_run(week=300)
        report = WeekReport(
            week=300,
            kind=WeekKind.OFF,
            vacated=(Title.INTERCONTINENTAL_CHAMPIONSHIP,),
        )
        row = to_week(view_of(report, run), seed=1)
        assert row.vacated == ["intercontinental_championship"]

    def test_the_injured_part_is_named_not_coded(self) -> None:
        """화면이 코드를 다시 사람 말로 옮기지 않게 라벨로 낸다 (§3-D43)."""
        run = make_run(week=300)
        report = WeekReport(
            week=300,
            kind=WeekKind.WEEKLY_SHOW,
            injury=InjuryGrade.MINOR,
            injury_weeks=3,
            injury_part=BodyPart.KNEE,
        )
        part = to_week(view_of(report, run), seed=1).injury_part
        assert part and part != BodyPart.KNEE.value

    def test_the_call_up_reason_reaches_the_row(self) -> None:
        run = make_run(week=100)
        report = WeekReport(week=100, kind=WeekKind.PLE, call_up=CallUpReason.EMERGENCY)
        assert to_week(view_of(report, run), seed=1).call_up == "emergency"

    def test_an_ordinary_week_stays_quiet(self) -> None:
        """새 필드가 평범한 주차에 줄을 만들면 안 된다 — 30년이면 1560줄이다."""
        run = make_run(week=300)
        row = to_week(view_of(WeekReport(week=300, kind=WeekKind.PROMO), run), seed=1)
        assert row.vacated == []
        assert row.injury_part is None
        assert row.call_up is None
        assert row.draft_night is False
        assert row.title_defended is False
