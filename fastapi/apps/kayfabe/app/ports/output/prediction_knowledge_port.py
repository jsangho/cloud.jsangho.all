from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.agent_prediction_dto import KnowledgeChunk


class KnowledgeSourceUnavailableError(Exception):
    """지식 저장소를 조회할 수 없다. 클라이언트에는 503."""


class PredictionKnowledgePort(ABC):
    """예측 근거 지식 검색 (RAG).

    검색은 kayfabe가 소유하고 생성만 ontology 허브에 위임한다 —
    `wrestler_chat_repository.py`와 같은 구조다(하네스 §3-D7).
    """

    @abstractmethod
    async def search(self, *, query: str, top_k: int) -> list[KnowledgeChunk]:
        """질의와 가까운 청크를 최신·유사도 순으로 돌려준다.

        일치하는 지식이 없으면 빈 목록이다 — 없는 것은 실패가 아니다.
        """
