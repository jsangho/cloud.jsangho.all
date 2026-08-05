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
