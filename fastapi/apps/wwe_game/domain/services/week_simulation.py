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
from wwe_game.domain.constants import roster
from wwe_game.domain.constants.career_clock import WEEKS_PER_YEAR
from wwe_game.domain.constants.career_flags import (
    CASH_IN_PENDING,
    CURSED,
    GROUNDED,
    GRUDGE,
    MANAGER,
    PAINKILLER,
    PUSH_FROZEN,
    TEAM_PENDING,
)
from wwe_game.domain.constants.play_styles import INJURY_STYLE_MULTIPLIER
from wwe_game.domain.constants.ple_calendar import (
    KING_AND_QUEEN,
    MITB,
    WRESTLEMANIA,
    PleShow,
    calendar_for,
)
from wwe_game.domain.entities.career_run import CareerRun, Trophy
from wwe_game.domain.services import (
    championship,
    elimination,
    event_draw,
    rivalry_engine,
    seeded_roll,
    team_engine,
    title_scene,
)
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.condition import Condition, InjuryGrade
from wwe_game.domain.value_objects.match_kind import (
    QUALIFIER_KINDS,
    SIGNATURE_MATCHES,
    STIPULATION_CHANCE,
    STIPULATION_PLE_MULTIPLIER,
    MatchKind,
    stipulation_odds,
)
from wwe_game.domain.value_objects.match_kind import format_of as match_format_of
from wwe_game.domain.value_objects.match_sequence import MatchSequence
from wwe_game.domain.value_objects.title import TITLES, Brand, Title, TitleTier
from wwe_game.domain.value_objects.week_report import (
    CallUpReason,
    OutcomeKind,
    TitleShotSource,
    WeekKind,
    WeekReport,
)
from wwe_game.domain.value_objects.wrestler_identity import Gender
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
    if tournament_round_at(run, upcoming) > 0:
        # **예선 주차에는 반드시 경기가 있다** (§3-D33). 프로모로 넘어가면 대진표가
        # 그 주에 멈추고, 결승 주차가 와도 올라간 사람이 없다.
        return WeekKind.WEEKLY_SHOW
    roll = SeededRoll(run.seed, upcoming, seeded_roll.CARD)
    return (
        WeekKind.WEEKLY_SHOW
        if roll.chance(rules.WEEKLY_MATCH_CHANCE)
        else WeekKind.PROMO
    )


