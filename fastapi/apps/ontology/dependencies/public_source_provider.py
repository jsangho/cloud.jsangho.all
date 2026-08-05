from __future__ import annotations

from ontology.adapter.outbound.httpx_robots_policy import HttpxRobotsPolicy
from ontology.adapter.outbound.httpx_web_page_fetcher import HttpxWebPageFetcher
from ontology.app.ports.input.public_source_use_case import PublicSourceUseCase
from ontology.app.use_cases.public_source_interactor import PublicSourceInteractor


def get_public_source_use_case(
    allowed_domains: frozenset[str],
) -> PublicSourceUseCase:
    """`Depends`가 아니라 인자를 받는 팩토리다.

    허용 도메인 목록은 부르는 앱이 정하므로(§3-D10) 요청 컨텍스트에서 주입될 값이
    아니다. 지금 호출자는 수집 스크립트 하나뿐이라 FastAPI 의존성으로 만들지 않는다.
    """
    return PublicSourceInteractor(
        allowed_domains=allowed_domains,
        fetcher=HttpxWebPageFetcher(),
        robots=HttpxRobotsPolicy(),
    )
