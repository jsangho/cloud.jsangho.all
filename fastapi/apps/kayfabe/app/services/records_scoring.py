"""PLE 선수 기록 계산 — MatchBoardSchema/ORM card_json 기준 순수 함수."""

from __future__ import annotations

import re

from kayfabe.adapter.inbound.api.schemas.ple_events_schema import (
    CompetitorSchema,
    MatchBoardSchema,
)
from kayfabe.adapter.inbound.api.schemas.ple_matches_schema import (
    CompetitorMatchRecordSchema,
    MatchResultKind,
)
from kayfabe.app.services.competitor_roster import (
    individual_in_roster_entry,
    unique_individuals,
)

RUMBLE_OTHER_LABEL = "다른 선수"


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip())


def is_placeholder_competitor(name: str) -> bool:
    n = normalize_name(name)
    return len(n) == 0 or n == RUMBLE_OTHER_LABEL


def extract_participants(match: MatchBoardSchema) -> list[str]:
    if match.format == "multi":
        return [
            normalize_name(c.name)
            for c in (match.competitors or [])
            if not is_placeholder_competitor(c.name)
        ]
    out: list[str] = []
    if match.left and match.left.name:
        out.append(normalize_name(match.left.name))
    if match.right and match.right.name:
        out.append(normalize_name(match.right.name))
    return [n for n in out if not is_placeholder_competitor(n)]


def match_includes_competitor(match: MatchBoardSchema, name: str) -> bool:
    target = normalize_name(name)
    if match.format == "multi":
        return any(normalize_name(c.name) == target for c in (match.competitors or []))
    left = normalize_name(match.left.name) if match.left and match.left.name else ""
    right = normalize_name(match.right.name) if match.right and match.right.name else ""
    return left == target or right == target


def _was_champion(competitor: CompetitorSchema, name: str) -> bool:
    return normalize_name(competitor.name) == normalize_name(name) and bool(
        competitor.is_champion
    )


def was_champion_in_match(match: MatchBoardSchema, name: str) -> bool:
    if match.format == "multi":
        return any(_was_champion(c, name) for c in (match.competitors or []))
    if match.left and _was_champion(match.left, name):
        return True
    if match.right and _was_champion(match.right, name):
        return True
    return False


def get_winner_name(match: MatchBoardSchema) -> str | None:
    if match.result and match.result.winner_name:
        return match.result.winner_name

    if not match.result:
        return None

    if match.format == "multi":
        idx = match.result.winner_index
        if idx is not None and idx >= 0:
            competitors = match.competitors or []
            if idx < len(competitors):
                return competitors[idx].name
        return None

    side = match.result.winner_side
    if side == "left" and match.left:
        return match.left.name
    if side == "right" and match.right:
        return match.right.name
    return None


def compute_outcome(match: MatchBoardSchema, name: str) -> MatchResultKind:
    if not match.result:
        return "pending"
    winner = get_winner_name(match)
    if not winner:
        return "no-contest"
    return "win" if normalize_name(winner) == normalize_name(name) else "loss"


def extract_opponents(match: MatchBoardSchema, name: str) -> list[str]:
    target = normalize_name(name)
    return [p for p in extract_participants(match) if normalize_name(p) != target]


def to_match_record(
    *,
    slug: str,
    ple_label: str,
    match: MatchBoardSchema,
    name: str,
) -> CompetitorMatchRecordSchema:
    return CompetitorMatchRecordSchema(
        slug=slug,
        ple_label=ple_label,
        match_key=match.id,
        title=match.title,
        format=match.format,
        result=compute_outcome(match, name),
        winner_name=get_winner_name(match),
        opponents=extract_opponents(match, name),
        participants=extract_participants(match),
        was_champion=was_champion_in_match(match, name),
    )


def roster_names_from_card_json(card_json: str) -> list[str]:
    import json

    try:
        card = json.loads(card_json)
    except json.JSONDecodeError:
        return []

    names: list[str] = []
    fmt = card.get("format")
    if fmt == "multi":
        for c in card.get("competitors") or []:
            n = c.get("name") if isinstance(c, dict) else None
            if isinstance(n, str) and not is_placeholder_competitor(n):
                names.append(normalize_name(n))
    else:
        for key in ("left", "right"):
            side = card.get(key)
            if isinstance(side, dict):
                n = side.get("name")
                if isinstance(n, str) and not is_placeholder_competitor(n):
                    names.append(normalize_name(n))
    return names


