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

from datetime import UTC, datetime, timedelta

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
    """본문을 돌려준다. 리다이렉트 사례는 **목적지 문서의 본문**을 싣는다 — 실제
    수집이 그렇게 동작한다(HTML fetch는 리다이렉트를 따라간다)."""

    def __init__(self, html: str = _PAGE) -> None:
        self.html = html

    async def fetch(self, url: str) -> FetchedPage:
        return FetchedPage(
            url=url,
            status_code=200,
            html=self.html,
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


def _interactor(
    revisions: RevisionMetadataPort | None, *, html: str = _PAGE
) -> PublicSourceInteractor:
    return PublicSourceInteractor(
        allowed_domains=_ALLOWED,
        fetcher=FakeFetcher(html),
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


def _redirect_page(subject: str, redirected_from: str) -> str:
    """리다이렉트로 도착한 문서의 본문 — 위키가 실제로 내보내는 모양이다."""
    return (
        f"<html><head><title>{subject} - Wikipedia</title></head>"
        f"<body><p>(Redirected from {redirected_from}) {subject} is a "
        "professional wrestler.</p></body></html>"
    )


class TestRedirectKeepsItsLineage:
    """**Phase 3-13 — 2026-09-21에 규칙을 뒤집었다.**

    Stage 1은 리다이렉트면 계보를 통째로 버렸다. 근거는 "본문은 목적지인데 계보는
    출발지 스텁의 것이라 서로 다른 글을 가리킨다"였다. 그런데 **그 위험은 같은
    Stage가 `redirects=1`을 붙이면서 사라졌다.** 실측으로 갈린다:

        IYO SKY 스텁     rev 1141484684 @ 2023-02-25   ← redirects 없이 물었을 때
        Iyo Sky 목적지   rev 1374199432 @ 2026-09-10   ← redirects=1이 주는 것

    어댑터는 후자를 받는다(`wikipedia_revision_metadata_test`의
    `test_query_sends_redirects_flag`가 그 파라미터를 못 박는다). 본문 fetch도
    리다이렉트를 따라가므로 **둘이 같은 글을 가리킨다.** 버리면 멀쩡한 계보가
    사라진다 — 운영 코퍼스에서 실제로 44청크가 그렇게 비어 있었다.

    그래서 관문을 없애는 대신 **대조 대상을 바꿨다**: 주소가 아니라 우리가 받아 온
    본문의 제목과 맞춘다. 주소는 우리가 이름으로 조립한 추측이고, 본문 제목은
    서버가 준 사실이다.
    """

    @pytest.mark.asyncio
    async def test_iyo_sky_keeps_the_destination_revision(self) -> None:
        """대소문자만 다른 리다이렉트 — 목적지 개정본이 본문의 계보가 맞다."""
        url = "https://en.wikipedia.org/wiki/IYO_SKY"
        revised_at = datetime(2026, 9, 10, 13, 14, 9, tzinfo=UTC)
        revisions = FakeRevisions(
            RevisionMetadata(
                revision_id="1374199432",
                revised_at=revised_at,
                title="Iyo Sky",
                is_redirect=True,
            )
        )
        interactor = _interactor(revisions, html=_redirect_page("Iyo Sky", "IYO SKY"))
        document = await interactor.collect(url)

        assert document is not None
        assert document.revision_id == "1374199432"
        assert document.revised_at == revised_at

    @pytest.mark.asyncio
    async def test_royce_keys_keeps_the_destination_revision(self) -> None:
        """주소가 말하는 이름과 본문이 달라도, 계보는 **본문**의 것이면 맞다.

        `/wiki/Royce_Keys` → `Powerhouse Hobbs`. 주소가 어긋난 것은 별개의 문제이고
        (수집기가 이름으로 URL을 조립한다), 계보 자체는 우리가 저장한 글의 것이다.
        """
        url = "https://en.wikipedia.org/wiki/Royce_Keys"
        revised_at = datetime(2026, 9, 20, 22, 41, 12, tzinfo=UTC)
        revisions = FakeRevisions(
            RevisionMetadata(
                revision_id="1375925293",
                revised_at=revised_at,
                title="Powerhouse Hobbs",
                is_redirect=True,
            )
        )
        interactor = _interactor(
            revisions, html=_redirect_page("Powerhouse Hobbs", "Royce Keys")
        )
        document = await interactor.collect(url)

        assert document is not None
        assert document.revision_id == "1375925293"
        assert document.revised_at == revised_at

    @pytest.mark.asyncio
    async def test_a_worthless_page_still_has_a_correct_lineage(self) -> None:
        """`/wiki/The_Bloodline` → 동음이의 페이지.

        **계보는 옳고 내용이 무가치한 경우**다. 둘은 다른 문제이고, 계보 관문이
        내용 품질까지 떠맡으면 판정이 무엇을 재는지 흐려진다.
        """
        url = "https://en.wikipedia.org/wiki/The_Bloodline"
        revisions = FakeRevisions(
            RevisionMetadata(
                revision_id="1367555159",
                revised_at=datetime(2026, 8, 3, 20, 19, 44, tzinfo=UTC),
                title="Bloodline (disambiguation)",
                is_redirect=True,
            )
        )
        interactor = _interactor(
            revisions,
            html=_redirect_page("Bloodline (disambiguation)", "The Bloodline"),
        )
        document = await interactor.collect(url)

        assert document is not None
        assert document.revision_id == "1367555159"

    @pytest.mark.asyncio
    async def test_a_revision_of_another_document_is_still_rejected(self) -> None:
        """**이 방어는 그대로다.** 잘린 `oldid`가 엉뚱한 문서로 해석된 실측 사례.

        계보가 말하는 제목("Who Framed Roger Rabbit")이 우리가 받아 온 본문
        ("Lash Legend")과 맞지 않는다. 리다이렉트 관문을 없애도 이쪽은 걸린다 —
        오히려 주소가 아니라 본문과 맞추므로 기준이 더 단단하다.
        """
        url = "https://en.wikipedia.org/wiki/Lash_Legend"
        revisions = FakeRevisions(
            RevisionMetadata(
                revision_id="13677280",
                revised_at=datetime(2005, 5, 7, 2, 19, 55, tzinfo=UTC),
                title="Who Framed Roger Rabbit",
            )
        )
        interactor = _interactor(
            revisions,
            html=(
                "<html><head><title>Lash Legend - Wikipedia</title></head>"
                "<body><p>Lash Legend is a professional wrestler.</p></body></html>"
            ),
        )
        document = await interactor.collect(url)

        assert document is not None, "계보를 버려도 본문 수집은 성공한다"
        assert document.text
        assert document.revision_id is None, "2005년 개정본이 새어 나가면 안 된다"
        assert document.revised_at is None

    @pytest.mark.asyncio
    async def test_without_a_body_title_it_falls_back_to_the_url(self) -> None:
        """대조할 사실이 없으면 주소로 돌아간다 — 통과시키지 않기 위해서다."""
        revisions = FakeRevisions(
            RevisionMetadata(
                revision_id="1367179316",
                revised_at=_REVISED,
                title="Money in the Bank (2026)",
            )
        )
        interactor = _interactor(
            revisions,
            html="<html><head></head><body><p>제목 없는 문서</p></body></html>",
        )
        document = await interactor.collect(_URL)

        assert document is not None
        # 주소에서 뽑은 제목과 맞으므로 통과한다 — 옛 경로가 그대로 산다.
        assert document.revision_id == "1367179316"


class TestFutureRevisionIsRejected:
    """CASE G — 아직 만들어지지도 않은 개정본을 우리가 읽었을 수는 없다."""

    @pytest.mark.asyncio
    async def test_revision_after_collection_is_dropped(self) -> None:
        revisions = FakeRevisions(
            RevisionMetadata(
                revision_id="9999",
                revised_at=datetime.now(UTC) + timedelta(days=1),
                title="Money in the Bank (2026)",
            )
        )
        document = await _interactor(revisions).collect(_URL)

        assert document is not None
        assert document.revision_id is None
        assert document.revised_at is None

    @pytest.mark.asyncio
    async def test_revision_just_before_collection_is_kept(self) -> None:
        """경계 바로 아래는 통과해야 한다 — 게이트가 과하게 닫히면 안 된다."""
        revisions = FakeRevisions(
            RevisionMetadata(
                revision_id="1367179316",
                revised_at=datetime.now(UTC) - timedelta(seconds=1),
                title="Money in the Bank (2026)",
            )
        )
        document = await _interactor(revisions).collect(_URL)

        assert document is not None
        assert document.revision_id == "1367179316"


class TestEmptyRevisionIdIsRejected:
    @pytest.mark.asyncio
    async def test_blank_revision_id_drops_provenance(self) -> None:
        """식별자가 빈 문자열이면 타입은 통과하지만 계보로는 쓸 수 없다."""
        revisions = FakeRevisions(
            RevisionMetadata(
                revision_id="",
                revised_at=_REVISED,
                title="Money in the Bank (2026)",
            )
        )
        document = await _interactor(revisions).collect(_URL)

        assert document is not None
        assert document.revision_id is None
