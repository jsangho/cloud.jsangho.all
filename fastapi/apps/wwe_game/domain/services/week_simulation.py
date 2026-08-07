"""자동 진행 한 주차 (하네스 §3-D2·D4).

순수 함수 두 개로 갈라 놓았다.

- `simulate_week(run)` — 무슨 일이 일어났는지 **계산만** 한다
- `apply_week(run, report)` — 그 결과를 세이브에 **반영만** 한다

가르는 이유: 리포트를 반영하지 않고 들여다볼 수 있어야 테스트가 쉽고, 저장은 진행
단위로 한 번뿐이라(§3-D6) 중간 상태를 만들 필요가 없다.

난수는 `run.seed`와 `run.week`에서 파생한다 — 인자로 받지 않는다. 받으면 호출자가
다른 난수를 넣어 재현을 깨뜨릴 수 있다.
"""

from __future__ import annotations

from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.constants.career_flags import (
    GROUNDED,
    GRUDGE,
    MANAGER,
    PAINKILLER,
    PUSH_FROZEN,
)
from wwe_game.domain.constants.ple_calendar import PleShow, calendar_for
from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.services import (
    championship,
    event_draw,
    rivalry_engine,
    seeded_roll,
)
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.condition import Condition, InjuryGrade
from wwe_game.domain.value_objects.title import TITLES, Brand, Title
from wwe_game.domain.value_objects.week_report import (
    CallUpReason,
    OutcomeKind,
    WeekKind,
    WeekReport,
)
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

# ── 나이 곡선 — 인기도가 상쇄한다 ────────────────────────────


def raw_age_penalty(age: int) -> float:
    """인기도를 고려하기 전의 나이 감점. 0.0~`AGE_PENALTY_CAP`."""
    if age <= rules.AGE_PRIME_END:
        return 0.0
    decline_years = min(age, rules.AGE_DECLINE_END) - rules.AGE_PRIME_END
    penalty = decline_years * rules.DECLINE_PENALTY_PER_YEAR
    if age > rules.AGE_DECLINE_END:
        penalty += (age - rules.AGE_DECLINE_END) * rules.VETERAN_PENALTY_PER_YEAR
    return min(penalty, rules.AGE_PENALTY_CAP)


def age_penalty(age: int, popularity: int) -> float:
    """인기도가 지우고 남은 실효 감점.

    `실효 = 원감점 × (1 − 인기도/100 × 0.80)`. 인기도가 높을수록 나이를 덜 탄다 —
    이 게임에서 나이보다 인기도가 우선한다는 결정의 핵심 구현이다.
    """
    offset = 1.0 - (popularity / 100) * rules.AGE_PENALTY_POPULARITY_OFFSET
    return raw_age_penalty(age) * offset


def performance_score(stats: WrestlerStats, condition: Condition, age: int) -> float:
    """0~100 종합점수. 인기도 가중치가 가장 크다."""
    raw = (
        stats.popularity * rules.WEIGHT_POPULARITY
        + stats.in_ring * rules.WEIGHT_IN_RING
        + stats.mic_work * rules.WEIGHT_MIC_WORK
    )
    if age > rules.AGE_DECLINE_END:
        raw += rules.VETERAN_MIC_BONUS * (stats.mic_work / 100)
    raw *= 1.0 - age_penalty(age, stats.popularity)
    raw *= 1.0 - rules.INJURY_MATCH_PENALTY[condition.grade]
    return max(0.0, min(100.0, raw))


def win_chance(score: float) -> float:
    chance = rules.WIN_CHANCE_BASE + rules.WIN_CHANCE_SPAN * (score / 100)
    return max(rules.WIN_CHANCE_FLOOR, min(rules.WIN_CHANCE_CEILING, chance))


# ── 주차 종류 ────────────────────────────────────────────────


