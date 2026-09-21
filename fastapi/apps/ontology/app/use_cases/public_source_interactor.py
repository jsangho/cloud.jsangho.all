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
from urllib.parse import urlparse

from bs4 import BeautifulSoup

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
    ) -> None:
        self._allowed_domains = frozenset(d.lower() for d in allowed_domains)
        self._fetcher = fetcher
        self._robots = robots
        #: 없으면 계보 없이 수집한다 — 계보는 있으면 좋은 것이지 수집의 조건이 아니다.
        self._revisions = revisions

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
        revision = await self._revision_of(url, collected_at, fetched_title)
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