def tournament_round_at(run: CareerRun, week: int) -> int:
    """그 주차가 킹 앤 퀸 오브 더 링의 몇 회전인지. 0이면 토너먼트 주차가 아니다.

    **결승은 대회 밤이고 예선은 그 앞 두 주다** (§3-D33) — 한 주에 안 끝나는 유일한
    형식이라, 어느 주차가 몇 회전인지를 달력에서 되짚는다. 상태(`tournament_round`)는
    "이겨서 올라왔는가"만 들고 있고 일정은 여기가 안다.

    **NXT에는 이 대회가 없다.** 육성 브랜드 달력에 없는 이름이라 자동으로 0이 된다.
    """
    calendar = calendar_for(run.brand)
    final = next(
        (s.week_of_year for s in calendar.shows if s.name == KING_AND_QUEEN), None
    )
    if final is None:
        return 0
    offset = final - (week - 1) % WEEKS_PER_YEAR - 1
    if not 0 <= offset < rules.TOURNAMENT_ROUNDS:
        return 0
    return rules.TOURNAMENT_ROUNDS - offset


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
    chance *= INJURY_STYLE_MULTIPLIER[run.identity.play_style]
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
        promo_delta, promo_hit = _promo_gain(run, week)
        return WeekReport(
            week=week,
            kind=kind,
            stat_delta=promo_delta,
            call_up=_call_up_of(run, promo_delta),
            draft_night=draft_night,
            promo_hit=promo_hit,
        )

    show = calendar_for(run.brand).show_for(week) if kind is WeekKind.PLE else None
    match_roll = SeededRoll(run.seed, week, seeded_roll.MATCH)
    score = performance_score(run.stats, run.condition, run.age)

    # 대형 대회에서만 타이틀전이 잡힌다. 잡히면 그날의 경기가 곧 타이틀전이다.
    title, shot_from = _draw_title_match(run, week, kind, show)
    match_kind = _match_kind_of(run, week, kind, show, title, shot_from)
    fmt = match_format_of(match_kind)
    # 저주는 **굴림보다 먼저다.** 확률로 옮기면 가끔 이기게 되고 그건 저주가 아니다.
    cursed = CURSED in run.flags
    if cursed:
        result = OutcomeKind.LOSS
    elif title is not None:
        chance = (
            championship.cash_in_win_chance(score, title)
            if shot_from is TitleShotSource.BRIEFCASE
            else championship.title_win_chance(score, title)
        )
        if match_roll.chance(chance * fmt.win_factor):
            result = OutcomeKind.WIN
        else:
            result = OutcomeKind.LOSS
    elif match_kind not in elimination.STAGED and match_roll.chance(rules.DRAW_CHANCE):
        # **단계가 있는 경기에는 무승부가 없다** (§3-D34). 서른이 붙어 아무도 못 이기는
        # 럼블은 없고, 화면에 "무 · 17번째 탈락"이 함께 뜨면 둘 중 하나가 거짓말이 된다.
        result = OutcomeKind.DRAW
    elif match_roll.chance(win_chance(score) * fmt.win_factor):
        result = OutcomeKind.WIN
    else:
        result = OutcomeKind.LOSS

    stat_delta = _growth(run, week, result)
    if (
        _tournament_round_of(run, week) == rules.TOURNAMENT_ROUNDS
        and result is OutcomeKind.WIN
    ):
        # 왕관의 값 (§3-D33). 벨트처럼 덮어쓰지 않고 더한다 — 그날의 승리분은 이미 위에서 났다.
        stat_delta["popularity"] = (
            stat_delta.get("popularity", 0) + rules.TOURNAMENT_WIN_POPULARITY
        )
        stat_delta["in_ring"] = (
            stat_delta.get("in_ring", 0) + rules.TOURNAMENT_WIN_IN_RING
        )
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
    wear_delta = _wear_gain(run, week, kind, fmt.wear_factor)

    injury: InjuryGrade | None = None
    injury_weeks = 0
    injury_roll = SeededRoll(run.seed, week, seeded_roll.INJURY)
    if injury_roll.chance(
        injury_chance(run, kind, major=show is not None and show.is_major)
        * fmt.injury_factor
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
        title_shot_from=shot_from,
        tournament_round=_tournament_round_of(run, week),
        call_up=_call_up_of(run, stat_delta),
        draft_night=draft_night,
        match_kind=match_kind,
        opponent=_opponent_for(run, week, title),
        # **판정이 끝난 뒤에 짠다** — 순서는 결과를 만들지 않고 결과를 설명한다 (§3-D34).
        sequence=_sequence_for(run, week, match_kind, result),
        cursed=cursed,
        vacated=_vacated_by(run, injury_weeks),
    )


def _sequence_for(
    run: CareerRun, week: int, match_kind: MatchKind, result: OutcomeKind
) -> MatchSequence | None:
    """럼블·챔버처럼 단계가 있는 경기의 진행 순서 (§3-D34).

    **출전 후보는 등급을 가리지 않는다.** 대립 상대는 급이 맞아야 하지만(§3-D13),
    럼블은 정상급과 유망주가 한 링에 서는 자리다 — 급으로 거르면 30명이 안 찬다.
    """
    if match_kind not in elimination.STAGED:
        return None
    pool = tuple(
        m.name
        for m in roster.active_at(week)
        if m.gender is run.identity.gender and m.name != str(run.identity.name)
    )
    return elimination.sequence_for(
        match_kind,
        player=str(run.identity.name),
        won=result is OutcomeKind.WIN,
        pool=pool,
        roll=SeededRoll(run.seed, week, seeded_roll.ELIMINATION),
    )


def _vacated_by(run: CareerRun, injury_weeks: int) -> tuple[Title, ...]:
    """이번 부상으로 비우는 벨트 (§3-D40).

    **판정은 여기서 하고 반영은 `apply_week`이 한다** — 다른 규칙과 같은 결이다.
    """
    if injury_weeks < rules.VACATE_AFTER_WEEKS:
        return ()
    return tuple(sorted(run.titles_held, key=lambda t: t.value))


def _tournament_after(run: CareerRun, report: WeekReport) -> tuple[int, Trophy | None]:
    """토너먼트 라운드를 갱신하고, 왕관을 썼으면 트로피를 함께 돌려준다 (§3-D33).

    **대회가 지나가면 0으로 돌아간다.** 이기든 지든, 심지어 그 주에 다쳐 결장했더라도 —
    해마다 새 대진표가 열리고 작년의 진출은 남지 않는다.
    """
    scheduled = tournament_round_at(run, report.week)
    if scheduled == rules.TOURNAMENT_ROUNDS:
        won = report.tournament_round == scheduled and report.result is OutcomeKind.WIN
        crown = Trophy(code=_crown_code(run), week=report.week) if won else None
        return 0, crown
    if report.tournament_round == 0:
        return run.tournament_round if scheduled == 0 else 0, None
    if report.result is OutcomeKind.WIN:
        return report.tournament_round, None
    return 0, None  # 졌다 — 대진표에서 빠진다


