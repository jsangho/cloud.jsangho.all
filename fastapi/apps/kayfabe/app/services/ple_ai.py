"""PLE AI 승패 예측 — 북메이커 배당(낮은 쪽) 기준 favorite pick."""

from __future__ import annotations

from typing import Any


def derive_ai_pick_from_card(card: dict[str, Any]) -> tuple[str, str] | None:
    """카드 JSON에서 AI 예측 pick(left/right 또는 index 문자열)과 표시 이름."""
    fmt = card.get("format")
    if fmt == "singles":
        left = card.get("left") or {}
        right = card.get("right") or {}
        odds = card.get("bookmakerDecimal") or {}
        if not isinstance(odds, dict):
            return None
        try:
            left_odds = float(odds.get("left", 0))
            right_odds = float(odds.get("right", 0))
        except (TypeError, ValueError):
            return None
        if left_odds <= 0 or right_odds <= 0:
            return None
        if left_odds <= right_odds:
            return "left", str(left.get("name", "Left"))
        return "right", str(right.get("name", "Right"))

    if fmt == "multi":
        competitors = card.get("competitors") or []
        odds = card.get("bookmakerDecimal")
        if (
            not competitors
            or not isinstance(odds, list)
            or len(odds) != len(competitors)
        ):
            return None
        try:
            decimals = [float(x) for x in odds]
        except (TypeError, ValueError):
            return None
        if any(d <= 0 for d in decimals):
            return None
        best = min(range(len(decimals)), key=lambda i: decimals[i])
        return str(best), str(competitors[best].get("name", f"#{best + 1}"))

    return None


def grade_ai_correct(ai_pick: str | None, winner_pick: str | None) -> bool | None:
    if not ai_pick or not winner_pick:
        return None
    return ai_pick == winner_pick
