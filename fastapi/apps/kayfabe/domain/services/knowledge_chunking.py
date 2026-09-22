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

#: MediaWiki가 모든 문서 앞에 붙이는 고정 문구. 운영 코퍼스에서 **문서당 정확히
#: 한 번**(57문서 57건) 나오므로 머리 표지로 신뢰할 수 있다.
_LEAD_CHROME = "Jump to content From Wikipedia, the free encyclopedia"

#: 본문이 끝나고 **장치**가 시작되는 제목들. 이 뒤에는 각주 목록과 내비게이션
#: 상자가 붙는데, 그것들은 근거가 아니라 잡음이다.
#:
#: `[ edit ]`가 붙은 형태만 본다 — 본문에도 "See also: …"가 인라인으로 나오는데
#: 그것은 문단이지 절 제목이 아니다.
_TAIL_HEADINGS = (
    "References [ edit ]",
    "Notes [ edit ]",
    "See also [ edit ]",
    "External links [ edit ]",
    "Further reading [ edit ]",
    "Bibliography [ edit ]",
)

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

    걷어내는 것은 넷이다 — 머리 내비게이션 · 꼬리(각주·외부링크·navbox) ·
    `[ edit ]` 표시 · `[ 12 ]` 인라인 각주 번호.

    **본문이 거의 사라지면 자르지 않는다.** 표지가 엉뚱한 자리에 맞았다는 뜻이고,
    그때는 잡음을 남기는 편이 문서를 통째로 잃는 것보다 낫다.
    """
    normalized = _WHITESPACE.sub(" ", text).strip()
    if not normalized:
        return ""

    lead = normalized.find(_LEAD_CHROME)
    if lead != -1:
        normalized = normalized[lead + len(_LEAD_CHROME) :].strip()

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
    return long_enough or [normalized[:MAX_CHUNK_CHARS]]


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
