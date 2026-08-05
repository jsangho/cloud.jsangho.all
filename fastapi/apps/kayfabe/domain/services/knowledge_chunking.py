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


def chunk_document(text: str) -> list[str]:
    """문장을 이어 붙여 `MAX_CHUNK_CHARS` 이하 덩어리로 만든다.

    짧은 문서는 통째로 한 조각이 된다 — `MIN_CHUNK_CHARS` 때문에 문서가 통째로
    사라지지는 않는다. 조각이 하나도 안 남으면 원문 전체를 한 조각으로 돌려준다.
    """
    normalized = _WHITESPACE.sub(" ", text).strip()
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
