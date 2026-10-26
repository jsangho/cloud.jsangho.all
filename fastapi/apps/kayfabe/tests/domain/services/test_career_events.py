"""사건과 관계 (`career_events` · `career_relations`).

**붙드는 것은 계약이다.**

1. **임계값을 넘었다고 전부 발생하지 않는다** — 후보를 모아 상한만큼만 연다
   (사용자 요구 §P0 관계 · 사건)
2. **같은 사건의 보상이 두 번 적용되지 않는다** — 해결 키가 멱등을 지킨다 (§7 검증 8)
3. **선택이 실제 상태를 움직인다** — 인기도·관계·컨디션·타이틀 기회·은퇴
   (§P0 사건 — "관계 수치만 변경하고 끝내지 말고")
4. **사건이 은퇴를 시키지 않는다** — 의사와 확정이 갈라져 있다 (§3.1)
5. **배신은 비대칭이다** — 당한 쪽과 한 쪽의 관계가 같지 않다

순수 함수라 DB가 필요 없다.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from kayfabe.domain.services import career_events as events
from kayfabe.domain.services import career_relations as relations
from kayfabe.domain.services.career_engine import create_world
from kayfabe.domain.services.career_world import (
    Ability,
    Alignment,
    Balance,
    Choice,
    PendingEvent,
    RelationKind,
    Relationship,
    RetirementCause,
    RetirementIntent,
    Status,
    Title,
)

BAL = Balance()


def _world(seed: int = 11):
    return create_world(player="Hero", style="테크니션", seed=seed, balance=BAL)


def _with_relation(state, *, kind: str, heat: int, other: str = "Dex Harlow"):
    """플레이어와 `other` 사이에 관계 하나를 박아 둔다."""
    return replace(
        state,
        relationships=(
            Relationship(
                a=state.player,
                b=other,
                kind=kind,
                heat=heat,
                started_week=1,
                last_week=1,
            ),
        ),
    )


def _event(kind: str, *, choices: tuple[Choice, ...], other: str | None = "Dex Harlow"):
    return PendingEvent(
        id=f"evt:s1w1:{kind}:Hero",
        kind=kind,
        season=1,
        week=1,
        subject="Hero",
        other=other,
        headline=f"{kind} 사건",
        detail="",
        choices=choices,
    )


def _open(state, event: PendingEvent):
    return replace(state, pending=state.pending + (event,))


# ── 관계: 모양과 이력 ─────────────────────────────────────────────


def test_upsert_creates_then_updates_one_row() -> None:
    state = relations.upsert(
        _world(), a="Hero", b="Dex Harlow", kind="ally", heat_delta=20
    )
    state = relations.upsert(
        state, a="Hero", b="Dex Harlow", kind="ally", heat_delta=15
    )

    assert len(state.relationships) == 1
    assert state.relationships[0].heat == 35


def test_heat_is_clamped_to_the_scale() -> None:
    state = relations.upsert(
        _world(), a="Hero", b="Dex Harlow", kind="rival", heat_delta=400
    )

    assert state.relationships[0].heat == 100


def test_changing_the_kind_is_written_to_history() -> None:
    """§P0 — "상태 변경 이력". "동맹이었다가 라이벌이 됐다" 를 화면이 적어야 한다."""
    state = relations.upsert(
        _world(), a="Hero", b="Dex Harlow", kind="ally", heat_delta=30
    )
    state = relations.upsert(state, a="Hero", b="Dex Harlow", kind="rival")

    assert "ally→rival" in state.relationships[0].history


def test_relations_have_a_direction() -> None:
    """양방향으로 저장하지 않는다 — 배신이 비대칭이라 한 줄로는 적을 수 없다."""
    state = relations.upsert(
        _world(), a="Hero", b="Dex Harlow", kind="rival", heat_delta=40
    )

    assert relations.find(state, "Hero", "Dex Harlow") is not None
    assert relations.find(state, "Dex Harlow", "Hero") is None


def test_after_match_makes_the_loser_a_rival() -> None:
    state = relations.after_match(
        _world(), winner="Hero", loser="Dex Harlow", week=3, title_match=False
    )

    beaten = relations.find(state, "Dex Harlow", "Hero")
    assert beaten is not None
    assert beaten.kind == RelationKind.RIVAL
    # 진 쪽이 더 끓는다 — "되갚을 상대" 와 "넘은 상대" 는 같은 무게가 아니다.
    assert beaten.heat > relations.find(state, "Hero", "Dex Harlow").heat


def test_a_title_match_heats_more_than_a_normal_one() -> None:
    normal = relations.after_match(
        _world(), winner="Hero", loser="Dex Harlow", week=3, title_match=False
    )
    titled = relations.after_match(
        _world(), winner="Hero", loser="Dex Harlow", week=3, title_match=True
    )

    assert (
        relations.find(titled, "Dex Harlow", "Hero").heat
        > relations.find(normal, "Dex Harlow", "Hero").heat
    )


def test_allies_who_fight_lose_trust_without_flipping_to_rivals() -> None:
    state = _with_relation(_world(), kind=RelationKind.ALLY, heat=50)
    state = relations.upsert(
        state, a="Dex Harlow", b="Hero", kind=RelationKind.ALLY, heat_delta=50
    )

    state = relations.after_match(
        state, winner="Hero", loser="Dex Harlow", week=4, title_match=False
    )

    beaten = relations.find(state, "Dex Harlow", "Hero")
    assert beaten.kind == RelationKind.ALLY
    assert beaten.heat < 50


def test_betrayal_is_asymmetric() -> None:
    """당한 쪽은 라이벌이 되고, 한 쪽은 관계를 끊는다."""
    state = _with_relation(_world(), kind=RelationKind.ALLY, heat=40)
    state = relations.upsert(
        state, a="Dex Harlow", b="Hero", kind=RelationKind.ALLY, heat_delta=40
    )

    state = relations.betray(state, traitor="Hero", victim="Dex Harlow", week=5)

    victim = relations.find(state, "Dex Harlow", "Hero")
    traitor = relations.find(state, "Hero", "Dex Harlow")
    assert victim.kind == RelationKind.RIVAL
    assert traitor.kind == RelationKind.RIVAL
    assert victim.heat > traitor.heat


def test_tag_partner_and_top_rival_pick_the_hottest() -> None:
    state = replace(
        _world(),
        relationships=(
            Relationship(a="Hero", b="Dex Harlow", kind=RelationKind.TAG_TEAM, heat=40),
            Relationship(
                a="Hero", b="Marcus Vane", kind=RelationKind.TAG_TEAM, heat=70
            ),
            Relationship(a="Hero", b="Rio Castellan", kind=RelationKind.RIVAL, heat=80),
            Relationship(a="Hero", b="Bastian Kord", kind=RelationKind.RIVAL, heat=30),
        ),
    )

    assert relations.tag_partner(state, "Hero") == "Marcus Vane"
    assert relations.top_rival(state, "Hero") == "Rio Castellan"


# ── 관계: 후보는 사건이 아니다 ────────────────────────────────────


def _kinds(state, subject: str = "Hero") -> list[str]:
    return [c.kind for c in relations.candidates(state, subject)]


def test_a_cool_rivalry_makes_no_taunt_candidate() -> None:
    state = _with_relation(
        _world(), kind=RelationKind.RIVAL, heat=relations.FEUD_HEAT - 1
    )

    # 같은 브랜드의 낯선 선수가 만드는 `ally_offer` 후보는 관계와 무관하게 남는다 —
    # 여기서 보는 것은 **임계값 아래의 라이벌이 도발 사건을 만들지 않는다** 는 것이다.
    assert "rival_taunt" not in _kinds(state)


def test_a_hot_rivalry_makes_a_taunt_candidate() -> None:
    state = _with_relation(_world(), kind=RelationKind.RIVAL, heat=relations.FEUD_HEAT)

    assert "rival_taunt" in _kinds(state)


def test_the_heaviest_candidate_comes_first() -> None:
    """후보는 무게 순이다 — `career_events` 가 맨 앞 하나만 고른다."""
    state = _with_relation(_world(), kind=RelationKind.RIVAL, heat=95)

    assert _kinds(state)[0] == "rival_taunt"


def test_a_candidate_carries_its_reason() -> None:
    """**근거를 들고 다닌다** — 화면이 왜 열렸는지 적을 수 있어야 한다."""
    state = _with_relation(_world(), kind=RelationKind.RIVAL, heat=90)

    assert relations.candidates(state, "Hero")[0].reason


def test_a_retired_partner_makes_no_candidate() -> None:
    """은퇴 선수는 기록으로 남지만 세계에 개입하지 않는다(§3.4 · §5)."""
    state = _with_relation(_world(), kind=RelationKind.RIVAL, heat=90)
    retired = replace(state.require("Dex Harlow"), status=Status.RETIRED)
    state = replace(
        state,
        roster=tuple(w if w.name != retired.name else retired for w in state.roster),
    )

    assert "rival_taunt" not in _kinds(state)
    assert all(c.other != "Dex Harlow" for c in relations.candidates(state, "Hero"))


def test_an_injured_subject_makes_no_candidate_at_all() -> None:
    state = _with_relation(_world(), kind=RelationKind.RIVAL, heat=90)
    hurt = replace(state.hero, out_weeks=4, status=Status.INJURED)
    state = replace(
        state, roster=tuple(w if not w.is_player else hurt for w in state.roster)
    )

    assert relations.candidates(state, "Hero") == ()


def test_drop_retired_does_not_delete_anything() -> None:
    """**이름과 달리 아무것도 지우지 않는다 — 그게 의도다.**

    §5 가 "은퇴 선수의 과거 라이벌 관계 및 경기 기록 조회" 를 요구하므로 삭제가
    금지된다. 은퇴 선수를 세계에서 빼는 일은 `candidates` 가 건너뛰는 것으로 한다.
    """
    state = _with_relation(_world(), kind=RelationKind.ALLY, heat=40)
    retired = replace(state.require("Dex Harlow"), status=Status.RETIRED)
    state = replace(
        state,
        roster=tuple(w if w.name != retired.name else retired for w in state.roster),
    )

    pruned = relations.drop_retired(state)

    assert relations.find(pruned, "Hero", "Dex Harlow") is not None
    assert pruned == state


# ── 사건 생성: 상한과 중복 ────────────────────────────────────────


def test_never_opens_more_than_the_weekly_cap() -> None:
    """**임계값 하나가 주당 사건 다섯 개를 만들지 않는다**(§P0)."""
    base = _with_relation(_world(), kind=RelationKind.RIVAL, heat=100)
    base = replace(
        base,
        roster=tuple(
            replace(w, losing_streak=9, condition=20) if w.is_player else w
            for w in base.roster
        ),
    )

    for seed in range(40):
        opened = events.generate(replace(base, seed=seed), balance=BAL)
        assert len(opened.pending) <= events.MAX_OPEN_PER_WEEK


def test_the_same_kind_is_not_opened_twice_for_the_same_subject() -> None:
    """조건이 유지되는 사건이 매주 새 id 로 다시 열리는 고장을 막는다."""
    state = _with_relation(_world(), kind=RelationKind.RIVAL, heat=100)
    state = _open(
        state,
        _event("rival_taunt", choices=(Choice("answer", "맞받아친다"),)),
    )

    for week in range(2, 8):
        state = events.generate(replace(state, week=week), balance=BAL)

    assert [e.kind for e in state.pending].count("rival_taunt") == 1


def test_a_resolved_event_is_not_reopened() -> None:
    state = _with_relation(_world(), kind=RelationKind.RIVAL, heat=100)
    event = _event("rival_taunt", choices=(Choice("answer", "맞받아친다"),))
    state = replace(state, applied=state.applied | {event.id})

    opened = events.generate(state, balance=BAL)

    assert all(e.id != event.id for e in opened.pending)


def test_pending_events_are_capped_overall() -> None:
    state = _world()
    filler = tuple(
        _event(f"k{i}", choices=(Choice("x", "x"),)) for i in range(events.MAX_PENDING)
    )
    state = replace(state, pending=filler)

    assert len(events.generate(state, balance=BAL).pending) == events.MAX_PENDING


# ── 사건 해결: 멱등과 검증 ────────────────────────────────────────


def test_resolving_twice_applies_the_reward_once() -> None:
    """§7 검증 8 — 같은 선택을 두 번 보내도 보상이 두 번 적용되지 않는다."""
    state = _open(
        _with_relation(_world(), kind=RelationKind.RIVAL, heat=60),
        _event("rival_taunt", choices=(Choice("answer", "맞받아친다"),)),
    )
    before = state.hero.popularity

    once = events.resolve(
        state, event_id_="evt:s1w1:rival_taunt:Hero", choice_code="answer", balance=BAL
    )
    twice = events.resolve(
        once, event_id_="evt:s1w1:rival_taunt:Hero", choice_code="answer", balance=BAL
    )

    assert once.hero.popularity > before
    assert twice.hero.popularity == once.hero.popularity
    assert twice.pending == ()


def test_resolving_closes_the_event_and_logs_it() -> None:
    state = _open(
        _with_relation(_world(), kind=RelationKind.RIVAL, heat=60),
        _event("rival_taunt", choices=(Choice("answer", "맞받아친다"),)),
    )

    resolved = events.resolve(
        state, event_id_="evt:s1w1:rival_taunt:Hero", choice_code="answer", balance=BAL
    )

    assert resolved.pending == ()
    assert resolved.log[-1].kind == "event"
    assert resolved.log[-1].result == "answer"


def test_an_unknown_event_raises() -> None:
    with pytest.raises(KeyError):
        events.resolve(
            _world(), event_id_="evt:nope", choice_code="answer", balance=BAL
        )


def test_an_unknown_choice_raises() -> None:
    state = _open(
        _world(), _event("rival_taunt", choices=(Choice("answer", "맞받아친다"),))
    )

    with pytest.raises(ValueError, match="없는 선택지"):
        events.resolve(
            state, event_id_="evt:s1w1:rival_taunt:Hero", choice_code="춤", balance=BAL
        )


def test_a_disabled_choice_cannot_be_taken() -> None:
    """못 고르는 선택지는 **지우지 않고 막는다** — 이유를 화면이 적어야 한다."""
    state = _open(
        _world(),
        _event(
            "medical",
            choices=(Choice("return", "복귀한다", False, "영구 불가 판정이다"),),
        ),
    )

    with pytest.raises(ValueError, match="고를 수 없는 선택지"):
        events.resolve(
            state, event_id_="evt:s1w1:medical:Hero", choice_code="return", balance=BAL
        )


# ── 사건 해결: 실제 효과 ──────────────────────────────────────────


def test_answering_a_taunt_raises_heat_and_popularity() -> None:
    state = _open(
        _with_relation(_world(), kind=RelationKind.RIVAL, heat=60),
        _event("rival_taunt", choices=(Choice("answer", "맞받아친다"),)),
    )

    after = events.resolve(
        state, event_id_="evt:s1w1:rival_taunt:Hero", choice_code="answer", balance=BAL
    )

    assert relations.find(after, "Hero", "Dex Harlow").heat == 70
    assert after.hero.popularity == state.hero.popularity + 4


def test_ignoring_a_taunt_cools_it_and_costs_popularity() -> None:
    state = _open(
        _with_relation(_world(), kind=RelationKind.RIVAL, heat=60),
        _event("rival_taunt", choices=(Choice("ignore", "무시한다"),)),
    )

    after = events.resolve(
        state, event_id_="evt:s1w1:rival_taunt:Hero", choice_code="ignore", balance=BAL
    )

    assert relations.find(after, "Hero", "Dex Harlow").heat == 48
    assert after.hero.popularity < state.hero.popularity


def test_attacking_turns_the_player_heel() -> None:
    """§2.1 — 선역·악역·캐릭터 전환이 가능해야 한다."""
    state = _open(
        _with_relation(_world(), kind=RelationKind.RIVAL, heat=60),
        _event("rival_taunt", choices=(Choice("attack", "기습한다"),)),
    )
    assert state.hero.alignment == Alignment.FACE

    after = events.resolve(
        state, event_id_="evt:s1w1:rival_taunt:Hero", choice_code="attack", balance=BAL
    )

    assert after.hero.alignment == "heel"
    assert relations.find(after, "Hero", "Dex Harlow").heat == 85


def test_a_heel_turn_flips_back_and_resets_the_streak() -> None:
    state = _world()
    state = replace(
        state,
        roster=tuple(
            replace(w, alignment="heel", losing_streak=5) if w.is_player else w
            for w in state.roster
        ),
    )
    state = _open(
        state, _event("poor_form", choices=(Choice("heel_turn", "변신한다"),))
    )

    after = events.resolve(
        state, event_id_="evt:s1w1:poor_form:Hero", choice_code="heel_turn", balance=BAL
    )

    assert after.hero.alignment == "face"
    assert after.hero.losing_streak == 0


def test_accepting_an_ally_offer_writes_both_directions() -> None:
    state = _open(
        _with_relation(_world(), kind=RelationKind.ALLY, heat=20),
        _event("ally_offer", choices=(Choice("accept", "받아들인다"),)),
    )

    after = events.resolve(
        state, event_id_="evt:s1w1:ally_offer:Hero", choice_code="accept", balance=BAL
    )

    assert relations.find(after, "Hero", "Dex Harlow").kind == RelationKind.ALLY
    assert relations.find(after, "Dex Harlow", "Hero").kind == RelationKind.ALLY


def test_accepting_a_tag_offer_creates_a_team_that_booking_can_find() -> None:
    """관계 변화가 **대진에 닿는다** — 수치만 바뀌고 끝나지 않는다(§P0)."""
    state = _open(
        _with_relation(_world(), kind=RelationKind.ALLY, heat=55),
        _event("tag_team_offer", choices=(Choice("accept", "팀을 짠다"),)),
    )

    after = events.resolve(
        state,
        event_id_="evt:s1w1:tag_team_offer:Hero",
        choice_code="accept",
        balance=BAL,
    )

    assert relations.tag_partner(after, "Hero") == "Dex Harlow"


def test_declining_an_offer_costs_trust_and_is_written_down() -> None:
    state = _open(
        _with_relation(_world(), kind=RelationKind.ALLY, heat=40),
        _event("ally_offer", choices=(Choice("decline", "거절한다"),)),
    )

    after = events.resolve(
        state, event_id_="evt:s1w1:ally_offer:Hero", choice_code="decline", balance=BAL
    )

    tie = relations.find(after, "Hero", "Dex Harlow")
    assert tie.heat == 22
    assert "제안을 거절했다" in tie.history


def test_betraying_flips_the_relationship_and_turns_heel() -> None:
    state = _open(
        _with_relation(_world(), kind=RelationKind.ALLY, heat=10),
        _event("betrayal", choices=(Choice("betray", "먼저 등을 돌린다"),)),
    )

    after = events.resolve(
        state, event_id_="evt:s1w1:betrayal:Hero", choice_code="betray", balance=BAL
    )

    assert relations.find(after, "Dex Harlow", "Hero").kind == RelationKind.RIVAL
    assert after.hero.alignment == "heel"


def test_mending_restores_trust() -> None:
    state = _open(
        _with_relation(_world(), kind=RelationKind.ALLY, heat=10),
        _event("betrayal", choices=(Choice("mend", "관계를 회복한다"),)),
    )

    after = events.resolve(
        state, event_id_="evt:s1w1:betrayal:Hero", choice_code="mend", balance=BAL
    )

    assert relations.find(after, "Hero", "Dex Harlow").heat == 35


def test_accepting_a_title_offer_books_next_week() -> None:
    """선택이 **다음 경기**를 바꾼다 — 기회가 상태에 남는다."""
    state = _open(
        _world(),
        _event("title_offer", choices=(Choice("accept", "받아들인다"),), other=None),
    )

    after = events.resolve(
        state, event_id_="evt:s1w1:title_offer:Hero", choice_code="accept", balance=BAL
    )

    assert "shot:s1w2" in after.applied


def test_declining_a_title_offer_costs_popularity_only() -> None:
    state = _open(
        _world(),
        _event("title_offer", choices=(Choice("decline", "거절한다"),), other=None),
    )

    after = events.resolve(
        state, event_id_="evt:s1w1:title_offer:Hero", choice_code="decline", balance=BAL
    )

    assert after.hero.popularity == state.hero.popularity - 3
    assert after.relationships == ()


# ── 사건 해결: 은퇴 계열 ──────────────────────────────────────────


def test_resting_through_an_event_heals_without_retiring() -> None:
    state = _world()
    state = replace(
        state,
        roster=tuple(
            replace(w, condition=30) if w.is_player else w for w in state.roster
        ),
    )
    state = _open(
        state, _event("decline", choices=(Choice("rest", "휴식한다"),), other=None)
    )

    after = events.resolve(
        state, event_id_="evt:s1w1:decline:Hero", choice_code="rest", balance=BAL
    )

    assert after.hero.condition > 30
    assert not after.hero.retired


def test_lightening_the_load_trades_skill_for_resilience() -> None:
    state = _world()
    state = replace(
        state,
        roster=tuple(
            replace(w, ability=Ability(in_ring=70, mic=50, stamina=60, resilience=50))
            if w.is_player
            else w
            for w in state.roster
        ),
    )
    state = _open(
        state,
        _event("decline", choices=(Choice("lighten", "강도를 낮춘다"),), other=None),
    )

    after = events.resolve(
        state, event_id_="evt:s1w1:decline:Hero", choice_code="lighten", balance=BAL
    )

    assert after.hero.ability.resilience == 54
    assert after.hero.ability.in_ring == 69


def test_declaring_a_final_season_is_intent_not_retirement() -> None:
    """§3.1 — 은퇴 의사와 확정은 다른 상태다."""
    state = _open(
        _world(),
        _event(
            "last_ride", choices=(Choice("final_season", "마지막 시즌"),), other=None
        ),
    )

    after = events.resolve(
        state,
        event_id_="evt:s1w1:last_ride:Hero",
        choice_code="final_season",
        balance=BAL,
    )

    assert after.hero.intent is not None
    assert after.hero.intent.final_season is True
    assert after.hero.intent.origin == "self"
    assert after.hero.retirement is None
    assert not after.hero.retired


def test_staying_withdraws_a_pending_intent() -> None:
    state = _world()
    state = replace(
        state,
        roster=tuple(
            replace(
                w,
                status=Status.RETIREMENT_PENDING,
                intent=RetirementIntent(
                    origin="offered",
                    cause=RetirementCause.AGE_DECLINE,
                    season=1,
                    week=1,
                ),
            )
            if w.is_player
            else w
            for w in state.roster
        ),
    )
    state = _open(
        state, _event("decline", choices=(Choice("stay", "현역 유지"),), other=None)
    )

    after = events.resolve(
        state, event_id_="evt:s1w1:decline:Hero", choice_code="stay", balance=BAL
    )

    assert after.hero.intent is None
    assert after.hero.status == Status.ACTIVE


def test_an_accepted_offer_is_recorded_as_such_not_as_a_request() -> None:
    """§3.1 — 선수가 요청한 은퇴와 게임이 제안해 받아들인 은퇴를 구별한다."""
    state = _open(
        _world(),
        _event("decline", choices=(Choice("retire", "은퇴한다"),), other=None),
    )

    after = events.resolve(
        state, event_id_="evt:s1w1:decline:Hero", choice_code="retire", balance=BAL
    )

    assert after.hero.retired
    assert after.hero.retirement.cause == RetirementCause.OFFER_ACCEPTED


def test_a_permanent_injury_is_recorded_as_medical() -> None:
    from kayfabe.domain.services.career_world import Injury, Severity

    state = _world()
    state = replace(
        state,
        roster=tuple(
            replace(
                w,
                injuries=(
                    Injury(
                        kind="목",
                        severity=Severity.CAREER_THREATENING,
                        season=1,
                        week=1,
                        weeks_out=30,
                        permanent=True,
                    ),
                ),
            )
            if w.is_player
            else w
            for w in state.roster
        ),
    )
    state = _open(
        state, _event("decline", choices=(Choice("retire", "은퇴한다"),), other=None)
    )

    after = events.resolve(
        state, event_id_="evt:s1w1:decline:Hero", choice_code="retire", balance=BAL
    )

    assert after.hero.retirement.cause == RetirementCause.MEDICAL


def test_retiring_through_an_event_keeps_the_record() -> None:
    """은퇴 선수를 지우지 않는다 — 전적·관계가 그대로 조회된다(§3.4 · §5)."""
    state = _with_relation(_world(), kind=RelationKind.RIVAL, heat=70)
    state = replace(
        state,
        roster=tuple(
            replace(w, wins=31, losses=12, reigns=("NXT Championship",))
            if w.is_player
            else w
            for w in state.roster
        ),
        titles=(Title(name="NXT Championship", brand="NXT", required_popularity=40),),
    )
    state = _open(
        state, _event("poor_form", choices=(Choice("retire", "은퇴한다"),), other=None)
    )

    after = events.resolve(
        state, event_id_="evt:s1w1:poor_form:Hero", choice_code="retire", balance=BAL
    )

    assert after.find("Hero") is not None
    assert after.hero.wins == 31
    assert after.hero.retirement.wins == 31
    assert after.hero.retirement.reigns == 1
    assert relations.find(after, "Hero", "Dex Harlow") is not None


def test_an_undefined_effect_is_loud() -> None:
    """**조용히 성공한 것처럼 보이지 않는다** — 화면이 "적용됐다" 고 믿으면 안 된다."""
    state = _open(_world(), _event("medical", choices=(Choice("나중에", "나중에"),)))

    with pytest.raises(ValueError, match="효과가 정의되지 않은 선택"):
        events.resolve(
            state, event_id_="evt:s1w1:medical:Hero", choice_code="나중에", balance=BAL
        )


# ── 재현성 ────────────────────────────────────────────────────────


def test_event_generation_is_reproducible_with_a_seed() -> None:
    """§3.2 — 확률 기반 로직은 테스트에서 재현할 수 있어야 한다."""
    base = _with_relation(_world(seed=777), kind=RelationKind.RIVAL, heat=95)

    first = events.generate(base, balance=BAL)
    second = events.generate(base, balance=BAL)

    assert [e.id for e in first.pending] == [e.id for e in second.pending]


def test_a_candidate_does_not_always_become_an_event() -> None:
    """**후보 ≠ 사건.** 뽑기를 한 번 더 거치므로 같은 조건이어도 매주 열리지 않는다.

    무게가 그대로 확률이라 `heat` 를 100으로 두면 항상 열린다(무게 1.3). 그래서
    임계값 바로 위(60 → 무게 0.9)에서 재 본다 — 여기서 열리지 않는 주가 있어야
    "임계값을 넘었다고 모두 발생" 이 아니다(§P0).
    """
    opened = [
        bool(
            events.generate(
                replace(
                    _with_relation(_world(seed=3), kind=RelationKind.RIVAL, heat=60),
                    week=week,
                ),
                balance=BAL,
            ).pending
        )
        for week in range(1, 40)
    ]

    assert any(opened)
    assert not all(opened)
