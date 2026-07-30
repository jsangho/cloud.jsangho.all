"""PLE 사용자 예측 채점 — 경기 유형별 점수·pick 적중."""

from __future__ import annotations

from typing import Any

from kayfabe.app.services.ple_ai import grade_ai_correct

# 적중 시 부여 점수 (오답·미채점 0)
#
# 맞힐 확률의 역수를 기준으로 하되 log2(참가자 수)로 눌러 꼬리를 압축했다. 순수
# 역배당(점수=참가자 수)이면 로열럼블 한 경기가 싱글 15경기와 맞먹어 운이 실력을
# 덮는다. 지금 배분은 럼블을 싱글의 5배로 제한한다.
# 5의 배수 단위는 상점 가격·보너스를 소수점 없이 다루기 위한 것이다.
POINTS_SINGLE_OR_TAG = 10
POINTS_TRIPLE_THREAT = 20
POINTS_FATAL_FOUR_WAY = 25
POINTS_ELIMINATION_CHAMBER = 30
POINTS_MITB_LADDER = 30
POINTS_ROYAL_RUMBLE = 50

# 타이틀이 걸린 경기에 형식 점수 위로 가산한다. 난이도가 아니라 스테이크에 대한
# 보너스이므로 형식과 독립이다 — 챔피언십 트리플 스렛은 20+5=25가 된다.
POINTS_CHAMPIONSHIP_BONUS = 5


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
    """경기 유형별 만점 (오답 시 0점은 예측 채점 단계에서 처리).

    형식 점수 + 타이틀 스테이크 보너스로 계산한다.
    """
    base = _derive_format_point_value(
        title,
        fmt,
        match_key=match_key,
        competitor_count=competitor_count,
    )
    if "championship" in title.casefold():
        return base + POINTS_CHAMPIONSHIP_BONUS
    return base


def _derive_format_point_value(
    title: str,
    fmt: str,
    *,
    match_key: str = "",
    competitor_count: int = 0,
) -> int:
    """형식만 보고 정하는 기본 점수.

    우선순위: 로얄럼블 > 엘리미네이션챔버 > MITB 래더 > 페이탈4way > 트리플 > 태그/싱글.
    MITB는 참가자가 6~8명이라 챔버와 같은 난이도로 본다. 참가자 수 기반 분기가
    먼저 삼켜 버리지 않도록 4way·트리플보다 위에 둔다.
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

    if "money in the bank" in t and "ladder" in t:
        return POINTS_MITB_LADDER

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

    if (
        "tag team match" in t
        or "six-man tag" in t
        or "6-man tag" in t
        or "mixed tag" in t
        or "tag match" in t
        or t.startswith("tag team")
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
