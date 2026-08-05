"""공개 소스를 모아 `ple_knowledge_chunks`에 넣는다 (하네스 §10-T3).

서사·루머 에이전트가 읽을 근거를 쌓는 작업이다. 여기가 비어 있으면 검색이 0건이고,
에이전트는 "의견 없음"만 낸다 — 고장이 아니라 아는 게 없는 상태다.

**허용 도메인 목록 안의 주소만 받는다**(`app/services/prediction_knowledge_sources.py`).
목록 밖 주소는 요청조차 보내지 않고 경고만 남긴다.

여러 번 실행해도 안전하다 — 같은 내용은 `content_hash`로 걸러진다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python apps/kayfabe/scripts/ingest_prediction_knowledge.py \\
        https://en.wikipedia.org/wiki/SummerSlam_(2026)
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402

from kayfabe.app.dtos.knowledge_ingestion_dto import (  # noqa: E402
    IngestKnowledgeCommand,
)
from kayfabe.app.services.prediction_knowledge_sources import (  # noqa: E402
    ALLOWED_DOMAINS,
)
from kayfabe.dependencies.knowledge_ingestion_provider import (  # noqa: E402
    get_knowledge_ingestion_use_case,
)


async def main(urls: list[str]) -> int:
    async with AsyncSessionLocal() as session:
        use_case = get_knowledge_ingestion_use_case(session)
        summary = await use_case.ingest(IngestKnowledgeCommand(urls=tuple(urls)))
        # 유스케이스는 flush까지만 한다 — 커밋 시점은 부르는 쪽이 정한다.
        await session.commit()

    print(
        f"요청 {summary.requested} · 수집 {summary.collected} · 청크 {summary.chunks} "
        f"· 저장 {summary.stored} · 중복 {summary.duplicates} · 실패 {summary.failed}"
    )
    # 하나도 못 가져왔으면 실패로 끝낸다 — 조용한 0건이 성공처럼 보이면 안 된다.
    return 0 if summary.collected else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("사용법: ingest_prediction_knowledge.py <url> [url ...]")
        print("허용 도메인: " + ", ".join(sorted(ALLOWED_DOMAINS)))
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(args)))
