"""모델의 주장을 쓸지 보류할지 정하는 **순수 함수**.

에이전트의 안전이 전부 이 파일에 있다. 관문 다섯을 순서대로 통과해야 쓴다.

    1. 주장이 있는가              없으면 보류 — 침묵을 승자로 바꾸지 않는다
    2. 인용이 **우리가 건넨 본문에 실제로 있는가**   없으면 지어낸 것이다
    3. 이름이 카드 선택지 **정확히 하나**에 걸리는가  0개·2개 이상이면 모른다
    4. 카드가 적은 이름이 인용 안에서 보이는가      아니면 인용이 딴 얘기다
    5. 인용이 그 사람을 **패자로 적고 있지 않은가**   적고 있으면 거꾸로 읽은 것이다

2번과 4번이 **양방향**을 만든다. 2번은 "모델의 인용 → 우리 본문" 방향이고, 4번은
"우리 카드 → 모델의 인용" 방향이다. 한쪽만 걸면 각각 이렇게 뚫린다 — 2번만 있으면
아무 문장이나 베껴 오고 승자는 지어낼 수 있고, 4번만 있으면 인용 자체를 지어내면서
이름만 카드에서 가져올 수 있다.

**순서를 지킨다.** 위조 판정(2)이 이름 대조(3)보다 앞이라, 지어낸 인용은 이름이 맞아도
쓰이지 않는다.

## 5번은 진실을 증명하지 않는다 — 모순을 잡는다

관문 1~4는 **출처**를 검증한다. 그런데 출처가 참이어도 방향이 틀릴 수 있다.
2026-09-28 실측이 그 구멍을 보여 줬다 — `Liv Morgan (c) defeated Iyo Sky by pinfall`을
정직하게 인용한 채 승자를 `Iyo Sky`라고 주장하면 네 관문을 **전부 통과한다.**

5번은 그 문장을 읽어 **모순만** 잡는다. 승패 관계를 알아볼 수 있고 주장한 승자가 진
쪽에 적혀 있으면 보류한다. 관계를 못 알아보면 **모순이 아니므로 통과시킨다** — 여기서
멈추는 것이 이 관문의 한계이고, 그래서 이름이 "모순 검출"이지 "승자 판정"이 아니다.
영어 위키의 결과 서술이 몇 가지 꼴로 굳어 있어서 실효가 있다(`_ACTIVE`·`_PASSIVE`).

## 위치를 근거로 승자를 고르지 않는다

위키 서술 순서가 카드의 좌우와 **반대인 문서가 있다.** `pick`은 언제나 **이름이 걸린
선택지**에서 나온다. 5번이 위치를 보지만 그것은 승자를 *고르기* 위한 것이 아니라
승패 동사의 어느 쪽에 있는지를 재기 위한 것이고, 수동태(`B was defeated by A`)를
따로 다루는 이유가 정확히 그 구분이다.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from kayfabe.domain.entities.result_verification import (
    Evidence,
    HoldReason,
    MatchUnderReview,
    ResultClaim,
    ReviewOption,
    Verdict,
)

#: 이름 조각으로 인정하는 최소 길이 (관문 4). `Jey`·`Rey`를 살리려고 3이고, 2로
#: 내리면 `El`·`La` 같은 관사가 아무 인용에나 걸려 관문이 무력해진다.
MIN_TOKEN_LENGTH = 3

_NON_WORD = re.compile(r"[^0-9a-z가-힣]+")
_WHITESPACE = re.compile(r"\s+")


def adjudicate(
    match: MatchUnderReview,
    claim: ResultClaim | None,
    evidence: Sequence[Evidence],
) -> Verdict:
    """관문 넷. 통과하면 쓸 수 있는 `Verdict`, 아니면 `hold`가 찬 `Verdict`."""
    if claim is None:
        return Verdict(match_key=match.match_key, hold=HoldReason.NO_CLAIM)

    if claim.winner_name is None or not claim.winner_name.strip():
        # 승자가 없는 경기는 실제로 있다. 그것을 억지로 쓰지 않는 것이 정답이다.
        return Verdict(match_key=match.match_key, hold=HoldReason.NO_WINNER)

    quote = claim.quote.strip()
    if not quote:
        return Verdict(match_key=match.match_key, hold=HoldReason.QUOTE_MISSING)

    source = _source_of(quote, evidence)
    if source is None:
        return Verdict(match_key=match.match_key, hold=HoldReason.QUOTE_NOT_FOUND)

    matched = _options_for(claim.winner_name, match.options)
    if not matched:
        return Verdict(
            match_key=match.match_key,
            winner_name=claim.winner_name,
            hold=HoldReason.NAME_NOT_ON_CARD,
            quote=quote,
            source_title=source.source_title,
            source_revision_id=source.revision_id,
        )
    if len(matched) > 1:
        return Verdict(
            match_key=match.match_key,
            winner_name=claim.winner_name,
            hold=HoldReason.AMBIGUOUS_NAME,
            quote=quote,
            source_title=source.source_title,
            source_revision_id=source.revision_id,
        )

    option = matched[0]
    if not _name_visible_in(option.name, quote):
        return Verdict(
            match_key=match.match_key,
            winner_name=option.name,
            hold=HoldReason.NAME_NOT_IN_QUOTE,
            quote=quote,
            source_title=source.source_title,
            source_revision_id=source.revision_id,
        )

    if _contradicted_by(quote, option):
        return Verdict(
            match_key=match.match_key,
            winner_name=option.name,
            hold=HoldReason.CONTRADICTED_BY_QUOTE,
            quote=quote,
            source_title=source.source_title,
            source_revision_id=source.revision_id,
        )

    return Verdict(
        match_key=match.match_key,
        pick=option.pick,
        # **카드의 표기를 쓴다**, 모델이 적어 보낸 표기가 아니다. `winner_name`은
        # 화면에 그대로 나가는 값이라 카드와 같은 철자여야 한다.
        winner_name=option.name,
        quote=quote,
        source_title=source.source_title,
        source_revision_id=source.revision_id,
    )


def _source_of(quote: str, evidence: Sequence[Evidence]) -> Evidence | None:
    """인용을 담고 있는 본문. 없으면 `None` — 지어낸 인용이다.

    공백만 흡수해서 대조한다. 위키텍스트에는 줄바꿈·연속 공백이 흔해서 그것까지
    글자 단위로 맞추라고 하면 정직한 인용도 떨어진다. **글자는 흡수하지 않는다** —
    대소문자나 철자를 봐 주면 이 관문이 막으려는 위조가 통과한다.
    """
    needle = _collapsed(quote)
    if not needle:
        return None
    for item in evidence:
        if needle in _collapsed(item.text):
            return item
    return None


def _options_for(
    winner_name: str, options: Sequence[ReviewOption]
) -> list[ReviewOption]:
    """이름이 걸리는 선택지 전부. **정확히 하나여야 쓴다.**

    먼저 완전 일치를 본다. 하나라도 있으면 거기서 끝낸다 — 완전 일치가 있는데 부분
    일치까지 모으면 `Jey Uso`가 `Jimmy Uso`까지 끌어와 모호해진다.
    """
    wanted = _normalized(winner_name)
    if not wanted:
        return []

    exact = [option for option in options if _normalized(option.name) == wanted]
    if exact:
        return exact

    # 부분 일치는 양방향으로 본다 — 모델이 `Reigns`로 짧게 적거나
    # `Roman Reigns (c)`로 길게 적는 날이 둘 다 있다.
    return [
        option
        for option in options
        if _contains_word(_normalized(option.name), wanted)
        or _contains_word(wanted, _normalized(option.name))
    ]


def _name_visible_in(card_name: str, quote: str) -> bool:
    """카드가 적은 이름의 조각 하나라도 인용에 보이는가.

    **이름 전체를 요구하지 않는다.** 위키 서술은 성만 쓰는 일이 흔해서(`Reigns
    pinned Rhodes`), 전체 일치를 요구하면 정직한 인용이 거의 다 보류로 떨어져
    에이전트가 무용해진다. 조각 하나로 낮추는 대신 관문 3이 **이미 모호성을
    걸러 냈다** — 같은 조각을 공유하는 선택지가 둘이면 여기 오지 못한다.
    """
    haystack = _normalized(quote)
    tokens = [
        token
        for token in _normalized(card_name).split()
        if len(token) >= MIN_TOKEN_LENGTH
    ]
    if not tokens:
        # 이름이 짧은 조각뿐이면(`Rey`보다 짧은 경우) 낮춰 주지 않고 전체를 요구한다.
        return _normalized(card_name) in haystack
    return any(_contains_word(haystack, token) for token in tokens)


#: 능동 승패 동사 — **앞쪽이 이긴 쪽**이다. `A defeated B`.
#:
#: 긴 것부터 본다. `def`가 먼저 걸리면 `defeated`의 앞 세 글자에 맞아 경계가 어긋난다.
_ACTIVE: tuple[str, ...] = (
    "defeated",
    "defeats",
    "submitted",
    "pinned",
    "beat",
    "def",
)

#: 수동 승패 표현 — **뒤쪽이 이긴 쪽**이다. `B was defeated by A`.
#:
#: **능동보다 먼저 본다.** `was defeated by`가 `defeated`를 품고 있어서, 순서를
#: 뒤집으면 수동태 문장이 능동으로 읽혀 승패가 거꾸로 판정된다.
_PASSIVE: tuple[str, ...] = (
    "was defeated by",
    "were defeated by",
    "was beaten by",
    "were beaten by",
    "lost to",
)


def _contradicted_by(quote: str, option: ReviewOption) -> bool:
    """인용이 이 사람을 **패자로** 적고 있는가 (관문 5).

    모순만 본다. 승패 관계를 못 알아보면 `False`다 — 모르는 것은 모순이 아니다.
    관계를 알아본 뒤에는 **그 한 번의 판정으로 끝낸다**: 한 인용에 동사가 여러 개면
    어느 관계가 이 경기의 것인지 알 수 없고, 그때 더 찾아보는 것은 추측이다.
    """
    haystack = _normalized(quote)

    for phrase in _PASSIVE:
        index = _phrase_index(haystack, phrase)
        if index is not None:
            # 수동태는 뒤쪽이 이긴 쪽이다. 앞쪽에만 있으면 진 쪽으로 적힌 것이다.
            return _side_only(haystack, index, len(phrase), option, winner_side="after")

    for phrase in _ACTIVE:
        index = _phrase_index(haystack, phrase)
        if index is not None:
            return _side_only(
                haystack, index, len(phrase), option, winner_side="before"
            )

    return False


def _phrase_index(haystack: str, phrase: str) -> int | None:
    """단어 경계를 지키며 구절의 위치를 찾는다. 없으면 `None`.

    `haystack`에 공백을 덧대 찾은 뒤 그 만큼 되돌린다 — `beat`가 `beaten`에,
    `def`가 `defeated`에 걸리지 않게 한다.
    """
    padded = f" {haystack} "
    index = padded.find(f" {phrase} ")
    return None if index == -1 else index


def _side_only(
    haystack: str,
    index: int,
    length: int,
    option: ReviewOption,
    *,
    winner_side: str,
) -> bool:
    """이름이 **지는 쪽에만** 적혀 있는가.

    양쪽에 다 있으면 `False`다 — 어느 쪽인지 모르므로 모순이라고 말할 수 없다
    (같은 이름이 승패 양쪽에 나오는 서술이 실제로 있다: `Reigns defeated Reigns`가
    아니라 `The Bloodline (... Jey Uso ...) defeated ...`처럼 팀 이름이 겹치는 경우).
    """
    padded = f" {haystack} "
    before = padded[:index]
    after = padded[index + length + 2 :]
    losing, winning = (after, before) if winner_side == "before" else (before, after)
    return _name_visible_in(option.name, losing) and not _name_visible_in(
        option.name, winning
    )


def _collapsed(text: str) -> str:
    """공백만 하나로 줄인다. 글자는 그대로 둔다."""
    return _WHITESPACE.sub(" ", text).strip()


def _normalized(text: str) -> str:
    """이름 대조용. 대소문자를 접고 기호를 공백으로 바꾼다.

    기호를 지우지 않고 **공백으로** 바꾸는 이유는 `L.A. Knight`가 `la knight`가 되어
    단어 경계를 지키기 때문이다. 지워 버리면 `laknight`가 되어 조각 대조가 깨진다.
    """
    return _collapsed(_NON_WORD.sub(" ", text.casefold()))


def _contains_word(haystack: str, needle: str) -> bool:
    """단어 경계를 지키는 포함 검사.

    `re.search`에 맡기지 않는 이유는 이름에 정규식 특수문자가 들어오기 때문이다.
    양쪽을 공백으로 감싸 부분 단어 일치를 막는다 — 없으면 `uso`가 `carouso`에 걸린다.
    """
    if not needle:
        return False
    return f" {needle} " in f" {haystack} "
