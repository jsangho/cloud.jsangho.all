from __future__ import annotations

from ontology.adapter.outbound.wikipedia_article_reader import WikipediaArticleReader
from ontology.app.ports.output.wiki_article_port import WikiArticlePort


def get_wiki_article_port() -> WikiArticlePort:
    """`get_wiki_title_port`와 같은 이유로 `Depends`가 아니다 — 요청 밖에서 도는 경로다."""
    return WikipediaArticleReader()
