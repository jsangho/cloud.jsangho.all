"""부상 구간은 통째로 흘러간다 (하네스 §3-D37).

다친 동안에는 할 수 있는 일이 없다. 그런데도 **부상 주차의 21%에서 이벤트가 떴고**,
뜨는 카드가 `ring_kickout_at_one`(원 카운트에 킥아웃)이었다 — 링에 못 서는 사람이
링에서 겪는 사건이다.
"""

from __future__ import annotations

from _helpers import make_run  # noqa: I001
from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.constants.event_deck import BY_CODE, DECK
from wwe_game.domain.services import career_advance, event_draw
from wwe_game.domain.value_objects.advance_outcome import StopReason
from wwe_game.domain.value_objects.condition import Condition, InjuryGrade

INJURED = Condition(grade=InjuryGrade.SERIOUS, weeks_left=12)


class TestNothingHappensInTheRingWhileYouAreOut:
    def test_ring_cards_cannot_fire_while_injured(self) -> None:
        """**링 카드는 결장 중에 뜰 수 없다.** 이 규칙의 존재 이유다."""
        run = make_run(week=300).evolve(condition=INJURED)
        ring_card = BY_CODE["ring_kickout_at_one"]
        assert not event_draw.is_eligible(run, ring_card)
        assert event_draw.is_eligible(run.evolve(condition=Condition()), ring_card)

    def test_only_cards_that_name_the_grade_survive(self) -> None:
        """다른 조건은 "생략 = 무관"인데 **여기만 반대다**."""
        run = make_run(week=300).evolve(condition=INJURED)
        pool = event_draw.candidates(run)
        assert pool, "재활 카드가 하나도 없으면 부상 구간에 사건이 영영 없다"
        for card in pool:
            assert InjuryGrade.SERIOUS in card.requires.condition_grades

    def test_the_rehab_pool_is_wide_enough_to_not_repeat(self) -> None:
        """등급마다 **다섯 장 이상**. 셋뿐이던 시절 한 카드가 커리어에 19번 나왔다."""
        for grade in (InjuryGrade.MINOR, InjuryGrade.SERIOUS):
            pool = [c for c in DECK if grade in c.requires.condition_grades]
            assert len(pool) >= 5, f"{grade.value} 재활 카드가 {len(pool)}장뿐이다"

    def test_events_are_rarer_while_injured(self) -> None:
        run = make_run(week=300)
        healthy = event_draw.event_chance(run)
        hurt = event_draw.event_chance(run.evolve(condition=INJURED))
        assert hurt == healthy * rules.INJURY_EVENT_FACTOR
        assert hurt < healthy


class TestOneClickToReturn:
    @staticmethod
    def clicks_to_recover(seed: int) -> tuple[int, StopReason]:
        """복귀까지 필요한 '다음' 횟수와 마지막 멈춤 이유."""
        run = make_run(week=300, seed=seed).evolve(condition=INJURED)
        clicks = 0
        while True:
            if run.is_blocked:
                card = BY_CODE[run.pending_event.code]
                run = event_draw.resolve_choice(run, card.choices[0].code)
                continue
            outcome = career_advance.advance(run)
            clicks += 1
            run = outcome.run
            if not run.condition.is_injured:
                return clicks, outcome.stop_reason

    def test_a_twelve_week_spell_costs_almost_no_clicks(self) -> None:
        """**열두 주 결장이 '다음' 한두 번이다** (2026-08-11 사용자 요청).

        정확히 한 번이라고 잠그지 않는 이유: 재활 카드가 가끔 뜬다(부상 주차의 5%).
        그건 없애야 할 방해가 아니라 그 구간의 유일한 내용이다.

        **평균과 최댓값을 함께 본다.** 평균만 보면 어쩌다 열 번 눌러야 하는 구간이
        숨고, 최댓값만 보면 한 시드의 운에 규칙이 매인다. 개정 전에는 부상 주차의
        21%에서 멈췄다 — 열두 주면 평균 3.5번이다.
        """
        counts = [self.clicks_to_recover(seed)[0] for seed in range(11, 21)]
        assert sum(counts) / len(counts) <= 2.0, f"평균 {sum(counts) / len(counts)}회"
        assert max(counts) <= 5, f"최악 {max(counts)}회 (시드별 {counts})"

    def test_it_stops_at_the_return(self) -> None:
        """복귀 주차에서 끊는다 — 안 끊으면 **언제 돌아왔는지가 로그에 묻힌다.**

        복귀 주차에 재활 카드가 겹치면 `EVENT`가 이긴다. 답할 사람이 필요한 쪽이
        먼저이고, 그 답을 하고 나면 어차피 몸은 나아 있다.
        """
        reasons = [self.clicks_to_recover(seed)[1] for seed in range(11, 21)]
        assert StopReason.RECOVERED in reasons
        assert set(reasons) <= {StopReason.RECOVERED, StopReason.EVENT}

    def test_a_healthy_career_never_reports_recovery(self) -> None:
        run = make_run(week=300, seed=11)
        outcome = career_advance.advance(run)
        assert outcome.stop_reason is not StopReason.RECOVERED
