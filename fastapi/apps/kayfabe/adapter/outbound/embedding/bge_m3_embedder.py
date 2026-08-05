"""bge-m3 임베딩 어댑터.

검색 쪽(`prediction_knowledge_repository._embed`)과 **같은 함수**를 부른다. 같은 모델·
같은 정규화를 써야 적재한 벡터와 질의 벡터가 같은 좌표계에 놓인다(하네스 §3-D9).
"""

from __future__ import annotations

import asyncio

from core.matrix.vault_keymaker_secret_manager import get_keymaker

from kayfabe.app.ports.output.text_embedding_port import (
    EmbeddingUnavailableError,
    TextEmbeddingPort,
)


class BgeM3Embedder(TextEmbeddingPort):
    async def embed(self, text: str) -> list[float]:
        try:
            # CPU 바운드다 — 이벤트 루프에서 직접 돌리면 서버가 멈춘다.
            return await asyncio.to_thread(get_keymaker().embed_text, text)
        except Exception as exc:  # 모델 로드 실패·메모리 부족 등
            raise EmbeddingUnavailableError("임베딩에 실패했습니다.") from exc
