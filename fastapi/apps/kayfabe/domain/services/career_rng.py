"""결정론적 뽑기. **시드와 키에서 나온다 — 전역 난수를 쓰지 않는다.**

`random.random()` 이나 `hash()` 를 쓰면 안 된다. 두 함정이 있다:

1. `hash()` 는 프로세스마다 달라진다(`PYTHONHASHSEED`). 재기동 뒤 같은 세이브가
   다른 결과를 낸다 — `match_sim`·`career_run` 이 같은 함정을 적어 뒀다.
2. 전역 난수는 **호출 순서**에 결과가 묶인다. 저장·재접속이 있으면 순서를 재현할
   수 없고, 같은 요청을 재시도하면 다른 결과가 난다.

그래서 뽑기는 `(seed, key)` 의 순수 함수다. 사용자 요구 §3.2 — "테스트에서
재현할 수 있도록 난수 시드를 지정할 수 있어야 한다."
"""

from __future__ import annotations

import hashlib


def roll(seed: int, *parts: object) -> float:
    """0.0 이상 1.0 미만. **같은 인수면 항상 같은 값.**

    `parts` 에 시즌·주차·선수 이름·용도를 넣어 쓴다. 구분자로 널 바이트를 쓰는
    것은 `("a", "bc")` 와 `("ab", "c")` 가 같은 키가 되지 않게 하려는 것이다.
    """
    key = "\x00".join([str(seed), *(str(p) for p in parts)])
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def pick(seed: int, items: tuple[str, ...], *parts: object) -> str | None:
    """목록에서 하나. 비었으면 `None`.

    목록을 **정렬해서** 고른다 — 호출부가 넘긴 순서에 결과가 묶이면, 로스터를
    다른 순서로 읽어 온 재접속이 다른 상대를 뽑는다.
    """
    if not items:
        return None
    ordered = tuple(sorted(items))
    index = int(roll(seed, *parts) * len(ordered))
    return ordered[min(index, len(ordered) - 1)]


def span(seed: int, low: int, high: int, *parts: object) -> int:
    """`low`~`high` 사이 정수(양끝 포함)."""
    if high <= low:
        return low
    return low + int(roll(seed, *parts) * (high - low + 1))
