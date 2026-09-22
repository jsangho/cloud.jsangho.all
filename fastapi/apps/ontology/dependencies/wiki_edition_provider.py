from __future__ import annotations

from ontology.adapter.outbound.wikipedia_edition_resolver import (
    WikipediaEditionResolver,
)
from ontology.app.ports.output.wiki_edition_port import WikiEditionPort


def get_wiki_edition_port() -> WikiEditionPort:
    """`Depends`가 아니다 — `get_wiki_title_port`와 같은 자리·같은 이유다.

    지금 호출자는 적재 스크립트뿐이고, 수집 경로는 요청 컨텍스트 밖에서 돈다.
    """
    return WikipediaEditionResolver()
