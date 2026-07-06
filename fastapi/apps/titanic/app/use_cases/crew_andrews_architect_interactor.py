from __future__ import annotations

import logging
from typing import Any

try:
    from kiwipiepy import Kiwi as _Kiwi

    _kiwi_instance = _Kiwi()
except ImportError:
    _kiwi_instance = None

from titanic.app.dtos.crew_andrews_architect_dto import (
    AndrewsArchitectQuery,
    AndrewsArchitectResponse,
)
from titanic.app.ports.input.crew_andrews_architect_use_case import (
    AndrewsArchitectUseCase,
)
from titanic.app.ports.output.crew_andrews_architect_port import AndrewsArchitectPort
from titanic.domain.constants.intent_map import INTENT_MAP

logger = logging.getLogger(__name__)


class AndrewsArchitectInteractor(AndrewsArchitectUseCase):
    def __init__(self, repository: AndrewsArchitectPort):
        self.repository = repository
        self.kiwi = _kiwi_instance

    def analyze_intent(self, question: str) -> dict[str, Any]:
        """Kiwi 형태소 분석으로 질문 의도를 파악하는 추상 메소드

        반환값:
            intent   : 감지된 의도 (SURVIVAL_PREDICT / STATISTICS / PASSENGER_SEARCH / MODEL_TRAIN / UNKNOWN)
            keywords : 분석에 사용된 핵심 형태소 목록
            scores   : 의도별 매칭 점수
            tokens   : Kiwi가 분석한 전체 (형태소, 품사) 쌍 목록
        """
        if self.kiwi is None:
            raise RuntimeError(
                "kiwipiepy가 설치되지 않아 형태소 분석을 사용할 수 없습니다."
            )
        # 명사(NN*), 동사 어간(VV/VA), 파생어근(XR)만 의도 판별에 사용
        tokens = self.kiwi.tokenize(question)
        keywords = [
            t.form for t in tokens if str(t.tag).startswith(("NN", "VV", "VA", "XR"))
        ]

        scores: dict[str, int] = dict.fromkeys(INTENT_MAP, 0)
        for keyword in keywords:
            for intent, kw_set in INTENT_MAP.items():
                if keyword in kw_set:
                    scores[intent] += 1

        best_intent = max(scores, key=lambda k: scores[k])
        intent = best_intent if scores[best_intent] > 0 else "UNKNOWN"

        logger.info(
            f"[AndrewsArchitectInteractor] analyze_intent | question={question!r} "
            f"intent={intent} scores={scores}"
        )
        return {
            "intent": intent,
            "keywords": keywords,
            "scores": scores,
            "tokens": [(t.form, str(t.tag)) for t in tokens],
        }

    async def introduce_myself(
        self, query: AndrewsArchitectQuery
    ) -> AndrewsArchitectResponse:
        return await self.repository.introduce_myself(query)
