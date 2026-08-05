"""지식 적재 코디네이션 테스트 — 하네스 §10-T3.

**네트워크도 임베딩 모델도 DB도 쓰지 않는다.** 페이크 포트만으로 검증한다.
핵심은 "한 URL의 실패가 나머지를 멈추지 않는다"와 "요약 숫자가 거짓말하지 않는다"다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/kayfabe/tests -q
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from kayfabe.app.dtos.knowledge_ingestion_dto import (
    IngestKnowledgeCommand,
    NewKnowledgeChunk,
    SourceDocument,
)
from kayfabe.app.ports.output.knowledge_chunk_repository import KnowledgeChunkRepository
from kayfabe.app.ports.output.public_source_port import (
    PublicSourcePort,
    SourceNotAllowedError,
)
from kayfabe.app.ports.output.text_embedding_port import (
    EmbeddingUnavailableError,
    TextEmbeddingPort,
)
from kayfabe.app.use_cases.knowledge_ingestion_interactor import (
    KnowledgeIngestionInteractor,
)

_WWE_URL = "https://www.wwe.com/shows/summerslam"
_LONG = "Roman Reigns가 SummerSlam 메인이벤트에 출전한다는 발표가 나왔다. " * 3


class FakeSource(PublicSourcePort):
    def __init__(self, documents: dict[str, SourceDocument | None]) -> None:
        self._documents = documents
        self.requested: list[str] = []

    async def collect(self, url: str) -> SourceDocument | None:
        self.requested.append(url)
        if url not in self._documents:
            raise SourceNotAllowedError(f"허용 도메인이 아닙니다: {url}")
        return self._documents[url]


class FakeEmbedder(TextEmbeddingPort):
    def __init__(self, *, fail_from: int | None = None) -> None:
        self.fail_from = fail_from
        self.calls: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        if self.fail_from is not None and len(self.calls) > self.fail_from:
            raise EmbeddingUnavailableError("모델 없음")
        return [0.1, 0.2]


class FakeRepository(KnowledgeChunkRepository):
    def __init__(self, *, stored: int | None = None) -> None:
        self.saved: list[NewKnowledgeChunk] = []
        self._stored = stored

    async def save_new(self, chunks: Sequence[NewKnowledgeChunk]) -> int:
        self.saved.extend(chunks)
        return len(chunks) if self._stored is None else self._stored


def _document(text: str = _LONG, **kwargs: object) -> SourceDocument:
    defaults: dict[str, object] = {
        "url": _WWE_URL,
        "title": "SummerSlam",
        "text": text,
        "published_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(kwargs)
    return SourceDocument(**defaults)  # type: ignore[arg-type]


def _interactor(
    source: FakeSource,
    embedder: FakeEmbedder | None = None,
    repository: FakeRepository | None = None,
    *,
    max_chunks: int | None = None,
) -> KnowledgeIngestionInteractor:
    return KnowledgeIngestionInteractor(
        source,
        embedder or FakeEmbedder(),
        repository or FakeRepository(),
        max_chunks_per_document=max_chunks,
    )


@pytest.mark.asyncio
async def test_stores_chunks_with_source_and_domain() -> None:
    source = FakeSource({_WWE_URL: _document()})
    repository = FakeRepository()

    summary = await _interactor(source, repository=repository).ingest(
        IngestKnowledgeCommand(urls=(_WWE_URL,))
    )

    assert summary.collected == 1
    assert summary.stored == len(repository.saved)
    chunk = repository.saved[0]
    assert chunk.source_url == _WWE_URL
    assert chunk.source_domain == "www.wwe.com"
    assert chunk.title == "SummerSlam"
    assert chunk.published_at == datetime(2026, 8, 1, tzinfo=UTC)
    assert chunk.embedding == [0.1, 0.2]
    assert len(chunk.content_hash) == 64


@pytest.mark.asyncio
async def test_disallowed_url_does_not_stop_the_rest() -> None:
    """오타 하나가 나머지 수집을 취소하면 재실행 비용이 상대 서버로 간다."""
    source = FakeSource({_WWE_URL: _document()})
    repository = FakeRepository()

    summary = await _interactor(source, repository=repository).ingest(
        IngestKnowledgeCommand(urls=("https://example.test/x", _WWE_URL))
    )

    assert summary.requested == 2
    assert summary.collected == 1
    assert repository.saved


@pytest.mark.asyncio
async def test_unreadable_document_counts_as_not_collected() -> None:
    """robots.txt가 막았거나 404면 수집 0건이다 — 실패가 아니라 읽지 않은 것이다."""
    source = FakeSource({_WWE_URL: None})

    summary = await _interactor(source).ingest(IngestKnowledgeCommand(urls=(_WWE_URL,)))

    assert summary.collected == 0
    assert summary.chunks == 0
    assert summary.stored == 0
    assert summary.failed == 0


@pytest.mark.asyncio
async def test_embedding_failure_is_counted_not_stored() -> None:
    """벡터 없는 청크는 검색에 잡히지 않는다 — 저장하면 죽은 행이다."""
    long_text = " ".join(
        f"{i}번째 문장입니다. 내용을 충분히 길게 채운 문장입니다." for i in range(60)
    )
    source = FakeSource({_WWE_URL: _document(text=long_text)})
    embedder = FakeEmbedder(fail_from=1)
    repository = FakeRepository()

    summary = await _interactor(source, embedder, repository).ingest(
        IngestKnowledgeCommand(urls=(_WWE_URL,))
    )

    assert summary.failed >= 1
    assert summary.stored == len(repository.saved)
    assert summary.chunks == summary.stored + summary.duplicates + summary.failed


@pytest.mark.asyncio
async def test_duplicates_are_reported_not_hidden() -> None:
    """재실행하면 대부분 중복으로 간다. 그 숫자가 요약에 드러나야 한다."""
    source = FakeSource({_WWE_URL: _document()})
    repository = FakeRepository(stored=0)

    summary = await _interactor(source, repository=repository).ingest(
        IngestKnowledgeCommand(urls=(_WWE_URL,))
    )

    assert summary.stored == 0
    assert summary.duplicates == summary.chunks
    assert summary.failed == 0


@pytest.mark.asyncio
async def test_empty_command_touches_nothing() -> None:
    source = FakeSource({})

    summary = await _interactor(source).ingest(IngestKnowledgeCommand(urls=()))

    assert source.requested == []
    assert summary.requested == 0
    assert summary.stored == 0


@pytest.mark.asyncio
async def test_chunk_cap_limits_embedding_work() -> None:
    """위키 인물 문서는 뒤로 갈수록 타이틀 이력·각주다 — 앞부분만 담는다."""
    long_text = " ".join(
        f"{i}번째 문단입니다. 내용을 충분히 길게 채운 문장을 넣습니다."
        for i in range(80)
    )
    source = FakeSource({_WWE_URL: _document(text=long_text)})
    embedder = FakeEmbedder()
    repository = FakeRepository()

    summary = await _interactor(source, embedder, repository, max_chunks=3).ingest(
        IngestKnowledgeCommand(urls=(_WWE_URL,))
    )

    assert summary.chunks == 3
    assert len(embedder.calls) == 3
    assert len(repository.saved) == 3
