"""사건과 선택지. **덱이 아니다 — 조건식이다.**

## 여기가 지난번에 터진 자리다

이전 커리어 시뮬레이터의 `domain/constants` 는 **18,994줄**이었고 그 대부분이
이벤트 카드 덱 21개였다(테스트 11,346줄이 따라붙었다). 카드가 데이터라서
"이벤트 하나 더" 가 **파일 하나 더**가 됐다.

그래서 이번에는 카드가 없다. 사건은 `_GENERATORS` 의 **조건 함수**에서 나오고,
문구는 그 자리에서 사실을 조립한다. 사건 종류를 더하려면 함수 하나를 더한다 —
데이터 파일이 아니라 코드 한 덩이고, 그래서 늘어나는 속도가 다르다.

**서술 템플릿 뱅크를 두지 않는다.** `headline`·`detail` 은 수치를 끼운 한 줄이고
산문이 아니다. 산문이 필요하면 AI 가 확정된 상태를 읽고 만든다 — 그게 사용자
요구 §2.3 의 분리이고, AI 응답을 파싱해 상태를 정하지 않는 이유다.

## 열리는 것과 발생하는 것이 다르다

`generate` 는 **후보를 모아 상한만큼만** 연다(`MAX_OPEN_PER_WEEK`). 조건을 만족한
사건이 전부 열리면, 관계 임계값 하나가 주당 사건 다섯 개를 만든다 — 사용자 요구
§P0 가 "임계값을 넘었다고 모든 이벤트를 강제 발생시키지 말고" 라고 적은 그 고장이다.

## 중복 해결이 안 된다

사건 `id` 는 `(시즌, 주차, 종류, 대상)` 에서 나온 **결정론적 문자열**이고, 해결은
`WorldState.applied` 에 그 id 를 넣는다. 같은 선택을 두 번 보내면 둘째는
아무 일도 하지 않는다 — 보상이 두 번 적용되지 않는다(§P0 사건).
"""

from __future__ import annotations

from dataclasses import replace

from kayfabe.domain.services import career_relations as relations
from kayfabe.domain.services import career_retirement as retire
from kayfabe.domain.services.career_injury import active_injury, rest
from kayfabe.domain.services.career_rng import roll
from kayfabe.domain.services.career_world import (
    Balance,
    Choice,
    LogEntry,
    PendingEvent,
    RelationKind,
    RetirementCause,
    Severity,
    WorldState,
)


class EventNotFoundError(KeyError):
    """해결하려는 사건이 보류 목록에 없다. **정상적인 입력 오류다.**

    `KeyError` 를 물려받는 것은 이 예외가 이미 `KeyError` 로 올라오던 자리를
    대체하기 때문이다. `KeyError` 로 잡던 호출자는 그대로 돌아가고, 구별이
    필요한 쪽만 이 이름을 본다.

    ## 왜 전용 이름이 필요한가

    `resolve` 안에서 `KeyError` 가 나는 자리가 **둘**이고 뜻이 반대다.

        이 예외          클라이언트가 없는 사건 id 를 보냈다 → 404
        `WorldState.require` 의 `KeyError`   **세이브가 자기모순이다** → 500

    둘이 같은 타입이면 호출자가 가를 수 없다. 2026-10-26 실측으로 `subject` 가
    로스터에 없는 보류 사건에 `/events/{id}` 를 보내면
    `404 "없는 사건입니다: evt"` 가 돌아왔다 — 세이브가 깨진 것을 "그 사건은
    없다" 고 보고한 것이다.

    **문구로 가르지 않는다.** 그 방식은 도메인 문장을 고칠 때 조용히 분기를
    바꾼다(`career_sandbox_router` 모듈 독스트링이 같은 이유로 배제한다).
    """


#: 한 주에 열리는 사건 수 상한. 후보가 많아도 이만큼만 열린다.
MAX_OPEN_PER_WEEK = 2

#: **열린 채 쌓일 수 있는 사건 수 상한.** 이 값이 없으면 미해결 사건이 무한히
#: 늘어난다 — 첫 시험 런이 52주에 **40건**을 쌓았다. `decline` 과 `poor_form` 은
#: 조건이 유지되는 동안 매주 참이고 `id` 가 주차마다 달라서, 안 고르고 넘기면
#: 같은 사건이 주마다 새로 열렸다. 아래 `_same_kind_open` 이 종류별 중복을 막고
#: 이 상한이 전체를 막는다.
MAX_PENDING = 6


