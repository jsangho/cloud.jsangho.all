"""공개 소스 수집 경계 DTO.

허브가 돌려주는 것은 **본문 텍스트와 출처**뿐이다. 어느 앱의 지식인지, 어떻게 쪼갤지,
어디에 저장할지는 부르는 쪽(스포크)이 정한다 — 그래서 이 DTO에 도메인 어휘가 없다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PublicDocument:
    """수집한 공개 문서 하나."""

    url: str
    title: str | None
    text: str
    #: 원문 게시 시각. 페이지에서 못 읽으면 `None` — 수집 시각으로 대신 채우지 않는다.
    published_at: datetime | None = None
    #: 우리가 읽은 개정본의 식별자 (Phase 3-12). 위키는 `revid`다.
    #: **`published_at`과 다른 것을 잰다** — 같은 URL도 개정본마다 내용이 다르다.
    revision_id: str | None = None
    #: 그 개정본이 만들어진 시각. 확인 못 하면 `None`이고, 그 `None`은
    #: "모른다"이지 "통과"가 아니다. 여기서도 오늘 날짜로 대신 채우지 않는다.
    revised_at: datetime | None = None
