"""은퇴 (`career_retirement` · `career_injury`).

**붙드는 것은 계약이다.**

1. **평가와 확정이 갈라져 있다** — `assess` 는 아무것도 바꾸지 않는다
2. **나이만으로는 은퇴하지 않는다** — 45세라도 몸이 멀쩡하면 "주의" 에 머문다
3. **의사와 확정이 다르다** — `RETIREMENT_PENDING` 인 선수는 계속 경기한다
4. **확정은 멱등이다** — 같은 은퇴가 반복돼도 기록이 한 번만 생긴다
5. **은퇴 선수는 지워지지 않는다** — 대진에서만 빠지고 기록은 조회된다
6. **영구 불가는 복귀 선택지가 없다** — 일반 은퇴 사건과 다르게 취급한다

순수 함수라 DB가 필요 없다.
"""

from __future__ import annotations

from kayfabe.domain.services import career_retirement as retire
from kayfabe.domain.services.career_injury import (
    active_injury,
    maybe_injure,
    rest,
    tick_recovery,
)
from kayfabe.domain.services.career_world import (
    Ability,
    Balance,
    Injury,
    RetirementCause,
    Severity,
    Status,
    Wrestler,
)

BAL = Balance()


def _wrestler(**kwargs) -> Wrestler:
    base = {
        "name": "Subject",
        "style": "테크니션",
        "age": 25,
        "debut_age": 22,
        "ability": Ability(in_ring=60, mic=55, stamina=80, resilience=78),
        "condition": 80,
    }
    base.update(kwargs)
    return Wrestler(**base)


def _injury(severity=Severity.SERIOUS, **kwargs) -> Injury:
    base = {
        "kind": "무릎",
        "severity": severity,
        "season": 1,
        "week": 10,
        "weeks_out": 6,
        "recovered": True,
    }
    base.update(kwargs)
    return Injury(**base)


# ── 1. 평가는 아무것도 바꾸지 않는다 ──────────────────────────────


def test_assess_does_not_mutate():
    """**평가는 순수하다.** 이것이 평가/확정 분리의 핵심이다."""
    before = _wrestler(age=40)
    risk = retire.assess(before, BAL)
    assert before == _wrestler(age=40)
    assert before.status == Status.ACTIVE
    assert before.retirement is None
    assert 0.0 <= risk.score <= 1.0


def test_risk_reports_reasons_not_just_a_number():
    """근거를 함께 낸다 — 화면이 "왜" 를 적어야 한다(§6)."""
    risk = retire.assess(
        _wrestler(age=41, ability=Ability(70, 65, 40, 35), injuries=(_injury(),)), BAL
    )
    # 41세 · 체력37 · 부상1 = 0.575 → "주의". **"높은 위험" 이 아니다** — 요소가
    # 셋뿐이라 상한 합이 거기까지 안 간다. 그게 §3.2 의 "단일 요소만으로" 금지가
    # 수치로 지켜지는 모습이다.
    assert risk.band == retire.BAND_CAUTION
    assert risk.explained
    assert any("나이" in r for r in risk.explained)
    # 무게 순으로 정렬돼 있다.
    weights = [f.weight for f in sorted(risk.factors, key=lambda x: -x.weight)]
    assert weights == sorted(weights, reverse=True)


# ── 2. 나이만으로는 은퇴하지 않는다 ───────────────────────────────


def test_young_healthy_wrestler_is_stable():
    """젊고 건강하면 "안정" 이다(§7 은퇴 테스트 1)."""
    risk = retire.assess(_wrestler(age=24), BAL)
    assert risk.band == retire.BAND_STABLE
    assert not retire.should_open_event(risk, BAL)


def test_age_alone_cannot_force_retirement():
    """**45세라도 몸이 멀쩡하면 자동 은퇴하지 않는다**(§3.2).

    나이 가중 상한이 0.30 이고 자동 은퇴 기준이 0.85 라 구조적으로 불가능하다.
    """
    ancient = _wrestler(age=45, ability=Ability(80, 80, 75, 72), condition=85)
    risk = retire.assess(ancient, BAL)
    assert risk.score < BAL.risk_auto_floor
    assert not retire.should_auto_retire(ancient, risk, BAL)


