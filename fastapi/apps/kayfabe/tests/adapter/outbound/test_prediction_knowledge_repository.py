"""지식 검색 리포지토리 테스트 — 하네스 §10-T4.

**DB를 띄우지 않는다.** `<=>`는 pgvector 연산자라 SQLite에서 실행되지 않고, 실제
임베딩 모델은 2.3GB짜리다. 여기서 고정하려는 계약은 그 둘이 아니라 이쪽이다.

1. 헛돈 호출을 하지 않는다 (빈 질의·`top_k<=0`이면 임베딩조차 만들지 않는다)
2. 조회 실패가 `KnowledgeSourceUnavailableError`로 올라온다 — 조용히 빈 목록이 되면
   "아는 게 없음"과 "못 물어봄"이 구분되지 않는다
3. 뽑는 것은 유사도, 늘어놓는 것은 최신순

실행 (반드시 `fastapi/` 안에서 — 하네스 §12 게이트와 같은 명령):

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/kayfabe/tests -q
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.exc import OperationalError

from kayfabe.adapter.outbound.repositories import prediction_knowledge_repository
from kayfabe.adapter.outbound.repositories.prediction_knowledge_repository import (
    PredictionKnowledgeRepository,
)
from kayfabe.app.ports.output.prediction_knowledge_port import (
    KnowledgeSourceUnavailableError,
)


class _Row:
    """`KnowledgeChunkModel` 대역 — 매핑에 쓰는 속성만 갖는다."""

    def __init__(
        self,
        *,
        content: str,
        source_url: str,
        title: str | None = None,
        published_at: datetime | None = None,
    ) -> None:
        self.content = content
        self.source_url = source_url
        self.title = title
        self.published_at = published_at


class _FakeSession:
    def __init__(self, rows: list[_Row], *, error: Exception | None = None) -> None:
        self._rows = rows
        self._error = error
        self.statements: list[Any] = []

    async def scalars(self, statement: Any) -> Any:
        self.statements.append(statement)
        if self._error is not None:
            raise self._error
        rows = self._rows

        class _Result:
            def all(self) -> list[_Row]:
                return rows

        return _Result()


class _FakeKeymaker:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[str] = []

    def embed_text(self, text: str) -> list[float]:
        self.calls.append(text)
        if self.error is not None:
            raise self.error
        return [0.1, 0.2, 0.3]


@pytest.fixture
def keymaker(monkeypatch: pytest.MonkeyPatch) -> _FakeKeymaker:
    fake = _FakeKeymaker()
    monkeypatch.setattr(
        prediction_knowledge_repository, "get_keymaker", lambda: fake, raising=True
    )
    return fake


def _repository(session: Any) -> PredictionKnowledgeRepository:
    return PredictionKnowledgeRepository(session)  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["", "   "])
async def test_blank_query_skips_embedding(keymaker: _FakeKeymaker, query: str) -> None:
    session = _FakeSession([])

    result = await _repository(session).search(query=query, top_k=5)

    assert result == []
    assert keymaker.calls == []
    assert session.statements == []


@pytest.mark.asyncio
async def test_non_positive_top_k_skips_embedding(keymaker: _FakeKeymaker) -> None:
    """0건을 요청했으면 임베딩도 조회도 낭비다."""
    session = _FakeSession([])

    result = await _repository(session).search(query="Roman Reigns", top_k=0)

    assert result == []
    assert keymaker.calls == []


@pytest.mark.asyncio
async def test_maps_row_to_chunk_with_source(keymaker: _FakeKeymaker) -> None:
    session = _FakeSession(
        [
            _Row(
                content="타이틀 매치가 확정됐다.",
                source_url="https://www.wwe.com/shows/summerslam",
                title="SummerSlam 카드 발표",
                published_at=datetime(2026, 8, 1, tzinfo=UTC),
            )
        ]
    )

    chunks = await _repository(session).search(query="SummerSlam", top_k=5)

    assert len(chunks) == 1
    # 제목이 본문 앞에 붙는다 — 청크만 보면 무슨 글인지 알 수 없다.
    assert chunks[0].text == "SummerSlam 카드 발표\n타이틀 매치가 확정됐다."
    assert chunks[0].source_url == "https://www.wwe.com/shows/summerslam"
    assert chunks[0].published_at == datetime(2026, 8, 1, tzinfo=UTC)
    assert keymaker.calls == ["SummerSlam"]


@pytest.mark.asyncio
async def test_untitled_row_keeps_content_only(keymaker: _FakeKeymaker) -> None:
    session = _FakeSession(
        [_Row(content="본문만 있다.", source_url="https://a.test/1")]
    )

    chunks = await _repository(session).search(query="q", top_k=5)

    assert chunks[0].text == "본문만 있다."


@pytest.mark.asyncio
async def test_results_are_newest_first(keymaker: _FakeKeymaker) -> None:
    """부상·복귀처럼 뒤집히는 사실에서는 최신 것이 이긴다."""
    session = _FakeSession(
        [
            _Row(
                content="옛날",
                source_url="https://a.test/old",
                published_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
            _Row(
                content="최신",
                source_url="https://a.test/new",
                published_at=datetime(2026, 8, 1, tzinfo=UTC),
            ),
        ]
    )

    chunks = await _repository(session).search(query="q", top_k=5)

    assert [c.text for c in chunks] == ["최신", "옛날"]


@pytest.mark.asyncio
async def test_unknown_published_at_goes_last(keymaker: _FakeKeymaker) -> None:
    """게시 시각을 모르는 청크를 수집 시각으로 채워 최신인 척하지 않는다."""
    session = _FakeSession(
        [
            _Row(content="시각 모름", source_url="https://a.test/x"),
            _Row(
                content="옛날",
                source_url="https://a.test/old",
                published_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        ]
    )

    chunks = await _repository(session).search(query="q", top_k=5)

    assert [c.text for c in chunks] == ["옛날", "시각 모름"]


@pytest.mark.asyncio
async def test_naive_and_aware_timestamps_sort_together(
    keymaker: _FakeKeymaker,
) -> None:
    """tz 유무가 섞여도 정렬이 TypeError로 죽지 않는다."""
    session = _FakeSession(
        [
            _Row(
                content="naive",
                source_url="https://a.test/1",
                published_at=datetime(2026, 3, 1),
            ),
            _Row(
                content="aware",
                source_url="https://a.test/2",
                published_at=datetime(2026, 6, 1, tzinfo=UTC),
            ),
        ]
    )

    chunks = await _repository(session).search(query="q", top_k=5)

    assert [c.text for c in chunks] == ["aware", "naive"]


@pytest.mark.asyncio
async def test_query_limit_is_top_k(keymaker: _FakeKeymaker) -> None:
    session = _FakeSession([])

    await _repository(session).search(query="q", top_k=3)

    compiled = str(session.statements[0])
    assert "LIMIT" in compiled
    assert session.statements[0]._limit == 3


@pytest.mark.asyncio
async def test_db_failure_becomes_knowledge_unavailable(
    keymaker: _FakeKeymaker,
) -> None:
    session = _FakeSession(
        [], error=OperationalError("SELECT 1", {}, Exception("down"))
    )

    with pytest.raises(KnowledgeSourceUnavailableError):
        await _repository(session).search(query="q", top_k=5)


@pytest.mark.asyncio
async def test_embedding_failure_becomes_knowledge_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """모델 로드 실패도 지식을 못 쓰는 상태다 — 코디네이터가 잡아 강등한다."""
    monkeypatch.setattr(
        prediction_knowledge_repository,
        "get_keymaker",
        lambda: _FakeKeymaker(error=RuntimeError("out of memory")),
        raising=True,
    )

    with pytest.raises(KnowledgeSourceUnavailableError):
        await _repository(_FakeSession([])).search(query="q", top_k=5)
