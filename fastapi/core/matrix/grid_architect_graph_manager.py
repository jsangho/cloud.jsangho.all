"""Neo4j 비동기 드라이버 · FastAPI Depends(get_neo4j_session)."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession

from core.matrix.vault_keymaker_secret_manager import get_keymaker
from fastapi import HTTPException

_NEO4J_URI = get_keymaker().get_secret("NEO4J_URI")
_NEO4J_USER = get_keymaker().get_secret("NEO4J_USER", "neo4j")
_NEO4J_PASSWORD = get_keymaker().get_secret("NEO4J_PASSWORD")

driver: AsyncDriver | None = (
    AsyncGraphDatabase.driver(_NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASSWORD))
    if _NEO4J_URI
    else None
)


async def dispose_neo4j_driver() -> None:
    if driver is not None:
        await driver.close()


async def get_neo4j_session() -> AsyncGenerator[AsyncSession]:
    if driver is None:
        raise HTTPException(
            status_code=503,
            detail="NEO4J_URI가 .env 등에 설정되지 않았습니다.",
        )
    async with driver.session() as session:
        yield session
