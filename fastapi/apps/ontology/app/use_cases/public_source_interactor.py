"""공개 소스 수집 유스케이스.

`ScraperInteractor`와 같은 자리·같은 방식(BeautifulSoup)이지만 목적이 다르다. 저쪽은
크롤 결과를 파일로 남기는 파이프라인이고, 이쪽은 **허용 도메인 안에서 본문만 뽑아
호출자에게 돌려준다.** 저장은 하지 않는다 — 어디에 담을지는 부르는 앱이 안다.

관문이 두 개다.
1. 허용 도메인 목록 — 목록 밖이면 **요청 자체를 보내지 않는다**
2. robots.txt — 상대가 막아 둔 경로는 가져오지 않는다
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ontology.app.dtos.crawler_dto import FetchedPage
from ontology.app.dtos.public_source_dto import PublicDocument
from ontology.app.ports.input.public_source_use_case import (
    PublicSourceUseCase,
    SourceNotAllowedError,
)
from ontology.app.ports.output.revision_metadata_port import (
    RevisionMetadata,
    RevisionMetadataPort,
    wiki_title_from_url,
)
from ontology.app.ports.output.robots_policy_port import RobotsPolicyPort
from ontology.app.ports.output.web_page_fetcher_port import WebPageFetcherPort

logger = logging.getLogger("uvicorn.error")

_WHITESPACE = re.compile(r"\s+")

#: 본문이 아닌 껍데기. 남겨 두면 청크가 메뉴·저작권 문구로 채워진다.
_NOISE_TAGS = (
    "script",
    "style",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "noscript",
)

#: 게시 시각이 실릴 만한 자리. 앞에서부터 처음 읽히는 값을 쓴다.
_PUBLISHED_META = (
    {"property": "article:published_time"},
    {"property": "og:published_time"},
    {"name": "article:published_time"},
    {"name": "pubdate"},
    {"name": "date"},
)


class PublicSourceInteractor(PublicSourceUseCase):
    def __init__(
        self,
        allowed_domains: frozenset[str],
        fetcher: WebPageFetcherPort,
        robots: RobotsPolicyPort,
        revisions: RevisionMetadataPort | None = None,
        header_lineage_domains: frozenset[str] = frozenset(),
    ) -> None:
        self._allowed_domains = frozenset(d.lower() for d in allowed_domains)
        self._fetcher = fetcher
        self._robots = robots
        #: 없으면 계보 없이 수집한다 — 계보는 있으면 좋은 것이지 수집의 조건이 아니다.
        self._revisions = revisions
        #: **개정본 API가 없어 응답 헤더를 계보로 인정하는 도메인** (2026-09-28).
        #:
        #: 기본이 빈 집합인 것이 중요하다 — 위키에는 절대 걸리면 안 된다. 그쪽
        #: `Last-Modified`는 `page_touched`라 개정본 시각이 아니고, 실측에서 21일
        #: 벌어져 있었다(`wikipedia_revision_metadata` 독스트링). API가 답하지 못한
        #: 날 헤더로 물러서면 계보의 품질이 조용히 떨어진다.
        #:
        #: **어느 소스를 이 목록에 넣을지는 허브가 정하지 않는다.** 수집 정책은 부르는
        #: 앱의 것이다(허용 도메인 목록과 같은 이유).
        self._header_lineage_domains = frozenset(
            d.lower() for d in header_lineage_domains
        )

    async def collect(self, url: str) -> PublicDocument | None:
        self._require_allowed(url)

        if not await self._robots.is_allowed(url):
            logger.info("[ontology.public_source] robots.txt가 막음 | url=%s", url)
            return None

        page = await self._fetcher.fetch(url)
        if page.status_code != 200:
            logger.info(
                "[ontology.public_source] 본문 아님 | url=%s | status=%s",
                url,
                page.status_code,
            )
            return None

        soup = BeautifulSoup(page.html, "html.parser")
        text = _body_text(soup)
        if not text:
            logger.info("[ontology.public_source] 본문 비어 있음 | url=%s", url)
            return None

        # 본문을 손에 넣은 시각이 곧 이 문서의 수집 시각이다. 개정본이 이보다 뒤면
        # 우리가 읽은 판본일 수 없다.
        collected_at = datetime.now(UTC)
        fetched_title = _title(soup)
        revision = await self._revision_of(
            url, collected_at, fetched_title
        ) or self._revision_from_response(url, page, fetched_title, collected_at)
        return PublicDocument(
            url=url,
            title=fetched_title,
            text=text,
            published_at=_published_at(soup),
            revision_id=revision.revision_id if revision else None,
            revised_at=revision.revised_at if revision else None,
        )

    async def _revision_of(
        self, url: str, collected_at: datetime, fetched_title: str | None = None
    ) -> RevisionMetadata | None:
        """계보를 **세 관문을 모두 통과했을 때만** 인정한다 (Phase 3-13).

        1. 응답이 있는가 — 없으면 계보 없음(API 장애·위키 아닌 소스)
        2. 계보의 제목이 **우리가 받아 온 본문**의 제목과 맞는가
        3. 개정본 시각이 수집 시각보다 앞서는가 — 뒤라면 우리가 읽은 판본이 아니다

        **2번의 대조 대상이 주소가 아니라 본문이다** (2026-09-21에 바꿨다). 원래는
        주소에서 뽑은 제목과 맞춰 보고, 리다이렉트면 그 앞에서 통째로 버렸다. 근거는
        "계보는 출발지 스텁의 것이라 본문과 다른 글을 가리킨다"였는데, **그 위험은
        `redirects=1`을 붙인 뒤로 성립하지 않는다.** 실측:

            IYO SKY 스텁        rev @ 2023-02-25   ← redirects 없이 물었을 때
            Iyo Sky 목적지      rev @ 2026-09-10   ← redirects=1이 돌려주는 것

        본문 fetch도 리다이렉트를 따라가 목적지를 저장하므로 **둘이 같은 글을
        가리킨다.** 그걸 버리면 멀쩡한 계보가 사라진다 — 실제로 44청크가 그렇게
        비어 있었다.

        그래서 관문을 없애는 대신 **더 좁게** 만들었다. 주소는 우리가 조립한 추측이지만
        본문 제목은 서버가 준 사실이다. 이 대조는 리다이렉트를 통과시키면서도
        잘린 `oldid=13677280` 사례는 그대로 잡는다 — 그때 계보가 말한
        "Who Framed Roger Rabbit"은 받아 온 "Lash Legend"와 맞지 않는다.

        본문 제목이 없으면 주소로 돌아간다. 대조할 사실이 없을 때 통과시키지 않기
        위해서다.

        `revision_id`·`revised_at`의 존재는 `RevisionMetadata`의 타입이 이미 보장한다
        (둘 다 선택 필드가 아니다). 다만 빈 문자열은 타입이 못 거르므로 여기서 본다.

        **어느 경우에도 예외를 올리지 않는다.** 계보가 비는 것과 문서를 못 가져오는
        것은 다른 일이고, 여기서 멈추면 본문까지 잃는다.
        """
        if self._revisions is None:
            return None
        revision = await self._revisions.fetch(url)
        if revision is None:
            return None

        expected = _page_title(fetched_title) or wiki_title_from_url(url)
        if expected is None:
            # 위키도 아니고 본문 제목도 없다. 대조할 기준이 없으면 계보를 주장하지 않는다.
            return None
        if _normalize_title(revision.title) != _normalize_title(expected):
            logger.info(
                "[ontology.public_source] 계보 제목 불일치 — 버린다 | url=%s "
                "| 기대=%s | 응답=%s | 리다이렉트=%s",
                url,
                expected,
                revision.title,
                revision.is_redirect,
            )
            return None

        if revision.is_redirect:
            # 버리지는 않는다 — 위 대조가 본문과 같은 글임을 이미 확인했다.
            # 다만 수집 주소가 정규 주소가 아니라는 사실은 남겨 둔다.
            logger.info(
                "[ontology.public_source] 리다이렉트지만 본문과 일치 | url=%s | 문서=%s",
                url,
                revision.title,
            )

        if not revision.revision_id:
            logger.info("[ontology.public_source] 계보 식별자 비어 있음 | url=%s", url)
            return None

        if revision.revised_at > collected_at:
            # 아직 만들어지지도 않은 개정본을 읽었을 수는 없다. 시계가 어긋났거나
            # 엉뚱한 문서를 본 것이므로, 어느 쪽이든 계보로 쓰지 않는다.
            logger.info(
                "[ontology.public_source] 개정본이 수집보다 미래 — 버린다 | url=%s "
                "| 개정본=%s | 수집=%s",
                url,
                revision.revised_at,
                collected_at,
            )
            return None
        return revision

    def _revision_from_response(
        self,
        url: str,
        page: FetchedPage,
        fetched_title: str | None,
        collected_at: datetime,
    ) -> RevisionMetadata | None:
        """개정본 API가 없는 소스의 계보를 **본문을 받아 온 그 응답**에서 만든다.

        **왜 제목을 대조하지 않는가.** `_revision_of`의 관문 2는 "계보가 다른 문서를
        가리키지 않는가"를 묻는다. 여기서는 그 위험이 **구조적으로 없다** — 계보의
        재료가 본문과 같은 HTTP 응답의 헤더이므로, 다른 문서일 수가 없다. 그래서
        대조 대신 응답의 제목을 그대로 실어 보낸다.

        **두 헤더가 서로 다른 것을 말한다.**

        * `ETag` — 내용의 판본 식별자. 내용이 바뀌면 바뀌므로 위키의 `revid`와
          같은 자리에 쓸 수 있다.
        * `Last-Modified` — 그 판본이 만들어진 시각. **CDN 재생성 시각일 수 있다**
          (실측: wwe.com이 조회 19분 전 값을 줬다). 그래서 이 값이 말할 수 있는 것은
          "이 판본이 **늦어도** 그때 존재했다"이고, 그것이 자격 판정이 묻는 것과
          맞는다 — 경기보다 앞서는가 · 예측보다 앞서는가.

          **이것을 발행 시각으로 쓰지 않는다.** `published_at`은 여전히 메타태그에서만
          온다 — 재생성 시각을 발행일로 적으면 없는 사실을 만드는 것이다.

        **둘 중 하나라도 없으면 계보를 주장하지 않는다.** 시각만 있고 식별자가 없으면
        "어느 판본인지"를 못 말하고, 식별자만 있으면 시간 판정에 쓸 수 없다.
        """
        host = (urlparse(url).hostname or "").lower()
        if host not in self._header_lineage_domains:
            return None
        if not page.etag or not page.last_modified:
            logger.info(
                "[ontology.public_source] 헤더 계보 재료 부족 | url=%s "
                "| etag=%s | last_modified=%s",
                url,
                page.etag,
                page.last_modified,
            )
            return None

        revised_at = _http_date(page.last_modified)
        if revised_at is None:
            logger.info(
                "[ontology.public_source] Last-Modified를 읽지 못했다 | url=%s | 값=%s",
                url,
                page.last_modified,
            )
            return None
        if revised_at > collected_at:
            # `_revision_of`의 관문 3과 같은 이유다 — 수집보다 미래인 판본을 읽었을
            # 수는 없다. 헤더 경로에도 같은 선을 긋는다.
            logger.info(
                "[ontology.public_source] 헤더 계보가 수집보다 미래 — 버린다 | url=%s "
                "| 판본=%s | 수집=%s",
                url,
                revised_at,
                collected_at,
            )
            return None

        return RevisionMetadata(
            revision_id=page.etag,
            revised_at=revised_at,
            # 같은 응답에서 나왔으므로 대조할 상대가 없다. 있는 그대로 싣는다.
            title=fetched_title or "",
        )

    def _require_allowed(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise SourceNotAllowedError(f"http(s) 주소가 아닙니다: {url}")
        host = (parsed.hostname or "").lower()
        if host not in self._allowed_domains:
            # 목록에 없는 주소는 존재조차 확인하지 않는다.
            raise SourceNotAllowedError(f"허용 도메인이 아닙니다: {host or url}")


def _normalize_title(text: str) -> str:
    """제목 대조용 정규화 — 밑줄·연속 공백·대소문자 차이만 흡수한다.

    구두점까지 지우지는 않는다. `Money in the Bank (2026)`과 `Money in the Bank`는
    **다른 문서**이고, 그 차이를 흘리면 이 대조가 하는 일이 없어진다.
    """
    return _WHITESPACE.sub(" ", text.replace("_", " ")).strip().casefold()


#: `<title>`이 달고 오는 사이트 꼬리표. 계보 API는 문서 제목만 주므로 떼고 대조한다.
_TITLE_SUFFIX = " - Wikipedia"


def _page_title(fetched_title: str | None) -> str | None:
    """받아 온 `<title>`에서 문서 제목만 남긴다.

    `Iyo Sky - Wikipedia` → `Iyo Sky`. 꼬리표가 없으면 그대로 둔다 — 위키가 아닌
    소스도 이 경로를 지나고, 그때는 제목이 안 맞아 관문에서 걸리는 것이 맞다.
    """
    if not fetched_title:
        return None
    title = fetched_title.strip()
    if title.endswith(_TITLE_SUFFIX):
        title = title[: -len(_TITLE_SUFFIX)].strip()
    return title or None


def _http_date(value: str) -> datetime | None:
    """RFC 7231 날짜 문자열을 UTC `datetime`으로. 못 읽으면 `None`이다.

    **타임존이 없는 값은 UTC로 읽는다.** HTTP 날짜는 규격상 GMT이지만 규격을 안
    지키는 서버가 있고, naive를 그대로 두면 aware 값과 비교하다 터진다.
    """
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _title(soup: BeautifulSoup) -> str | None:
    if soup.title is None:
        return None
    return soup.title.get_text(strip=True) or None


def _body_text(soup: BeautifulSoup) -> str:
    for tag in soup(_NOISE_TAGS):
        tag.decompose()
    body = soup.body or soup
    return _WHITESPACE.sub(" ", body.get_text(separator=" ", strip=True)).strip()


def _published_at(soup: BeautifulSoup) -> datetime | None:
    for attrs in _PUBLISHED_META:
        tag = soup.find("meta", attrs=attrs)
        parsed = _parse_datetime(tag.get("content") if tag else None)
        if parsed is not None:
            return parsed

    time_tag = soup.find("time")
    return _parse_datetime(time_tag.get("datetime") if time_tag else None)


def _parse_datetime(raw: object) -> datetime | None:
    """읽히면 UTC로, 못 읽으면 `None`. **오늘 날짜로 대신 채우지 않는다.**

    모르는 시각을 오늘로 채우면 몇 달 전 소식이 최신 소식 자리를 차지한다.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