def week_kind_of(run: CareerRun) -> WeekKind:
    """부상 중이면 결장, 13주마다 대형 대회, 나머지 주간 TV는 경기 또는 빌드업.

    **PLE에는 반드시 경기가 있다**(스펙). 주간 TV는 `WEEKLY_MATCH_CHANCE`로 갈리며,
    경기가 없는 주차는 `PROMO` — 대립을 쌓는 데 한 주를 쓴다.
    """
    if run.condition.is_injured:
        return WeekKind.OFF
    upcoming = run.week + 1
    calendar = calendar_for(run.brand)
    if calendar.is_show_week(upcoming):
        # 특별 방송은 대회가 아니다 — 경기는 보장되지만 위상이 한 단계 아래다 (§3-D21-2).
        return (
            WeekKind.SPECIAL if calendar.show_for(upcoming).is_special else WeekKind.PLE
        )
    roll = SeededRoll(run.seed, upcoming, seeded_roll.CARD)
    return (
        WeekKind.WEEKLY_SHOW
        if roll.chance(rules.WEEKLY_MATCH_CHANCE)
        else WeekKind.PROMO
    )


def is_ple_stop_week(run: CareerRun) -> bool:
    """PLE에서 진행을 끊을지. **대형 대회에서만** 끊는다 (§3-D17 · §3-D21-1).

    대회가 연 4회에서 13회로 늘었으므로 전부 끊으면 클릭이 세 배가 된다. 멈춤은
    "보고 싶은 것"일 때만 의미가 있고, 그 기준이 곧 급이다.
    """
    if run.mode.weeks_per_tick > rules.PLE_STOP_MAX_TICK_WEEKS:
        return False
    upcoming = run.week + 1
    calendar = calendar_for(run.brand)
    if week_kind_of(run) is not WeekKind.PLE:
        return False
    return calendar.show_for(upcoming).is_major


# ── 부상 ─────────────────────────────────────────────────────


def injury_chance(run: CareerRun, kind: WeekKind, *, major: bool = False) -> float:
    if kind is WeekKind.OFF:
        return 0.0
    chance = rules.INJURY_BASE_CHANCE
    chance *= 1.0 + (run.condition.wear / 100) * rules.INJURY_WEAR_FACTOR
    chance *= rules.INJURY_STYLE_MULTIPLIER[run.identity.play_style]
    if PAINKILLER in run.flags:
        chance *= rules.PAINKILLER_INJURY_MULTIPLIER
    if GROUNDED in run.flags:
        chance *= rules.GROUNDED_INJURY_MULTIPLIER
    if kind is WeekKind.PLE:
        chance *= rules.INJURY_PLE_MULTIPLIER
        if major:
            chance *= rules.MAJOR_INJURY_MULTIPLIER
    return min(1.0, chance)


def _draw_injury_grade(roll: SeededRoll) -> tuple[InjuryGrade, int]:
    total = sum(w for _, w, _, _ in rules.INJURY_GRADE_WEIGHTS)
    pick = roll.between(1, total)
    cursor = 0
    for grade, weight, low, high in rules.INJURY_GRADE_WEIGHTS:
        cursor += weight
        if pick <= cursor:
            weeks = 0 if high == 0 else roll.between(low, high)
            return grade, weeks
    raise AssertionError("가중치 합이 어긋났습니다")  # pragma: no cover


# ── 시뮬레이션 ───────────────────────────────────────────────


