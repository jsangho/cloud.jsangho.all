"""결과 확정 에이전트 배선.

## 라우터에 열었다 (2026-10-01, 사용자 결정)

**이전 결정은 반대였다.** 여기에는 "라우터에 열지 않은 것은 결정이다 — 결과 쓰기가
HTTP 요청으로 가능해지면 누가 언제 무엇을 썼는지가 흐려지고, 무엇보다 모델이 읽은
문서에서 파생된 값이 사람의 확인 없이 들어가는 경로가 생긴다"고 적혀 있었다.

그 두 걱정은 유효하므로 **엔드포인트 쪽에서 각각 막았다**
(`adapter/inbound/api/v1/result_verification_router.py`):

1. **누가 썼는지** — 관리자 전용이고, 쓰기 요청은 토큰의 `sub`를 로그에 남긴다.
   스크립트는 **아무도 기록하지 않았으므로** 이 축은 오히려 나아진다.
2. **사람의 확인** — 대상 목록(`GET .../pending`)은 모델을 부르지 않는 공짜 조회이고,
   화면은 그 목록을 먼저 세운다. 실행은 **기본이 드라이런**이며, 쓰기는 `apply=true`를
   명시한 별도 요청이다. 화면은 경기를 **한 건씩** 보낸다(사람이 집은 `matchKeys`).

`Depends` 판본을 함께 둔다. 스크립트 경로(`get_result_verification_use_case(db)`)는
그대로다 — 요청 컨텍스트가 없는 곳에서 계속 쓰인다.

## 모델을 예측 에이전트와 나눈다

무료 등급 한도가 **모델 단위**라, 다른 모델을 쓰면 승부예측 세 에이전트의 몫을
갉아먹지 않는다(`gemini_generation_dto.model`이 열려 있는 이유). `RESULT_AGENT_MODEL`이
있으면 그것을 쓰고, 없으면 `None`을 넘겨 어댑터 기본값(`GEMINI_MODEL`)으로 돈다 —
**환경변수를 새로 강제하지 않는다.**
"""

from __future__ import annotations

import os

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.matrix.grid_oracle_database_manager import get_db
from kayfabe.adapter.outbound.pg.match_result_pg_writer import MatchResultPgWriter
from kayfabe.adapter.outbound.pg.pending_result_pg_repository import (
    PendingResultPgRepository,
)
from kayfabe.adapter.outbound.pg.ple_events_pg_repository import PleEventsPgRepository
from kayfabe.app.ports.input.result_verification_use_case import (
    ResultVerificationUseCase,
)
from kayfabe.app.services.wiki_result_lookup import WikiResultLookup
from kayfabe.app.use_cases.result_verification_interactor import (
    ResultVerificationInteractor,
)
from ontology.dependencies.gemini_tool_provider import get_gemini_tool_use_case
from ontology.dependencies.wiki_article_provider import get_wiki_article_port
from ontology.dependencies.wiki_title_provider import get_wiki_title_port


def _model() -> str | None:
    return (os.getenv("RESULT_AGENT_MODEL") or "").strip() or None


def get_result_verification(
    db: AsyncSession = Depends(get_db),
) -> ResultVerificationUseCase:
    """FastAPI 판본. 아래 스크립트 판본과 **같은 조립**을 쓴다."""
    return get_result_verification_use_case(db)


def get_result_verification_use_case(
    db: AsyncSession, *, use_wiki_engine: bool = True
) -> ResultVerificationUseCase:
    """**기본이 위키 엔진이다** (2026-10-07).

    결과 표가 템플릿이라 승자를 모델 없이 읽을 수 있고, 운영 DB의 확정값 63건을
    100% 재현했다(`app/services/wiki_result_lookup` 독스트링에 실측이 적혀 있다).
    모델은 위키가 못 읽은 경기에만 붙는 **폴백**으로 남는다 — 템플릿을 안 쓰는
    문서와 무승부가 실제로 있다.

    `use_wiki_engine=False`면 예전처럼 모델만 쓴다. 두 엔진의 답을 견줘야 할 때
    쓰는 문이고, 평소에 끌 이유는 없다.
    """
    articles = get_wiki_article_port()
    return ResultVerificationInteractor(
        pending=PendingResultPgRepository(db=db),
        writer=MatchResultPgWriter(events=PleEventsPgRepository(db)),
        tools=get_gemini_tool_use_case(),
        titles=get_wiki_title_port(),
        articles=articles,
        wiki=WikiResultLookup(articles) if use_wiki_engine else None,
        model=_model(),
    )
