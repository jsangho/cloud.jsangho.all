"""ORM ↔ app DTO 변환 (outbound 전용)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kayfabe.app.dtos.ple_events_dto import (
    PleEventReadQuery,
    PleEventSnapshotQuery,
    PleMatchReadQuery,
    PleMatchSnapshotQuery,
)

if TYPE_CHECKING:
    from kayfabe.adapter.outbound.orm.ple_orm import PleEventModel, PleMatchModel


def event_to_snapshot(event: PleEventModel) -> PleEventSnapshotQuery:
    return PleEventSnapshotQuery(
        id=event.id,
        slug=event.slug,
        status=event.status,
        finished_at=event.finished_at,
        matches=[
            PleMatchSnapshotQuery(id=m.id, match_key=m.match_key, status=m.status)
            for m in event.matches
        ],
    )


def match_to_read(row: PleMatchModel) -> PleMatchReadQuery:
    return PleMatchReadQuery(
        id=row.id,
        match_key=row.match_key,
        title=row.title,
        format=row.format,  # type: ignore[arg-type]
        card_variant=row.card_variant,
        sort_order=row.sort_order,
        card_json=row.card_json,
        status=row.status,
        winner_pick=row.winner_pick,
        winner_name=row.winner_name,
        ai_pick=row.ai_pick,
        ai_pick_name=row.ai_pick_name,
        ai_correct=row.ai_correct,
        point_value=row.point_value,
    )


def event_to_read(event: PleEventModel) -> PleEventReadQuery:
    return PleEventReadQuery(
        slug=event.slug,
        label=event.label,
        month=event.month,
        year=event.year,
        status=event.status,
        finished_at=event.finished_at,
        updated_at=event.updated_at,
        matches=[
            match_to_read(m) for m in sorted(event.matches, key=lambda x: x.sort_order)
        ],
    )


def card_command_to_json(card) -> dict:
    """MatchCardSyncCommand → card_json dict (camelCase keys)."""

    def competitor(c):
        if c is None:
            return None
        out = {"name": c.name}
        if c.is_champion is not None:
            out["isChampion"] = c.is_champion
        return out

    payload: dict = {
        "id": card.id,
        "title": card.title,
        "cardVariant": card.card_variant,
        "format": card.format,
    }
    if card.left is not None:
        payload["left"] = competitor(card.left)
    if card.right is not None:
        payload["right"] = competitor(card.right)
    if card.competitors:
        payload["competitors"] = [competitor(c) for c in card.competitors]
    if card.bookmaker_decimal is not None:
        payload["bookmakerDecimal"] = card.bookmaker_decimal
    if card.result is not None:
        r = card.result
        res: dict = {}
        if r.winner_side is not None:
            res["winnerSide"] = r.winner_side
        if r.winner_index is not None:
            res["winnerIndex"] = r.winner_index
        if r.winner_name is not None:
            res["winnerName"] = r.winner_name
        payload["result"] = res
    return payload
