"""영수증 판독 어댑터 — Gemini 멀티모달.

Textract `AnalyzeExpense` 대신 Gemini를 고른 이유는 `GEMINI_API_KEY`와
`google-genai`가 이미 있고 IAM 정책 추가가 필요 없어서다. 대신 출력이 확률적이라
JSON 스키마를 강제하고, 형식이 깨지면 판독 실패로 처리한다.

**이 어댑터는 파싱을 하지 않는다.** 영수증에 적힌 텍스트를 그대로 옮겨 적게 하고,
상호·금액·품목 해석은 도메인 파서(`receipt_parser.py`)가 맡는다 — 엔진을 바꿔도
가계부 규칙이 따라 흔들리지 않게 하기 위해서다.
"""

from __future__ import annotations

import asyncio
import json
import logging

from core.matrix.vault_keymaker_secret_manager import get_keymaker
from google import genai
from google.genai import types
from lion_king.app.dtos.receipt_dto import OcrRawResult, ReceiptImage
from lion_king.app.ports.output.receipt_ocr_port import (
    OcrUnavailableError,
    ReceiptOcrPort,
)

logger = logging.getLogger("uvicorn.error")

_MODEL_ID = "gemini-3.5-flash"

_PROMPT = """이 이미지는 한국의 영수증 사진이다. 영수증에 인쇄된 글자를 위에서 아래로,
줄 단위로 그대로 옮겨 적어라. 해석·요약·번역·계산을 하지 말고, 읽은 그대로 옮긴다.
품목 줄은 "품목명 수량 단가 금액" 순서를 유지한다.

JSON으로만 답한다:
{"text": "<영수증 전문(줄바꿈 포함)>", "confidence": <0.0~1.0 판독 확신도>}

글자가 흐려 확신이 낮으면 confidence를 낮게 준다. 영수증이 아니거나 글자를 전혀
읽을 수 없으면 text를 빈 문자열로 둔다."""

_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "text": {"type": "STRING"},
        "confidence": {"type": "NUMBER"},
    },
    "required": ["text", "confidence"],
}


class GeminiOcrReader(ReceiptOcrPort):
    def __init__(self) -> None:
        self._client = genai.Client(api_key=get_keymaker().get_gemini_api_key())

    async def read(self, image: ReceiptImage) -> OcrRawResult:
        logger.info("[lion_king.gemini_ocr] 판독 시작 | model=%s", _MODEL_ID)
        try:
            response = await self._client.aio.models.generate_content(
                model=_MODEL_ID,
                contents=[
                    types.Part.from_bytes(
                        data=image.data, mime_type=image.content_type
                    ),
                    _PROMPT,
                ],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": _RESPONSE_SCHEMA,
                },
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # 엔진 오류·한도 초과·네트워크 실패
            # 엔진 이름·원문은 로그까지만. 클라이언트에는 503 문구만 나간다.
            logger.warning("[lion_king.gemini_ocr] 판독 실패 | %s", exc)
            raise OcrUnavailableError(str(exc)) from exc

        return _to_result(response.text)


def _to_result(payload: str | None) -> OcrRawResult:
    """모델 응답(JSON 문자열) → 엔진 중립 DTO."""
    if not payload:
        raise OcrUnavailableError("판독 응답이 비어 있습니다.")
    try:
        body = json.loads(payload)
    except json.JSONDecodeError as exc:
        # 스키마를 걸어도 형식이 깨질 수 있다. 조용히 빈 결과로 삼키지 않는다.
        raise OcrUnavailableError("판독 응답 형식이 올바르지 않습니다.") from exc

    text = body.get("text")
    if not isinstance(text, str):
        raise OcrUnavailableError("판독 응답에 텍스트가 없습니다.")

    confidence = body.get("confidence")
    if not isinstance(confidence, (int, float)):
        # 확신도를 못 받으면 0으로 둔다 — needs_review가 켜져 사람이 확인하게 된다.
        confidence = 0.0

    return OcrRawResult(raw_text=text, confidence=max(0.0, min(1.0, float(confidence))))
