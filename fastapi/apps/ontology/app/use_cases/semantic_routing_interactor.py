from __future__ import annotations

import json
import logging
import re

from ontology.app.dtos.semantic_routing_dto import (
    RoutingDecision,
    SemanticRoutingCommand,
)
from ontology.app.ports.input.semantic_routing_use_case import SemanticRoutingUseCase
from ontology.app.ports.output.semantic_routing_port import SemanticRoutingPort

logger = logging.getLogger("uvicorn.error")

_VALID_DESTINATIONS = {"crud", "exaone_rag", "gemini"}
_FALLBACK_DESTINATION = "exaone_rag"

_HAS_DIGIT = re.compile(r"\d")
_ARITHMETIC_HINT = re.compile(
    r"(더하기|더해|빼기|빼줘|곱하기|곱해|나누기|나눠|덧셈|뺄셈|곱셈|나눗셈|[+\-*/×÷])"
)


class SemanticRoutingInteractor(SemanticRoutingUseCase):
    def __init__(self, classifier: SemanticRoutingPort) -> None:
        self._classifier = classifier

    async def route(self, command: SemanticRoutingCommand) -> RoutingDecision:
        logger.info(
            "[ontology.semantic_routing] 허브 진입 | question=%r", command.question
        )
        if self._is_arithmetic(command.question):
            logger.info(
                "[ontology.semantic_routing] 정규식 필터로 산술 연산 감지 | LLM 호출 생략 | gemini로 즉시 라우팅"
            )
            return RoutingDecision(destination="gemini", entities=())

        raw = await self._classifier.classify(command)
        decision = self._parse(raw)
        logger.info(
            "[ontology.semantic_routing] 허브 완료 | destination=%s | entities=%s",
            decision.destination,
            decision.entities,
        )
        return decision

    def _is_arithmetic(self, question: str) -> bool:
        return bool(_HAS_DIGIT.search(question) and _ARITHMETIC_HINT.search(question))

    def _parse(self, raw: str) -> RoutingDecision:
        try:
            payload = json.loads(raw)
            destination = payload["destination"]
            entities = tuple(payload.get("entities", []))
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning(
                "[ontology.semantic_routing] JSON 파싱 실패, 기본값(%s)으로 폴백 | raw=%r | error=%s",
                _FALLBACK_DESTINATION,
                raw,
                exc,
            )
            return RoutingDecision(destination=_FALLBACK_DESTINATION, entities=())

        if destination not in _VALID_DESTINATIONS:
            logger.warning(
                "[ontology.semantic_routing] 알 수 없는 destination=%r, 기본값(%s)으로 폴백",
                destination,
                _FALLBACK_DESTINATION,
            )
            return RoutingDecision(destination=_FALLBACK_DESTINATION, entities=entities)

        return RoutingDecision(destination=destination, entities=entities)