def _crown_code(run: CareerRun) -> str:
    """왕관은 디비전마다 이름이 다르다 — 킹과 퀸이다."""
    return (
        "king_of_the_ring"
        if run.identity.gender is Gender.MALE
        else "queen_of_the_ring"
    )


def _tournament_round_of(run: CareerRun, week: int) -> int:
    """이 주차가 플레이어에게 몇 회전인지. **떨어졌으면 0이다.**

    일정상 토너먼트 주차라도, 앞 라운드에서 진 선수에게는 그냥 평범한 밤이다.
    """
    scheduled = tournament_round_at(run, week)
    if scheduled == 0 or run.brand is Brand.NXT:
        return 0
    if run.tournament_round != scheduled - 1:
        return 0  # 앞 라운드를 못 이겼다 — 대진표에서 빠졌다
    return scheduled


def _opponent_for(run: CareerRun, week: int, title: Title | None) -> str | None:
    """그 주차에 붙는 상대.

    **벨트에 도전하는 밤은 상대가 정해져 있다 — 챔피언이다** (§3-D38). 도전인데
    상대가 대립 목록에서 뽑히면 "누구의 벨트인지"가 사라지고, 벨트가 허공에서 온다.

    방어전은 반대다: 내가 챔피언이니 **도전자가 온다.** 그 자리는 대립 상대가 맞다 —
    몇 주째 쌓아 온 이야기가 벨트를 걸 이유가 된다.
    """
    if title is not None and title not in run.titles_held:
        champion = title_scene.champion_at(
            run.seed, week, title, exclude=str(run.identity.name)
        )
        if champion is not None:
            return champion
    return rivalry_engine.pick_opponent(
        run, SeededRoll(run.seed, week, seeded_roll.OPPONENT)
    )


def _is_show(brand: Brand, week: int, name: str) -> bool:
    """그 주차가 이 브랜드의 `name` 대회 주차인지. NXT 달력에는 없는 이름이면 늘 거짓."""
    calendar = calendar_for(brand)
    return calendar.is_show_week(week) and calendar.show_for(week).name == name


def _spoils(
    run: CareerRun, report: WeekReport, flags: frozenset[str]
) -> tuple[bool, int, frozenset[str]]:
    """그 밤이 남긴 권리 — 도전권과 가방 (§3-D36).

    **얻는 것과 쓰는 것을 한자리에서 본다.** 나눠 두면 "우승했는데 도전권이 안 생긴"
    경우와 "썼는데 가방이 남은" 경우가 서로 다른 파일에서 생긴다.

    도전권은 **레슬매니아가 지나가면 사라진다** — 이기든 지든, 심지어 그날 다쳐서
    결장했더라도. 쓰지 못한 도전권을 다음 해로 넘기면 도전권이 아니라 적립금이 된다.
    """
    title_shot, briefcase_week = run.title_shot, run.briefcase_week
    won = report.result is OutcomeKind.WIN

    if won and report.match_kind in (MatchKind.BATTLE_ROYAL, MatchKind.CHAMBER):
        title_shot = True
    if (
        won
        and report.match_kind is MatchKind.LADDER
        and report.show is not None
        and report.show.name == MITB
    ):
        # 래더는 다른 밤에도 걸린다(§3-D32). **가방은 그 대회의 것이다.**
        # 이미 들고 있었다면 시계가 새로 간다 — 새 계약이다.
        briefcase_week = report.week

    if _is_show(run.brand, report.week, WRESTLEMANIA):
        # **달력으로 지운다, 리포트로 지우지 않는다.** 그 주에 부상으로 결장하면
        # `report.show`가 비어 도전권이 이듬해로 넘어간다 — 그 해 레슬매니아에서
        # 쓰는 것이 도전권이고(2026-08-11 사용자 확인), 못 쓴 것은 사라진다.
        title_shot = False
    if report.title_shot_from is not TitleShotSource.BRIEFCASE:
        # **신호는 쓰일 때까지 남는다.** 매주 지우면 "지금 쓴다"를 고른 다음 주에
        # 부상으로 결장했을 때 가방만 남고 결정이 사라진다.
        return title_shot, briefcase_week, flags
    return title_shot, 0, flags - {CASH_IN_PENDING}


