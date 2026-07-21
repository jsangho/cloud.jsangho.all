from __future__ import annotations

import httpx
from mcp.server.fastmcp import FastMCP

from ontology.adapter.outbound.convnext_image_classifier import ConvNextImageClassifier
from ontology.app.use_cases.image_classifier_interactor import ImageClassifierInteractor

"""
`classify_image` MCP 도구 — 단일 이미지 단일 라벨 분류(ConvNeXt Nano, ImageNet-1k).

model.py(ConvNextImageClassifier)를 FastAPI `/classify` 엔드포인트 대신 직접 import한다:
같은 프로세스 안에서 클래스 변수 캐시(싱글턴)를 그대로 재사용해 모델을 중복 로딩하지
않고, FastAPI 서버가 떠 있지 않아도 이 도구 단독으로 동작할 수 있기 때문이다.
"""

mcp = FastMCP("OntologyVision")

_classifier = ImageClassifierInteractor(classifier=ConvNextImageClassifier())


async def _load_image_bytes(image_path: str) -> bytes:
    if image_path.startswith(("http://", "https://")):
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(image_path)
            response.raise_for_status()
            return response.content
    with open(image_path, "rb") as f:
        return f.read()


@mcp.tool(
    "classify_image",
    description=(
        "단일 이미지 한 장에 대해 가장 가능성 높은 라벨 하나(top-1)와 상위 5개 후보를 "
        "반환하는 이미지 분류 도구입니다(ConvNeXt Nano, ImageNet-1k 1000개 클래스 기준).\n\n"
        "이 도구가 하는 일: 이미지 전체를 하나의 라벨로 분류합니다(단일 객체 분류).\n"
        "언제 쓰면 안 되는지: 이미지 안에 여러 객체가 있고 그것들을 각각 구분/위치까지 "
        "찾아야 하는 경우(다중 객체 탐지)에는 부적합합니다 — 이 도구는 이미지 전체에 대한 "
        "하나의 라벨만 냅니다.\n"
        "출력 해석 가이드: `is_confident=false`이면 top-1 라벨을 단정적으로 사용하지 말고, "
        "`top5` 후보들을 사용자에게 제시하거나 재확인을 요청하세요."
    ),
)
async def classify_image(image_path: str) -> dict:
    """image_path: 로컬 파일 경로 또는 http(s) URL."""
    image_bytes = await _load_image_bytes(image_path)
    result = await _classifier.classify(image_bytes)
    return {
        "label": result.label,
        "confidence": result.confidence,
        "is_confident": result.is_confident,
        "top5": [{"label": p.label, "score": p.score} for p in result.top5],
    }
