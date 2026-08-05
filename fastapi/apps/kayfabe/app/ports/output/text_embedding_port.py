"""텍스트 임베딩 출력 포트.

검색 쪽(`prediction_knowledge_repository`)은 질의 하나를 어댑터 안에서 임베딩하지만,
적재는 청크 수십 개를 벡터로 바꾸고 **몇 개가 실패했는지 보고해야** 한다. 그래서
적재 경로만 포트로 뽑았다 — 유스케이스가 2.3GB 모델 없이 테스트되는 이유이기도 하다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingUnavailableError(Exception):
    """임베딩 모델을 쓸 수 없다 (로드 실패·메모리 부족)."""


class TextEmbeddingPort(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """검색에 쓰는 것과 **같은 모델·같은 정규화**여야 한다.

        다른 모델로 만든 벡터끼리의 코사인 거리는 아무 의미가 없다(하네스 §3-D9).
        """
