"""지식 코퍼스 집계 테스트 (Phase 3-4).

이 화면의 주장은 하나다 — **코퍼스에 있는 것과 실제로 쓰인 것은 다르다.** 그 대조가
URL 하나 어긋나는 것으로 무너지므로, 맞추는 규칙을 DB 없이 여기서 못 박는다.

셋을 구분한다.
- 출처가 없는 리포트(`sources=()`)는 어떤 문서도 쓰지 않은 것이다 — `odds`가 그렇다.
- 코퍼스에 **없는** 출처는 문서에 안 세고 따로 센다.
- 한 리포트가 같은 문서를 두 번 들어도 한 번이다.
"""

from __future__ import annotations

from datetime import UTC, datetime

from kayfabe.app.services.ai_lab_integrity import ReportRow
from kayfabe.app.services.ai_lab_knowledge import DocumentRow, summarize_knowledge

_NOW = datetime(2026, 8, 5, tzinfo=UTC)


def _document(
    *,
    url: str,
    domain: str = "en.wikipedia.org",
    title: str | None = "SummerSlam (2026)",
    chunks: int = 10,
    embedded: int | None = None,
    published: int = 0,
    collected: datetime | None = _NOW,
) -> DocumentRow:
    return DocumentRow(
        source_url=url,
        source_domain=domain,
        title=title,
        chunks=chunks,
        chunks_embedded=chunks if embedded is None else embedded,
        chunks_with_published_at=published,
        first_published_at=None,
        last_collected_at=collected,
    )


def _report(
    *,
    agent: str = "storyline",
    match_key: str = "m1",
    sources: tuple[str, ...] = (),
    pick: str | None = "left",
) -> ReportRow:
    return ReportRow(
        event_slug="summerslam",
        match_key=match_key,
        agent=agent,
        pick=pick,
        weight=1.0,
        summary="…",
        sources=sources,
    )


class TestUsage:
    def test_a_document_no_report_used_is_counted_but_unused(self) -> None:
        totals, documents, _ = summarize_knowledge(
            [_document(url="https://en.wikipedia.org/wiki/A")],
            [_report(sources=())],
        )
        assert totals.documents == 1
        assert totals.used_documents == 0
        assert totals.used_document_rate == 0.0
        assert documents[0].used_by_reports == 0
        assert documents[0].used_by_agents == ()

    def test_reports_that_loaded_a_document_are_counted_per_agent(self) -> None:
        url = "https://en.wikipedia.org/wiki/A"
        _, documents, _ = summarize_knowledge(
            [_document(url=url)],
            [
                _report(agent="storyline", match_key="m1", sources=(url,)),
                _report(agent="rumor", match_key="m1", sources=(url,)),
                _report(agent="odds", match_key="m1", sources=()),
            ],
        )
        assert documents[0].used_by_reports == 2
        assert documents[0].used_by_agents == ("rumor", "storyline")

    def test_the_same_document_twice_in_one_report_counts_once(self) -> None:
        url = "https://en.wikipedia.org/wiki/A"
        _, documents, _ = summarize_knowledge(
            [_document(url=url)], [_report(sources=(url, f"{url}/"))]
        )
        assert documents[0].used_by_reports == 1

    def test_a_trailing_slash_is_the_same_document(self) -> None:
        _, documents, _ = summarize_knowledge(
            [_document(url="https://en.wikipedia.org/wiki/A")],
            [_report(sources=("https://en.wikipedia.org/wiki/A/",))],
        )
        assert documents[0].used_by_reports == 1

    def test_a_different_case_is_a_different_document(self) -> None:
        """대소문자를 접지 않는다 — 접으면 다른 문서가 한 건으로 합쳐질 수 있다."""
        totals, documents, _ = summarize_knowledge(
            [_document(url="https://en.wikipedia.org/wiki/A")],
            [_report(sources=("https://en.wikipedia.org/wiki/a",))],
        )
        assert documents[0].used_by_reports == 0
        assert totals.sources_outside_corpus == 1

    def test_a_source_missing_from_the_corpus_is_counted_apart(self) -> None:
        totals, documents, _ = summarize_knowledge(
            [_document(url="https://en.wikipedia.org/wiki/A")],
            [_report(sources=("https://en.wikipedia.org/wiki/Gone",))],
        )
        assert totals.sources_outside_corpus == 1
        assert documents[0].used_by_reports == 0

    def test_used_documents_are_listed_first(self) -> None:
        used = "https://en.wikipedia.org/wiki/Used"
        _, documents, _ = summarize_knowledge(
            [
                _document(url="https://en.wikipedia.org/wiki/Unused", chunks=99),
                _document(url=used, chunks=1),
            ],
            [_report(sources=(used,))],
        )
        assert [d.source_url for d in documents] == [
            used,
            "https://en.wikipedia.org/wiki/Unused",
        ]


class TestTotals:
    def test_totals_come_from_the_document_rows(self) -> None:
        """타일과 목록이 같은 원천을 봐야 둘이 어긋나지 않는다."""
        totals, _, _ = summarize_knowledge(
            [
                _document(
                    url="https://a.example/1", chunks=10, embedded=8, published=2
                ),
                _document(
                    url="https://b.example/2",
                    domain="b.example",
                    chunks=5,
                    embedded=5,
                    published=0,
                ),
            ],
            [],
        )
        assert totals.documents == 2
        assert totals.chunks == 15
        assert totals.chunks_embedded == 13
        assert totals.chunks_with_published_at == 2
        assert totals.domains == 2

    def test_an_empty_corpus_gives_a_null_rate_not_zero(self) -> None:
        totals, documents, domains = summarize_knowledge([], [])
        assert totals.documents == 0
        assert totals.used_document_rate is None
        assert documents == []
        assert domains == []

    def test_reports_with_sources_counts_reports_not_urls(self) -> None:
        url = "https://en.wikipedia.org/wiki/A"
        totals, _, _ = summarize_knowledge(
            [_document(url=url)],
            [
                _report(agent="storyline", sources=(url, "https://other.example/x")),
                _report(agent="odds", sources=()),
            ],
        )
        assert totals.reports_total == 2
        assert totals.reports_with_sources == 1

    def test_the_latest_collection_wins(self) -> None:
        later = datetime(2026, 8, 10, tzinfo=UTC)
        totals, _, _ = summarize_knowledge(
            [
                _document(url="https://a.example/1", collected=_NOW),
                _document(url="https://a.example/2", collected=later),
            ],
            [],
        )
        assert totals.last_collected_at == later


class TestDomains:
    def test_a_domain_row_counts_its_documents_and_used_documents(self) -> None:
        used = "https://en.wikipedia.org/wiki/Used"
        _, _, domains = summarize_knowledge(
            [
                _document(url=used, chunks=10),
                _document(url="https://en.wikipedia.org/wiki/Unused", chunks=4),
                _document(
                    url="https://other.example/x", domain="other.example", chunks=2
                ),
            ],
            [_report(sources=(used,))],
        )
        assert [
            (d.domain, d.documents, d.chunks, d.used_documents) for d in domains
        ] == [
            ("en.wikipedia.org", 2, 14, 1),
            ("other.example", 1, 2, 0),
        ]
