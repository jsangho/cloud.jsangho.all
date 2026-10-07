"""DB 경기 ↔ 위키 결과 줄 짝짓기. **순수 함수다.**

## 왜 짝짓기가 따로 필요한가

위키 결과 표는 경기 순서가 우리 카드 순서와 다르고(다크 매치가 앞에 끼고, 킥오프가
본편 뒤에 적히기도 한다), `match_key` 같은 공통 식별자가 없다. 그래서 **적힌 이름으로**
맞춘다.

## 승자 이름으로 맞추지 않는다

같은 선수가 한 대회에서 두 번 이기는 일이 있다(2026 로얄럼블의 Gunther는 4경기에서
이기고 6경기에서 마지막에 탈락당했다). 승자만 보고 맞추면 그런 대회에서 엉뚱한 줄을
집는다. **참가자 전원**으로 맞추고, 경기 제목은 동점을 가르는 데만 쓴다.

## 애매하면 짝짓지 않는다

1등과 2등 점수가 같으면 그 경기는 짝을 못 지은 것으로 둔다. 둘 중 하나를 고르면
50% 확률로 틀린 승자를 쓰는데, 그것은 보류보다 나쁘다 — 보류는 사람이 보지만 틀린
값은 아무도 안 본다.

## 실측 (2026-10-07)

운영 DB에 확정돼 있던 63건으로 전수 대조했다. 짝짓기까지 포함해 **63건 전부**
재현했고 승자 불일치는 0건이었다. 그 전 판은 점수 문턱을 2로 두어 둘을 놓쳤다 —
럼블(본문에 참가자가 둘만 적힌다)과 트리오스(DB가 `팀명 — 멤버`로 적는다)였다.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from kayfabe.domain.services.ple_card_parser import (
    WikiMatchRow,
    WikiMatchWinner,
    WikiResultsTable,
    competitor_names,
    result_matches,
    winner_of,
)
from kayfabe.domain.services.winner_name_match import (
    normalize_wrestler_name,
    split_names,
)

#: DB가 참가자를 `팀명 — 멤버, 멤버` 로 적는 일이 있다 (`worlds-collide` 실측).
#: 대시를 구분자로 올려 멤버까지 꺼낸다.
_TEAM_DASH = re.compile(r"\s*[—–-]\s*")

#: 제목·조건에서 경기를 가리키지 못하는 흔한 낱말. 동점 가르기에서 빼지 않으면
#: "match" 하나로 모든 줄이 같은 점수를 받는다.
_STOPWORDS = frozenset(
    {
        "match",
        "matches",
        "the",
        "for",
        "a",
        "an",
        "and",
        "of",
        "at",
        "to",
        "vs",
        "singles",
        "tag",
        "team",
        "championship",
        "title",
        "wwe",
    }
)


@dataclass(frozen=True)
class MatchCandidate:
    """짝을 찾아야 할 DB 경기. 어댑터가 ORM에서 떠 와 채운다."""

    key: str
    title: str
    participants: tuple[str, ...]


@dataclass(frozen=True)
class PairedResult:
    """짝지은 결과. `winner`가 곧 이 경기의 승자다."""

    candidate: MatchCandidate
    row: WikiMatchRow
    winner: WikiMatchWinner
    #: 겹친 참가자 수. 사람이 보고 믿을지 정하는 숫자라 들고 다닌다.
    overlap: int


def _person_keys(values: Iterable[str]) -> set[str]:
    """참가자 문자열들 → 정규화된 사람 이름 집합."""
    keys: set[str] = set()
    for value in values:
        for chunk in _TEAM_DASH.split(value):
            for name in split_names(chunk):
                key = normalize_wrestler_name(name)
                if key:
                    keys.add(key)
    return keys


def _title_keys(text: str) -> set[str]:
    return {
        word
        for word in normalize_wrestler_name(text).split()
        if word not in _STOPWORDS and len(word) > 2
    }


def pair_results(
    candidates: Sequence[MatchCandidate],
    tables: tuple[WikiResultsTable, ...],
) -> tuple[tuple[PairedResult, ...], tuple[MatchCandidate, ...]]:
    """짝지은 것과 **못 지은 것을 함께** 낸다.

    못 지은 쪽을 버리지 않는 이유: 부르는 쪽이 그 경기를 보류로 적고 사람에게
    넘겨야 한다. 조용히 사라지면 "결과가 없는 경기"와 "우리가 못 맞춘 경기"가
    구분되지 않는다.
    """
    rows: list[tuple[WikiMatchRow, WikiMatchWinner, set[str], set[str]]] = []
    for row in result_matches(tables):
        won = winner_of(row)
        if won is None:
            continue  # 무승부·노컨테스트. 승자를 쓸 자리가 아니다.
        rows.append(
            (
                row,
                won,
                _person_keys(competitor_names(row)),
                _title_keys(row.stipulation or ""),
            )
        )

    scored: list[tuple[int, int, int, int]] = []  # (people, title, cand_idx, row_idx)
    for ci, cand in enumerate(candidates):
        people = _person_keys(cand.participants)
        title = _title_keys(cand.title)
        for ri, (_, _, row_people, row_title) in enumerate(rows):
            overlap = len(people & row_people)
            if overlap == 0:
                continue
            scored.append((overlap, len(title & row_title), ci, ri))

    # 점수가 높은 짝부터 확정한다. 같은 줄·같은 경기를 두 번 쓰지 않는다.
    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    taken_rows: set[int] = set()
    taken_cands: dict[int, PairedResult] = {}
    #: 동점이라 못 고른 경기. **한 번 애매하면 끝까지 애매하다** — 이 집합이 없으면
    #: 동점 쌍 중 뒤엣것이 "뒤에 경쟁자가 없다"는 이유로 그냥 짝지어진다.
    ambiguous: set[int] = set()
    for rank, (overlap, title_hits, ci, ri) in enumerate(scored):
        if ci in taken_cands or ci in ambiguous or ri in taken_rows:
            continue
        # **동점이면 짝짓지 않는다.** 아직 안 쓰인 줄 중 같은 점수로 이 경기를
        # 노리는 다른 줄이 있으면 어느 쪽인지 알 수 없다.
        rivals = [
            s
            for s in scored[rank + 1 :]
            if s[2] == ci
            and s[3] not in taken_rows
            and (s[0], s[1]) == (overlap, title_hits)
        ]
        if rivals:
            ambiguous.add(ci)
            continue
        row, won, _, _ = rows[ri]
        taken_rows.add(ri)
        taken_cands[ci] = PairedResult(
            candidate=candidates[ci], row=row, winner=won, overlap=overlap
        )

    paired = tuple(taken_cands[i] for i in sorted(taken_cands))
    unpaired = tuple(c for i, c in enumerate(candidates) if i not in taken_cands)
    return paired, unpaired
