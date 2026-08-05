"""예측 근거 지식 검색 (RAG) — 하네스 §10-T4.

`wrestler_chat_repository.py`와 같은 구조다: **검색은 kayfabe가 소유하고**, 생성만
ontology 허브에 위임한다(§3-D7). 이 리포지토리는 검색까지만 한다 — 프롬프트를 만들지도
LLM을 부르지도 않는다. 그건 T5의 에이전트 어댑터 몫이다.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from core.matrix.vault_keymaker_secret_manager import get_keymaker
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.orm.knowledge_chunk_orm import KnowledgeChunkModel
from kayfabe.app.dtos.agent_prediction_dto import KnowledgeChunk
from kayfabe.app.ports.output.prediction_knowledge_port import (
    KnowledgeSourceUnavailableError,
    PredictionKnowledgePort,
)

logger = logging.getLogger("uvicorn.error")

#: 게시 시각을 모르는 청크의 정렬 하한.
_OLDEST = datetime.min.replace(tzinfo=UTC)


class PredictionKnowledgeRepository(PredictionKnowledgePort):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(self, *, query: str, top_k: int) -> list[KnowledgeChunk]:
        cleaned = query.strip()
        if not cleaned or top_k <= 0:
            return []

        embedding = await self._embed(cleaned)
        rows = await self._nearest(embedding, top_k)
        logger.info(
            "[kayfabe.prediction_knowledge] 검색 완료 | top_k=%d | 결과=%d건",
            top_k,
            len(rows),
        )
        return _newest_first([_to_chunk(row) for row in rows])

    async def _embed(self, text: str) -> list[float]:
        """bge-m3는 CPU 바운드라 스레드로 넘긴다(하네스 §3-D9).

        `wrestlers.embedding`과 같은 함수를 써야 같은 좌표계가 된다 — 다른 모델로
        만든 벡터끼리의 코사인 거리는 아무 의미가 없다.
        """
        try:
            return await asyncio.to_thread(get_keymaker().embed_text, text)
        except Exception as exc:  # 모델 로드 실패·메모리 부족 등
            raise KnowledgeSourceUnavailableError(
                "질의 임베딩에 실패했습니다."
            ) from exc

    async def _nearest(
        self, embedding: list[float], top_k: int
    ) -> list[KnowledgeChunkModel]:
        stmt = (
            select(KnowledgeChunkModel)
            # 임베딩이 없는 행은 거리 계산 대상이 아니다 — 적재 중이거나 실패한 청크다.
            .where(KnowledgeChunkModel.embedding.is_not(None))
            .order_by(KnowledgeChunkModel.embedding.op("<=>")(embedding))
            .limit(top_k)
        )
        try:
            return list((await self.session.scalars(stmt)).all())
        except SQLAlchemyError as exc:
            raise KnowledgeSourceUnavailableError("지식 조회에 실패했습니다.") from exc


def _to_chunk(row: KnowledgeChunkModel) -> KnowledgeChunk:
    #: 제목을 본문 앞에 붙인다 — 청크만 보면 무슨 글인지 알 수 없는 경우가 많다.
    text = f"{row.title}\n{row.content}" if row.title else row.content
    return KnowledgeChunk(
        text=text, source_url=row.source_url, published_at=row.published_at
    )


def _newest_first(chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
    """뽑는 것은 유사도, 늘어놓는 것은 최신순이다.

    선정을 최신순으로 하면 질문과 무관한 최신 글이 밀려 들어온다. 반대로 순서까지
    유사도로 두면 에이전트가 6개월 전 소식을 어제 것보다 먼저 읽는다 — 부상·복귀처럼
    **뒤집히는 사실**에서는 최신 것이 이긴다.

    게시 시각을 모르는 청크는 뒤로 보낸다. 수집 시각으로 대신 채우지 않는다.
    """
    return sorted(chunks, key=_recency_key, reverse=True)


def _recency_key(chunk: KnowledgeChunk) -> datetime:
    """비교는 tz-aware끼리만 한다 — 섞이면 정렬이 `TypeError`로 죽는다."""
    published = chunk.published_at
    if published is None:
        return _OLDEST
    return published if published.tzinfo else published.replace(tzinfo=UTC)
