"""프론트 대진표 픽스처(`www/lib/wwe-ple-matches.ts`)를 읽고 다시 쓴다.

## 왜 백엔드가 프론트 파일을 만지나

**대진표의 원본은 그 TS 파일이다.** DB가 아니다. `ple-match-bracket.tsx`의
`needsStaticResync`가 경기 id 집합을 비교해서 다르면 정적 카드로
`sync-from-client`를 POST하고, 그 API는 **페이로드에 없는 경기를 지운다.** 그래서
DB에만 경기를 더하면 다음 방문자가 페이지를 여는 순간 되돌아가고, 그 경기에 달린
예측이 CASCADE로 함께 사라진다.

위키에서 읽은 대진이 살아남는 경로는 하나뿐이다 — **픽스처를 고치고 배포한다.**
그 뒤는 기존 흐름이 알아서 DB까지 옮긴다.

## id는 만들지 않고 **보존한다**

경기 id(`mitb26-whc`)는 사람이 지은 의미 슬러그이고 **DB 행과 사용자 예측이 여기에
걸려 있다.** 접두사도 규칙이 없다 — 실측하면 `wm42`(연도가 아니라 회차)·`sad26`·
`italy26`·`bl26`처럼 제각각이다. 그래서 이 모듈은 접두사를 **기존 id에서 읽고**,
이미 있는 경기의 id는 글자 하나 바꾸지 않는다. 새 경기에만 id를 제안하며, 그 제안은
**사람이 커밋 전에 고칠 수 있는 초안**이다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: 픽스처가 쓰는 생성자 **넷**. `m2`·`mm`·`mq`·`rumbleWinner`.
#:
#: **`mq`는 2026-10-06에 더했다.** 그 전에는 셋만 알아서, 호가를 여러 벌 아는
#: 단일전(`mq`로 적는다)을 **통째로 못 봤다.** 결과가 조용한 데이터 손실이었다:
#: `mitb26-whc`가 `existing`에 안 들어가니 `plan_cards`가 그 경기를 「신규」로 보고
#: 새 id(`mitb26-reigns-knight`)를 제안했고, 그대로 적용했으면 배포 뒤
#: `sync-from-client`가 옛 `match_key`를 **DELETE** 해 예측이 CASCADE로 사라졌다.
#: `only_in_fixture` 경고조차 안 떴다 — 아예 안 보였으니 "남은 것"에도 못 든다.
#:
#: **새 생성자를 추가하면 여기도 고친다.** 안 고치면 에러가 아니라 침묵이다.
_CALL = re.compile(r"\b(m2|mm|mq|rumbleWinner)\(\s*\"([^\"]+)\"")

#: `{ name: "Bron Breakker" }` · `{ name: "Roman Reigns", isChampion: true }`
_NAME = re.compile(r"name:\s*\"([^\"]+)\"")

#: `BRACKET_LABELS.tbd` — 미정 칸. 이름이 아니라 자리 표시다.
_LABEL = re.compile(r"BRACKET_LABELS\.(\w+)")

#: 럼블 우승 경기의 `topFive` 는 맨 문자열 배열이다.
_BARE_STRING = re.compile(r"\"([^\"]+)\"")


@dataclass(frozen=True)
class FixtureCard:
    """픽스처에 이미 있는 경기 하나. **id 보존이 이 타입의 존재 이유다.**"""

    id: str
    #: 이 경기에 선 이름들. 미정 칸(`BRACKET_LABELS.tbd`)은 빠져 있다 —
    #: 위키 대진과 맞춰 보는 데 쓰는 값이라 확정된 이름만 필요하다.
    names: tuple[str, ...]


def _event_block_span(source: str, slug: str) -> tuple[int, int] | None:
    """`"<slug>": [ ... ]` 의 대괄호 안쪽 범위. 없으면 `None`.

    **대괄호를 세어서 닫는다.** 경기 하나가 `[...]`(다인전 참가자 배열)를 품고 있어서
    첫 `]`로 자르면 첫 경기 중간에서 끊긴다.
    """
    # **따옴표는 있을 수도 없을 수도 있다.** 하이픈이 있는 슬러그는 JS 식별자가 아니라
    # `"royal-rumble":`로 적히지만, 한 낱말짜리(`wrestlemania`·`backlash`·`summerslam`)는
    # prettier가 따옴표를 뗀다. 따옴표를 요구하면 그 대회들이 통째로 "항목 없음"이 된다.
    head = re.search(rf'(?:"{re.escape(slug)}"|{re.escape(slug)})\s*:\s*\[', source)
    if head is None:
        return None
    start = head.end()
    depth = 1
    i = start
    while i < len(source):
        ch = source[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return start, i
        i += 1
    return None


def read_event_cards(source: str, slug: str) -> tuple[FixtureCard, ...] | None:
    """그 대회의 기존 경기들. 대회 항목 자체가 없으면 `None`.

    **빈 튜플과 `None`은 다르다** — 앞은 "항목은 있는데 경기가 없다"(대진 미발표)이고
    뒤는 "이 대회가 픽스처에 아예 없다"다. 뒤쪽은 슬러그를 잘못 줬거나 다섯 자리
    등록이 안 된 것이라(`wwe-ple.ts` 등) 사람이 볼 일이다.
    """
    span = _event_block_span(source, slug)
    if span is None:
        return None
    block = source[span[0] : span[1]]

    cards: list[FixtureCard] = []
    calls = list(_CALL.finditer(block))
    for index, call in enumerate(calls):
        body_start = call.end()
        body_end = calls[index + 1].start() if index + 1 < len(calls) else len(block)
        body = block[body_start:body_end]
        names = list(_NAME.findall(body))
        if not names:
            # `rumbleWinner`의 `topFive`는 `{ name: ... }`가 아니라 맨 문자열 배열이다.
            # 첫 둘(제목·`cardVariant`)은 이름이 아니므로 뒤에서만 줍는다.
            names = [
                s for s in _BARE_STRING.findall(body) if s not in {"sideA", "sideB"}
            ][1:]
        cards.append(FixtureCard(id=call.group(2), names=tuple(names)))
    return tuple(cards)


def id_prefix_of(cards: tuple[FixtureCard, ...]) -> str | None:
    """기존 id들이 공유하는 접두사(`mitb26-whc` → `mitb26`). 모르면 `None`.

    **규칙으로 만들지 않는다.** 실측 접두사가 `wm42`·`sad26`·`italy26`·`bl26`처럼
    제각각이라 슬러그에서 유도하면 틀린다. 기존 경기가 없는 대회는 접두사를 알 수
    없고, 그때는 사람이 첫 경기를 손으로 넣는 것이 맞다.
    """
    prefixes = {card.id.split("-", 1)[0] for card in cards if "-" in card.id}
    return prefixes.pop() if len(prefixes) == 1 else None


def _ts_string(value: str) -> str:
    """TS 문자열 리터럴. 큰따옴표만 이스케이프한다 — 픽스처가 큰따옴표를 쓴다."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _render_competitor(name: str, *, champion: bool, undetermined: bool) -> str:
    if undetermined and _TBD_ONLY.match(name):
        # 자리만 있고 이름이 없다 — 픽스처의 미정 라벨을 쓴다.
        return "{ name: BRACKET_LABELS.tbd }"
    field = f"name: {_ts_string(name)}"
    return "{ " + field + (", isChampion: true }" if champion else " }")


