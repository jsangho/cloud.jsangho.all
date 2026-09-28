"""결과 확정 에이전트 배선.

**`Depends`가 아니다.** 이 경로는 요청 컨텍스트 밖에서 돈다 —
`get_knowledge_ingestion_use_case`·`get_wiki_title_port`와 같은 자리이고 이유도 같다
(§3-D10: 수집·확정 경로는 스크립트가 돌린다). 이것을 라우터에 열지 않은 것은 결정이다:
결과 쓰기가 HTTP 요청으로 가능해지면 누가 언제 무엇을 썼는지가 흐려지고, 무엇보다
**모델이 읽은 문서에서 파생된 값**이 사람의 확인 없이 들어가는 경로가 생긴다.

## 모델을 예측 에이전트와 나눈다

무료 등급 한도가 **모델 단위**라, 다른 모델을 쓰면 승부예측 세 에이전트의 몫을
갉아먹지 않는다(`gemini_generation_dto.model`이 열려 있는 이유). `RESULT_AGENT_MODEL`이
있으면 그것을 쓰고, 없으면 `None`을 넘겨 어댑터 기본값(`GEMINI_MODEL`)으로 돈다 —
**환경변수를 새로 강제하지 않는다.**
"""

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.pg.match_result_pg_writer import MatchResultPgWriter
from kayfabe.adapter.outbound.pg.pending_result_pg_repository import (
    PendingResultPgRepository,
)
from kayfabe.adapter.outbound.pg.ple_events_pg_repository import PleEventsPgRepository
from kayfabe.app.ports.input.result_verification_use_case import (
    ResultVerificationUseCase,
)
from kayfabe.app.use_cases.result_verification_interactor import (
    ResultVerificationInteractor,
)
from ontology.dependencies.gemini_tool_provider import get_gemini_tool_use_case
from ontology.dependencies.wiki_article_provider import get_wiki_article_port
from ontology.dependencies.wiki_title_provider import get_wiki_title_port


def _model() -> str | None:
    return (os.getenv("RESULT_AGENT_MODEL") or "").strip() or None


def get_result_verification_use_case(db: AsyncSession) -> ResultVerificationUseCase:
    return ResultVerificationInteractor(
        pending=PendingResultPgRepository(db=db),
        writer=MatchResultPgWriter(events=PleEventsPgRepository(db)),
        tools=get_gemini_tool_use_case(),
        titles=get_wiki_title_port(),
        articles=get_wiki_article_port(),
        model=_model(),
    )
