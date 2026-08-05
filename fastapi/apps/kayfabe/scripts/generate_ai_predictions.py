"""PLE 하나의 AI 예측을 만든다 (하네스 §10-T5 · §13-Q3).

**HTTP가 아니라 스크립트인 이유:** 무료 등급 한도(분당 5회)에 맞춰 호출을 늦추므로
12경기짜리 대회는 6분 안팎이 걸린다. 그 시간을 요청 하나로 붙들면 nginx·cloudflared
타임아웃에 먼저 걸린다. 관리자 엔드포인트(`POST .../ai-predictions`)는 경기 몇 개를
다시 만드는 용도로 남긴다.

이미 예측이 있는 경기는 건너뛴다. 다시 만들려면 `--force`.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python apps/kayfabe/scripts/generate_ai_predictions.py summerslam
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402
import logging  # noqa: E402

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402

from kayfabe.adapter.outbound.pg.agent_prediction_pg_repository import (  # noqa: E402
    AgentPredictionPgRepository,
)
from kayfabe.adapter.outbound.repositories.prediction_knowledge_repository import (  # noqa: E402
    PredictionKnowledgeRepository,
)
from kayfabe.app.dtos.agent_prediction_dto import (  # noqa: E402
    GeneratePredictionCommand,
)
from kayfabe.dependencies.ai_prediction_provider import (  # noqa: E402
    get_ai_prediction_use_case,
)
from ontology.dependencies.gemini_generation_provider import (  # noqa: E402
    get_gemini_generation_use_case,
)


async def main(slug: str, *, force: bool, match_keys: tuple[str, ...]) -> int:
    # 오래 걸리는 작업이라 진행 상황이 보여야 한다 — 어느 경기에서 멈췄는지 알 수 있게.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    async with AsyncSessionLocal() as session:
        use_case = get_ai_prediction_use_case(
            AgentPredictionPgRepository(db=session),
            PredictionKnowledgeRepository(session),
            get_gemini_generation_use_case(),
        )
        summary = await use_case.generate(
            GeneratePredictionCommand(
                event_slug=slug, match_keys=match_keys, force=force
            )
        )
        # 유스케이스는 flush까지만 한다 — 커밋 시점은 부르는 쪽이 정한다.
        await session.commit()

    print(
        f"요청 {summary.requested} · 생성 {summary.generated} "
        f"· 건너뜀 {summary.skipped} · 실패 {summary.failed}"
    )
    # 만들 대상이 있었는데 하나도 못 만들었으면 실패로 끝낸다.
    return 0 if summary.generated or not summary.requested else 1


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--force"]
    if not args:
        print("사용법: generate_ai_predictions.py <slug> [match_key ...] [--force]")
        raise SystemExit(2)
    raise SystemExit(
        asyncio.run(
            main(
                args[0],
                force="--force" in sys.argv[1:],
                match_keys=tuple(args[1:]),
            )
        )
    )
