"""위키 대진과 기존 픽스처를 맞춰 **무엇이 바뀌었는지** 낸다. **순수 함수다.**

`champion_board_sync.plan_wiki_sync`와 같은 자리다 — 읽기·쓰기는 스크립트가 하고
여기서는 계획만 세운다.

## 이 계획이 지키는 것 하나: **id는 보존된다**

경기 id에 DB 행과 사용자 예측이 걸려 있다. 그래서 위키 경기를 기존 경기에 **맞출 수
있으면 그 id를 그대로 물려준다.** 못 맞춘 위키 경기에만 새 id를 제안한다.

## 이름을 정확 일치로 맞추지 않는다

픽스처의 이름은 손으로 조합한 표시 문자열이다 — 실측하면
`"Lucha Brothers — Penta & Rey Fénix"` 한 칸이 위키의
`The Lucha Brothers (Penta and Rey Fénix)` 한 쪽에 대응한다. 정확 일치로 맞추면
**한 건도 안 맞고 전부 "새 경기"가 되어, 기존 id가 통째로 갈린다.** 그래서 이름을
토큰으로 부수어 겹치는 수로 맞춘다.

## 빠진 경기를 **지우자고 하지 않는다**

위키에 없는데 픽스처에 있는 경기는 `only_in_fixture`로 보고만 한다. 위키가 아직
안 실은 것과 실제로 취소된 것을 이 도구는 구별할 수 없고, 지우면 그 경기의 예측이
함께 사라진다. 지우는 판단은 사람 몫이다 — 챔피언 보드가 `missing_on_wiki`를
보고만 하는 것과 같은 이유다.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from kayfabe.domain.services.ple_card_parser import WikiMatchRow

#: 맞춤으로 인정할 최소 겹침. 하나만 겹치면 흔한 이름 하나로 엉뚱한 경기에 붙는다.
_MIN_OVERLAP = 2

#: 두 글자 이하는 버린다 — `LA`·`AJ`·`of`가 점수를 흔든다.
_MIN_TOKEN = 3

_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)


def _tokens(names: tuple[str, ...]) -> frozenset[str]:
    """이름들 → 대조용 토큰. **악센트를 접어서 비교한다**(`Fénix` ↔ `Fenix`)."""
    out: set[str] = set()
    for name in names:
        folded = unicodedata.normalize("NFKD", name)
        folded = "".join(c for c in folded if not unicodedata.combining(c))
        for token in _NON_WORD.sub(" ", folded).lower().split():
            if len(token) >= _MIN_TOKEN:
                out.add(token)
    return frozenset(out)


@dataclass(frozen=True)
class ExistingCard:
    """픽스처에 이미 있는 경기. `app.services.ple_fixture_file`이 읽어 준다."""

    id: str
    names: tuple[str, ...]


@dataclass(frozen=True)
class PlannedCard:
    """계획된 경기 한 장."""

    #: 물려받았거나(기존) 제안된(신규) id.
    id: str
    #: 기존 경기에서 물려받은 id면 참. **거짓이면 사람이 커밋 전에 고칠 초안이다.**
    id_inherited: bool
    row: WikiMatchRow


@dataclass(frozen=True)
class CardPlan:
    slug: str
    #: 위키 순서 그대로의 최종 카드. 픽스처에 이대로 쓴다.
    cards: tuple[PlannedCard, ...]
    #: 기존 id를 물려받은 경기 수.
    kept: int
    #: 새로 제안한 경기들.
    added: tuple[PlannedCard, ...]
    #: 픽스처에는 있는데 위키 대진에는 없는 경기. **지우지 않고 보고만 한다.**
    only_in_fixture: tuple[str, ...]


def _suggest_id(prefix: str, row: WikiMatchRow, taken: set[str]) -> str:
    """새 경기의 id 초안. **사람이 고칠 것을 전제로 읽기 쉽게 만든다.**

    확정된 이름의 마지막 낱말(성)을 이어 붙인다 — `mitb26-reed-femi`. 미정 칸은
    빼므로 `A or B` 같은 자리는 이름에 안 들어간다.

    **이 초안은 안정적이지 않다.** 위키가 `Becky Lynch or Liv Morgan`을 한 사람으로
    확정하면 이름이 바뀌고 id도 바뀐다 — 그때 같은 경기가 새 경기로 보인다. 그래서
    스크립트가 신규 id를 따로 모아 보여 주고, 사람이 커밋 전에 기존 규칙에 맞는
    이름으로 고치게 한다.
    """
    parts: list[str] = []
    for competitor in row.competitors:
        if competitor.undetermined:
            continue
        folded = unicodedata.normalize("NFKD", competitor.name)
        folded = "".join(c for c in folded if not unicodedata.combining(c))
        words = _NON_WORD.sub(" ", folded).lower().split()
        if words:
            parts.append(words[-1])
    stem = "-".join(parts[:2]) if parts else f"match{row.number}"
    candidate = f"{prefix}-{stem}"
    if candidate not in taken:
        return candidate
    # 같은 성 짝이 두 번 나오는 대회가 있을 수 있다. 번호로 가른다.
    n = 2
    while f"{candidate}-{n}" in taken:
        n += 1
    return f"{candidate}-{n}"


def plan_cards(
    slug: str,
    wiki_rows: tuple[WikiMatchRow, ...],
    existing: tuple[ExistingCard, ...],
    *,
    id_prefix: str,
) -> CardPlan:
    """위키 카드 + 기존 픽스처 → 계획. **순서는 위키를 따른다.**"""
    existing_tokens = {card.id: _tokens(card.names) for card in existing}
    unclaimed = {card.id for card in existing}

    cards: list[PlannedCard] = []
    added: list[PlannedCard] = []
    taken = {card.id for card in existing}

    for row in wiki_rows:
        row_tokens = _tokens(
            tuple(c.name for c in row.competitors if not c.undetermined)
        )
        best_id, best_score = None, 0
        for card_id in unclaimed:
            score = len(row_tokens & existing_tokens[card_id])
            if score > best_score:
                best_id, best_score = card_id, score

        if best_id is not None and best_score >= _MIN_OVERLAP:
            unclaimed.discard(best_id)
            cards.append(PlannedCard(id=best_id, id_inherited=True, row=row))
            continue

        new_id = _suggest_id(id_prefix, row, taken)
        taken.add(new_id)
        planned = PlannedCard(id=new_id, id_inherited=False, row=row)
        cards.append(planned)
        added.append(planned)

    return CardPlan(
        slug=slug,
        cards=tuple(cards),
        kept=sum(1 for c in cards if c.id_inherited),
        added=tuple(added),
        only_in_fixture=tuple(sorted(unclaimed)),
    )
