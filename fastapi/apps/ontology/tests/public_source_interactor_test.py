"""공개 소스 수집 유스케이스 테스트 — 하네스(kayfabe) §10-T3의 허브 쪽.

가장 중요한 계약: **허용 도메인 밖으로는 요청 자체를 보내지 않는다.** 그래서 페이크
fetcher가 "불렸는지"를 본다 — 결과가 비었다는 것만으로는 요청을 안 보냈다는 증거가 못 된다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/ontology/tests/public_source_interactor_test.py -q
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ontology.app.dtos.crawler_dto import FetchedPage
from ontology.app.ports.input.public_source_use_case import SourceNotAllowedError
from ontology.app.ports.output.robots_policy_port import RobotsPolicyPort
from ontology.app.ports.output.web_page_fetcher_port import WebPageFetcherPort
from ontology.app.use_cases.public_source_interactor import PublicSourceInteractor

_ALLOWED = frozenset({"www.wwe.com"})
_URL = "https://www.wwe.com/shows/summerslam"

_PAGE = """
<html>
  <head>
    <title>SummerSlam 2026</title>
    <meta property="article:published_time" content="2026-08-01T12:00:00Z">
  </head>
  <body>
    <nav>메뉴 홈 로그인</nav>
    <script>var ads = 1;</script>
    <p>Roman Reigns가 메인이벤트에 출전한다.</p>
    <footer>저작권 표시</footer>
  </body>
</html>
"""


class FakeFetcher(WebPageFetcherPort):
    def __init__(self, html: str = _PAGE, status_code: int = 200) -> None:
        self.html = html
        self.status_code = status_code
        self.calls: list[str] = []

    async def fetch(self, url: str) -> FetchedPage:
        self.calls.append(url)
        return FetchedPage(
            url=url,
            status_code=self.status_code,
            html=self.html,
            fetched_at=datetime.now(UTC).isoformat(),
        )


class FakeRobots(RobotsPolicyPort):
    def __init__(self, *, allowed: bool = True) -> None:
        self.allowed = allowed
        self.calls: list[str] = []

    async def is_allowed(self, url: str) -> bool:
        self.calls.append(url)
        return self.allowed


def _interactor(
    fetcher: FakeFetcher | None = None, robots: FakeRobots | None = None
) -> PublicSourceInteractor:
    return PublicSourceInteractor(
        allowed_domains=_ALLOWED,
        fetcher=fetcher or FakeFetcher(),
        robots=robots or FakeRobots(),
    )


@pytest.mark.asyncio
async def test_collects_body_without_navigation_noise() -> None:
    document = await _interactor().collect(_URL)

    assert document is not None
    assert document.title == "SummerSlam 2026"
    assert "Roman Reigns가 메인이벤트에 출전한다." in document.text
    # 메뉴·스크립트·푸터는 근거가 아니다.
    assert "메뉴" not in document.text
    assert "var ads" not in document.text
    assert "저작권" not in document.text


@pytest.mark.asyncio
async def test_reads_published_time_as_utc() -> None:
    document = await _interactor().collect(_URL)

    assert document is not None
    assert document.published_at == datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_missing_published_time_stays_none() -> None:
    """모르는 시각을 오늘로 채우면 몇 달 전 소식이 최신 자리를 차지한다."""
    fetcher = FakeFetcher(html="<html><body><p>날짜 없는 글입니다.</p></body></html>")

    document = await _interactor(fetcher).collect(_URL)

    assert document is not None
    assert document.published_at is None


@pytest.mark.asyncio
async def test_domain_outside_allowlist_is_never_requested() -> None:
    fetcher = FakeFetcher()
    robots = FakeRobots()

    with pytest.raises(SourceNotAllowedError):
        await _interactor(fetcher, robots).collect("https://example.test/rumor")

    assert fetcher.calls == []
    assert robots.calls == []


@pytest.mark.asyncio
async def test_subdomain_is_not_implicitly_allowed() -> None:
    """`www.wwe.com`을 허용했다고 `shop.wwe.com`까지 열리지 않는다."""
    fetcher = FakeFetcher()

    with pytest.raises(SourceNotAllowedError):
        await _interactor(fetcher).collect("https://shop.wwe.com/x")

    assert fetcher.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://www.wwe.com/x"])
async def test_non_http_scheme_is_rejected(url: str) -> None:
    fetcher = FakeFetcher()

    with pytest.raises(SourceNotAllowedError):
        await _interactor(fetcher).collect(url)

    assert fetcher.calls == []


@pytest.mark.asyncio
async def test_robots_disallow_skips_fetch() -> None:
    fetcher = FakeFetcher()
    robots = FakeRobots(allowed=False)

    document = await _interactor(fetcher, robots).collect(_URL)

    assert document is None
    assert fetcher.calls == []


@pytest.mark.asyncio
async def test_non_200_response_is_not_a_document() -> None:
    fetcher = FakeFetcher(status_code=404)

    assert await _interactor(fetcher).collect(_URL) is None


@pytest.mark.asyncio
async def test_empty_body_is_not_a_document() -> None:
    fetcher = FakeFetcher(html="<html><body><nav>메뉴</nav></body></html>")

    assert await _interactor(fetcher).collect(_URL) is None