#: `1 TBD` — 숫자는 자리 수다. `A or B`는 이름이 있으므로 여기 안 걸린다.
_TBD_ONLY = re.compile(r"^\d*\s*TBD$", re.IGNORECASE)


def render_event_block(
    cards: list[tuple[str, str, str, list[tuple[str, bool, bool]]]],
) -> str:
    """경기들 → `PLE_MATCH_CARDS` 항목 안쪽 TS.

    입력은 `(id, title, cardVariant, [(이름, 챔피언, 미정), ...])`다. 타입을 따로
    만들지 않은 이유는 이 함수가 **문자열만 다루는 마지막 한 겹**이기 때문이다 —
    계획은 도메인이 이미 세웠다.

    **prettier 서식을 흉내만 낸다.** 정확한 줄바꿈은 `pnpm format`이 잡으므로,
    여기서는 읽을 수 있는 수준까지만 맞춘다.
    """
    lines = ["\n"]
    for card_id, title, variant, people in cards:
        rendered = [
            _render_competitor(name, champion=champion, undetermined=undetermined)
            for name, champion, undetermined in people
        ]
        if len(rendered) == 2:
            lines.append("    m2(\n")
            lines.append(f"      {_ts_string(card_id)},\n")
            lines.append(f"      {_ts_string(title)},\n")
            lines.append(f"      {_ts_string(variant)},\n")
            lines.append(f"      {rendered[0]},\n")
            lines.append(f"      {rendered[1]},\n")
            lines.append("    ),\n")
            continue
        lines.append(
            f"    mm({_ts_string(card_id)}, {_ts_string(title)}, "
            f"{_ts_string(variant)}, [\n"
        )
        lines.extend(f"      {one},\n" for one in rendered)
        lines.append("    ]),\n")
    lines.append("  ")
    return "".join(lines)