def simulate_week(run: CareerRun) -> WeekReport:
    """한 주차를 굴린다. 세이브는 건드리지 않는다."""
    week = run.week + 1
    kind = week_kind_of(run)

    draft_night = week % championship.DRAFT_INTERVAL_WEEKS == 0
    """**모든 경로에서 채운다.** 예전에는 매치 주차에서만 세웠는데, 드래프트 주기(52주)가
    PLE 주기(13주)의 배수라 늘 매치 주차와 겹쳐서 드러나지 않았다. 달력이 달 단위가 되며
    (§3-D21-1) 겹침이 깨지자 **드래프트가 프로모·결장 주차에 열리면 그냥 사라졌다.**"""

    if kind is WeekKind.OFF:
        # 쉬는 동안에도 인기는 식는다 — 오히려 더 빨리 (§career_rules 망각 배수).
        return WeekReport(
            week=week,
            kind=kind,
            stat_delta=_decay_only(run, week),
            wear_delta=-rules.WEAR_RECOVERY_PER_OFF_WEEK,
            draft_night=draft_night,
        )

    if kind is WeekKind.PROMO:
        # 경기 없는 주차. 마이크로 벌고 몸은 쉰다 — 마모도 부상도 없다.
        promo_delta = _promo_gain(run, week)
        return WeekReport(
            week=week,
            kind=kind,
            stat_delta=promo_delta,
            call_up=_call_up_of(run, promo_delta),
            draft_night=draft_night,
        )

    show = calendar_for(run.brand).show_for(week) if kind is WeekKind.PLE else None
    match_roll = SeededRoll(run.seed, week, seeded_roll.MATCH)
    score = performance_score(run.stats, run.condition, run.age)

    # 대형 대회에서만 타이틀전이 잡힌다. 잡히면 그날의 경기가 곧 타이틀전이다.
    title = _draw_title_match(run, week, kind, show)
    if title is not None:
        if match_roll.chance(championship.title_win_chance(score, title)):
            result = OutcomeKind.WIN
        else:
            result = OutcomeKind.LOSS
    elif match_roll.chance(rules.DRAW_CHANCE):
        result = OutcomeKind.DRAW
    elif match_roll.chance(win_chance(score)):
        result = OutcomeKind.WIN
    else:
        result = OutcomeKind.LOSS

    stat_delta = _growth(run, week, result)
    if title is not None:
        # 벨트가 오가면 성장 굴림보다 훨씬 큰 폭으로 움직인다. 덮어쓰지 않고 더한다.
        held = title in run.titles_held
        if result is not OutcomeKind.WIN:
            swing = championship.loss_of(title) if held else {}
        elif held:
            swing = championship.DEFENSE_REWARD  # 방어 성공 — 새 대관이 아니다
        else:
            swing = championship.reward_of(
                title, first_time=title not in run.titles_won
            )
        for key, value in swing.items():
            stat_delta[key] = stat_delta.get(key, 0) + value
    wear_delta = _wear_gain(run, week, kind)

    injury: InjuryGrade | None = None
    injury_weeks = 0
    injury_roll = SeededRoll(run.seed, week, seeded_roll.INJURY)
    if injury_roll.chance(
        injury_chance(run, kind, major=show is not None and show.is_major)
    ):
        injury, injury_weeks = _draw_injury_grade(injury_roll)
        # 몸이 약하다는 평판은 실력과 별개로 쌓인다.
        stat_delta["backstage"] = (
            stat_delta.get("backstage", 0) + rules.BACKSTAGE_INJURY_PENALTY
        )

    return WeekReport(
        week=week,
        kind=kind,
        result=result,
        stat_delta=stat_delta,
        wear_delta=wear_delta,
        injury=injury,
        injury_weeks=injury_weeks,
        show=show,
        title_at_stake=title,
        title_defended=title is not None and title in run.titles_held,
        call_up=_call_up_of(run, stat_delta),
        draft_night=draft_night,
    )


def _call_up_of(run: CareerRun, stat_delta: dict[str, int]) -> CallUpReason | None:
    """이번 주차에 콜업되는지, 된다면 어느 경로로.

    **깜짝 콜업이 먼저다.** 대타 자리를 수락해 둔 선수는 문턱과 무관하게 올라간다.
    결장 주차는 여기까지 오지 않는다 — 부상자는 대타로도 못 나가고, 플래그는 남으므로
    복귀하는 주에 올라간다.
    """
    if run.brand is not Brand.NXT:
        return None
    if championship.EMERGENCY_CALLUP_FLAG in run.flags:
        return CallUpReason.EMERGENCY
    projected = run.evolve(stats=run.stats.apply(stat_delta))
    return CallUpReason.EARNED if championship.should_call_up(projected) else None


def _draw_title_match(
    run: CareerRun, week: int, kind: WeekKind, show: PleShow | None
) -> Title | None:
    """타이틀전이 잡히는지.

    주무대는 PLE고, 주간 TV에서도 **가끔** 열린다(스펙). 대형 대회는 확률이 두 배다.
    """
    if kind not in (WeekKind.PLE, WeekKind.SPECIAL, WeekKind.WEEKLY_SHOW):
        return None
    roll = SeededRoll(run.seed, week, seeded_roll.TITLE)
    chance = championship.title_shot_chance(
        run.stats.popularity,
        on_tv=kind is WeekKind.WEEKLY_SHOW,
        major=show is not None and show.is_major,
        special=kind is WeekKind.SPECIAL,
    )
    if not roll.chance(chance):
        return None
    return championship.target_title(run, roll)


