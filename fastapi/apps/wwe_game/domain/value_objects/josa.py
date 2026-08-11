"""한국어 조사 — 받침에 맞는 형태를 고른다 (하네스 §3-D44).

**어댑터가 아니라 도메인이다.** 원래 `rule_narrator`(서술 어댑터) 안에 있었는데,
배경 대립 연대기(§3-D44)가 도메인에서 사람 이름에 조사를 붙이게 되면서 두 곳이
쓰게 됐다. 조사는 화면의 관심사가 아니라 **언어의 규칙**이라 여기가 맞다.

복제하지 않은 이유: 같은 표가 둘이면 한쪽만 고쳐지고, 그 어긋남은 "문장이 조금
어색하다"로 나타나 아무도 못 잡는다.
"""

from __future__ import annotations

from typing import Final

JOSA: Final[dict[str, tuple[str, str]]] = {
    # 스펙: (받침 있음, 받침 없음)
    "은": ("은", "는"),
    "는": ("은", "는"),
    "이": ("이", "가"),
    "가": ("이", "가"),
    "을": ("을", "를"),
    "를": ("을", "를"),
    "과": ("과", "와"),
    "와": ("과", "와"),
    "과의": ("과의", "와의"),
    "으로": ("으로", "로"),
    "이었다": ("이었다", "였다"),
}

_HANGUL_START, _HANGUL_END = 0xAC00, 0xD7A3
_JONG_COUNT = 28
_JONG_RIEUL = 8
_ASCII_VOWELS = frozenset("aeiouyAEIOUY")


def _ends_with_batchim(word: str) -> tuple[bool, bool]:
    """(받침이 있는가, 그 받침이 ㄹ인가).

    한글 음절이면 정확히 계산하고, 아니면 마지막 글자로 어림한다 — 링 네임은 사용자
    자유 입력이라 영문이 들어올 수 있다(§3-D12). 어림이 틀려도 문장이 어색해질 뿐이다.
    """
    if not word:
        return False, False
    last = word[-1]
    code = ord(last)
    if _HANGUL_START <= code <= _HANGUL_END:
        jong = (code - _HANGUL_START) % _JONG_COUNT
        return jong != 0, jong == _JONG_RIEUL
    if last.isascii() and last.isalpha():
        return last not in _ASCII_VOWELS, last in "lLrR"
    return True, False


def josa_for(word: str, spec: str) -> str:
    """받침에 맞는 조사. `으로`만 ㄹ 받침을 예외로 둔다 — '칼로', '서울로'."""
    with_batchim, is_rieul = _ends_with_batchim(word)
    if spec == "으로" and is_rieul:
        return "로"
    hard, soft = JOSA[spec]
    return hard if with_batchim else soft
