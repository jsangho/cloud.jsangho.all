from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from kayfabe.app.dtos.knowledge_ingestion_dto import NewKnowledgeChunk


class KnowledgeChunkRepository(ABC):
    @abstractmethod
    async def save_new(self, chunks: Sequence[NewKnowledgeChunk]) -> int:
        """아직 없는 청크만 넣고, 실제로 넣은 수를 돌려준다.

        중복 판정은 `content_hash`다. **재실행이 안전해야 한다** — 같은 URL을 다시
        수집하는 일이 정상 운용이기 때문이다.
        """
