"""PLE 사용자 예측 채점 — 경기 유형별 점수·pick 적중."""

from __future__ import annotations

from typing import Any

from kayfabe.app.services.ple_ai import grade_ai_correct

# 적중 시 부여 점수 (오답·미채점 0)
POINTS_SINGLE_OR_TAG = 1
POINTS_CHAMPIONSHIP = 2
POINTS_TRIPLE_THREAT = 3
POINTS_FATAL_FOUR_WAY = 4
POINTS_ELIMINATION_CHAMBER = 4
POINTS_ROYAL_RUMBLE = 5


def grade_pick_correct(pick: str | None, winner_pick: str | None) -> bool | None:
    """예측 pick이 방송 승자와 일치하면 True, 미확정이면 None."""
    return grade_ai_correct(pick, winner_pick)


def competitor_count_from_card(card: dict[str, Any], fmt: str) -> int:
    if fmt == "multi":
        return len(card.get("competitors") or [])
    return 2


def derive_match_point_value(
    title: str,
    fmt: str,
    *,
    match_key: str = "",
    competitor_count: int = 0,
) -> int:
    """
    경기 유형별 만점 (오답 시 0점은 예측 채점 단계에서 처리).

    우선순위: 로얄럼블 > 엘리미네이션챔버 > 페이탈4way > 트리플 > 챔피언십 > 태그/싱글.
    """
    t = title.casefold()
    key = match_key.casefold()
    n = competitor_count

    if (
        "royal rumble" in t
        or " rumble match" in t
        or ("rumble" in key and ("-rumble" in key or key.endswith("rumble")))
    ):
        return POINTS_ROYAL_RUMBLE

    if "elimination chamber" in t or " chamber match" in t:
        return POINTS_ELIMINATION_CHAMBER

    if (
        "fatal 4-way" in t
        or "fatal 4 way" in t
        or "fatal four-way" in t
        or "fatal four way" in t
        or "fatal 4" in t
    ):
        return POINTS_FATAL_FOUR_WAY
    if fmt == "multi" and n == 4:
        return POINTS_FATAL_FOUR_WAY

    if "triple threat" in t or "triple-threat" in t:
        return POINTS_TRIPLE_THREAT
    if fmt == "multi" and n == 3:
        return POINTS_TRIPLE_THREAT

    if "money in the bank" in t and "ladder" in t:
        return POINTS_SINGLE_OR_TAG

    if "championship" in t:
        return POINTS_CHAMPIONSHIP

    if (
        "tag team match" in t
        or "six-man tag" in t
        or "6-man tag" in t
        or "mixed tag" in t
        or ("tag match" in t and "championship" not in t)
        or (t.startswith("tag team") and "championship" not in t)
    ):
        return POINTS_SINGLE_OR_TAG

    if "single match" in t:
        return POINTS_SINGLE_OR_TAG

    if fmt == "singles":
        return POINTS_SINGLE_OR_TAG

    if fmt == "multi":
        if n >= 6 and "rumble" in t:
            return POINTS_ROYAL_RUMBLE
        if n >= 6 and "chamber" in t:
            return POINTS_ELIMINATION_CHAMBER

    return POINTS_SINGLE_OR_TAG


def points_for_prediction(is_correct: bool | None, match_point_value: int) -> int:
    return match_point_value if is_correct is True else 0