def _match_kind_of(
    run: CareerRun,
    week: int,
    kind: WeekKind,
    show: PleShow | None,
    title: Title | None,
    shot_from: TitleShotSource | None = None,
) -> MatchKind:
    """그 주차 경기의 형식 (§3-D32).

    **가방을 쓴 밤은 무조건 싱글이다** (§3-D36). 현금화는 지친 챔피언과 둘이 붙는
    3분짜리이지, 서른이 들어오는 럼블이 아니다 — 그날 럼블이 예정돼 있었더라도.

    그다음은 **대회의 시그니처**다 — 로열럼블 주차에는 럼블이 열린다. 그다음이
    태그팀(팀이 있고 태그 벨트가 걸렸으면), 나머지는 싱글이다.
    """
    if shot_from is TitleShotSource.BRIEFCASE:
        return MatchKind.SINGLES
    if tournament_round_at(run, week) > 0:
        # 예선에 쓸 수 있는 형식은 셋뿐이다 (§3-D33 · 2026-08-10 사용자 스펙) —
        # 대진표가 도는 밤에 30인 럼블이 열릴 수는 없다.
        return SeededRoll(run.seed, week, seeded_roll.STIPULATION).pick(QUALIFIER_KINDS)
    if show is not None and show.name in SIGNATURE_MATCHES:
        return SIGNATURE_MATCHES[show.name]
    if title is not None and TITLES[title].tier is TitleTier.TAG:
        return MatchKind.TAG
    return _stipulation_of(run, week, kind)


def _stipulation_of(run: CareerRun, week: int, kind: WeekKind) -> MatchKind:
    """평범한 경기가 가끔 특수 경기가 된다 (2026-08-10 사용자 요청).

    **시그니처와 다른 자리다.** 시그니처는 달력이 반드시 실행하고, 이쪽은 굴림이다 —
    래더나 케이지는 MITB가 아닌 밤에도 걸린다.
    """
    chance = STIPULATION_CHANCE
    if kind in (WeekKind.PLE, WeekKind.SPECIAL):
        chance *= STIPULATION_PLE_MULTIPLIER
    roll = SeededRoll(run.seed, week, seeded_roll.STIPULATION)
    if not roll.chance(chance):
        return MatchKind.SINGLES
    odds = stipulation_odds(run.identity.play_style.value)
    total = sum(weight for _, weight in odds)
    ticket = roll.between(1, total)
    for stipulation, weight in odds:
        ticket -= weight
        if ticket <= 0:
            return stipulation
    return MatchKind.SINGLES


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
) -> tuple[Title | None, TitleShotSource | None]:
    """타이틀전이 잡히는지, 그리고 **자격으로 잡혔는지 권리로 잡혔는지** (§3-D36).

    주무대는 PLE고, 주간 TV에서도 **가끔** 열린다(스펙). 대형 대회는 확률이 두 배다.

    **권리가 굴림보다 먼저다.** 럼블을 이겨서 얻은 레슬매니아 도전권과 가방은 인기도
    관문도 추첨도 건너뛴다 — 확률로 두면 "우승했는데 도전은 못 하는" 밤이 생기고,
    그러면 럼블을 이길 이유가 사라진다.
    """
    if run.briefcase and (
        CASH_IN_PENDING in run.flags
        or week - run.briefcase_week >= rules.BRIEFCASE_WEEKS
    ):
        cashed = championship.world_title_of(run)
        if cashed is not None and cashed not in run.titles_held:
            return cashed, TitleShotSource.BRIEFCASE
    if run.title_shot and show is not None and show.name == WRESTLEMANIA:
        earned = championship.world_title_of(run)
        if earned is not None:
            return earned, TitleShotSource.EARNED
    if kind not in (WeekKind.PLE, WeekKind.SPECIAL, WeekKind.WEEKLY_SHOW):
        return None, None
    roll = SeededRoll(run.seed, week, seeded_roll.TITLE)
    chance = championship.title_shot_chance(
        run.stats.popularity,
        on_tv=kind is WeekKind.WEEKLY_SHOW,
        major=show is not None and show.is_major,
        special=kind is WeekKind.SPECIAL,
    )
    if not roll.chance(chance):
        return None, None
    return championship.target_title(run, roll), None


def promo_hit_chance(mic_work: int) -> float:
    """프로모가 먹힐 확률 (§3-D41). **마이크웍이 유일한 입력이다.**"""
    return min(1.0, rules.PROMO_HIT_BASE + rules.PROMO_HIT_SPAN * (mic_work / 100))


