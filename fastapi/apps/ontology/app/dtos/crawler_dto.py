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


@dataclass(frozen=True)
class CrawlResult:
    website: str
    keyword: str
    status_code: int
    html: str
    fetched_at: str
    content_length: int
    saved_path: str