def test_risk_rises_with_combined_factors():
    """여러 요소가 겹치면 위험이 오른다 — 하나로는 안 오른다."""
    just_old = retire.assess(_wrestler(age=40), BAL)
    old_and_broken = retire.assess(
        _wrestler(
            age=40,
            ability=Ability(70, 65, 35, 30),
            condition=30,
            consecutive_matches=11,
            injuries=(_injury(), _injury(kind="목", recurrence=True)),
        ),
        BAL,
    )
    assert old_and_broken.score > just_old.score
    assert old_and_broken.band == retire.BAND_HIGH


def test_auto_retire_needs_both_score_and_intent():
    """**자물쇠가 둘이다.** 점수만으로도, 의사만으로도 은퇴하지 않는다."""
    broken = _wrestler(
        age=44,
        ability=Ability(70, 70, 20, 18),
        condition=20,
        consecutive_matches=12,
        losing_streak=8,
        injuries=tuple(
            _injury(kind=k) for k in ("무릎", "어깨", "허리", "발목", "손목")
        ),
    )
    risk = retire.assess(broken, BAL)
    assert risk.score >= BAL.risk_auto_floor
    # 점수는 충분한데 의사가 없다 → 은퇴하지 않는다.
    assert not retire.should_auto_retire(broken, risk, BAL)

    willing = retire.declare_intent(
        broken, origin="self", cause=RetirementCause.VOLUNTARY, season=2, week=10
    )
    assert retire.should_auto_retire(willing, retire.assess(willing, BAL), BAL)


# ── 3. 의사 ≠ 확정 ────────────────────────────────────────────────


def test_intent_is_not_retirement():
    """은퇴 **의사**는 은퇴가 아니다(§3.1)."""
    pending = retire.declare_intent(
        _wrestler(age=38),
        origin="offered",
        cause=RetirementCause.AGE_DECLINE,
        season=2,
        week=4,
    )
    assert pending.status == Status.RETIREMENT_PENDING
    assert pending.retirement is None
    assert not pending.retired
    assert pending.intent is not None


def test_retirement_pending_wrestler_still_competes():
    """**마지막 시즌을 선언한 선수는 계속 경기한다.**

    대진에서 빼면 선언이 곧 은퇴가 되고, 그게 §3.1 이 구별하라고 한 혼동이다.
    """
    pending = retire.declare_intent(
        _wrestler(), origin="self", cause=RetirementCause.VOLUNTARY, season=1, week=1
    )
    assert pending.bookable


def test_intent_origin_distinguishes_self_from_offered():
    """선수가 요청한 것과 게임이 제안한 것을 가른다(§3.1)."""
    asked = retire.declare_intent(
        _wrestler(), origin="self", cause=RetirementCause.REQUESTED, season=1, week=5
    )
    offered = retire.declare_intent(
        _wrestler(),
        origin="offered",
        cause=RetirementCause.AGE_DECLINE,
        season=1,
        week=5,
    )
    assert asked.intent.origin == "self"
    assert offered.intent.origin == "offered"
    assert (
        retire.infer_cause(asked, retire.assess(asked, BAL), BAL)
        == RetirementCause.REQUESTED
    )


def test_intent_is_not_overwritten():
    """이미 의사가 있으면 덮어쓰지 않는다 — 이력이 지워지면 안 된다."""
    first = retire.declare_intent(
        _wrestler(), origin="self", cause=RetirementCause.VOLUNTARY, season=1, week=3
    )
    second = retire.declare_intent(
        first, origin="offered", cause=RetirementCause.POOR_FORM, season=2, week=9
    )
    assert second.intent == first.intent


def test_withdraw_intent_returns_to_active():
    """ "현역을 유지한다" 는 의사를 거둔다(§4)."""
    pending = retire.declare_intent(
        _wrestler(),
        origin="offered",
        cause=RetirementCause.AGE_DECLINE,
        season=1,
        week=5,
    )
    back = retire.withdraw_intent(pending)
    assert back.intent is None
    assert back.status == Status.ACTIVE


