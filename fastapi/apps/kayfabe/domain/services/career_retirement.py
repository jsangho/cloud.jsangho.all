"""은퇴. **평가와 확정이 갈라져 있다**(사용자 요구 §3.2 · §8).

이 파일의 두 함수가 그 분리다:

    assess(...)  → RetirementRisk    위험을 **재기만** 한다. 아무것도 바꾸지 않는다
    confirm(...) → Wrestler          은퇴를 **확정한다**. 평가를 다시 하지 않는다

둘을 한 함수로 묶으면 "위험이 높으니 은퇴시킨다" 가 되고, 그러면 §3.2 의 "단일
요소만으로 자동 은퇴가 확정되지 않도록 한다" 를 지킬 자리가 없어진다. 평가는
**사건을 열지 말지**만 정하고, 확정은 플레이어의 선택이나 좁은 자동 조건을 거친다.

## 자물쇠가 둘이다

자동 은퇴(`should_auto_retire`)는 **점수와 의사를 모두** 요구한다. 점수만으로는
은퇴하지 않고, 의사만으로도 은퇴하지 않는다. 나이만으로는 더더욱 아니다 —
나이는 아래 여섯 요소 중 하나의 가중치일 뿐이다.

예외는 의학적 영구 불가 하나다(`permanently_out`). 그건 평가의 문제가 아니라
사실이고, 복귀 선택지 자체가 없다(§3.3 "영구적인 활동 불가").
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from kayfabe.domain.services.career_aging import recent_trend
from kayfabe.domain.services.career_world import (
    Balance,
    Retirement,
    RetirementCause,
    RetirementIntent,
    Severity,
    Status,
    Wrestler,
)


@dataclass(frozen=True)
class RiskFactor:
    """위험의 **근거 한 줄**. 화면이 이걸 읽어 설명한다.

    점수만 내보내면 "높은 위험" 이 왜인지 말할 수 없다. 사용자 요구 §6 —
    "근거 없는 퍼센트를 표시하지 말고 설명 가능한 단계로 제공한다."
    """

    code: str
    label: str
    #: 이 요소가 점수에 더한 양(0~1 척도).
    weight: float


@dataclass(frozen=True)
class RetirementRisk:
    """위험 **평가 결과**. 이것이 은퇴를 시키지 않는다.

    `score` 는 0~1 이지만 **화면에 퍼센트로 내보내지 않는다** — 검증된 수치가
    아니라 가중합일 뿐이고, 퍼센트로 적으면 근거 없는 정밀도가 생긴다(§6).
    화면이 쓰는 것은 `band` 와 `factors` 다.
    """

    score: float
    band: str
    factors: tuple[RiskFactor, ...]

    @property
    def explained(self) -> tuple[str, ...]:
        """근거 문구. 무게 순이다."""
        return tuple(
            f.label
            for f in sorted(self.factors, key=lambda x: -x.weight)
            if f.weight > 0
        )


#: 밴드 이름. 사용자 요구 §6 가 지정한 세 단계다.
BAND_STABLE = "안정"
BAND_CAUTION = "주의"
BAND_HIGH = "높은 위험"


def _band(score: float, balance: Balance) -> str:
    if score >= balance.risk_high:
        return BAND_HIGH
    if score >= balance.risk_caution:
        return BAND_CAUTION
    return BAND_STABLE


def assess(wrestler: Wrestler, balance: Balance) -> RetirementRisk:
    """은퇴 위험을 **잰다**. 선수를 바꾸지 않는다.

    요소는 §3.2 의 목록을 그대로 따른다. 가중치 합이 1.0 을 넘을 수 있으므로
    마지막에 자른다 — 여러 요소가 동시에 나쁘면 1.0 에 붙는 것이 맞다.

    **나이 하나로는 `risk_auto_floor` 에 닿지 못한다.** 나이 최대 가중이 0.30 이고
    자동 은퇴 기준이 0.85 라, 45세라도 몸·부상·성적이 멀쩡하면 "주의" 에 머문다.
    그게 §3.2 의 "특히 나이만으로 무조건 은퇴시키지 않는다" 를 수치로 지키는 방식이다.
    """
    factors: list[RiskFactor] = []

    # 1) 나이 — 상한 0.30.
    over = wrestler.age - balance.decline_age
    if over > 0:
        weight = min(0.30, over * 0.03)
        factors.append(RiskFactor("age", f"나이 {wrestler.age}세", weight))

    # 2) 체력·회복력 — 상한 0.25. 낮을수록 무겁다.
    body = (wrestler.ability.stamina + wrestler.ability.resilience) / 2
    if body < 60:
        weight = min(0.25, (60 - body) / 100.0)
        factors.append(RiskFactor("body", f"체력·회복력 {int(body)}", weight))

    # 3) 능력치 추이 — 상한 0.12. 떨어지는 중이면 수치가 멀쩡해도 위험하다.
    trend = recent_trend(wrestler)
    if trend is not None:
        slide = -(trend.stamina + trend.resilience)
        if slide > 0:
            weight = min(0.12, slide / 40.0)
            factors.append(RiskFactor("trend", f"최근 체력 하락 {slide}", weight))

    # 4) 누적 부상 — 상한 0.18.
    if wrestler.injuries:
        weight = min(0.18, len(wrestler.injuries) * 0.03)
        factors.append(
            RiskFactor("injury_count", f"누적 부상 {len(wrestler.injuries)}회", weight)
        )

    # 5) 심각한 부상 이력 — 상한 0.22. 재발이면 더 무겁다.
    grave = wrestler.serious_injuries
    if grave:
        recurrences = sum(1 for i in wrestler.injuries if i.recurrence)
        weight = min(0.22, grave * 0.08 + recurrences * 0.04)
        factors.append(RiskFactor("injury_grave", f"심각한 부상 {grave}회", weight))

    # 6) 현재 부상 상태 — 지금 앓고 있으면 더한다.
    if wrestler.out_weeks > 0:
        current = next(
            (i for i in reversed(wrestler.injuries) if not i.recovered), None
        )
        if current is not None and current.severity != Severity.MINOR:
            factors.append(
                RiskFactor("injury_now", f"{current.kind} 부상 회복 중", 0.10)
            )

    # 7) 경기 부담 — 상한 0.10.
    if wrestler.consecutive_matches >= 8:
        weight = min(0.10, (wrestler.consecutive_matches - 7) * 0.02)
        factors.append(
            RiskFactor("load", f"연속 출전 {wrestler.consecutive_matches}주", weight)
        )

    # 8) 컨디션.
    if wrestler.condition < 40:
        factors.append(RiskFactor("condition", f"컨디션 {wrestler.condition}", 0.08))

    # 9) 성적 부진 — 커리어 만족도의 음수 쪽.
    if wrestler.losing_streak >= balance.poor_form_losses:
        factors.append(RiskFactor("form", f"{wrestler.losing_streak}연패", 0.12))

    # 10) 은퇴 의사. **의사가 위험을 올리지만 확정하지는 않는다.**
    if wrestler.intent is not None:
        label = "마지막 시즌 선언" if wrestler.intent.final_season else "은퇴 의사"
        factors.append(RiskFactor("intent", label, 0.20))

    score = min(1.0, sum(f.weight for f in factors))
    return RetirementRisk(
        score=score, band=_band(score, balance), factors=tuple(factors)
    )


def should_open_event(risk: RetirementRisk, balance: Balance) -> bool:
    """은퇴 **사건을 열지** 말지. 은퇴 여부가 아니다.

    §3.2 — "위험 평가 결과는 은퇴 이벤트를 발생시킬지 판단하는 데 사용하고,
    실제 은퇴는 확정 조건과 처리 절차를 거쳐 실행한다."
    """
    return risk.score >= balance.risk_event_floor


def should_auto_retire(
    wrestler: Wrestler, risk: RetirementRisk, balance: Balance
) -> bool:
    """플레이어 개입 없이 은퇴하는가. **자물쇠가 둘이다.**

    점수가 `risk_auto_floor` 를 넘고 **의사까지** 있어야 한다. 둘 중 하나만으로는
    은퇴하지 않는다 — 그래서 나이만으로도, 부상만으로도 강제 은퇴가 없다.

    의학적 영구 불가는 예외다. 그건 위험이 아니라 사실이다.
    """
    if wrestler.permanently_out:
        return True
    return risk.score >= balance.risk_auto_floor and wrestler.intent is not None


def infer_cause(wrestler: Wrestler, risk: RetirementRisk, balance: Balance) -> str:
    """은퇴 원인을 **가장 무거운 근거에서** 고른다.

    원인을 호출부가 적게 하면 같은 은퇴가 호출 위치마다 다른 이름을 갖는다.
    여기 한 곳에서 정한다.
    """
    if wrestler.permanently_out:
        return RetirementCause.MEDICAL
    if wrestler.intent is not None and wrestler.intent.origin == "self":
        return RetirementCause.REQUESTED
    ranked = sorted(risk.factors, key=lambda f: -f.weight)
    top = ranked[0].code if ranked else "age"
    if top in ("injury_grave", "injury_now"):
        return RetirementCause.SEVERE_INJURY
    if top == "injury_count":
        return RetirementCause.REPEATED_INJURY
    if top == "form":
        return RetirementCause.POOR_FORM
    if top in ("body", "trend", "age"):
        return RetirementCause.AGE_DECLINE
    return RetirementCause.VOLUNTARY


def declare_intent(
    wrestler: Wrestler,
    *,
    origin: str,
    cause: str,
    season: int,
    week: int,
    final_season: bool = False,
) -> Wrestler:
    """은퇴 **의사**를 남긴다. 아직 은퇴가 아니다.

    상태가 `RETIREMENT_PENDING` 으로 가지만 **대진에는 계속 선다**(`BOOKABLE` 이
    이 상태를 포함한다) — 마지막 시즌을 뛰는 선수가 경기를 못 하면 선언이 곧
    은퇴가 되고, 그게 §3.1 이 구별하라고 한 바로 그 혼동이다.

    이미 의사가 있으면 그대로 둔다 — 중복 선언이 이력을 덮어쓰지 않는다.
    """
    if wrestler.retired or wrestler.intent is not None:
        return wrestler
    intent = RetirementIntent(
        origin=origin,
        cause=cause,
        season=season,
        week=week,
        final_season=final_season,
    )
    status = (
        wrestler.status
        if wrestler.status == Status.INJURED
        else Status.RETIREMENT_PENDING
    )
    return replace(wrestler, intent=intent, status=status)


def withdraw_intent(wrestler: Wrestler) -> Wrestler:
    """의사를 거둔다 — "현역을 유지한다" 선택의 결과다(§4).

    영구 불가인 선수는 거둘 수 없다. 규칙상 복귀가 없는 상황을 일반 선택지와
    같이 취급하지 않는다(§4 마지막 문단).
    """
    if wrestler.retired or wrestler.permanently_out:
        return wrestler
    status = Status.INJURED if wrestler.out_weeks > 0 else Status.ACTIVE
    return replace(wrestler, intent=None, status=status)


def confirm(
    wrestler: Wrestler,
    *,
    cause: str,
    season: int,
    week: int,
    note: str = "",
) -> Wrestler:
    """은퇴를 **확정한다**. 평가를 다시 하지 않는다 — 부르는 쪽이 이미 정했다.

    **멱등이다.** 이미 은퇴한 선수는 그대로 돌려준다. 그래서 같은 은퇴 이벤트가
    반복 실행되어도 기록이 두 번 생기지 않는다(§3.4). 벨트 공석 처리는 여기서
    하지 않는다 — 벨트는 세계의 것이고 선수의 것이 아니라서
    `career_season.vacate_titles_of` 가 세계 쪽에서 처리한다.

    `held` 를 그대로 복사해 두는 것은 의도다. 공석 처리 뒤에도 "은퇴 당시 챔피언
    이었다" 를 읽을 수 있어야 한다(§3.4 "은퇴 당시 ... 주요 타이틀 기록").
    """
    if wrestler.retired:
        return wrestler
    record = Retirement(
        cause=cause,
        season=season,
        week=week,
        age=wrestler.age,
        wins=wrestler.wins,
        losses=wrestler.losses,
        held=wrestler.held,
        reigns=len(wrestler.reigns),
        titles=tuple(dict.fromkeys(wrestler.reigns)),
        note=note,
    )
    return replace(
        wrestler,
        status=Status.RETIRED,
        retirement=record,
        out_weeks=0,
        # 보유 벨트는 비운다. 기록은 `retirement.held` 에 남았다.
        held=(),
        consecutive_matches=0,
    )
