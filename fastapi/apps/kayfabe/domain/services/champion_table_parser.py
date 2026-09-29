"""위키 `List of current champions in WWE`의 표를 읽는 **순수 파서**.

## 왜 위키를 봐야 하는가

우리 DB에는 **PLE 경기만** 있다. 그런데 타이틀 교체는 대부분 다른 데서 일어난다 —
2026-09-28 전수 대조에서 22개 벨트 중 13개가 틀렸고, 그 대부분이 Raw·SmackDown·
하우스쇼·Saturday/Sunday Night's Main Event에서 바뀐 것이었다:

    Undisputed WWE       CM Punk    → Sami Zayn        (9/11 SmackDown)
    WWE United States    Baron Corbin → Trick Williams (9/6 Sunday Night's Main Event)
    Women's World        Liv Morgan → Stephanie Vaquer (9/12 WWE Live 남미 투어)

`championship_succession`(PLE 결과에서 끌어내는 규칙)은 여전히 옳지만 **덮는 범위가
좁다.** 그쪽은 PLE 결과가 들어오는 즉시 반영하는 빠른 축이고, 이쪽은 나머지를 메우는
넓은 축이다. 둘은 경쟁하지 않는다 — 동기화가 기준선을 갱신하면 그 날짜 이전 PLE는
`apply_results`의 기준일 관문이 알아서 건너뛴다.

## 입력은 `reduce_markup`을 거친 위키텍스트다

`WikiArticlePort.read_section`이 주는 본문, 곧 `reduce_markup` 출력을 받는다. 원문
위키텍스트를 그대로 넣으면 **말없이 다른 값을 집는다** — 2026-09-29 실측에서 벨트
이름이 `[[World Heavyweight Championship (WWE)|World Heavyweight Championship]]`로
남고 챔피언 자리에 `[[File:Roman Reigns RR25 (1) (headshot).jpg|100px]]`가 들어왔다.

줄이기가 링크 대괄호를 벗기기 때문에 이미지 칸이 `100px`만 남는 것이고, 이 파서가
그것을 이미지로 알아보는 근거가 거기 있다. **입력 계약을 바꾸려면 이 모듈의 모양
판정을 전부 다시 봐야 한다.**

## 표의 모양이 절마다 다르다

이미지 칸이 있는 표(Raw·SmackDown·Open)와 없는 표가 섞여 있고, **같은 표 안에서도
사진이 없는 행은 칸이 빈 채로 온다**(NXT 여성·NXT North American·Evolve 남성).
Evolve에는 `Days rec.` 칸이 하나 더 있다. **칸 번호로 읽으면 절마다, 행마다 다른
값을 집는다.** 그래서 이 파서는 위치가 아니라 **모양**으로 찾는다:

    0번 칸           벨트 이름 (`championship`을 품어야 한다)
    빈 칸            건너뛴다 — 사진 없는 행의 이미지 칸이다
    `100px` 꼴       이미지 — 건너뛴다 (`<br>`로 여러 장인 태그 팀 포함)
    그다음 칸        챔피언
    숫자 하나        재위 회차
    날짜처럼 생긴 칸 획득일
    결과 문장 칸     Notes — 여기서 대회명을 뽑는다

`{{age in days|...}}`처럼 날짜를 품은 템플릿 칸은 `_clean`이 통째로 지운다. Evolve의
`Days rec.`가 **획득일과 다른 날짜**를 그 템플릿에 담고 있어서(테이프 딜레이 방영일),
남겨 두면 어느 쪽이 재위 시작인지 알 수 없게 된다. 그래도 **획득일은 처음 만난 날짜
칸 하나만** 쓴다.

## 테이프 딜레이 — 경기일을 쓴다

Evolve 두 벨트에는 날짜가 둘이다. `Date won`은 **경기가 열린 날**이고, Notes가 적는
`WWE recognizes ... as beginning on ...`은 그 회차가 방영된 날이다(WWE 공식 재위
시작일). 우리는 `Date won`, 곧 경기일을 쓴다 — `apply_results`가 PLE의 **대회 날짜**로
재위를 세므로 그래야 보드의 두 축이 같은 자를 쓴다. 손으로 적힌 카탈로그는 방영일을
들고 있었고(`WWE Evolve Women's` 6/24), 동기화하면 경기일(5/29)로 바뀐다. **틀린 값을
고치는 것이 아니라 재는 자를 하나로 맞추는 것이다.**
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: 행 구분자. 표의 각 줄은 `|-`로 갈린다.
_ROW_SPLIT = re.compile(r"^\|-\s*$", re.MULTILINE)

#: 이미지 칸. 줄이기를 거치면 `[[File:x.jpg|100px]]`가 `100px`만 남는다. 태그 팀은
#: 사진이 둘이라 `<br>`로 이어져 오는데, `_clean`이 그것을 줄바꿈으로 바꾸므로
#: **줄마다** 본다.
_IMAGE_LINE = re.compile(r"^\d+px$", re.IGNORECASE)

#: `{{small|(A and B)}}` 같은 템플릿 껍질.
_SMALL = re.compile(r"\{\{\s*small\s*\|(.*?)\}\}", re.IGNORECASE | re.DOTALL)

#: 남은 템플릿 전부. 값이 아니라 표시 지시다.
_TEMPLATE = re.compile(r"\{\{.*?\}\}", re.DOTALL)

_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")

#: 재위 회차 칸. 이 칸이 챔피언으로 읽히면 보드에 `1`이 챔피언으로 앉는다.
_REIGN_COUNT = re.compile(r"^\d+$")

#: `April 19, 2026`. 위키 표는 이 형식으로만 적는다.
_DATE = re.compile(
    r"^(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{1,2}),\s*(\d{4})$"
)

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

#: 괄호 안 구성원. `The Vision (Bron Breakker and Austin Theory)`.
_MEMBERS_IN_PARENS = re.compile(r"^\((.*)\)$")
_MEMBER_SPLIT = re.compile(r"\s*,\s*|\s+and\s+", re.IGNORECASE)

#: 공석. 사람 이름이 아니므로 챔피언으로 읽지 않는다.
_VACANT = re.compile(r"^'*vacant'*$", re.IGNORECASE)

#: Notes 칸의 `... at <대회>` · `... on <프로그램>`. **처음 만난 것만** 쓴다 —
#: 같은 칸 뒤쪽에 `aired on tape delay`처럼 대회가 아닌 `on`이 따라온다.
_EVENT_IN_NOTES = re.compile(r"\b(?:at|on)\s+(.+)", re.DOTALL)

#: 대회명 뒤에 붙는 꼬리. `WrestleMania 42 Night 2` → `WrestleMania 42`.
_NIGHT_SUFFIX = re.compile(r"\s+Night\s+(?:\d+|One|Two|Three)$", re.IGNORECASE)

#: **관사를 떼어 낸 뒤에만** 지우는 꼬리. `a ... Live Tour event`는 "어떤 종류의
#: 행사인가"를 덧붙인 설명이지만, `Sunday Night's Main Event`는 `Event`까지가 이름이다.
#: 관사 없이 지우면 그 이름이 `Sunday Night's Main`으로 잘린다(2026-09-29 실측).
_EVENT_TAIL = re.compile(r"\s+(?:event|episode|PLE|premium live event)$", re.IGNORECASE)
_LEADING_ARTICLE = re.compile(r"^(?:a|an|the)\s+", re.IGNORECASE)

#: 소유격으로 끝나면 대회명이 아니라 주최자다 — `The Nightmare Factory's event,
#: The ID Showcase`에서 정작 대회명은 쉼표 **뒤**에 있고, 쉼표 앞을 집으면 주최자를
#: 대회로 적는다. 그 문장 모양을 규칙으로 풀 수 없으니 아무것도 말하지 않는다.
_POSSESSIVE_TAIL = re.compile(r"['’]s$")

#: 대회명이 한 칸에 이 길이로 들어오는 일은 없다. 넘으면 문장을 집은 것이다.
_EVENT_MAX_LENGTH = 60


@dataclass(frozen=True)
class WikiChampionRow:
    """표 한 줄 — 위키가 말하는 현 챔피언."""

    belt_name: str
    champions: tuple[str, ...]
    team_name: str | None
    #: `YYYY-MM-DD`. 읽지 못하면 빈 문자열이고, 그때 부르는 쪽은 날짜를 쓰지 않는다.
    won_at: str
    #: 획득 대회. Notes 문장에서 뽑으므로 **못 뽑으면 `None`이다** — 지어내지 않는다.
    won_event: str | None = None


def parse_champion_table(wikitext: str) -> tuple[WikiChampionRow, ...]:
    """절 본문에서 챔피언 행을 뽑는다. **읽지 못한 행은 버린다.**

    헤더 행(`!`로 시작하는 칸만 있는 줄)과 표 테두리(`{|`·`|}`)는 자연히 걸러진다 —
    벨트 이름 자리에 값이 없거나 날짜를 못 찾기 때문이다. 억지로 채우지 않는다.
    """
    rows: list[WikiChampionRow] = []
    for chunk in _ROW_SPLIT.split(wikitext):
        row = _parse_row(chunk)
        if row is not None:
            rows.append(row)
    return tuple(rows)


def _parse_row(chunk: str) -> WikiChampionRow | None:
    cells = _cells(chunk)
    if len(cells) < 3:
        return None

    belt = cells[0]
    if not belt or "championship" not in belt.casefold():
        return None

    rest = [c for c in cells[1:] if c and not _is_image(c)]
    if not rest or _VACANT.match(rest[0]):
        return None

    team_name, champions = _split_champions(rest[0])
    if not champions or _REIGN_COUNT.match(rest[0]):
        # 챔피언 칸이 비어 있던 행이다. 재위 회차를 챔피언으로 앉히지 않는다.
        return None

    won_at = ""
    won_event: str | None = None
    for cell in rest[1:]:
        if not won_at:
            won_at = _iso_date(cell)
            if won_at:
                continue
        if won_at and won_event is None:
            won_event = _event_from_notes(cell)

    return WikiChampionRow(
        belt_name=belt,
        champions=champions,
        team_name=team_name,
        won_at=won_at,
        won_event=won_event,
    )


def _cells(chunk: str) -> list[str]:
    """`| 값` 줄들을 값 목록으로.

    `| align=left | 설명`처럼 **표 서식과 값이 `|`로 붙어 오는 칸**이 있다. 그때는
    마지막 조각이 값이다 — 서식을 값으로 읽으면 엉뚱한 칸이 챔피언 자리에 들어간다.
    """
    out: list[str] = []
    for line in chunk.split("\n"):
        line = line.strip()
        if not line.startswith("|") or line.startswith("|}") or line.startswith("|-"):
            continue
        body = line[1:]
        if "|" in body and "=" in body.split("|", 1)[0]:
            body = body.split("|", 1)[1]
        out.append(_clean(body))
    return out


def _clean(text: str) -> str:
    """템플릿·태그를 걷어 내되 `<br>`은 **자리표시자로 남긴다.**

    `<br>`이 팀 이름과 구성원을 가르는 유일한 신호라, 다른 태그와 함께 지우면
    `The Vision(Bron Breakker and Austin Theory)`로 붙어 버린다.
    """
    text = _SMALL.sub(r"\1", text)
    text = _TEMPLATE.sub("", text)
    text = _BR.sub("\n", text)
    text = _TAG.sub("", text)
    return "\n".join(
        _WHITESPACE.sub(" ", part).strip() for part in text.split("\n")
    ).strip()


def _is_image(cell: str) -> bool:
    """사진만 든 칸인가. 태그 팀은 두 장이 줄바꿈으로 이어져 온다."""
    lines = [line for line in cell.split("\n") if line]
    return bool(lines) and all(_IMAGE_LINE.match(line) for line in lines)


def _split_champions(cell: str) -> tuple[str | None, tuple[str, ...]]:
    """챔피언 칸 → (팀 이름, 구성원).

    "Roman Reigns"                              → (None, ("Roman Reigns",))
    "The Vision\\n(Bron Breakker and Austin Theory)"
                                                → ("The Vision", ("Bron Breakker", "Austin Theory"))
    "Fatal Influence\\n(Fallon Henley and Lainey Reid)"
                                                → ("Fatal Influence", ("Fallon Henley", "Lainey Reid"))
    """
    parts = [p.strip() for p in cell.split("\n") if p.strip()]
    if not parts:
        return None, ()

    head = parts[0]
    for tail in parts[1:]:
        inner = _MEMBERS_IN_PARENS.match(tail)
        if inner:
            members = tuple(
                name.strip()
                for name in _MEMBER_SPLIT.split(inner.group(1))
                if name.strip()
            )
            if members:
                return head, members
    return None, (head,)


def _iso_date(cell: str) -> str:
    match = _DATE.match(cell.strip())
    if not match:
        return ""
    month = _MONTHS[match.group(1).casefold()]
    return f"{int(match.group(3)):04d}-{month:02d}-{int(match.group(2)):02d}"


def _event_from_notes(cell: str) -> str | None:
    """`Defeated Penta at SummerSlam Night 2.` → `SummerSlam`.

    **표가 대회명을 따로 주지 않는다.** 획득 대회는 Notes 문장 안에만 있어서 문장에서
    뽑는데, 그것은 추정이므로 **자신 없으면 `None`을 낸다** — 획득일이 바뀐 줄에 옛
    대회명이 남으면 보드가 `Chad Gable · 8/02 · Raw`처럼 거짓을 말한다. 비어 있는
    칸은 사람이 채울 수 있지만 틀린 칸은 아무도 의심하지 않는다.

    읽는 것은 **처음 만난 `at`·`on` 하나**다. 뒤쪽에는 대회가 아닌 `on`이 온다:
    `... on Evolve. WWE recognizes Lewis' reign as ... aired on tape delay.`
    """
    match = _EVENT_IN_NOTES.search(cell)
    if match is None:
        return None

    name = re.split(r"[.,;]", match.group(1), maxsplit=1)[0]
    name = _WHITESPACE.sub(" ", name).strip()
    without_article = _LEADING_ARTICLE.sub("", name)
    without_tail = _EVENT_TAIL.sub("", without_article).strip()

    # 꼬리를 뗀 쪽으로 소유격을 본다. `Beyond Wrestling's event`는 꼬리가 붙은 채로는
    # 소유격으로 끝나지 않아 그대로 통과해 버린다.
    if _POSSESSIVE_TAIL.search(without_tail):
        return None

    name = without_tail if without_article != name else without_article
    name = _NIGHT_SUFFIX.sub("", name).strip()
    if not name or len(name) > _EVENT_MAX_LENGTH or not name[0].isupper():
        # 소문자로 시작하면 대회명이 아니라 문장 조각이다(`the June 9 episode ...`).
        return None
    return name
