"""위키 대회 문서의 `{{Pro wrestling results table}}`를 읽는다. **순수 함수다.**

## 입력은 `reduce_markup` 출력이다

`champion_table_parser`와 같은 규칙이다 — `WikiArticlePort.read_section`이 준 본문을
그대로 받는다. 줄이기가 링크 대괄호와 굵게 따옴표를 벗겨 주므로 `[[Penta|Penta]]`나
`'''Gunther'''`가 이름 대조를 빗나가게 하지 않는다. **원문 위키텍스트를 넣으면 에러
없이 다른 값이 나온다.**

`reduce_markup`이 템플릿(`{{...}}`)은 지우지 않기 때문에 이 파서가 성립한다.

## 표가 둘일 수 있다 — 번호가 다시 1부터다

레슬매니아 42는 2일 대회라 템플릿이 **둘**이고 각각 `match1`부터 다시 센다
(실측 rev 1376818511: Night 1이 `match1..7`, Night 2가 `match1..6`). 문서 전체에
정규식을 한 번 돌리면 Night 2가 Night 1을 덮어쓴다 — 실제로 첫 스파이크가 그렇게
`stip`을 어긋나게 붙였다. 그래서 **템플릿 단위로 잘라서** 판다.

`caption`이 그 표의 이름이다(`Night 1 (April 18)`). 없으면 `None`이고, 1일 대회가
그렇다.

## 카드형과 결과형은 다른 문서다

    |match1 = Roman Reigns (c) vs. LA Knight        ← 카드형: 아직 안 열렸다
    |match1 = Gunther defeated Seth Rollins         ← 결과형: 끝났다

같은 키에 **다른 종류의 사실**이 들어온다. 이 파서는 둘을 구분해서 내보내고 어느
쪽을 쓸지는 부르는 쪽이 정한다 — 대진표 생성은 카드형만 쓴다. 결과형을 대진으로
옮기면 승자가 적힌 문자열이 "예정된 경기"로 둔갑한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: 표 템플릿 이름. 위키가 대소문자·밑줄을 섞어 쓰므로 느슨하게 연다.
_TABLE_HEAD = re.compile(r"\{\{\s*Pro[ _]wrestling[ _]results[ _]table", re.IGNORECASE)

#: `|match1 = ...` · `| match1 = ...` 양쪽을 받는다 (실측: 같은 문서 안에서 섞인다).
#:
#: **글자와 숫자를 갈라 받는다.** `(\w+?)(\d*)`로 쓰면 `\w`가 숫자를 포함해서
#: 비탐욕 쪽이 `match1`을 통째로 삼키고 번호가 빈 문자열이 된다.
#:
#: **줄 안의 공백만 건너뛴다(`[ \t]`).** `\s`를 쓰면 줄바꿈까지 먹어서, 값이 빈
#: 필드가 **다음 줄을 자기 값으로 삼킨다** — 실측 본문의 `|times  =`와 `|timeN  = `가
#: 정확히 그래서 바로 아래 `matchN` 줄을 통째로 가져갔고, 표가 0경기로 나왔다.
#: 두 함정 모두 실제 본문에 돌려 보고서야 드러났다.
_FIELD = re.compile(r"^\|[ \t]*([A-Za-z]+)(\d*)[ \t]*=[ \t]*(.*)$", re.MULTILINE)

#: 카드형 구분자. `vs.`·`vs`를 단어 경계로 본다 — 이름 안의 `vs`를 자르지 않는다.
_VS = re.compile(r"\s+vs\.?\s+", re.IGNORECASE)

#: 결과형 표시. 이것이 있으면 카드가 아니라 결과다.
_RESULT_VERB = re.compile(r"\bdefeated\b|\bdef\.\s", re.IGNORECASE)

#: 챔피언 표시 `(c)`. 이름 뒤에 붙는다.
_CHAMPION = re.compile(r"\s*\(c\)\s*$", re.IGNORECASE)

#: `1 TBD` · `2 TBD` — 아직 정해지지 않은 자리다. 숫자는 자리 수다.
_TBD = re.compile(r"^\d*\s*TBD$", re.IGNORECASE)

#: `(with Paul Heyman)` · `(with Nikki Bella)` — 동행자는 경기 참가자가 아니다.
_WITH = re.compile(r"\s*\(with [^)]*\)", re.IGNORECASE)

#: 승자를 가리키는 동사. **`_RESULT_VERB`보다 넓다** — 럼블은 `defeated`를 안 쓰고
#: `won by last eliminating`으로 적는다.
#:
#: 🔴 **`is_card` 판정에는 쓰지 않는다.** 저쪽을 넓히면 `vs.`로 적힌 카드 중 `won`이
#: 들어간 줄이 결과형으로 뒤집히고, 대진 동기화(`sync_ple_cards_from_wiki`)가 그
#: 영향을 그대로 받는다. 승자 추출 경로에서만 쓴다.
#:
#: 긴 쪽을 먼저 둔다 — `\bwon\b`가 앞에 서면 나중에 패턴을 늘릴 때 함정이 된다.
_WINNER_VERB = re.compile(
    r"\bwon by last eliminating\b|\bdefeated\b|\bdef\.\s|\bwon\b", re.IGNORECASE
)

#: 승자가 없는 결말. 무승부·노컨테스트가 여기다.
#:
#: **"못 읽었다"와 "승자가 없다"를 구분하려고 둔다.** 결과 확정 에이전트가 이 둘을
#: 각각 `HoldReason.NO_CLAIM`과 `NO_WINNER`로 가르고 있고, 섞으면 다시 돌리면 되는
#: 것과 사람이 봐야 하는 것이 뒤섞인다.
_NO_WINNER = re.compile(
    r"\bno[- ]contest\b"
    r"|\bdouble (?:count-?out|disqualification|pin|knockout)\b"
    r"|\btime[- ]limit draw\b"
    r"|\bended in a draw\b"
    r"|\bfought to a draw\b",
    re.IGNORECASE,
)

#: 챔피언 표시 — 승자 쪽 문자열 **안쪽**에 선다 (`Drew McIntyre (c) defeated ...`).
#: `_CHAMPION`은 줄 끝에 고정돼 있어 이 자리에 못 쓴다. `(c1)`처럼 번호가 붙는
#: 복수 벨트 표기도 받는다.
_CHAMPION_ANY = re.compile(r"\s*\(c\d*\)", re.IGNORECASE)

#: 괄호 한 겹. 승자 쪽에서는 **멤버 나열**이다 (`The Wyatt Sicks (Dexter Lumis and
#: Joe Gacy)`). 중첩은 실측에 없었다.
_PAREN = re.compile(r"\(([^()]*)\)")

#: 이름 구분자. `, and`를 `,`보다 먼저 둬야 `and`가 빈 칸으로 남지 않는다.
_NAME_SEP = re.compile(r",\s*and\s+|,\s*|\s+and\s+|\s*&\s*|\s*/\s*", re.IGNORECASE)


@dataclass(frozen=True)
class WikiCompetitor:
    """카드 한쪽에 선 이름."""

    name: str
    #: `(c)`가 붙어 있었다.
    is_champion: bool = False
    #: 상대가 아직 안 정해졌다 — `1 TBD`이거나 `A or B`다. **이름을 고르지 않는다.**
    undetermined: bool = False


@dataclass(frozen=True)
class WikiMatchRow:
    """표의 `matchN` 한 줄."""

    #: 템플릿 안에서의 번호. **문서 안에서 유일하지 않다** (2일 대회는 둘 다 1부터).
    number: int
    #: `matchN` 원문. 파싱을 못 믿을 때 사람이 볼 것이라 그대로 들고 다닌다.
    raw: str
    #: `stipN` 원문. 없으면 `None`.
    stipulation: str | None
    #: 카드형(`vs.`)이면 참. 결과형(`defeated`)이면 거짓.
    is_card: bool
    #: 카드형일 때만 채운다. 결과형은 빈 튜플 — 승자를 대진으로 옮기지 않기 위해서다.
    competitors: tuple[WikiCompetitor, ...]


@dataclass(frozen=True)
class WikiResultsTable:
    """표 하나. 2일 대회는 이것이 둘이다."""

    #: `caption` 값. `Night 1 (April 18)` 같은 것이고 1일 대회는 `None`.
    caption: str | None
    matches: tuple[WikiMatchRow, ...]


def _split_templates(text: str) -> list[str]:
    """`{{Pro wrestling results table ... }}` 본문만 잘라 낸다.

    **중괄호를 세어서 닫는다.** `}}`를 먼저 만나는 자리로 자르면 안쪽 템플릿
    (`{{small|...}}` 등)에서 일찍 끊긴다.
    """
    blocks: list[str] = []
    for head in _TABLE_HEAD.finditer(text):
        depth = 0
        i = head.start()
        while i < len(text) - 1:
            pair = text[i : i + 2]
            if pair == "{{":
                depth += 1
                i += 2
                continue
            if pair == "}}":
                depth -= 1
                i += 2
                if depth == 0:
                    blocks.append(text[head.start() : i])
                    break
                continue
            i += 1
        else:
            # 닫히지 않은 템플릿 — 문서가 잘렸거나 문법이 깨진 것이다. 버린다.
            continue
    return blocks


def _clean_name(part: str) -> WikiCompetitor | None:
    """카드 한쪽 문자열 → 참가자. **모르는 것은 모른다고 적는다.**"""
    text = _WITH.sub("", part).strip().strip(",").strip()
    if not text:
        return None
    if _TBD.match(text):
        return WikiCompetitor(name=text, undetermined=True)
    # `Becky Lynch or Liv Morgan` — 둘 중 누구인지 위키도 모른다. 앞 이름을 고르면
    # 화면이 확정되지 않은 것을 확정된 것처럼 그린다.
    if re.search(r"\s+or\s+", text, re.IGNORECASE):
        return WikiCompetitor(name=text, undetermined=True)
    champion = bool(_CHAMPION.search(text))
    name = _CHAMPION.sub("", text).strip()
    return WikiCompetitor(name=name, is_champion=champion) if name else None


def _parse_card(value: str) -> tuple[WikiCompetitor, ...]:
    parts = _VS.split(value)
    out = [c for c in (_clean_name(p) for p in parts) if c is not None]
    # 한 쪽만 남으면 `vs.`가 없었다는 뜻이다 — 카드가 아니다.
    return tuple(out) if len(out) >= 2 else ()


def parse_results_tables(section_text: str) -> tuple[WikiResultsTable, ...]:
    """절 본문 → 표들. 표가 없으면 빈 튜플이다.

    **빈 튜플과 실패를 구분하지 않는다** — 이 함수는 본문을 받았다는 전제이고,
    본문을 못 받은 상태(`None`)는 부르는 쪽이 이미 걸렀다.
    """
    tables: list[WikiResultsTable] = []
    for block in _split_templates(section_text):
        caption: str | None = None
        raws: dict[int, str] = {}
        stips: dict[int, str] = {}
        for key, digits, value in _FIELD.findall(block):
            value = value.strip()
            if key == "caption" and not digits:
                caption = value or None
                continue
            if not digits:
                continue
            number = int(digits)
            if key == "match":
                raws[number] = value
            elif key == "stip":
                stips[number] = value

        rows: list[WikiMatchRow] = []
        for number in sorted(raws):
            raw = raws[number]
            if not raw:
                continue
            is_card = not _RESULT_VERB.search(raw)
            competitors = _parse_card(raw) if is_card else ()
            rows.append(
                WikiMatchRow(
                    number=number,
                    raw=raw,
                    stipulation=stips.get(number) or None,
                    # `vs.`를 못 쪼갠 카드형은 카드로 치지 않는다 — 한 칸짜리
                    # 대진은 없다. 사람이 원문을 봐야 하는 자리다.
                    is_card=is_card and bool(competitors),
                    competitors=competitors,
                )
            )
        tables.append(WikiResultsTable(caption=caption, matches=tuple(rows)))
    return tuple(tables)


def _winner_names(text: str) -> tuple[str, ...]:
    """승자 쪽 문자열 → 대조용 이름들.

    **팀명과 멤버를 모두 담는다.** DB가 어느 표기를 들고 있을지 모르기 때문이다 —
    2026년 전수 실측에서 `Danhausen & Minihausen`(팀명)과 `CM Punk, Rey Mysterio &
    El Grande Americano`(멤버 나열)가 같은 DB에 섞여 있었다. 한쪽만 담으면 그
    절반이 대조에서 빗나간다.
    """
    text = _CHAMPION_ANY.sub("", _WITH.sub("", text))
    inner = _PAREN.findall(text)
    outer = _PAREN.sub(" ", text)

    out: list[str] = []
    seen: set[str] = set()
    for chunk in (outer, *inner):
        for part in _NAME_SEP.split(chunk):
            name = part.strip().strip(",").strip()
            if not name:
                continue
            key = name.casefold()
            if key not in seen:
                seen.add(key)
                out.append(name)
    return tuple(out)


@dataclass(frozen=True)
class WikiMatchWinner:
    """결과형 한 줄에서 읽은 승자."""

    row: WikiMatchRow
    #: 승부 동사 **왼쪽 원문**. 파싱을 못 믿을 때 사람이 볼 자리라 그대로 들고 다닌다.
    text: str
    #: 대조용 이름들 — 팀명과 멤버가 함께 들어 있다.
    names: tuple[str, ...]
    #: `(c)`가 붙어 있었다 — 챔피언이 방어했다.
    defended: bool


def is_no_winner(row: WikiMatchRow) -> bool:
    """무승부·노컨테스트로 끝났는가.

    **승부 동사가 있으면 거짓이다.** 두 표시가 한 줄에 같이 서는 서술(재경기 언급
    등)에서는 승부 쪽이 이긴다 — 승자가 적혀 있는데 "없다"고 읽으면 안 된다.
    """
    if _WINNER_VERB.search(row.raw):
        return False
    return bool(_NO_WINNER.search(row.raw))


def winner_of(row: WikiMatchRow) -> WikiMatchWinner | None:
    """결과형 한 줄에서 승자를 읽는다. **순수 함수다.**

    위키의 결과 표는 산문이 아니라 `{{Pro wrestling results table}}` 템플릿이고
    승부 동사 왼쪽이 승자다. 2026년 대회 12개 실측에서 83경기 전부가 이 문법을
    따랐고, DB에 이미 확정돼 있던 63건과 전수 대조해 모두 같은 승자가 나왔다.

    `None`을 내는 이유는 둘이다 — 승부 동사가 없거나(무승부면 `is_no_winner`가
    참이다), 동사 왼쪽에서 이름을 못 건졌다. **둘을 섞지 않는 것이 부르는 쪽의 일**
    이다.
    """
    found = _WINNER_VERB.search(row.raw)
    if not found:
        return None
    text = row.raw[: found.start()].strip()
    if not text:
        return None
    names = _winner_names(text)
    if not names:
        return None
    return WikiMatchWinner(
        row=row,
        text=text,
        names=names,
        defended=bool(_CHAMPION_ANY.search(text)),
    )


#: 결말 표시 꼬리 — `by pinfall` · `by technical submission`. 사람 이름이 아니다.
_FINISH_TAIL = re.compile(r"\s*\bby\s+[A-Za-z][A-Za-z \-]*$", re.IGNORECASE)


def competitor_names(row: WikiMatchRow) -> tuple[str, ...]:
    """결과형 줄에 적힌 **모든 이름** — 이긴 쪽과 진 쪽을 가리지 않는다.

    경기 짝짓기에 쓴다. 승자 이름만으로 DB 경기와 위키 줄을 맞추면 같은 선수가 한
    대회에서 두 번 이겼을 때 어긋나고, 럼블처럼 본문에 참가자가 둘만 적히는 경기는
    아예 못 맞춘다.
    """
    found = _WINNER_VERB.search(row.raw)
    if found:
        left, right = row.raw[: found.start()], row.raw[found.end() :]
    else:
        left, right = row.raw, ""
    right = _FINISH_TAIL.sub("", right)
    return tuple(dict.fromkeys(_winner_names(left) + _winner_names(right)))


def result_matches(tables: tuple[WikiResultsTable, ...]) -> tuple[WikiMatchRow, ...]:
    """표 전체에서 **결과형만** 순서대로 모은다. `card_matches`의 거울이다.

    `is_card`가 거짓인 줄에는 `vs.`를 못 쪼갠 카드형도 섞여 있다. 승부 동사도
    무승부 표시도 없는 줄은 결과가 아니므로 여기서 뺀다 — 사람이 원문을 봐야 하는
    자리이지 결과로 셀 자리가 아니다.
    """
    return tuple(
        row
        for table in tables
        for row in table.matches
        if not row.is_card
        and (_WINNER_VERB.search(row.raw) or _NO_WINNER.search(row.raw))
    )


def card_matches(tables: tuple[WikiResultsTable, ...]) -> tuple[WikiMatchRow, ...]:
    """표 전체에서 **카드형만** 순서대로 모은다.

    2일 대회의 번호 충돌을 여기서 흡수한다 — 표 순서 → 표 안의 번호 순서로 늘어놓고
    번호는 더 이상 식별자로 쓰지 않는다.
    """
    return tuple(row for table in tables for row in table.matches if row.is_card)