def _promo_gain(run: CareerRun, week: int) -> dict[str, int]:
    """빌드업 주차의 소득 — 마이크웍과 약간의 인기도. 망각도 함께 굴린다."""
    roll = SeededRoll(run.seed, week, seeded_roll.GROWTH)
    delta: dict[str, int] = {}
    headroom = _headroom(run.stats.mic_work)
    if roll.chance(min(1.0, rules.PROMO_MIC_GAIN_CHANCE * headroom)):
        delta["mic_work"] = 1
    if roll.chance(
        popularity_decay_chance(
            run.stats.popularity, off_week=False, held=run.titles_held
        )
    ):
        delta["popularity"] = -1
    return delta


def popularity_decay_chance(
    popularity: int, *, off_week: bool, held: frozenset[Title] = frozenset()
) -> float:
    """인기도에 비례하는 망각 확률. 높이 오를수록 유지 비용이 크다.

    벨트를 들고 있으면 느려진다 — 가장 높은 계층 하나만 적용한다(§career_rules).
    """
    chance = rules.POPULARITY_DECAY_CHANCE * (popularity / 100)
    if off_week:
        chance *= rules.POPULARITY_DECAY_OFF_MULTIPLIER
    if held:
        relief = min(rules.CHAMPION_DECAY_RELIEF[TITLES[t].tier.value] for t in held)
        chance *= relief
    return min(1.0, chance)


def _decay_only(run: CareerRun, week: int) -> dict[str, int]:
    """결장 주차의 스탯 변화 — 망각과 **신뢰 하락**.

    쓸 수 없는 선수는 관중에게 잊히고 단체에는 짐이 된다. 부상 잦은 커리어가
    방출로 이어지는 경로가 여기서 열린다(§3-D24).
    """
    roll = SeededRoll(run.seed, week, seeded_roll.GROWTH)
    delta: dict[str, int] = {}
    chance = popularity_decay_chance(
        run.stats.popularity, off_week=True, held=run.titles_held
    )
    if roll.chance(chance):
        delta["popularity"] = -1
    if roll.chance(rules.BACKSTAGE_OFF_DROP_CHANCE):
        delta["backstage"] = -1
    return delta


def _wear_gain(run: CareerRun, week: int, kind: WeekKind) -> int:
    """마모는 확률로 쌓인다 (`WEAR_GAIN_CHANCE_*`). 스타일이 배수로 곱해진다."""
    base = {
        WeekKind.PLE: rules.WEAR_GAIN_CHANCE_PLE,
        WeekKind.SPECIAL: rules.SPECIAL_WEAR_CHANCE,
    }.get(kind, rules.WEAR_GAIN_CHANCE_SHOW)
    chance = base * rules.INJURY_STYLE_MULTIPLIER[run.identity.play_style]
    roll = SeededRoll(run.seed, week, seeded_roll.WEAR)
    return 1 if roll.chance(min(1.0, chance)) else 0


def alignment_clarity(alignment: int) -> float:
    """성향이 뚜렷할수록 인기도가 빨리 오른다. 부호가 아니라 **절댓값**을 본다."""
    return 1.0 + (abs(alignment) / 100) * rules.ALIGNMENT_CLARITY_BONUS


def _headroom(current: int) -> float:
    """남은 여지에서 나오는 성장 계수. 지수가 1보다 작아 상단에서도 성장이 살아 있다."""
    return max(0.0, (100 - current) / 100) ** rules.GAIN_HEADROOM_EXPONENT


