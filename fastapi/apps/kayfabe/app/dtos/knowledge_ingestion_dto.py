"""지식 적재 경계 DTO — 하네스 §10-T3."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IngestKnowledgeCommand:
    """수집 요청. **관리자·스크립트가 명시적으로 부른다** — 사용자 요청 경로가 아니다."""

    urls: tuple[str, ...]


@dataclass(frozen=True)
class SourceDocument:
    """허브가 가져다준 문서 하나. 여기서부터는 kayfabe의 말로 다룬다."""

    url: str
    title: str | None
    text: str
    published_at: datetime | None = None
    #: 개정본 계보 (Phase 3-12). 확인 못 했으면 `None`이고, 그 `None`은 "모른다"다.
    revision_id: str | None = None
    revised_at: datetime | None = None


@dataclass(frozen=True)
class NewKnowledgeChunk:
    """저장 직전의 청크. `source_url`이 비면 만들 수 없다(하네스 §3-D6)."""

    source_url: str
    source_domain: str
    title: str | None
    content: str
    content_hash: str
    embedding: list[float]
    published_at: datetime | None = None
    #: 이 청크를 뽑아낸 개정본. 같은 URL이라도 개정본이 다르면 다른 글이다.
    source_revision_id: str | None = None
    source_revised_at: datetime | None = None


@dataclass(frozen=True)
class IngestionSummary:
    """적재 결과. 숫자가 어긋나는 지점이 곧 점검할 지점이다."""

    requested: int
    #: 실제로 본문을 받아 온 문서 수. `requested`와 차이 나면 robots.txt·404다.
    collected: int
    chunks: int
    stored: int
    #: 이미 있는 내용이라 넘어간 청크. 재실행하면 대부분 여기로 간다.
    duplicates: int
    #: 임베딩에 실패해 저장하지 못한 청크.
    failed: int
    #: 본문은 받았지만 **개정본 계보를 확인하지 못한** 문서 수 (Phase 3-12).
    #: API 장애·제목 불일치·위키 아닌 소스가 전부 여기로 온다. 수집 실패가 아니므로
    #: `collected`에서 빼지 않고 따로 센다 — 이 숫자가 곧 시간 판정 불가 표본이다.
    provenance_unavailable: int = 0