def names_from_card_json(card_json: str) -> list[str]:
    """카드 로스터명을 개인 링네임으로 펼친 목록."""
    return unique_individuals(roster_names_from_card_json(card_json))


def competitor_name_in_card_json(*, card_json: str, name: str) -> bool:
    target = normalize_name(name)
    for roster_name in roster_names_from_card_json(card_json):
        if individual_in_roster_entry(roster_name, target):
            return True
    return False


def _card_sides(card: dict, fmt: str) -> list[tuple[str | int, dict]]:
    if fmt == "multi":
        return [
            (idx, c)
            for idx, c in enumerate(card.get("competitors") or [])
            if isinstance(c, dict)
        ]
    sides: list[tuple[str | int, dict]] = []
    for key in ("left", "right"):
        side = card.get(key)
        if isinstance(side, dict) and isinstance(side.get("name"), str):
            if not is_placeholder_competitor(side["name"]):
                sides.append((key, side))
    return sides


def _find_individual_side(
    card: dict, fmt: str, individual: str
) -> tuple[str | int, dict, str] | None:
    target = normalize_name(individual)
    for side_id, side in _card_sides(card, fmt):
        roster_name = side.get("name")
        if isinstance(roster_name, str) and individual_in_roster_entry(
            roster_name, target
        ):
            return side_id, side, normalize_name(roster_name)
    return None


def _opponents_for_individual(card: dict, fmt: str, individual: str) -> list[str]:
    found = _find_individual_side(card, fmt, individual)
    if not found:
        return []
    side_id, _, _ = found
    opponents: list[str] = []
    for other_id, other in _card_sides(card, fmt):
        if other_id == side_id:
            continue
        roster_name = other.get("name")
        if isinstance(roster_name, str) and not is_placeholder_competitor(roster_name):
            opponents.append(normalize_name(roster_name))
    return opponents


def derive_match_record_from_orm(
    *,
    event_slug: str,
    event_label: str,
    match_key: str,
    title: str,
    format: str,
    card_json: str,
    winner_pick: str | None,
    winner_name: str | None,
    status: str | None,
    name: str,
) -> CompetitorMatchRecordSchema:
    """
    ORM(PleMatchModel) 행에서 records 응답을 만든다.
    - singles: winner_pick = left/right
    - multi: winner_pick = index string ("0"..)
    """
    import json

    try:
        card = json.loads(card_json) if card_json else {}
    except json.JSONDecodeError:
        card = {}

    fmt = (format or card.get("format") or "").strip()
    participants = roster_names_from_card_json(card_json) if card_json else []
    was_champion = False
    found_side = _find_individual_side(card, fmt, name)
    if found_side:
        _, side, _ = found_side
        was_champion = bool(side.get("isChampion"))

    opponents = _opponents_for_individual(card, fmt, name)

    derived_winner: str | None = winner_name
    if not derived_winner and winner_pick:
        if fmt == "multi":
            try:
                idx = int(winner_pick)
                comps = card.get("competitors") or []
                if 0 <= idx < len(comps) and isinstance(comps[idx], dict):
                    wn = comps[idx].get("name")
                    if isinstance(wn, str):
                        derived_winner = wn
            except ValueError:
                derived_winner = None
        else:
            if winner_pick == "left":
                left = card.get("left")
                if isinstance(left, dict) and isinstance(left.get("name"), str):
                    derived_winner = left["name"]
            elif winner_pick == "right":
                right = card.get("right")
                if isinstance(right, dict) and isinstance(right.get("name"), str):
                    derived_winner = right["name"]

    # outcome
    if not winner_pick and not derived_winner:
        outcome: MatchResultKind = "pending"
    elif not derived_winner:
        outcome = "no-contest"
    else:
        outcome = "win" if individual_in_roster_entry(derived_winner, name) else "loss"

    # If DB status says finished but we can't derive a winner, treat as no-contest
    st = (status or "").strip().lower()
    if st == "finished" and outcome == "pending":
        outcome = "no-contest" if not derived_winner else outcome

    return CompetitorMatchRecordSchema(
        slug=event_slug,
        ple_label=event_label,
        match_key=match_key,
        title=title,
        format="multi" if fmt == "multi" else "singles",
        result=outcome,
        winner_name=derived_winner,
        opponents=opponents,
        participants=participants,
        was_champion=was_champion,
    )
