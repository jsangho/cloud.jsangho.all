from admin.app.ports.output.graph_retrieval_port import GraphRetrievalPort
from neo4j import AsyncSession

_MAX_DOCUMENTS = 3


class GraphRetrievalRepository(GraphRetrievalPort):
    """`(:Document)` 평면 노드에서 reasoning 경로의 retrieve 노드가 쓸 텍스트를 조회.

    엔티티·관계 추출(그래프 탐색)은 아직 없다 — `apps/admin/_docs/langgraph-strategy.md`
    §5 1단계 스코프대로 기존 `(:Document)` 텍스트 조회까지만 담당한다.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search_documents(self, keywords: list[str]) -> list[str]:
        if keywords:
            result = await self.session.run(
                """
                MATCH (d:Document)
                WHERE any(k IN $keywords WHERE d.text CONTAINS k)
                RETURN d.text AS text
                ORDER BY d.uploaded_at DESC
                LIMIT $limit
                """,
                keywords=keywords,
                limit=_MAX_DOCUMENTS,
            )
        else:
            result = await self.session.run(
                """
                MATCH (d:Document)
                RETURN d.text AS text
                ORDER BY d.uploaded_at DESC
                LIMIT $limit
                """,
                limit=_MAX_DOCUMENTS,
            )
        return [record["text"] async for record in result]