# ── 4. 확정은 멱등이다 ────────────────────────────────────────────


def test_confirm_is_idempotent():
    """**은퇴 기록이 두 번 생기지 않는다**(§3.4)."""
    once = retire.confirm(
        _wrestler(age=40, wins=50, losses=30),
        cause=RetirementCause.AGE_DECLINE,
        season=3,
        week=20,
    )
    twice = retire.confirm(once, cause=RetirementCause.SEVERE_INJURY, season=9, week=1)
    assert twice.retirement == once.retirement
    assert twice.retirement.season == 3


def test_confirm_snapshots_record_at_the_time():
    """은퇴 당시 수치를 **복사해 둔다** — 나중에 규칙이 바뀌어도 소급되지 않는다."""
    champ = _wrestler(
        age=39,
        wins=80,
        losses=40,
        held=("World Heavyweight Championship",),
        reigns=(
            "NXT Championship",
            "World Heavyweight Championship",
            "World Heavyweight Championship",
        ),
    )
    retired = retire.confirm(
        champ, cause=RetirementCause.GOAL_COMPLETE, season=4, week=52
    )
    record = retired.retirement
    assert record.age == 39
    assert (record.wins, record.losses) == (80, 40)
    assert record.reigns == 3
    # 보유 벨트는 비워지지만 **기록에는 남는다**.
    assert retired.held == ()
    assert "World Heavyweight Championship" in record.held
    # `titles` 는 중복 없는 목록이다.
    assert record.titles == ("NXT Championship", "World Heavyweight Championship")


# ── 5. 은퇴 선수는 지워지지 않는다 ────────────────────────────────


def test_retired_wrestler_is_not_bookable_but_keeps_records():
    """대진에서만 빠진다. **전적·기록은 그대로 조회된다**(§3.4 · §5)."""
    retired = retire.confirm(
        _wrestler(wins=12, losses=7, reigns=("NXT Championship",)),
        cause=RetirementCause.VOLUNTARY,
        season=2,
        week=30,
    )
    assert retired.status == Status.RETIRED
    assert not retired.bookable
    # 지워지지 않았다.
    assert retired.wins == 12
    assert retired.losses == 7
    assert retired.reigns == ("NXT Championship",)


# ── 6. 부상과 은퇴의 연계 ─────────────────────────────────────────


def test_minor_injury_recovers():
    """경미한 부상은 회복된다(§3.3)."""
    hurt = _wrestler(
        out_weeks=1,
        status=Status.INJURED,
        injuries=(_injury(severity=Severity.MINOR, weeks_out=1, recovered=False),),
    )
    healed, back = tick_recovery(hurt)
    assert back
    assert healed.out_weeks == 0
    assert healed.status == Status.ACTIVE
    assert active_injury(healed) is None


def test_rest_restores_condition():
    """휴식이 컨디션을 올린다 — `career_run` 이 뺐던 선택지가 값을 갖게 된 이유."""
    tired = _wrestler(condition=30)
    rested = rest(tired)
    assert rested.condition > tired.condition
    assert rested.consecutive_matches == 0


def test_serious_injury_lowers_body_and_raises_risk():
    """심각한 부상은 능력치를 깎고 위험을 올린다(§3.3)."""
    healthy = _wrestler(age=34)
    before = retire.assess(healthy, BAL)
    hurt, injury = maybe_injure(
        healthy, seed=1, balance=BAL, season=1, week=5, key="k", forced=True
    )
    assert injury is not None
    after = retire.assess(hurt, BAL)
    assert after.score > before.score
    if injury.severity != Severity.MINOR:
        assert hurt.ability.stamina < healthy.ability.stamina


def test_repeated_injuries_raise_risk():
    """**반복 부상이 위험 평가에 반영된다**(§7 은퇴 테스트 5)."""
    one = retire.assess(_wrestler(age=35, injuries=(_injury(),)), BAL)
    many = retire.assess(
        _wrestler(
            age=35,
            injuries=tuple(
                _injury(kind=k) for k in ("무릎", "어깨", "허리", "목", "발목")
            ),
        ),
        BAL,
    )
    assert many.score > one.score
    assert any("누적 부상" in r for r in many.explained)


