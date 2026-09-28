from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CrawlJob:
    website: str
    keyword: str


@dataclass(frozen=True)
class FetchedPage:
    url: str
    status_code: int
    html: str
    fetched_at: str
    #: 아래 둘은 **이 응답이 스스로 말하는 판본**이다. 개정본 API가 없는 소스의
    #: 계보가 여기서 나온다 — 본문과 같은 응답이라 "다른 문서를 가리킬" 수 없다.
    #: 헤더가 없으면 `None`이고, 그때는 계보를 주장하지 않는다.
    #:
    #: 기본값을 둔 이유는 이 칸을 모르는 기존 호출자(크롤러·테스트)를 그대로 두기
    #: 위해서다.
    etag: str | None = None
    #: RFC 7231 형식의 문자열 그대로 둔다 — 파싱은 쓰는 쪽에서 한다.
    last_modified: str | None = None


@dataclass(frozen=True)
class CrawlResult:
    website: str
    keyword: str
    status_code: int
    html: str
    fetched_at: str
    content_length: int
    saved_path: str
