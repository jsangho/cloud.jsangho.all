"""수집한 문서를 검색 단위로 쪼갠다 — 순수 함수. 하네스 §10-T3.

**왜 쪼개나:** 기사 한 편을 통째로 임베딩하면 벡터가 평균값이 되어 어느 질의와도
어중간하게 가까워진다. 문장 몇 개 단위여야 "누구의 부상 소식"이 제대로 검색된다.

**왜 문장 경계인가:** 글자 수로 자르면 문장이 중간에서 끊겨, 검색 결과로 뽑혀도
에이전트가 읽을 수 없는 조각이 된다.
"""

from __future__ import annotations

import hashlib
import re

#: 청크 최대 길이. bge-m3는 더 긴 입력도 받지만, 길수록 벡터가 뭉개진다.
MAX_CHUNK_CHARS = 1200

#: 이보다 짧은 조각은 버린다 — 메뉴 문구·저작권 한 줄이 근거로 딸려 오는 것을 막는다.
MIN_CHUNK_CHARS = 80

#: 문장 끝. 영어 마침표와 한국어·일본어 종결부를 함께 본다.
_SENTENCE_END = re.compile(r"(?<=[.!?。？！])\s+")

_WHITESPACE = re.compile(r"\s+")

#: 문서 앞에 붙는 고정 머리 문구. 이 뒤부터가 본문이다.
#:
#: 위키 것은 운영 코퍼스에서 **문서당 정확히 한 번**(57문서 57건) 나오므로 표지로
#: 신뢰할 수 있다. wwe.com 것은 2026-10-06에 더했다 — 선수 문서가 코퍼스에 50청크
#: 들어와 있는데 이 사이트는 표지가 전혀 없어 크롬이 통째로 통과하고 있었다.
_LEAD_CHROME = (
    "Jump to content From Wikipedia, the free encyclopedia",
    "Skip to main content",
)

#: 본문이 끝나고 **장치**가 시작되는 제목들. 이 뒤에는 각주 목록과 내비게이션
#: 상자가 붙는데, 그것들은 근거가 아니라 잡음이다.
#:
#: `[ edit ]`가 붙은 형태만 본다 — 본문에도 "See also: …"가 인라인으로 나오는데
#: 그것은 문단이지 절 제목이 아니다.
#:
#: `Continue Reading`은 wwe.com 선수 문서에서 소개글이 끝나고 「Latest News」
#: 위젯이 시작되는 자리다 — 위키의 `References [ edit ]`와 같은 역할을 한다.
_TAIL_HEADINGS = (
    "References [ edit ]",
    "Notes [ edit ]",
    "See also [ edit ]",
    "External links [ edit ]",
    "Further reading [ edit ]",
    "Bibliography [ edit ]",
    "Continue Reading",
)

#: 문서 **어디에나** 끼어드는 공유 버튼 덩어리 (wwe.com). 머리도 꼬리도 아니라
#: 잘라낼 수 없고, 소개글 한가운데 박혀 있어 그대로 두면 본문 청크를 오염시킨다.
_SHARE_WIDGET = re.compile(
    r"(?:More Share Options\s*)+Share close(?:\s+\w+){0,6}",
)

#: 목록 판정 기준 — 이보다 길면서 문장 종결부가 이 개수 이하면 **글이 아니라 목록**이다.
#:
#: 2026-10-06 운영 코퍼스 1016청크 실측에서 종결부 개수가 **0개 50 · 1개 46 ·
#: 2개 8 · 3개 이상 912**로 갈렸다. 1과 3 사이가 절벽이라 경계를 거기에 둔다.
LIST_LIKE_MIN_CHARS = 400
LIST_LIKE_MAX_SENTENCE_ENDS = 1

_SENTENCE_END_CHAR = re.compile(r"[.!?。？！]")

#: 각주 목록의 되돌이 화살표. 절 제목을 못 찾았을 때의 차선책이다.
_CITATION_ARROW = "↑"

_EDIT_TOKEN = re.compile(r"\[\s*edit\s*\]")
_INLINE_REF = re.compile(r"\[\s*\d+\s*\]")


def strip_source_boilerplate(text: str) -> str:
    """위키 문서에서 **근거가 될 수 없는 부분**을 걷어낸다.

    2026-09-22 운영 실측이 이 함수를 만든 이유다. `worlds-collide` 예측이 두 번
    연속 0건으로 끝났는데, 검색은 정상이었고 **잡혀 온 것이 잡음**이었다:

        La_Catalina       "Jump to content From Wikipedia, the"    내비게이션
        La_Catalina       "Retrieved 14 April 2026 . ↑ Hetfield"   각주 목록
        Mascarita_Dorada  "Omos Pagano Pimpinela Escarlata"        navbox 이름 나열

    코퍼스 1179청크 중 **730건(61%)** 이 이런 조각이었다.

    **왜 하필 그것들이 상위에 오나.** navbox는 레슬러 이름이 빽빽한 목록이고
    검색 질의도 이름 나열(`"Trios Match CM Punk, Rey Mysterio & …"`)이다. 임베딩
    공간에서 이름 목록끼리 가장 가까우므로, **내용이 0인 조각이 구조적으로 이긴다.**
    에이전트가 "근거 부족"이라고 답한 것은 정확한 판단이었다.

    걷어내는 것은 다섯이다 — 머리 내비게이션 · 꼬리(각주·외부링크·navbox) ·
    공유 버튼 덩어리 · `[ edit ]` 표시 · `[ 12 ]` 인라인 각주 번호.

    **머리와 꼬리만 본다.** 본문 한가운데 박힌 navbox는 이 함수가 못 잡고
    `is_list_like`가 청크 단위로 거른다 — 자리가 아니라 모양으로 가려야 한다.

    **본문이 거의 사라지면 자르지 않는다.** 표지가 엉뚱한 자리에 맞았다는 뜻이고,
    그때는 잡음을 남기는 편이 문서를 통째로 잃는 것보다 낫다.
    """
    normalized = _WHITESPACE.sub(" ", text).strip()
    if not normalized:
        return ""

    normalized = _SHARE_WIDGET.sub(" ", normalized)

    for marker in _LEAD_CHROME:
        lead = normalized.find(marker)
        if lead != -1:
            normalized = normalized[lead + len(marker) :].strip()
            break

    cut = _tail_cut(normalized)
    body = normalized[:cut].strip() if cut is not None else normalized
    # 표지가 문서 맨 앞에 맞으면 본문이 통째로 날아간다. 그럴 바엔 안 자른다.
    if len(body) < MIN_CHUNK_CHARS:
        body = normalized

    body = _EDIT_TOKEN.sub(" ", body)
    body = _INLINE_REF.sub(" ", body)
    return _WHITESPACE.sub(" ", body).strip()


