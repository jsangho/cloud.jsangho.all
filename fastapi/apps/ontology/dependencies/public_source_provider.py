from __future__ import annotations

from ontology.adapter.outbound.httpx_robots_policy import HttpxRobotsPolicy
from ontology.adapter.outbound.httpx_web_page_fetcher import HttpxWebPageFetcher
from ontology.adapter.outbound.wikipedia_revision_metadata import (
    WikipediaRevisionMetadata,
)
from ontology.app.ports.input.public_source_use_case import PublicSourceUseCase
from ontology.app.use_cases.public_source_interactor import PublicSourceInteractor


def get_public_source_use_case(
    allowed_domains: frozenset[str],
    header_lineage_domains: frozenset[str] = frozenset(),
    collection_lineage_domains: frozenset[str] = frozenset(),
) -> PublicSourceUseCase:
    """`Depends`가 아니라 인자를 받는 팩토리다.

    허용 도메인 목록은 부르는 앱이 정하므로(§3-D10) 요청 컨텍스트에서 주입될 값이
    아니다. 지금 호출자는 수집 스크립트 하나뿐이라 FastAPI 의존성으로 만들지 않는다.
    """
    return PublicSourceInteractor(
        allowed_domains=allowed_domains,
        fetcher=HttpxWebPageFetcher(),
        robots=HttpxRobotsPolicy(),
        # 위키가 아닌 주소면 이 어댑터가 스스로 `None`을 낸다 — 여기서 도메인을
        # 갈라 끼우지 않는다(허용 목록은 이미 유스케이스가 본다).
        revisions=WikipediaRevisionMetadata(),
        # 개정본 API가 없는 소스의 계보를 응답 헤더에서 얻을지 — **부르는 앱이 정한다.**
        # 기본이 빈 집합이라 아무 것도 안 넘기면 기존 거동 그대로다.
        header_lineage_domains=header_lineage_domains,
        # 판본을 스스로 밝히지 않는 소스의 계보를 **수집 시각**으로 삼을지 — 역시
        # 부르는 앱이 정한다. 기본이 빈 집합이라 안 넘기면 기존 거동 그대로다.
        collection_lineage_domains=collection_lineage_domains,
    )
