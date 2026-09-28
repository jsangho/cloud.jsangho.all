"""문서의 **목차와 절 본문**을 묻는 출력 포트.

기존 위키 포트 셋과 묻는 것이 다르다.

    WikiTitlePort          이 이름에 해당하는 문서가 있기는 한가
    RevisionMetadataPort   이 주소의 본문이 어느 개정본인가
    WebPageFetcherPort     이 주소의 HTML을 주세요
    WikiArticlePort        이 문서의 **어느 절**에 무엇이 적혀 있나   ← 이것

**왜 절 단위인가.** 대회 문서는 통째로 받으면 수십 KB다(WrestleMania가 그렇다).
그것을 모델에게 다 건네면 비용이 문서 길이에 비례하고, 정작 필요한 것은 결과가 적힌
한두 절뿐이다. 목차를 먼저 주고 **모델이 읽을 절을 고르게** 하면 그 비례가 끊긴다 —
에이전트에게 자율성이 필요한 이유가 여기 있다. 어느 절에 결과가 있는지는 문서마다
다르고(`Results` · `Event` · `Matches`), 규칙으로 정할 수 없다.

## 본문은 위키텍스트다 — 그리고 줄여서 준다

평문 추출(`prop=extracts&explaintext`)을 쓰지 않는다. **그쪽은 표를 버린다.** 대회
문서의 결과는 `{| class="wikitable"` 표에 실려 있어서, 평문으로 받으면 정작 찾는 것이
사라진다.

그래서 위키텍스트를 받되 `reduce_markup`으로 **줄여서** 준다. 무엇을 지우는지는 그
함수의 독스트링에 적혀 있다. 원문 그대로가 아니므로, 이 본문을 인용의 대조 기준으로
쓰는 쪽은 **자기가 건넨 그 문자열**과 대조해야 한다 — 위키에 다시 물어 대조하면
줄이기 규칙이 달라진 날 조용히 어긋난다.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class WikiSection:
    """목차 한 줄."""

    #: MediaWiki가 매기는 절 번호. `"1"`·`"12"`처럼 문자열이다(`"3.1"`이 아니다).
    index: str
    #: 절 제목.
    line: str
    #: 문서 안에서의 깊이. `2`가 최상위 절(`== 제목 ==`)이다.
    level: int


@dataclass(frozen=True)
class WikiSectionText:
    """절 하나의 본문과 그 본문이 속한 개정본."""

    #: 위키가 말하는 정규 문서 제목. 리다이렉트를 따라간 뒤의 이름이다.
    title: str
    index: str
    line: str
    #: `reduce_markup`을 거친 위키텍스트.
    text: str
    #: 이 본문을 낸 개정본. 계보이자 **재현의 열쇠**다. 없으면 주장하지 않는다.
    revision_id: str | None = None


_REF_PAIRED = re.compile(r"<ref[^>/]*>.*?</ref>", re.DOTALL | re.IGNORECASE)
_REF_SELF = re.compile(r"<ref[^>]*/\s*>", re.IGNORECASE)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_LINK_PIPED = re.compile(r"\[\[[^\]|]*\|([^\]]*)\]\]")
_LINK_PLAIN = re.compile(r"\[\[([^\]|]*)\]\]")
_BOLD_ITALIC = re.compile(r"'{2,5}")
_BLANK_RUN = re.compile(r"\n{3,}")


def reduce_markup(wikitext: str) -> str:
    """인용할 수 있을 만큼만 위키텍스트를 줄인다. **순수 함수다.**

    지우는 것:

    - `<ref>...</ref>` 각주와 `<!-- -->` 주석 — 본문이 아니고, 인용 안에 섞이면
      사람이 읽을 수 없다.
    - 링크 대괄호. `[[Pentagón Jr.|Penta]]` → `Penta`, `[[Rhea Ripley]]` →
      `Rhea Ripley`. **표시되는 쪽을 남긴다** — 카드에 적힌 이름이 그쪽이다.
    - 굵게·기울임 따옴표(`'''`). 승자 이름이 굵게 적히는 일이 많아서, 남겨 두면
      이름 대조가 따옴표 때문에 빗나간다.

    **지우지 않는 것:** 표 구분자(`{|` · `|-` · `!`)와 템플릿(`{{...}}`). 표 구조가
    사라지면 어느 칸이 승자인지 알 수 없고, 템플릿 안에 결과가 들어 있는 문서가 있다.
    읽기 불편한 것은 모델이 감당할 몫이고, 여기서 더 지우면 **사실이 사라진다.**
    """
    text = _COMMENT.sub("", wikitext)
    text = _REF_PAIRED.sub("", text)
    text = _REF_SELF.sub("", text)
    text = _LINK_PIPED.sub(r"\1", text)
    text = _LINK_PLAIN.sub(r"\1", text)
    text = _BOLD_ITALIC.sub("", text)
    return _BLANK_RUN.sub("\n\n", text).strip()


class WikiArticlePort(ABC):
    """**조회가 실패하면 `None`이다** — 추측한 목차나 빈 본문을 만들지 않는다."""

    @abstractmethod
    async def sections(self, title: str) -> tuple[WikiSection, ...] | None:
        """문서의 목차. 문서가 없거나 조회가 실패하면 `None`.

        빈 튜플과 `None`은 다르다 — 앞은 "절이 없는 문서"(짧은 문서가 그렇다)이고
        뒤는 "모른다"다.
        """
        ...

    @abstractmethod
    async def read_section(self, title: str, index: str) -> WikiSectionText | None:
        """절 하나의 본문. 없는 절이거나 조회가 실패하면 `None`."""
        ...
