"""챔피언십 매치 vs 비타이틀 매치(MITB 래더, 로얄럼블 등) 구분."""

from __future__ import annotations

import re


def is_mitb_ladder_match(title: str, match_key: str = "") -> bool:
    """MITB 서류(브리프케이스) 래더매치 — 챔피언십 획득이 아님."""
    t = title.casefold()
    k = match_key.casefold()

    if "money in the bank" in t and "ladder" in t:
        return True
    if re.search(r"(men's|women's)\s+money in the bank", t):
        return True
    if "mitb" in k and "ladder" in t:
        return True
    if re.search(r"mitb\d+-women$|mitb\d+-men$", k):
        return True
    return False


def is_non_title_special_match(title: str, match_key: str = "") -> bool:
    """챔피언십이 걸리지 않은 스페셜 매치."""
    if is_mitb_ladder_match(title, match_key):
        return True

    t = title.casefold()
    k = match_key.casefold()

    if "royal rumble" in t or " rumble match" in t:
        return True
    if "rumble" in k and ("-rumble" in k or k.endswith("rumble")):
        return True
    if t in {"single match", "tag team match", "street fight", "unsanctioned match"}:
        return True
    if "king of the ring" in t and "championship" not in t:
        return True
    if "queen of the ring" in t and "championship" not in t:
        return True
    return False


def is_championship_match(title: str, match_key: str = "") -> bool:
    """챔피언십이 걸린 경기 (MITB 래더·로얄럼블 등 제외)."""
    if is_non_title_special_match(title, match_key):
        return False
    t = title.casefold()
    return "championship" in t or "챔피언십" in t


def extract_belt_name(title: str) -> str:
    """경기 제목에서 벨트명 추출."""
    belt = title.strip()
    belt = re.sub(r"\s+—\s+.*$", "", belt)
    belt = re.sub(r"\s+match\s*$", "", belt, flags=re.IGNORECASE)
    return belt.strip()
