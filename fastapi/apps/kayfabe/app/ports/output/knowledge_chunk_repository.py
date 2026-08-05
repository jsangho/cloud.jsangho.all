from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from kayfabe.app.dtos.knowledge_ingestion_dto import NewKnowledgeChunk


class KnowledgeChunkRepository(ABC):
    @abstractmethod
    async def replace_document_chunks(self, chunks: Sequence[NewKnowledgeChunk]) -> int:
        """같은 `source_url`의 기존 청크를 **갈아 끼우고**, 넣은 수를 돌려준다.

        추가가 아니라 교체인 이유: 위키 문서는 갱신된다. 내용이 한 글자만 달라져도
        `content_hash`가 달라지므로 그냥 넣으면 **작년 판본과 올해 판본이 함께
        검색된다.** 부상·복귀처럼 뒤집히는 사실에서 옛 판본은 틀린 근거다.

        문서를 못 가져온 경우에는 호출되지 않는다 — 수집 실패로 기존 지식을 잃지
        않기 위해서다.
        """