def event_id(*, season: int, week: int, kind: str, subject: str) -> str:
    """사건의 고유 키. **상태에서 파생**되므로 재시도가 같은 id 를 만든다."""
    return f"s{season}w{week}:{kind}:{subject}"


def _retirement_choices(
    state: WorldState, subject: str, *, grave: bool
) -> tuple[Choice, ...]:
    """은퇴 계열 사건의 선택지.

    **못 고르는 선택지를 지우지 않고 막는다**(`enabled=False`). 왜 복귀할 수
    없는지 화면이 적어야 하기 때문이다(사용자 요구 §6 사건 화면 — "선택에 따른
    예상 영향").
    """
    me = state.require(subject)
    permanent = me.permanently_out
    return (
        Choice(
            code="stay",
            label="현역을 유지한다",
            enabled=not permanent,
            note=(
                "의학적으로 복귀할 수 없다"
                if permanent
                else "은퇴 의사를 거둔다 · 위험은 그대로 남는다"
            ),
        ),
        Choice(
            code="rest",
            label="일정 기간 휴식한다",
            enabled=not permanent,
            note=("복귀가 불가능하다" if permanent else "컨디션·회복력이 오른다"),
        ),
        Choice(
            code="lighten",
            label="훈련 강도를 낮추고 회복에 집중한다",
            enabled=not permanent,
            note=(
                "복귀가 불가능하다"
                if permanent
                else "회복력이 오르고 기술 상승이 늦어진다"
            ),
        ),
        Choice(
            code="final_season",
            label="마지막 시즌을 선언한다",
            enabled=not permanent,
            note=(
                "복귀가 불가능하다"
                if permanent
                else "이 시즌 끝에 은퇴한다 · 인기도가 오른다"
            ),
        ),
        Choice(
            code="retire",
            label="은퇴를 확정한다",
            enabled=True,
            note=("의학적 사유로 기록된다" if permanent else "되돌릴 수 없다"),
        ),
    )


# ── 생성기 ────────────────────────────────────────────────────────
#
# 각 생성기는 `(state, subject, balance, seed) -> PendingEvent | None` 이다.
# 조건을 만족하지 않으면 `None`. **순수 함수다** — 세계를 바꾸지 않는다.


def _gen_medical(state: WorldState, subject: str, balance: Balance, seed: int):
    """의학적 영구 불가. **일반 은퇴 사건과 갈라 둔다**(§4 마지막 문단)."""
    me = state.require(subject)
    if not me.permanently_out or me.retired:
        return None
    hurt = active_injury(me) or me.injuries[-1]
    return PendingEvent(
        id=event_id(
            season=state.season, week=state.week, kind="medical", subject=subject
        ),
        kind="medical",
        season=state.season,
        week=state.week,
        subject=subject,
        headline=f"{hurt.kind} 부상 — 의료진이 복귀 불가를 통보했다",
        detail=(
            f"{hurt.kind} {hurt.severity} 부상이 재발했다. "
            f"{me.age}세 · 누적 부상 {len(me.injuries)}회. 복귀 선택지가 없다."
        ),
        choices=_retirement_choices(state, subject, grave=True),
    )


def _gen_severe_injury(state: WorldState, subject: str, balance: Balance, seed: int):
    """심각한 부상 뒤의 결정. **즉시 은퇴시키지 않는다**(§3.3)."""
    me = state.require(subject)
    hurt = active_injury(me)
    if hurt is None or hurt.severity == Severity.MINOR or me.permanently_out:
        return None
    if hurt.week != state.week or hurt.season != state.season:
        return None
    return PendingEvent(
        id=event_id(
            season=state.season, week=state.week, kind="severe_injury", subject=subject
        ),
        kind="severe_injury",
        season=state.season,
        week=state.week,
        subject=subject,
        headline=f"{hurt.kind} 부상 — {hurt.weeks_out}주 결장",
        detail=(
            f"{'재발이다. ' if hurt.recurrence else ''}"
            f"{me.age}세 · 회복력 {me.ability.resilience} · 누적 부상 {len(me.injuries)}회."
        ),
        choices=_retirement_choices(state, subject, grave=True),
    )