def _growth(run: CareerRun, week: int, result: OutcomeKind) -> dict[str, int]:
    """스탯 상승은 체감한다 — 남은 여지에 비례해 확률이 준다 (`GAIN_DIMINISH`)."""
    roll = SeededRoll(run.seed, week, seeded_roll.GROWTH)
    delta: dict[str, int] = {}
    multiplier = (
        rules.GROWTH_GAIN_MULTIPLIER if run.age <= rules.AGE_GROWTH_END else 1.0
    )

    for stat in ("in_ring", "mic_work"):
        current = getattr(run.stats, stat)
        chance = rules.GAIN_BASE_CHANCE * _headroom(current) * multiplier
        if stat == "mic_work" and MANAGER in run.flags:
            chance *= rules.MANAGER_MIC_BONUS
        if roll.chance(min(1.0, chance)):
            delta[stat] = 1

    # 패배도 인기도를 올린다. 승리에만 붙이면 승률이 낮은 초반에 기대값이 음수가 된다.
    # 상승은 남은 여지에, 망각은 현재 인기도에 비례해 서로 균형점을 만든다.
    headroom = _headroom(run.stats.popularity)
    gain = (
        rules.POPULARITY_GAIN_CHANCE[result.value]
        * headroom
        * multiplier
        * alignment_clarity(run.stats.alignment)
    )
    if run.brand is Brand.NXT:
        gain *= rules.NXT_POPULARITY_GAIN_MULTIPLIER
    if PUSH_FROZEN in run.flags:
        gain *= rules.PUSH_FROZEN_GAIN_FACTOR
    if roll.chance(min(1.0, gain)):
        delta["popularity"] = 1
    elif roll.chance(
        popularity_decay_chance(
            run.stats.popularity, off_week=False, held=run.titles_held
        )
    ):
        delta["popularity"] = -1
    elif result is OutcomeKind.LOSS and roll.chance(rules.POPULARITY_DROP_CHANCE):
        delta["popularity"] = -1

    backstage_chance = rules.BACKSTAGE_GAIN_CHANCE
    if GRUDGE in run.flags:
        backstage_chance *= rules.GRUDGE_BACKSTAGE_FACTOR
    if roll.chance(backstage_chance):
        delta["backstage"] = delta.get("backstage", 0) + 1

    return delta


def apply_week(run: CareerRun, report: WeekReport) -> CareerRun:
    """리포트를 세이브에 반영한다. 종료 판정은 하지 않는다 — `career_end`의 몫이다."""
    if report.week != run.week + 1:
        raise ValueError(f"리포트 주차가 어긋납니다: {report.week} != {run.week + 1}")

    condition = run.condition.recover(1).with_wear(report.wear_delta)
    if report.injury is not None:
        condition = condition.injured(report.injury, report.injury_weeks)

    moved = run
    if report.title_at_stake is not None:
        if report.result is OutcomeKind.WIN:
            moved = championship.award(run, report.title_at_stake)
        elif report.title_defended:
            moved = championship.strip(run, report.title_at_stake)

    heat_gain = {
        WeekKind.PLE: rivalry_engine.HEAT_PER_PLE,
        WeekKind.SPECIAL: rivalry_engine.HEAT_PER_MATCH,
        WeekKind.WEEKLY_SHOW: rivalry_engine.HEAT_PER_MATCH,
        WeekKind.PROMO: rivalry_engine.HEAT_PER_PROMO,
        WeekKind.OFF: -rivalry_engine.COOL_PER_QUIET_WEEK,
    }[report.kind]
    moved = moved.evolve(
        week=report.week,
        stats=moved.stats.apply(report.stat_delta),
        condition=condition,
        rivalries=rivalry_engine.advance_rivalries(
            moved,
            report.week,
            heat_gain,
            SeededRoll(run.seed, report.week, seeded_roll.RIVALRY),
            blowoff=report.kind is WeekKind.PLE,
        ),
    )

    # 이벤트는 대립·스탯이 갱신된 뒤에 뽑는다 — 조건이 이번 주 상태를 봐야 한다.
    if moved.is_active and not moved.is_blocked:
        drawn = event_draw.draw_event(moved)
        if drawn is not None:
            moved = moved.evolve(pending_event=drawn)

    # 브랜드 이동은 스탯 반영 뒤에 판정한다 — 콜업 임계값이 이번 주 인기도를 봐야 한다.
    if report.call_up is not None:
        moved = championship.call_up(
            moved,
            SeededRoll(run.seed, report.week, seeded_roll.BRAND),
            report.call_up,
        )
    elif report.draft_night:
        moved = championship.draft(
            moved, SeededRoll(run.seed, report.week, seeded_roll.BRAND)
        )
    return moved
