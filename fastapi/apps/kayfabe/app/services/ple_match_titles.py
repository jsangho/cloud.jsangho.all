"""위키 `stipN` → 화면 경기 제목. **사람이 확인한 규칙표다.**

`wiki_belt_names`·`wiki_event_titles`와 같은 자리다 — 코드가 규칙으로 만들어 낼 수
없고 사람이 대조해야 아는 값들의 집.

## 제목 규칙은 픽스처가 이미 정해 뒀다

`www/lib/wwe-ple-matches.ts` 머리주석:

    챔피언십 → belt명만, 기믹 → 기믹명, 일반 1v1 → 「Single Match」,
    태그 → 「Tag Team Match」

그래서 `Singles match for the World Heavyweight Championship`는
`World Heavyweight Championship`가 되고, 벨트가 안 걸린
`Singles match`는 `Single Match`가 된다.

## 머니 인 더 뱅크는 벨트가 아니다

`Money in the Bank ladder match for a men's championship match contract`에서
`for a ...` 뒤는 벨트 이름이 아니라 **계약서**다. 규칙대로 잘라 쓰면
`Men's Championship Match Contract`라는 없는 벨트가 화면에 선다. 이 대회만
따로 잡는 이유다 — 실제 픽스처 값도 `Men's Money in the Bank Ladder Match`다.
"""

from __future__ import annotations

import re

#: `... for the <벨트>` · `... for a <무언가>` — 뒤쪽이 걸린 것이다.
_FOR = re.compile(r"\s+for\s+(?:the|a|an)\s+(.+)$", re.IGNORECASE)

#: MITB 래더는 벨트가 아니라 계약서를 건다.
_MITB = re.compile(r"money in the bank ladder match", re.IGNORECASE)
_MENS = re.compile(r"\bmen'?s\b", re.IGNORECASE)
_WOMENS = re.compile(r"\bwomen'?s\b", re.IGNORECASE)

#: 벨트가 안 걸린 기본형. 왼쪽이 위키 표기, 오른쪽이 이 앱의 표기다.
_PLAIN: dict[str, str] = {
    "singles match": "Single Match",
    "tag team match": "Tag Team Match",
    "six-man tag team match": "Six-Man Tag Team Match",
    "trios match": "Trios Match",
    "street fight": "Street Fight",
    "unsanctioned match": "Unsanctioned Match",
    "submission match": "Submission Match",
}


def title_from_stipulation(stipulation: str | None) -> str | None:
    """경기 제목. **모르면 `None`이고, 그때는 사람이 적는다.**

    지어내지 않는 이유는 제목이 단순한 장식이 아니기 때문이다 — `apply_results`가
    경기 제목과 **정확 일치**로 벨트를 찾는다(`wiki_belt_names` 독스트링). 엉뚱한
    제목을 넣으면 그 경기의 결과가 어느 벨트에도 안 닿는다.
    """
    if not stipulation:
        return None
    text = stipulation.strip()

    if _MITB.search(text):
        if _WOMENS.search(text):
            return "Women's Money in the Bank Ladder Match"
        if _MENS.search(text):
            return "Men's Money in the Bank Ladder Match"
        return "Money in the Bank Ladder Match"

    hit = _FOR.search(text)
    if hit:
        belt = hit.group(1).strip().rstrip(".")
        # `a men's championship match contract`처럼 벨트가 아닌 것은 위에서 걸렀다.
        # 여기 남는 것은 실제 벨트 이름이므로 그대로 쓴다 — 대문자도 위키 표기대로다.
        return belt or None

    plain = _PLAIN.get(text.casefold())
    if plain:
        return plain
    # 모르는 기믹은 **원문 그대로 올린다.** 번역하거나 줄이면 벨트 대조가 깨지고,
    # 무엇보다 사람이 diff에서 "이건 내가 봐야 하는 줄"이라고 알아볼 수 있어야 한다.
    return text