def _promo_gain(run: CareerRun, week: int) -> tuple[dict[str, int], bool]:
    """빌드업 주차의 소득과 **그날 프로모가 먹혔는지** (§3-D41).

    먹힌 밤은 인기도를 벌고 대립을 크게 달군다. 빗나간 밤은 망각 굴림만 남는다 —
    말이 안 먹히면 아무 일도 없었던 주가 된다.
    """
    roll = SeededRoll(run.seed, week, seeded_roll.GROWTH)
    delta: dict[str, int] = {}
    hit = roll.chance(promo_hit_chance(run.stats.mic_work))
    headroom = _headroom(run.stats.mic_work)
    if roll.chance(min(1.0, rules.PROMO_MIC_GAIN_CHANCE * headroom)):
        delta["mic_work"] = 1
    if hit and roll.chance(
        min(
            1.0,
            rules.PROMO_HIT_POPULARITY_CHANCE
            * _headroom(run.stats.popularity)
            * alignment_clarity(run.stats.alignment),
        )
    ):
        # 경기 승리와 같은 경로다 — 확률 × 체감 × 성향 명료도 (§3-D41).
        delta["popularity"] = 1
    elif not hit and roll.chance(
        popularity_decay_chance(
            run.stats.popularity, off_week=False, held=run.titles_held
        )
    ):
        delta["popularity"] = -1
    return delta, hit


def popularity_decay_chance(
    popularity: int, *, off_week: bool, held: frozenset[Title] = frozenset()
) -> float:
    """인기도에 비례하는 망각 확률. 높이 오를수록 유지 비용이 크다.

    벨트를 들고 있으면 느려진다 — 가장 높은 계층 하나만 적용한다(§career_rules).
    """
    chance = rules.POPULARITY_DECAY_CHANCE * (
        (popularity / 100) ** rules.POPULARITY_DECAY_EXPONENT
    )
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


def _wear_gain(
    run: CareerRun, week: int, kind: WeekKind, format_factor: float = 1.0
) -> int:
    """마모는 확률로 쌓인다 (`WEAR_GAIN_CHANCE_*`). 스타일이 배수로 곱해진다."""
    base = {
        WeekKind.PLE: rules.WEAR_GAIN_CHANCE_PLE,
        WeekKind.SPECIAL: rules.SPECIAL_WEAR_CHANCE,
    }.get(kind, rules.WEAR_GAIN_CHANCE_SHOW)
    chance = base * INJURY_STYLE_MULTIPLIER[run.identity.play_style] * format_factor
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
    for vacated in report.vacated:
        # 길게 빠지는 챔피언은 자리를 비운다 (§3-D40). 이력은 남는다.
        moved = championship.strip(moved, vacated)
    if report.title_at_stake is not None:
        if report.result is OutcomeKind.WIN:
            moved = championship.award(run, report.title_at_stake)
        elif report.title_defended:
            moved = championship.strip(run, report.title_at_stake)

    heat_gain = {
        WeekKind.PLE: rivalry_engine.HEAT_PER_PLE,
        WeekKind.SPECIAL: rivalry_engine.HEAT_PER_MATCH,
        WeekKind.WEEKLY_SHOW: rivalry_engine.HEAT_PER_MATCH,
        WeekKind.PROMO: (
            rivalry_engine.HEAT_PER_PROMO
            if report.promo_hit
            else rivalry_engine.HEAT_PER_PROMO_MISS
        ),
        WeekKind.OFF: -rivalry_engine.COOL_PER_QUIET_WEEK,
    }[report.kind]
    # 저주는 경기 하나를 먹고 사라진다 — 경기 없는 주차는 그냥 지나간다.
    flags = moved.flags - {CURSED} if report.cursed else moved.flags

    # 팀 제안을 수락해 뒀으면 여기서 실제로 세운다 (§3-D30). 표식은 남는다 — 카드
    # 조건이 "팀에 있는가"를 계속 읽어야 하고, 표식이 곧 그 상태다.
    team = moved.team
    if TEAM_PENDING in flags:
        formed = team_engine.form_for_player(
            str(moved.identity.name),
            report.week,
            SeededRoll(run.seed, report.week, seeded_roll.TEAM),
            moved.identity.gender,
        )
        if formed is not None:
            team = formed
            flags = flags - {TEAM_PENDING}

    title_shot, briefcase_week, flags = _spoils(moved, report, flags)
    tournament_round, crown = _tournament_after(moved, report)
    if crown is not None:
        moved = moved.evolve(trophies=(*moved.trophies, crown))

    moved = moved.evolve(
        week=report.week,
        stats=moved.stats.apply(report.stat_delta),
        condition=condition,
        flags=flags,
        team=team,
        title_shot=title_shot,
        briefcase_week=briefcase_week,
        tournament_round=tournament_round,
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