def _gen_decline(state: WorldState, subject: str, balance: Balance, seed: int):
    """노장의 회복 속도 호소. 위험 평가가 열어 준다."""
    me = state.require(subject)
    risk = retire.assess(me, balance)
    if not retire.should_open_event(risk, balance) or me.intent is not None:
        return None
    if me.permanently_out:
        return None
    return PendingEvent(
        id=event_id(
            season=state.season, week=state.week, kind="decline", subject=subject
        ),
        kind="decline",
        season=state.season,
        week=state.week,
        subject=subject,
        headline="회복이 예전 같지 않다",
        # **근거를 적는다.** 퍼센트가 아니라 요소 나열이다(§6).
        detail=f"{risk.band} — " + " · ".join(risk.explained[:4]),
        choices=_retirement_choices(state, subject, grave=False),
    )


def _gen_last_ride(state: WorldState, subject: str, balance: Balance, seed: int):
    """장기 보유 챔피언의 마지막 시즌 선언 제안(§4)."""
    me = state.require(subject)
    if me.intent is not None or me.retired or me.age < balance.decline_age + 3:
        return None
    held = state.title_held_by(subject)
    if not held:
        return None
    long_reign = [t for t in held if t.defenses >= 4]
    if not long_reign:
        return None
    belt = long_reign[0]
    return PendingEvent(
        id=event_id(
            season=state.season, week=state.week, kind="last_ride", subject=subject
        ),
        kind="last_ride",
        season=state.season,
        week=state.week,
        subject=subject,
        headline=f"{belt.name} {belt.defenses}차 방어 — 마지막 시즌을 말한다",
        detail=f"{me.age}세 · 전적 {me.wins}승 {me.losses}패 · 역대 재위 {len(me.reigns)}회.",
        choices=_retirement_choices(state, subject, grave=False),
    )


def _gen_poor_form(state: WorldState, subject: str, balance: Balance, seed: int):
    """연패 뒤 커리어 위기(§P0 사건 — "연속 패배에 따른 커리어 위기")."""
    me = state.require(subject)
    if me.losing_streak < balance.poor_form_losses or me.retired:
        return None
    return PendingEvent(
        id=event_id(
            season=state.season, week=state.week, kind="poor_form", subject=subject
        ),
        kind="poor_form",
        season=state.season,
        week=state.week,
        subject=subject,
        headline=f"{me.losing_streak}연패 — 커리어 방향을 고민한다",
        detail=f"인기도 {me.popularity} · 컨디션 {me.condition}.",
        choices=(
            Choice("stay", "현역을 유지한다", True, "인기도가 조금 깎인다"),
            Choice(
                "lighten", "훈련 강도를 낮추고 회복에 집중한다", True, "회복력이 오른다"
            ),
            Choice(
                "heel_turn",
                "캐릭터를 바꾼다",
                True,
                "선역·악역을 뒤집고 인기도가 오른다",
            ),
            Choice("retire", "은퇴를 확정한다", True, "되돌릴 수 없다"),
        ),
    )