def _tail_cut(text: str) -> int | None:
    """본문이 끝나는 지점. 절 제목이 먼저이고, 없으면 첫 각주 화살표다."""
    found = [text.find(h) for h in _TAIL_HEADINGS]
    hits = [i for i in found if i != -1]
    if hits:
        return min(hits)
    arrow = text.find(_CITATION_ARROW)
    return arrow if arrow != -1 else None


def chunk_document(text: str) -> list[str]:
    """문장을 이어 붙여 `MAX_CHUNK_CHARS` 이하 덩어리로 만든다.

    짧은 문서는 통째로 한 조각이 된다 — `MIN_CHUNK_CHARS` 때문에 문서가 통째로
    사라지지는 않는다. 조각이 하나도 안 남으면 원문 전체를 한 조각으로 돌려준다.
    """
    normalized = strip_source_boilerplate(text)
    if not normalized:
        return []

    chunks: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(normalized):
        if not sentence:
            continue
        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= MAX_CHUNK_CHARS:
            current = f"{current} {sentence}"
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)

    split: list[str] = []
    for chunk in chunks:
        split.extend(_hard_split(chunk))

    long_enough = [c for c in split if len(c) >= MIN_CHUNK_CHARS]
    if not long_enough:
        # 짧은 문서가 통째로 사라지지 않게 하는 길. 목록 판정에는 길이 하한이
        # 있으므로 여기 걸리는 조각은 애초에 목록으로 잡히지 않는다.
        return [normalized[:MAX_CHUNK_CHARS]]

    # **목록은 여기서 버린다.** 머리·꼬리를 잘라도 본문 **한가운데** 박힌 navbox는
    # 남는데(위키의 「Part of a series on …」 사이드바), 그건 위치로는 못 거르고
    # 모양으로만 걸러진다 — 문장이 없다.
    return [c for c in long_enough if not is_list_like(c)]


def is_list_like(chunk: str) -> bool:
    """**글이 아니라 목록인가.** 길면서 문장 종결부가 거의 없으면 목록이다.

    2026-10-06 실측이 이 함수를 만든 이유다. MITB 여성 세계왕좌전 예측이 계속
    실패했는데, 지식이 없어서가 아니라 검색 상위 10위를 **무관한 선수의 navbox와
    사이트 크롬이 독식**해서 참가자 문서가 `top_k=5` 안에 한 건도 못 들어갔다
    (경쟁자 문서 최상위가 11위였다).

    `strip_source_boilerplate`는 머리·꼬리만 자른다. 그 가정이 깨지는 자리가 있다 —
    위키의 「Part of a series on Professional wrestling …」 사이드바는 `References`
    **앞**, 본문 한복판에 있어 꼬리 자르기로는 닿지 않는다. 위치가 아니라 **모양**을
    봐야 한다.

    이름 목록은 쉼표도 마침표도 없이 고유명사만 이어지므로 종결부가 0~1개다.
    운영 코퍼스 1016청크의 종결부 분포가 **0개 50 · 1개 46 · 2개 8 · 3개 이상 912**로
    절벽이라, 경계를 1과 3 사이에 둔다. 이 규칙이 잡는 것은 85건(8.4%)이다.

    **길이 하한이 안전장치다.** 짧은 조각은 한 문장짜리 정상 본문일 수 있다.
    """
    if len(chunk) < LIST_LIKE_MIN_CHARS:
        return False
    return len(_SENTENCE_END_CHAR.findall(chunk)) <= LIST_LIKE_MAX_SENTENCE_ENDS


def content_fingerprint(text: str) -> str:
    """같은 글을 다시 수집해도 한 벌만 남기기 위한 지문.

    공백을 정규화한 뒤 해싱한다 — 사이트가 줄바꿈만 바꿔도 다른 글이 되면 재수집마다
    같은 내용이 쌓여 검색 결과를 독식한다.
    """
    normalized = _WHITESPACE.sub(" ", text).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _hard_split(chunk: str) -> list[str]:
    """문장 부호가 없어 한 문장이 통째로 긴 경우의 마지막 수단.

    최대 길이로 잘라 나가면 마지막 조각이 몇십 자만 남아 `MIN_CHUNK_CHARS`에 걸려
    버려진다 — 문장 끝이 통째로 사라진다. 그래서 **필요한 조각 수로 균등 분할**한다.
    """
    if len(chunk) <= MAX_CHUNK_CHARS:
        return [chunk]
    pieces = -(-len(chunk) // MAX_CHUNK_CHARS)
    size = -(-len(chunk) // pieces)
    return [chunk[i : i + size] for i in range(0, len(chunk), size)]
