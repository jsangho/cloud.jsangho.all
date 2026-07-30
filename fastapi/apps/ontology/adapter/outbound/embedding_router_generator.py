from __future__ import annotations

import asyncio
import json
import logging
import re

import numpy as np

from ontology.app.dtos.semantic_routing_dto import SemanticRoutingCommand
from ontology.app.ports.output.semantic_routing_port import SemanticRoutingPort

logger = logging.getLogger("uvicorn.error")

_MODEL_NAME = "intfloat/multilingual-e5-small"

_CRUD_VERB_PATTERN = re.compile(
    r"(지워|삭제|수정해|변경해|바꿔줘|등록해|추가해|생성해|만들어줘|업데이트)"
)

_EXAONE_RAG_EXAMPLES = (
    "로만 레인즈 피니셔가 뭐야?",
    "회사 인프라 서버 사양이 어떻게 돼?",
    "코디 로즈 정보 알려줘",
    "가장 최근에 데뷔한 선수는 누구야?",
    "스타 토폴로지 구조가 어떻게 되어 있어?",
)
_GEMINI_EXAMPLES = (
    "안녕",
    "오늘 기분 어때?",
    "고마워",
    "너는 누구야?",
    "오늘 날씨 어때?",
)
_REASONING_EXAMPLES = (
    "업로드된 자료들을 종합해서 결론을 도출해줘",
    "이 문서와 저 문서 내용을 비교해서 차이점을 분석해줘",
    "여러 자료에 흩어진 내용을 연결해서 원인을 설명해줘",
    "업로드한 문서들을 근거로 이번 분기 리스크를 정리해줘",
    "문서 전체를 훑어보고 핵심 논점을 종합해서 알려줘",
)

try:
    from kiwipiepy import Kiwi as _Kiwi

    _kiwi_instance = _Kiwi()
except ImportError:
    _kiwi_instance = None

_model = None
_category_centroids: dict[str, np.ndarray] | None = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _get_category_centroids() -> dict[str, np.ndarray]:
    global _category_centroids
    if _category_centroids is None:
        model = _get_model()
        exaone_vecs = model.encode(
            [f"passage: {t}" for t in _EXAONE_RAG_EXAMPLES],
            normalize_embeddings=True,
        )
        gemini_vecs = model.encode(
            [f"passage: {t}" for t in _GEMINI_EXAMPLES],
            normalize_embeddings=True,
        )
        reasoning_vecs = model.encode(
            [f"passage: {t}" for t in _REASONING_EXAMPLES],
            normalize_embeddings=True,
        )
        _category_centroids = {
            "exaone_rag": np.mean(exaone_vecs, axis=0),
            "gemini": np.mean(gemini_vecs, axis=0),
            "reasoning": np.mean(reasoning_vecs, axis=0),
        }
    return _category_centroids


def _extract_entities(question: str) -> list[str]:
    if _kiwi_instance is None:
        return []
    tokens = _kiwi_instance.tokenize(question)
    return [t.form for t in tokens if str(t.tag).startswith(("NNG", "NNP"))]


def _classify_sync(question: str) -> tuple[str, list[str]]:
    entities = _extract_entities(question)

    if _CRUD_VERB_PATTERN.search(question):
        return "crud", entities

    model = _get_model()
    centroids = _get_category_centroids()
    query_vec = model.encode(f"query: {question}", normalize_embeddings=True)

    destination = max(
        centroids, key=lambda dest: float(np.dot(query_vec, centroids[dest]))
    )
    return destination, entities


class EmbeddingRouterGenerator(SemanticRoutingPort):
    """로컬 임베딩(multilingual-e5-small) + 규칙 기반으로 의도를 분류하는 어댑터.

    LLM 호출 없이 로컬에서 즉시 응답해 Ollama/Gemini 대비 훨씬 빠르다. crud
    동사는 정규식으로 먼저 걸러내고(임베딩은 주제 유사도는 잘 잡아도 "조회 vs
    삭제" 같은 동사 뉘앙스엔 약하다), 나머지는 exaone_rag/gemini/reasoning 대표
    예문과의 코사인 유사도로 라우팅한다. entities는 Kiwi 형태소 분석으로 명사만 뽑는다.
    """

    async def classify(self, command: SemanticRoutingCommand) -> str:
        destination, entities = await asyncio.to_thread(
            _classify_sync, command.question
        )
        logger.info(
            "[ontology.embedding_router_generator] 임베딩 라우팅 완료 | destination=%s | entities=%s",
            destination,
            entities,
        )
        return json.dumps({"destination": destination, "entities": entities})