def _gen_relation(state: WorldState, subject: str, balance: Balance, seed: int):
    """관계가 만든 사건. **후보 중 하나만** 고른다.

    `career_relations.candidates` 가 준 목록에서 가장 무거운 것 하나다. 전부
    열면 §P0 가 금지한 "임계값 넘으면 모두 발생" 이 된다.
    """
    cands = relations.candidates(state, subject)
    if not cands:
        return None
    top = cands[0]
    # 무게가 그대로 확률이 아니다 — 뽑기를 한 번 더 거쳐 매주 같은 사건이 열리는
    # 것을 막는다.
    if roll(seed, "relation_event", state.season, state.week, subject) > top.weight:
        return None

    other = top.other
    if top.kind == "rival_taunt":
        return PendingEvent(
            id=event_id(
                season=state.season,
                week=state.week,
                kind="rival_taunt",
                subject=subject,
            ),
            kind="rival_taunt",
            season=state.season,
            week=state.week,
            subject=subject,
            other=other,
            headline=f"{other}가 공개적으로 도발했다",
            detail=top.reason,
            choices=(
                Choice("answer", "맞받아친다", True, "앙금과 인기도가 함께 오른다"),
                Choice("ignore", "무시한다", True, "앙금이 식고 인기도가 조금 깎인다"),
                Choice(
                    "attack",
                    "기습한다",
                    True,
                    "악역 쪽으로 기운다 · 앙금이 크게 오른다",
                ),
            ),
        )
    if top.kind == "ally_offer":
        return PendingEvent(
            id=event_id(
                season=state.season, week=state.week, kind="ally_offer", subject=subject
            ),
            kind="ally_offer",
            season=state.season,
            week=state.week,
            subject=subject,
            other=other,
            headline=f"{other}가 함께하자고 제안했다",
            detail=top.reason,
            choices=(
                Choice("accept", "받아들인다", True, "동맹이 된다"),
                Choice("decline", "거절한다", True, "관계가 서늘해진다"),
            ),
        )
    if top.kind == "tag_team_offer":
        return PendingEvent(
            id=event_id(
                season=state.season,
                week=state.week,
                kind="tag_team_offer",
                subject=subject,
            ),
            kind="tag_team_offer",
            season=state.season,
            week=state.week,
            subject=subject,
            other=other,
            headline=f"{other}와 태그팀을 짠다",
            detail=top.reason,
            choices=(
                Choice("accept", "팀을 짠다", True, "태그 경기가 열린다"),
                Choice("decline", "거절한다", True, "신뢰가 깎인다"),
            ),
        )
    if top.kind == "betrayal":
        return PendingEvent(
            id=event_id(
                season=state.season, week=state.week, kind="betrayal", subject=subject
            ),
            kind="betrayal",
            season=state.season,
            week=state.week,
            subject=subject,
            other=other,
            headline=f"{other}와의 관계가 금 갔다",
            detail=top.reason,
            choices=(
                Choice(
                    "betray",
                    "먼저 등을 돌린다",
                    True,
                    "라이벌이 된다 · 악역 쪽으로 기운다",
                ),
                Choice("mend", "관계를 회복한다", True, "신뢰가 오른다"),
            ),
        )
    return None


def _gen_title_offer(state: WorldState, subject: str, balance: Balance, seed: int):
    """GM 의 타이틀전 제안(§P0 사건). 자격이 될 때만 열린다."""
    me = state.require(subject)
    if not me.bookable or state.title_held_by(subject):
        return None
    open_belts = [
        t
        for t in state.titles
        if t.brand == me.brand and me.popularity >= t.required_popularity
    ]
    if not open_belts:
        return None
    belt = max(open_belts, key=lambda t: t.required_popularity)
    if roll(seed, "title_offer", state.season, state.week, subject) > 0.22:
        return None
    champ = belt.holder or "공석"
    return PendingEvent(
        id=event_id(
            season=state.season, week=state.week, kind="title_offer", subject=subject
        ),
        kind="title_offer",
        season=state.season,
        week=state.week,
        subject=subject,
        other=belt.holder,
        headline=f"GM 이 {belt.name} 도전을 제안했다",
        detail=f"현 챔피언 {champ} · 인기도 {me.popularity} / 요구 {belt.required_popularity}.",
        choices=(
            Choice("accept", "받아들인다", True, "다음 주 타이틀전"),
            Choice("decline", "거절한다", True, "인기도가 조금 깎인다"),
        ),
    )


#: 생성기 목록. **순서가 우선순위다** — 의학적 통보가 관계 사건보다 먼저 열린다.
_GENERATORS = (
    _gen_medical,
    _gen_severe_injury,
    _gen_last_ride,
    _gen_poor_form,
    _gen_decline,
    _gen_title_offer,
    _gen_relation,
)


