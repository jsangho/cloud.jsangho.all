from __future__ import annotations

from ontology.adapter.outbound.wikipedia_title_resolver import WikipediaTitleResolver
from ontology.app.ports.output.wiki_title_port import WikiTitlePort


def get_wiki_title_port() -> WikiTitlePort:
    """`Depends`가 아니다 — 지금 호출자는 적재 스크립트뿐이다.

    `get_public_source_use_case`와 같은 이유로 FastAPI 의존성이 아니라 맨 팩토리다
    (§3-D10: 수집 경로는 요청 컨텍스트 밖에서 돈다).
    """
    return WikipediaTitleResolver()
