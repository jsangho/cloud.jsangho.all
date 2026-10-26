"""부상. **결장으로 끝나지 않는다** — 이력이 커리어에 남아 은퇴 위험에 들어간다.

사용자 요구 §3.3. 이전 판본(`career_run`)의 부상은 "결장 N주" 한 칸이었고, 그
독스트링은 등급을 **일부러 안 만든다**고 적었다. 이번에는 등급이 필요하다 —
은퇴 원인 셋(반복 부상·심각한 부상·의학적 불가)이 부상 이력을 읽기 때문이다.

대신 **부상이 은퇴를 결정하지 않는다.** 여기서 하는 일은 부상을 만들고 회복시키는
것뿐이고, 그것이 은퇴로 이어질지는 `career_retirement` 가 따로 평가한다
(§3.3 — "심각한 부상 이벤트가 발생했다고 항상 즉시 은퇴시키지는 않는다").
"""

from __future__ import annotations

from dataclasses import replace

from kayfabe.domain.services.career_rng import pick, roll, span
from kayfabe.domain.services.career_world import (
    Balance,
    Injury,
    Severity,
    Status,
    Wrestler,
)

#: 부상 부위. **재발을 세려면 부위가 필요하다** — "무릎을 또 다쳤다" 가 "어딘가
#: 다쳤다" 보다 무겁다(§3.3 재발 여부).
PARTS = ("무릎", "어깨", "허리", "목", "발목", "손목", "뇌")

#: 부위별 심각도 가중. 목·뇌는 가볍게 끝나지 않는다.
GRAVE_PARTS = ("목", "뇌")

#: 스타일별 주당 부상 확률. `career_run` 의 값을 그대로 가져왔다 —
#: 파워=보통 · 테크니션=안전 · 하이플라이어=자주.
STYLE_RISK = {"파워": 0.07, "테크니션": 0.04, "하이플라이어": 0.09}


def injury_chance(wrestler: Wrestler, balance: Balance) -> float:
    """이번 주 다칠 확률. **컨디션·나이·회복력이 함께 올린다.**

    스타일만 보던 이전 판본과 다른 점이고, 그래야 "지친 노장을 계속 내보내면
    다친다" 가 규칙이 된다 — 그게 §3.2 의 "최근 경기 빈도와 연속 경기 부담" 이다.
    """
    base = STYLE_RISK.get(wrestler.style, 0.05)
    # 컨디션이 낮으면 최대 2배.
    base *= 1.0 + (100 - wrestler.condition) / 100.0
    # 회복력이 낮으면 더 다친다.
    base *= 1.0 + max(0, 60 - wrestler.ability.resilience) / 120.0
    # 노화분.
    if wrestler.age > balance.decline_age:
        base *= 1.0 + (wrestler.age - balance.decline_age) * 0.04
    # 연속 출전 부담.
    base *= 1.0 + min(wrestler.consecutive_matches, 12) * 0.02
    # 이미 다친 이력이 많으면 재발이 잦다.
    base *= 1.0 + min(len(wrestler.injuries), 8) * balance.recurrence_weight / 8.0
    # **상한을 0.28 로 둔다.** 위의 곱이 네 개라 금방 0.4 를 넘는데, 첫 시험 런이
    # 52주 중 **26주를 결장**으로 보냈다(하이플라이어 · 행동 없음 · 컨디션 바닥).
    # 그 런은 커리어가 아니라 대기실이었다.
    return min(0.28, base)


def _severity(seed: int, wrestler: Wrestler, part: str, key: str) -> str:
    """심각도. **부위와 나이가 가른다.**

    목·뇌는 경상으로 끝나지 않게 했다 — 등급이 부위와 무관하면 "목을 경미하게
    다쳤다" 가 나오고, 그러면 §3.3 의 "영구적 활동 불가" 가 아무 부위에서나 나와
    설명이 안 된다.
    """
    r = roll(seed, key, "severity", wrestler.name, part)
    grave = part in GRAVE_PARTS
    # 나이가 많으면 무거운 쪽으로 기운다.
    if wrestler.age >= 36:
        r *= 0.75
    if grave:
        r *= 0.5
    if r < 0.08:
        return Severity.CAREER_THREATENING
    if r < 0.32:
        return Severity.SERIOUS
    return Severity.MINOR


def _weeks_out(
    seed: int, severity: str, wrestler: Wrestler, balance: Balance, key: str
) -> int:
    """결장 주차. **회복력이 낮으면 길어진다**(§3.3 "회복 기간 증가")."""
    index = {
        Severity.MINOR: 0,
        Severity.SERIOUS: 1,
        Severity.CAREER_THREATENING: 2,
    }[severity]
    low, high = balance.out_weeks[index]
    weeks = span(seed, low, high, key, "weeks", wrestler.name)
    if wrestler.ability.resilience < 50:
        weeks = int(weeks * 1.3) + 1
    return max(1, weeks)


