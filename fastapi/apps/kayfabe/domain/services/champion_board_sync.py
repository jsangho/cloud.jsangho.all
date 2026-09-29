"""위키가 말하는 현 챔피언을 보드 기준선에 얹는 **순수 함수**.

`championship_succession.apply_results`와 짝이다. 둘은 같은 기준선(`TitleReign`)을
고치지만 재료와 범위가 다르다:

    apply_results     PLE 경기 결과      좁고 빠르다 — 결과가 들어오면 즉시 따라온다
    plan_wiki_sync    위키 현 챔피언 표  넓고 늦다 — Raw·하우스쇼까지 메운다

**둘의 순서가 중요하다.** 동기화가 기준일(`as_of`)을 읽은 날로 올리므로, 그 이전
PLE는 `apply_results`의 기준일 관문이 건너뛴다 — 위키가 이미 그 결과를 반영한 표를
주기 때문이다. 같은 변경을 두 번 얹어 방어를 재위로 둔갑시키는 일이 그래서 없다.

## 무엇을 바꾸고 무엇을 안 바꾸는가

- **챔피언·획득일·팀 이름이 같으면 그 줄은 손대지 않는다.** 표기가 조금 달라졌다고
  줄을 갈아 끼우면 보드 순서와 `won_event`가 이유 없이 흔들린다.
- **바뀐 줄의 `won_event`는 위키가 준 것으로 덮는다**(못 뽑았으면 비운다). 옛 대회명을
  남기면 보드가 `Chad Gable · 8/02 · Raw`처럼 **두 사실을 섞은 거짓**을 말한다.
- **위키에 없는 벨트는 지우지 않는다.** 폐지인지 문서 누락인지 표가 말해 주지 않으므로
  `missing_on_wiki`로 알리고 사람이 정한다 — Speed 벨트 둘이 그렇게 걸려 폐지로 확인돼
  카탈로그에서 지워졌다(2026-09-29).
- **보드에 없는 위키 행도 추가하지 않는다.** 보드 한 줄에는 위키가 안 주는 칸
  (`brand_id`·`tier`)이 있어서 지어내야 하고, 새 벨트가 생기는 일은 드물다.

## 방어 판정을 여기서 하지 않는 이유

위키의 `Date won`은 **그 재위가 시작된 날**이다. 방어가 열 번 있었어도 그 칸은 안
바뀌므로, 날짜가 달라졌다면 그것은 표기 차이가 아니라 우리 쪽이 틀린 것이다. 그래서
`apply_results`가 하는 "승자가 현 챔피언이면 날짜를 건드리지 않는다" 판정이 이쪽에는
필요하지 않다 — 위키 값을 그대로 받는 것이 옳다.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from kayfabe.domain.services.champion_table_parser import WikiChampionRow
from kayfabe.domain.services.championship_succession import TitleReign

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class BoardUpdate:
    """위키가 고친 한 줄. 보고와 로그에 쓴다."""

    belt_name: str
    before: TitleReign
    after: TitleReign


@dataclass(frozen=True)
class WikiSyncPlan:
    """**쓰기는 부르는 쪽이 한다.** 이 함수는 무엇을 쓸지만 정한다."""

    reigns: tuple[TitleReign, ...]
    #: 보드가 이 날짜의 위키와 일치한다. 아무것도 안 바뀌어도 올라간다 — 갱신된 것은
    #: 값이 아니라 **"언제까지 확인했는가"** 다.
    as_of: str
    updated: tuple[BoardUpdate, ...] = ()
    #: 위키와 이미 같던 벨트 이름.
    unchanged: tuple[str, ...] = ()
    #: 위키 표에 없던 보드 벨트. 지우지 않고 알린다.
    missing_on_wiki: tuple[str, ...] = ()
    #: 보드에 없던 위키 벨트. 추가하지 않고 알린다.
    unmatched_wiki: tuple[str, ...] = ()


def plan_wiki_sync(
    baseline: Sequence[TitleReign],
    wiki_rows: Sequence[WikiChampionRow],
    *,
    as_of: str,
    aliases: Mapping[str, str],
) -> WikiSyncPlan:
    """기준선과 위키 표를 맞춰 본다. **날짜를 못 읽은 위키 행은 쓰지 않는다.**

    `aliases`는 위키 이름 → 보드 이름이다(`app.services.wiki_belt_names`). 도메인이
    app을 import할 수 없어 주입받는다 — `apply_results`가 `is_title_match`를 받는 것과
    같은 이유다.
    """
    alias = {_normalized(k): _normalized(v) for k, v in aliases.items()}
    by_belt: dict[str, WikiChampionRow] = {}
    for row in wiki_rows:
        key = _normalized(row.belt_name)
        by_belt[alias.get(key, key)] = row

    reigns: list[TitleReign] = []
    updated: list[BoardUpdate] = []
    unchanged: list[str] = []
    missing: list[str] = []
    matched: set[str] = set()

    for reign in baseline:
        key = _normalized(reign.belt_name)
        row = by_belt.get(key)
        if row is None:
            missing.append(reign.belt_name)
            reigns.append(reign)
            continue

        matched.add(key)
        if not row.won_at:
            # 획득일을 못 읽은 행이다. 챔피언만 바꾸면 "언제부터"가 거짓이 되므로
            # 아무것도 안 바꾸고 못 읽은 것으로 남긴다.
            missing.append(reign.belt_name)
            reigns.append(reign)
            continue

        if _same_reign(reign, row):
            unchanged.append(reign.belt_name)
            reigns.append(reign)
            continue

        after = TitleReign(
            # **보드 이름을 지킨다** — PLE 경기 제목이 이 이름과 정확 일치해야 한다.
            belt_name=reign.belt_name,
            champions=row.champions,
            team_name=row.team_name,
            won_at=row.won_at,
            won_event=row.won_event,
        )
        reigns.append(after)
        updated.append(
            BoardUpdate(belt_name=reign.belt_name, before=reign, after=after)
        )

    unmatched = tuple(
        row.belt_name
        for row in wiki_rows
        if alias.get(_normalized(row.belt_name), _normalized(row.belt_name))
        not in matched
    )
    return WikiSyncPlan(
        reigns=tuple(reigns),
        as_of=as_of,
        updated=tuple(updated),
        unchanged=tuple(unchanged),
        missing_on_wiki=tuple(missing),
        unmatched_wiki=unmatched,
    )


def _same_reign(reign: TitleReign, row: WikiChampionRow) -> bool:
    """같은 재위인가 — 챔피언 **집합**·획득일·팀 이름이 모두 같을 때만.

    집합으로 보는 이유는 위키와 카탈로그의 나열 순서가 다를 수 있기 때문이다. 순서만
    다른 것을 변경으로 세면 매번 같은 줄을 다시 쓰고, 그때마다 `won_event`가 위키
    문장에서 뽑은 값으로 갈린다.
    """
    if reign.won_at != row.won_at:
        return False
    if _normalized(reign.team_name or "") != _normalized(row.team_name or ""):
        return False
    return {_normalized(name) for name in reign.champions} == {
        _normalized(name) for name in row.champions
    }


def _normalized(text: str) -> str:
    """대조용 정규화 — **공백과 대소문자만** 흡수한다.

    `championship_succession._normalized`와 같은 규칙이다. 구두점을 건드리지 않으므로
    `WWE Evolve Men's`가 `WWE Evolve`와 저절로 같아지지 않는다 — 그 둘을 잇는 것은
    별칭표의 일이고, 정규화가 대신하면 어느 이름이 왜 붙었는지 아무 데도 안 남는다.
    """
    return _WHITESPACE.sub(" ", text).strip().casefold()