def generate(
    state: WorldState, *, balance: Balance, subject: str | None = None
) -> WorldState:
    """이번 주 사건을 연다. **상한까지만.**

    이미 열려 있는 사건과 이미 해결한 사건(`applied`)은 다시 열리지 않는다.
    """
    who = subject or state.player
    if state.find(who) is None:
        return state

    open_ids = {e.id for e in state.pending}
    # **같은 종류가 이미 열려 있으면 또 열지 않는다.** `id` 는 주차를 포함하므로
    # id 비교만으로는 막히지 않는다 — 조건이 유지되는 사건이 매주 새 id 로 다시
    # 열린다. 막는 기준은 `(종류, 대상)` 이다.
    open_kinds = {(e.kind, e.subject) for e in state.pending}
    room = MAX_PENDING - len(state.pending)
    if room <= 0:
        return state

    fresh: list[PendingEvent] = []
    for gen in _GENERATORS:
        if len(fresh) >= min(MAX_OPEN_PER_WEEK, room):
            break
        event = gen(state, who, balance, state.seed)
        if event is None:
            continue
        if event.id in open_ids or event.id in state.applied:
            continue
        if (event.kind, event.subject) in open_kinds:
            continue
        fresh.append(event)
        open_ids.add(event.id)
        open_kinds.add((event.kind, event.subject))

    if not fresh:
        return state
    return replace(state, pending=state.pending + tuple(fresh))


# ── 해결 ──────────────────────────────────────────────────────────


def _log(state: WorldState, entry: LogEntry) -> WorldState:
    return replace(state, log=state.log + (entry,))


def _put(state: WorldState, wrestler) -> WorldState:
    return replace(
        state,
        roster=tuple(w if w.name != wrestler.name else wrestler for w in state.roster),
    )


def resolve(
    state: WorldState, *, event_id_: str, choice_code: str, balance: Balance
) -> WorldState:
    """사건 하나를 해결한다. **멱등이다.**

    이미 해결된 id 면 세계를 그대로 돌려준다 — 같은 선택을 두 번 보내도 보상이
    두 번 적용되지 않는다(§P0 사건 · §7 검증 8).

    모르는 사건이면 `EventNotFoundError`, 모르는 선택이면 `ValueError` 를 낸다.
    조용히 무시하면 화면이 "적용됐다" 고 믿는다.

    **`EventNotFoundError` 는 `KeyError` 와 구별해서 받아야 한다.** 아래
    `_apply_choice` 가 `WorldState.require` 를 부르므로 이 함수는 세이브가
    자기모순일 때 **평범한 `KeyError`** 도 낸다. 그쪽은 입력 오류가 아니라 저장된
    데이터의 고장이고, 호출자가 둘을 같이 잡으면 고장이 404 로 보고된다
    (`EventNotFoundError` 독스트링에 실측이 있다).
    """
    if event_id_ in state.applied:
        return state

    event = next((e for e in state.pending if e.id == event_id_), None)
    if event is None:
        raise EventNotFoundError(f"없는 사건: {event_id_}")
    choice = next((c for c in event.choices if c.code == choice_code), None)
    if choice is None:
        raise ValueError(f"없는 선택지: {choice_code}")
    if not choice.enabled:
        raise ValueError(f"고를 수 없는 선택지: {choice_code} — {choice.note}")

    state = _apply_choice(state, event=event, choice_code=choice_code, balance=balance)

    # 사건을 닫고 키를 남긴다. **이 두 줄이 중복 해결을 막는다.**
    state = replace(
        state,
        pending=tuple(e for e in state.pending if e.id != event_id_),
        applied=state.applied | {event_id_},
    )
    return _log(
        state,
        LogEntry(
            season=event.season,
            week=event.week,
            kind="event",
            subject=event.subject,
            other=event.other,
            summary=f"{event.headline} → {choice.label}",
            result=choice_code,
        ),
    )