def maybe_injure(
    wrestler: Wrestler,
    *,
    seed: int,
    balance: Balance,
    season: int,
    week: int,
    key: str,
    forced: bool = False,
) -> tuple[Wrestler, Injury | None]:
    """한 주의 부상 판정. 안 다치면 `(그대로, None)`.

    `forced` 는 사건이 부상을 직접 지정할 때 쓴다(테스트도 이 문으로 들어온다).
    **능력치를 깎는 것은 심각한 부상뿐**이다 — 경상이 능력치를 깎으면 긴 커리어가
    부상 누적만으로 무너지고, 그건 §2 의 "노화가 일괄 하락을 의미해서는 안 된다"
    와 같은 종류의 고장이다.
    """
    if not forced and roll(seed, key, "injury", wrestler.name) >= injury_chance(
        wrestler, balance
    ):
        return wrestler, None

    part = pick(seed, PARTS, key, "part", wrestler.name) or PARTS[0]
    severity = _severity(seed, wrestler, part, key)
    weeks = _weeks_out(seed, severity, wrestler, balance, key)
    recurrence = any(i.kind == part for i in wrestler.injuries)
    if recurrence:
        # 재발은 더 오래 간다.
        weeks = int(weeks * 1.25) + 1

    # **영구 불가는 좁게 둔다.** 심각도가 최상이고 재발이며 나이까지 많을 때만이다.
    # 셋을 모두 요구하는 것은 의도다 — 한 요소로 커리어가 끝나면 §3.2 의
    # "단일 요소만으로 자동 은퇴가 확정되지 않도록 한다" 가 부상 쪽에서 깨진다.
    permanent = (
        severity == Severity.CAREER_THREATENING
        and recurrence
        and wrestler.age >= balance.decline_age
    )

    injury = Injury(
        kind=part,
        severity=severity,
        season=season,
        week=week,
        weeks_out=weeks,
        recovered=False,
        recurrence=recurrence,
        permanent=permanent,
    )

    ability = wrestler.ability
    if severity != Severity.MINOR:
        drop = 3 if severity == Severity.SERIOUS else 7
        ability = replace(
            ability,
            stamina=ability.stamina - drop,
            resilience=ability.resilience - drop,
        ).clamped()

    hurt = replace(
        wrestler,
        injuries=wrestler.injuries + (injury,),
        out_weeks=weeks,
        status=Status.INJURED,
        ability=ability,
        condition=max(10, wrestler.condition - 15),
        consecutive_matches=0,
    )
    return hurt, injury


def tick_recovery(wrestler: Wrestler) -> tuple[Wrestler, bool]:
    """결장 한 주 소모. 돌아왔으면 `(선수, True)`.

    **영구 불가는 회복하지 않는다** — 결장 주차가 0이 되어도 상태가 `ACTIVE` 로
    돌아가지 않는다. 그 선수는 복귀 선택지 자체가 열리지 않는다(§4).
    """
    if wrestler.out_weeks <= 0:
        return wrestler, False
    left = wrestler.out_weeks - 1
    if left > 0:
        return replace(wrestler, out_weeks=left), False

    healed = tuple(
        replace(i, recovered=True) if not i.recovered and not i.permanent else i
        for i in wrestler.injuries
    )
    if wrestler.permanently_out:
        # 결장은 끝났지만 복귀는 못 한다. 상태를 `INJURED` 로 남겨 대진에서 빠지게
        # 한다 — 은퇴 확정은 `career_retirement` 가 별도로 한다.
        return replace(wrestler, out_weeks=0, injuries=healed), False

    back = replace(
        wrestler,
        out_weeks=0,
        status=Status.ACTIVE if wrestler.status == Status.INJURED else wrestler.status,
        injuries=healed,
        condition=min(100, wrestler.condition + 10),
    )
    return back, True


def rest(wrestler: Wrestler, *, weeks: int = 1) -> Wrestler:
    """쉰다. **경미한 부상은 휴식으로 해결된다**(§3.3).

    컨디션이 오르고 회복력이 조금 돌아온다. `career_run` 이 `휴식` 을 선택지에서
    뺀 이유는 "득이 없는 함정" 이었기 때문인데, 이번에는 컨디션·부상·은퇴 위험이
    생겨서 **쉬는 것에 값이 있다**. 그래서 선택지로 돌아왔다.
    """
    ability = replace(
        wrestler.ability, resilience=wrestler.ability.resilience + weeks
    ).clamped()
    return replace(
        wrestler,
        condition=min(100, wrestler.condition + 18 * weeks),
        ability=ability,
        consecutive_matches=0,
    )


def active_injury(wrestler: Wrestler) -> Injury | None:
    """지금 앓고 있는 부상. 없으면 `None`."""
    for injury in reversed(wrestler.injuries):
        if not injury.recovered:
            return injury
    return None