def test_recurrence_is_heavier_than_a_fresh_injury():
    """재발이 새 부상보다 무겁다(§3.3 재발 여부)."""
    fresh = retire.assess(_wrestler(age=36, injuries=(_injury(),)), BAL)
    again = retire.assess(
        _wrestler(age=36, injuries=(_injury(), _injury(recurrence=True))), BAL
    )
    assert again.score > fresh.score


def test_severe_injury_does_not_retire_immediately():
    """**심각한 부상이 곧 은퇴가 아니다**(§3.3)."""
    victim = _wrestler(age=30)
    hurt, injury = maybe_injure(
        victim, seed=3, balance=BAL, season=1, week=8, key="k", forced=True
    )
    assert injury is not None
    assert not hurt.retired
    assert hurt.retirement is None
    assert hurt.status == Status.INJURED


def test_permanent_injury_is_medical_and_blocks_return():
    """영구 불가는 **의학적 사유**이고 복귀 선택지가 없다(§3.3 · §4)."""
    doomed = _wrestler(
        age=39,
        injuries=(
            _injury(
                kind="목",
                severity=Severity.CAREER_THREATENING,
                permanent=True,
                recovered=False,
            ),
        ),
        out_weeks=0,
        status=Status.INJURED,
    )
    assert doomed.permanently_out
    risk = retire.assess(doomed, BAL)
    # 평가 없이도 은퇴한다 — 위험이 아니라 사실이다.
    assert retire.should_auto_retire(doomed, risk, BAL)
    assert retire.infer_cause(doomed, risk, BAL) == RetirementCause.MEDICAL
    # 의사를 거둘 수 없다.
    assert retire.withdraw_intent(doomed).status != Status.ACTIVE


def test_permanent_injury_does_not_heal_back_to_active():
    """결장이 끝나도 `ACTIVE` 로 돌아가지 않는다."""
    doomed = _wrestler(
        status=Status.INJURED,
        out_weeks=1,
        injuries=(
            _injury(
                kind="뇌",
                severity=Severity.CAREER_THREATENING,
                permanent=True,
                recovered=False,
            ),
        ),
    )
    healed, back = tick_recovery(doomed)
    assert not back
    assert healed.status == Status.INJURED
    assert not healed.bookable


def test_cause_is_inferred_from_heaviest_factor():
    """원인을 가장 무거운 근거에서 고른다 — 호출부마다 다른 이름이 붙지 않는다."""
    broken = _wrestler(
        age=34,
        injuries=tuple(
            _injury(kind=k, severity=Severity.CAREER_THREATENING)
            for k in ("목", "무릎")
        ),
    )
    assert (
        retire.infer_cause(broken, retire.assess(broken, BAL), BAL)
        == RetirementCause.SEVERE_INJURY
    )

    slumping = _wrestler(age=28, losing_streak=12)
    assert (
        retire.infer_cause(slumping, retire.assess(slumping, BAL), BAL)
        == RetirementCause.POOR_FORM
    )

    aging = _wrestler(age=44, ability=Ability(70, 70, 45, 42))
    assert (
        retire.infer_cause(aging, retire.assess(aging, BAL), BAL)
        == RetirementCause.AGE_DECLINE
    )


def test_probabilistic_logic_is_reproducible_with_a_seed():
    """**같은 시드면 같은 부상**이다(§7 은퇴 테스트 마지막 줄)."""
    victim = _wrestler(age=33, condition=40, consecutive_matches=9)
    runs = [
        maybe_injure(victim, seed=42, balance=BAL, season=2, week=7, key="s2w7")
        for _ in range(3)
    ]
    assert runs[0] == runs[1] == runs[2]
    # 시드가 다르면 달라질 수 있다 — 고정값이 아니라 시드 함수라는 뜻이다.
    other = maybe_injure(victim, seed=43, balance=BAL, season=2, week=7, key="s2w7")
    assert isinstance(other[1], Injury) or other[1] is None