#: `render_event_block`이 **다시 만들 수 없는** 것들. 블록을 통째로 새로 쓰므로,
#: 여기 걸리는 것이 하나라도 있으면 덮어쓰기는 곧 삭제다.
_UNREPRODUCIBLE: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bmq\("), "호가 여러 벌(mq)"),
    (re.compile(r"\brumbleWinner\("), "럼블 우승 생성자(rumbleWinner)"),
    # 렌더러는 숫자를 내보내지 않는다 — 숫자로 시작하는 배열은 배당이다.
    (re.compile(r"\[\s*\d"), "배당 배열(bookmakerDecimal)"),
    (re.compile(r"^[ \t]*//", re.MULTILINE), "손으로 쓴 주석"),
    (re.compile(r"/\*"), "손으로 쓴 주석"),
)


def unreproducible_in_event(source: str, slug: str) -> tuple[str, ...]:
    """그 대회 블록을 다시 쓰면 **잃게 되는 것들**. 없으면 빈 튜플.

    `render_event_block`은 `(id, 제목, 좌우, 참가자)`만 받아 블록을 통째로 새로
    찍는다. 배당·호가·주석은 위키가 모르는 값이라 입력에 없고, 그래서 **조용히
    사라진다.** `replace_event_block` 독스트링이 "다른 대회의 배당과 주석은 남는다"고
    약속하는데, 그 약속은 **대상 대회에는 해당되지 않는다** — 2026-10-06에
    `money-in-the-bank`에서 실제로 확인했다(BetOnline 호가 2벌 + 설명 주석 10줄이
    덮어쓰기 대상이었다).

    그래서 쓰기 전에 사람에게 넘긴다. 자동으로 보존하는 쪽이 아니라 **멈추는 쪽**을
    고른 이유는, 보존하려면 TS 인자를 제대로 파싱해야 하는데 그 파서가 틀리면 같은
    손실이 더 조용히 일어나기 때문이다. 멈추는 것은 틀려도 아무것도 잃지 않는다.
    """
    span = _event_block_span(source, slug)
    if span is None:
        return ()
    block = source[span[0] : span[1]]
    found = {label for pattern, label in _UNREPRODUCIBLE if pattern.search(block)}
    return tuple(sorted(found))


def replace_event_block(source: str, slug: str, rendered: str) -> str | None:
    """그 대회의 경기 목록만 갈아 끼운다. 대회 항목이 없으면 `None`.

    **파일 전체를 다시 쓰지 않는다.** 다른 대회의 손으로 적은 주석과 배당이 그대로
    남아야 한다 — 이 도구가 건드릴 권한이 있는 것은 위키가 말해 주는 그 대회뿐이다.
    """
    span = _event_block_span(source, slug)
    if span is None:
        return None
    return source[: span[0]] + rendered + source[span[1] :]
