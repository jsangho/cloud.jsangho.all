"""개정본 계보 수집 테스트 (Phase 3-12) — 허브 쪽.

가장 중요한 계약: **식별자만 믿지 않는다.** 위키의 잘린 `oldid`는 에러를 내지 않고
**다른 문서로 조용히 해석된다** — 실측에서 `oldid=13677280`이 "Who Framed Roger
Rabbit"(2005년)으로 돌아왔다. 그런 계보를 저장하면 판정이 엉뚱한 문서의 시각으로
통과/보류를 가르게 된다.

두 번째 계약: **계보를 못 얻어도 수집은 성공한다.** 본문은 이미 손에 있고, 계보만
비는 것이 정직한 상태다. 여기서 예외를 올리면 API 장애 하나가 코퍼스 적재를 통째로
멈춘다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/ontology/tests/revision_provenance_test.py -q
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ontology.app.dtos.crawler_dto import FetchedPage
from ontology.app.ports.output.revision_metadata_port import (
    RevisionMetadata,
    RevisionMetadataPort,
    wiki_title_from_url,
)
from ontology.app.ports.output.robots_policy_port import RobotsPolicyPort
from ontology.app.ports.output.web_page_fetcher_port import WebPageFetcherPort
from ontology.app.use_cases.public_source_interactor import PublicSourceInteractor

_ALLOWED = frozenset({"en.wikipedia.org"})
_URL = "https://en.wikipedia.org/wiki/Money_in_the_Bank_(2026)"
_PAGE = """
<html>
  <head><title>Money in the Bank (2026) - Wikipedia</title></head>
  <body><p>The 2026 Money in the Bank is an upcoming event.</p></body>
</html>
"""

_REVISED = datetime(2026, 8, 1, 14, 24, 4, tzinfo=UTC)


class FakeFetcher(WebPageFetcherPort):
    async def fetch(self, url: str) -> FetchedPage:
        return FetchedPage(
            url=url,
            status_code=200,
            html=_PAGE,
            fetched_at=datetime.now(UTC).isoformat(),
        )


class FakeRobots(RobotsPolicyPort):
    async def is_allowed(self, url: str) -> bool:
        return True


class FakeRevisions(RevisionMetadataPort):
    """`result`를 그대로 돌려주거나, `raises`가 있으면 그것을 던진다."""

    def __init__(
        self,
        result: RevisionMetadata | None = None,
        *,
        raises: Exception | None = None,
    ) -> None:
        self.result = result
        self.raises = raises
        self.calls: list[str] = []

    async def fetch(self, url: str) -> RevisionMetadata | None:
        self.calls.append(url)
        if self.raises is not None:
            raise self.raises
        return self.result


def _interactor(revisions: RevisionMetadataPort | None) -> PublicSourceInteractor:
    return PublicSourceInteractor(
        allowed_domains=_ALLOWED,
        fetcher=FakeFetcher(),
        robots=FakeRobots(),
        revisions=revisions,
    )


class TestTitleDerivation:
    def test_path_form(self) -> None:
        assert wiki_title_from_url(_URL) == "Money in the Bank (2026)"

    def test_percent_encoded(self) -> None:
        url = "https://en.wikipedia.org/wiki/Finn_B%C3%A1lor"
        assert wiki_title_from_url(url) == "Finn Bálor"

    def test_query_form(self) -> None:
        url = "https://en.wikipedia.org/w/index.php?title=Penta&oldid=1366119756"
        assert wiki_title_from_url(url) == "Penta"

    def test_non_wiki_url_has_no_title(self) -> None:
        assert wiki_title_from_url("https://www.wwe.com/shows/summerslam") is None


class TestValidRevisionIsKept:
    @pytest.mark.asyncio
    async def test_matching_title_is_accepted(self) -> None:
        revisions = FakeRevisions(
            RevisionMetadata(
                revision_id="1367179316",
                revised_at=_REVISED,
                title="Money in the Bank (2026)",
            )
        )
        document = await _interactor(revisions).collect(_URL)

        assert document is not None
        assert document.revision_id == "1367179316"
        assert document.revised_at == _REVISED

    @pytest.mark.asyncio
    async def test_underscore_and_case_differences_are_absorbed(self) -> None:
        revisions = FakeRevisions(
            RevisionMetadata(
                revision_id="1367179316",
                revised_at=_REVISED,
                title="money_in_the_bank (2026)",
            )
        )
        document = await _interactor(revisions).collect(_URL)

        assert document is not None
        assert document.revision_id == "1367179316"


class TestCorruptedOldidIsRejected:
    """CASE F — **실측 사례를 고정한다.**

    잘린 `oldid=13677280`은 API에서 에러가 아니라 "Who Framed Roger Rabbit"으로
    돌아온다. 계보를 버리되 수집은 성공해야 한다.
    """

    @pytest.mark.asyncio
    async def test_mismatched_title_drops_provenance(self) -> None:
        revisions = FakeRevisions(
            RevisionMetadata(
                revision_id="13677280",
                revised_at=datetime(2005, 5, 7, 2, 19, 55, tzinfo=UTC),
                title="Who Framed Roger Rabbit",
            )
        )
        document = await _interactor(revisions).collect(_URL)

        assert document is not None, "계보가 틀렸다고 수집까지 실패시키지 않는다"
        assert document.revision_id is None
        assert document.revised_at is None
        assert document.text, "본문은 그대로 남는다"

    @pytest.mark.asyncio
    async def test_near_miss_title_is_also_rejected(self) -> None:
        """연도만 다른 문서도 다른 문서다 — 구두점까지 지우면 이 대조가 무너진다."""
        revisions = FakeRevisions(
            RevisionMetadata(
                revision_id="999",
                revised_at=_REVISED,
                title="Money in the Bank (2025)",
            )
        )
        document = await _interactor(revisions).collect(_URL)

        assert document is not None
        assert document.revision_id is None


class TestApiFailureDoesNotStopIngestion:
    """CASE G — API가 죽어도 본문 수집은 계속된다."""

    @pytest.mark.asyncio
    async def test_none_result_leaves_provenance_empty(self) -> None:
        document = await _interactor(FakeRevisions(None)).collect(_URL)

        assert document is not None
        assert document.revision_id is None
        assert document.revised_at is None

    @pytest.mark.asyncio
    async def test_no_revision_port_at_all(self) -> None:
        """계보 포트를 안 끼운 호출자(기존 테스트·스크립트)가 그대로 돈다."""
        document = await _interactor(None).collect(_URL)

        assert document is not None
        assert document.revision_id is None
        assert document.text
