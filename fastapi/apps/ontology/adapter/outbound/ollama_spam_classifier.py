from __future__ import annotations

import json
import os

import httpx

from ontology.app.dtos.spam_classification_dto import SpamClassificationDto
from ontology.app.ports.output.spam_label_classifier import SpamLabelClassifier
from ontology.domain.enums.spam_classes import SpamLabel

_MODEL_ID = "exaone3.5:7.8b"

_PROMPT_TEMPLATE = """당신은 이메일 스팸 분류기입니다. 아래 여섯 라벨 중 정확히 하나만 선택하세요.

- ham: 정상적인 업무/개인 메일. 발신자가 수신자에게 문의·안내·보고를 하는 경우 포함.
- phishing: 계정/비밀번호/로그인 정보를 입력하도록 유도하는 사칭 메일.
- advertisement: 발신자가 자신의 상품/서비스를 수신자에게 홍보·판매하려는 광고 메일.
- scam: 금전 송금이나 개인정보를 요구하는 사기 메일.
- malware: 첨부파일 실행이나 프로그램 다운로드를 유도하는 악성코드 메일.
- abusive: 욕설·모욕·혐오 표현이 포함된 메일.

주의: 수신자가 발신자에게 무언가를 문의하는 메일은 ham이다. advertisement가 아니다.

제목: {subject}
본문: {body}

다음 형식의 JSON으로만 답하세요: {{"label": "<라벨>", "confidence": <0.0~1.0>}}
"""


class OllamaSpamClassifier(SpamLabelClassifier):
    """Ollama 로컬 LLM(exaone3.5:7.8b)으로 스팸을 zero-shot 분류하는 어댑터."""

    def __init__(self, host: str | None = None) -> None:
        self._host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    async def classify(self, subject: str, body: str) -> SpamClassificationDto:
        prompt = _PROMPT_TEMPLATE.format(subject=subject, body=body)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._host}/api/generate",
                json={
                    "model": _MODEL_ID,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False,
                },
            )
            response.raise_for_status()
            raw = json.loads(response.json()["response"])

        label = raw.get("label", SpamLabel.HAM.value)
        if label not in {member.value for member in SpamLabel}:
            label = SpamLabel.HAM.value
        confidence = float(raw.get("confidence", 0.5))

        return SpamClassificationDto(label=label, confidence=confidence)
