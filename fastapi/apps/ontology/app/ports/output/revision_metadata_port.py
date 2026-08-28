"""문서의 **개정본 계보**를 묻는 출력 포트 (Phase 3-12).

`WebPageFetcherPort`가 "지금 이 주소의 본문"을 가져온다면, 이 포트는 "그 본문이
어느 개정본이고 언제 만들어졌는가"를 가져온다. 둘을 나눈 이유는 소스마다 답하는
방법이 다르기 때문이다 — 위키는 API를 갖고 있고, 대부분의 사이트는 갖고 있지 않다.

**답을 모르면 `None`이다.** 추정한 시각을 돌려주지 않는다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse


def wiki_title_from_url(url: str) -> str | None:
    """위키 주소에서 문서 제목을 뽑는다.

    `/wiki/Money_in_the_Bank_(2026)` 형태와 `?title=...` 형태를 모두 받는다.
    퍼센트 인코딩을 풀고 밑줄을 공백으로 바꿔 API가 돌려주는 제목과 같은 모양으로
    맞춘다 — 이 값이 계보 검증의 기준이 된다.

    **어댑터가 아니라 여기 있는 이유**: 유스케이스가 이 값으로 대조를 하는데,
    app 레이어가 adapter를 import하면 의존 방향이 뒤집힌다. 어댑터 쪽이 이것을
    가져다 쓴다(`adapter → app`은 허용 방향이다).
    """
    parsed = urlparse(url)
    query_title = parse_qs(parsed.query).get("title")
    raw = query_title[0] if query_title else None
    if raw is None:
        path = parsed.path
        marker = "/wiki/"
        if marker not in path:
            return None
        raw = path.split(marker, 1)[1]
    if not raw:
        return None
    return unquote(raw).replace("_", " ").strip() or None


@dataclass(frozen=True)
class RevisionMetadata:
    """개정본 하나의 계보.

    `title`을 함께 담는 이유가 이 DTO의 존재 이유에 가깝다 — 식별자만 믿으면
    **조용히 다른 문서를 가리킬 수 있다**(실측: 잘린 `oldid=13677280`이
    "Who Framed Roger Rabbit"으로 해석됐다). 부르는 쪽이 기대한 제목과 대조할 수
    있도록 돌려준다.
    """

    revision_id: str
    revised_at: datetime
    #: 소스가 말하는 문서 제목. 요청한 문서와 같은지 확인하는 데 쓴다.
    title: str


class RevisionMetadataPort(ABC):
    """주소 하나의 개정본 계보를 조회한다."""

    @abstractmethod
    async def fetch(self, url: str) -> RevisionMetadata | None:
        """모르면 `None`. **예외를 던져 수집을 멈추지 않는다.**

        계보를 못 얻는 것은 문서를 못 얻는 것과 다르다. 본문은 이미 손에 있고,
        계보만 비는 것이 정직한 상태다.
        """
        ...