def _apply_choice(
    state: WorldState, *, event: PendingEvent, choice_code: str, balance: Balance
) -> WorldState:
    """선택의 **실제 효과**. 인기도·관계·컨디션·타이틀 기회·은퇴가 여기서 움직인다."""
    me = state.require(event.subject)
    week, season = state.week, state.season

    # ── 은퇴 계열 ────────────────────────────────────────────
    if choice_code == "retire":
        risk = retire.assess(me, balance)
        cause = retire.infer_cause(me, risk, balance)
        if event.kind in ("decline", "last_ride", "poor_form") and me.intent is None:
            # 플레이어가 제안을 받아 확정한 것이다 — 선수가 요청한 것과 구별한다.
            cause = (
                RetirementCause.MEDICAL
                if me.permanently_out
                else RetirementCause.OFFER_ACCEPTED
            )
        state = _put(
            state,
            retire.confirm(
                me, cause=cause, season=season, week=week, note=event.headline
            ),
        )
        return state

    if choice_code == "stay":
        return _put(state, retire.withdraw_intent(me))

    if choice_code == "rest":
        healed = rest(me, weeks=2)
        return _put(state, replace(healed, out_weeks=max(healed.out_weeks, 1)))

    if choice_code == "lighten":
        ability = replace(
            me.ability,
            resilience=me.ability.resilience + 4,
            in_ring=me.ability.in_ring - 1,
        ).clamped()
        return _put(
            state, replace(me, ability=ability, condition=min(100, me.condition + 10))
        )

    if choice_code == "final_season":
        declared = retire.declare_intent(
            me,
            origin="self",
            cause=RetirementCause.VOLUNTARY,
            season=season,
            week=week,
            final_season=True,
        )
        return _put(
            state, replace(declared, popularity=min(100, declared.popularity + 6))
        )

    # ── 관계 계열 ────────────────────────────────────────────
    if choice_code == "answer" and event.other:
        state = relations.upsert(
            state,
            a=me.name,
            b=event.other,
            kind=RelationKind.RIVAL,
            heat_delta=10,
            week=week,
        )
        return _put(state, replace(me, popularity=min(100, me.popularity + 4)))

    if choice_code == "ignore" and event.other:
        state = relations.upsert(
            state,
            a=me.name,
            b=event.other,
            kind=RelationKind.RIVAL,
            heat_delta=-12,
            week=week,
        )
        return _put(
            state,
            replace(me, popularity=max(balance.min_popularity, me.popularity - 2)),
        )

    if choice_code == "attack" and event.other:
        state = relations.upsert(
            state,
            a=me.name,
            b=event.other,
            kind=RelationKind.RIVAL,
            heat_delta=25,
            week=week,
        )
        return _put(
            state,
            replace(me, alignment="heel", popularity=min(100, me.popularity + 7)),
        )

    if choice_code == "accept" and event.kind == "ally_offer" and event.other:
        state = relations.upsert(
            state,
            a=me.name,
            b=event.other,
            kind=RelationKind.ALLY,
            heat_delta=30,
            week=week,
        )
        state = relations.upsert(
            state,
            a=event.other,
            b=me.name,
            kind=RelationKind.ALLY,
            heat_delta=30,
            week=week,
        )
        return state

    if choice_code == "accept" and event.kind == "tag_team_offer" and event.other:
        state = relations.upsert(
            state,
            a=me.name,
            b=event.other,
            kind=RelationKind.TAG_TEAM,
            heat_delta=15,
            week=week,
        )
        state = relations.upsert(
            state,
            a=event.other,
            b=me.name,
            kind=RelationKind.TAG_TEAM,
            heat_delta=15,
            week=week,
        )
        return state

    if choice_code == "decline" and event.other and event.kind != "title_offer":
        state = relations.upsert(
            state,
            a=me.name,
            b=event.other,
            kind=RelationKind.ALLY,
            heat_delta=-18,
            week=week,
            note="제안을 거절했다",
        )
        return state

    if choice_code == "betray" and event.other:
        state = relations.betray(state, traitor=me.name, victim=event.other, week=week)
        return _put(
            state, replace(me, alignment="heel", popularity=min(100, me.popularity + 5))
        )

    if choice_code == "mend" and event.other:
        state = relations.upsert(
            state,
            a=me.name,
            b=event.other,
            kind=RelationKind.ALLY,
            heat_delta=25,
            week=week,
        )
        return state

    # ── 타이틀 제안 ──────────────────────────────────────────
    if choice_code == "accept" and event.kind == "title_offer":
        # **기회를 상태에 남긴다.** `applied` 에 키가 들어가므로 다음 주 대진이
        # 이걸 읽고 타이틀전을 만든다(`career_engine._booked_title`).
        return replace(state, applied=state.applied | {f"shot:s{season}w{week + 1}"})

    if choice_code == "decline" and event.kind == "title_offer":
        return _put(
            state,
            replace(me, popularity=max(balance.min_popularity, me.popularity - 3)),
        )

    if choice_code == "heel_turn":
        flipped = "heel" if me.alignment == "face" else "face"
        return _put(
            state,
            replace(
                me,
                alignment=flipped,
                popularity=min(100, me.popularity + 10),
                losing_streak=0,
            ),
        )

    raise ValueError(f"효과가 정의되지 않은 선택: {event.kind}/{choice_code}")
