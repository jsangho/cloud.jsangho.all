"""위키가 적은 이름 ↔ 우리 DB가 적은 이름. **순수 함수다.**

## 왜 별칭표가 아니라 정규화인가

벨트는 스무 개뿐이라 `wiki_belt_names` 처럼 사람이 전수로 짝을 적을 수 있다. 선수는
178명이고 계속 는다 — 표로 들면 새 선수가 들어올 때마다 조용히 빗나간다. 그래서
**표기 규칙만 벗기고 나머지는 글자 그대로 본다.**

## 무엇을 벗기는가 (2026-10-07 전수 실측에서 실제로 걸린 것만)

63건을 대조했을 때 어긋난 것은 둘뿐이었고, 둘 다 승자는 맞고 표기만 달랐다.

    "The Demon" Finn Bálor   ↔  Finn Bálor     따옴표로 감싼 페르소나 접두사
    Wren Sinclair            ↔  Sinclair       성만 적은 짧은 표기

여기에 더해 `&` ↔ `and`, 이름 순서, 팀명 ↔ 멤버 나열이 갈렸는데 그것은
`ple_card_parser._winner_names`가 **양쪽을 다 담아** 흡수한다.

## 무엇을 벗기지 않는가

**이름 안의 숫자와 접미사는 남긴다.** `Dominik Mysterio`와 `Rey Mysterio`는 성이
같고, 성만으로 맞추면 둘이 한 사람이 된다. 그래서 짧은 표기는 **한쪽이 다른 쪽의
마지막 낱말일 때만** 받아 주고(`Sinclair` ⊂ `Wren Sinclair`), 가운데 낱말이나
부분 문자열로는 맞추지 않는다.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

#: 따옴표로 감싼 페르소나 접두사 — `"The Demon" Finn Bálor`. 곧은 따옴표와 둥근
#: 따옴표가 섞여 들어온다.
_PERSONA = re.compile(r'^[\'"“”‘’]\s*[^\'"“”‘’]{1,30}[\'"“”‘’]\s*')

#: 맨 앞 관사. `The Usos` ↔ `Usos`.
_LEADING_THE = re.compile(r"^the\s+", re.IGNORECASE)

#: 이름 구분자. `ple_card_parser._NAME_SEP`와 같은 규칙이다 — DB 쪽 문자열도
#: 같은 방식으로 쪼개야 양쪽이 같은 모양이 된다.
_NAME_SEP = re.compile(r",\s*and\s+|,\s*|\s+and\s+|\s*&\s*|\s*/\s*", re.IGNORECASE)

#: 낱말이 아닌 것. 악센트를 푼 뒤에 돌린다.
_NON_WORD = re.compile(r"[^a-z0-9 ]+")


def normalize_wrestler_name(name: str) -> str:
    """대조용 표기로 줄인다. 빈 문자열이면 대조에 쓰지 않는다.

    악센트를 푼다 — `Finn Bálor` 와 `Finn Balor` 가 같은 사람이고, 위키와 우리
    카탈로그가 서로 다른 쪽으로 적는다.
    """
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = _PERSONA.sub("", text.strip())
    text = _LEADING_THE.sub("", text.strip())
    text = _NON_WORD.sub(" ", text.casefold())
    return " ".join(text.split())


def split_names(text: str) -> tuple[str, ...]:
    """여러 사람이 적힌 한 칸을 사람별로 쪼갠다 (`A, B & C`)."""
    return tuple(part.strip() for part in _NAME_SEP.split(text) if part.strip())


def _is_short_form(a: str, b: str) -> bool:
    """한쪽이 다른 쪽의 **마지막 낱말**인가 — `Sinclair` ⊂ `Wren Sinclair`.

    가운데 낱말은 받지 않는다. `Mysterio` 로 `Rey Mysterio` 와 `Dominik Mysterio` 를
    가를 수 없는 것은 어쩔 수 없지만, 적어도 `Rey` 가 `Rey Mysterio` 를 끌어오는 일은
    막는다 — 링네임이 한 낱말인 선수가 많아서 앞 낱말 일치는 충돌이 잦다.
    """
    short, long = (a, b) if len(a) < len(b) else (b, a)
    if not short or short == long:
        return False
    return long.split()[-1] == short and " " not in short


def names_agree(wiki_names: Iterable[str], db_name: str) -> bool:
    """위키가 읽은 승자 이름들과 DB가 들고 있는 승자명이 같은 사람(들)을 가리키는가.

    **한 사람이라도 정확히 겹치면 같다고 본다.** 팀 경기에서 양쪽이 적는 멤버 수가
    다를 수 있기 때문이다(팀명만 적기도, 멤버를 다 적기도 한다).

    🔴 **이 함수만으로 경기를 짝짓지 않는다.** 승자 이름만 보고 맞추면 같은 선수가
    두 경기에서 이긴 대회에서 엉뚱한 줄을 집는다. 경기 짝짓기는 **참가자**로 하고,
    이 함수는 그렇게 짝지은 줄의 승자를 확인하는 데만 쓴다.
    """
    left = {normalize_wrestler_name(n) for n in wiki_names}
    left.discard("")
    right = {normalize_wrestler_name(n) for n in split_names(db_name)}
    right.discard("")
    if not left or not right:
        return False
    if left & right:
        return True
    return any(_is_short_form(a, b) for a in left for b in right)
