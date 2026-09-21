"""공개 소스를 모아 `ple_knowledge_chunks`에 넣는다 (하네스 §10-T3).

서사·루머 에이전트가 읽을 근거를 쌓는 작업이다. 여기가 비어 있으면 검색이 0건이고,
에이전트는 "의견 없음"만 낸다 — 고장이 아니라 아는 게 없는 상태다.

**허용 도메인 목록 안의 주소만 받는다**(`app/services/prediction_knowledge_sources.py`).
목록 밖 주소는 요청조차 보내지 않고 경고만 남긴다.

여러 번 실행해도 안전하다 — 같은 내용은 `content_hash`로 걸러진다.

**문서당 청크 상한은 기본 25다** (`ingest_event_knowledge.py`와 같은 값).
예전에는 이 스크립트가 상한을 넘기지 않아 `None`(무제한)으로 돌았는데, 그러면
재수집이 "같은 모양으로 다시 모으기"가 아니라 **코퍼스를 몇 배로 불리는 작업**이
된다. 검색은 경기당 `top_k=5`이므로 코퍼스가 커지면 무엇이 뽑히는지가 달라진다 —
계보를 얻으려고 돌린 재수집이 검색 거동까지 바꾸면 안 된다. 상한을 바꾸는 것은
그 자체로 판단이 필요한 일이라 **명시적으로 적어야** 바뀐다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python apps/kayfabe/scripts/ingest_prediction_knowledge.py \\
        https://en.wikipedia.org/wiki/SummerSlam_(2026) [--max-chunks=N]
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
    IngestionSummary,
    IngestKnowledgeCommand,
)
from kayfabe.app.services.prediction_knowledge_sources import (  # noqa: E402
    ALLOWED_DOMAINS,
)
from kayfabe.dependencies.knowledge_ingestion_provider import (  # noqa: E402
    get_knowledge_ingestion_use_case,
)

#: 하나도 못 가져왔다.
EXIT_NOTHING_COLLECTED = 1
#: 본문은 받았지만 **개정본 계보를 확보하지 못한 문서가 있다** (Phase 3-13 Stage 1).
#: `EXIT_NOTHING_COLLECTED`와 구분하는 이유는 손봐야 할 곳이 다르기 때문이다 —
#: 저쪽은 주소·robots를 보고, 이쪽은 계보 API(429·리다이렉트·제목 불일치)를 본다.
EXIT_PROVENANCE_UNAVAILABLE = 3

#: 문서당 청크 상한의 기본값. `ingest_event_knowledge.py`와 **같은 값이어야 한다** —
#: 현재 코퍼스가 그 값으로 쌓였으므로, 다른 값으로 재수집하면 같은 문서가 다른
#: 분량으로 들어가 검색 결과가 조용히 갈린다.
DEFAULT_MAX_CHUNKS = 25

_MAX_CHUNKS_FLAG = "--max-chunks="


def max_chunks_from_argv(argv: list[str]) -> int | None:
    """`--max-chunks=N`을 읽는다. 없으면 `DEFAULT_MAX_CHUNKS`.

    `--max-chunks=0`은 **무제한(`None`)** 이다. "0개를 넣어라"는 뜻으로 읽힐 여지가
    있지만 그 동작은 쓸 데가 없고, 무제한을 적을 자리는 필요하다. 무제한은 코퍼스
    분량을 바꾸는 선택이므로 숫자를 직접 적어야만 닿는다.
    """
    flag = next((a for a in argv if a.startswith(_MAX_CHUNKS_FLAG)), None)
    if flag is None:
        return DEFAULT_MAX_CHUNKS
    value = int(flag[len(_MAX_CHUNKS_FLAG) :])
    if value < 0:
        raise ValueError(f"--max-chunks는 음수일 수 없습니다: {value}")
    return value or None


def urls_from_argv(argv: list[str]) -> list[str]:
    """`--`로 시작하지 않는 인자만 URL로 본다."""
    return [a for a in argv if not a.startswith("--")]


def exit_code_for(summary: IngestionSummary) -> int:
    """요약 하나를 종료 코드로 바꾼다.

    **계보 없는 적재를 성공으로 보고하지 않는다.** 예전에는 `collected`만 봐서,
    계보 API가 429로 통째로 막혀도 청크는 교체되고 종료 코드는 0이었다. 재수집의
    목적이 계보 확보인데 그 실패가 성공처럼 보이면, 아무도 다시 돌리지 않는다.

    청크 처리 자체는 건드리지 않았다 — 계보가 없어도 본문을 저장하는 기존 결정
    (`KnowledgeIngestionInteractor`)은 그대로다. 바뀐 것은 **보고**뿐이다.
    """
    if not summary.collected:
        return EXIT_NOTHING_COLLECTED
    if summary.provenance_unavailable:
        return EXIT_PROVENANCE_UNAVAILABLE
    return 0


async def main(urls: list[str], *, max_chunks: int | None) -> int:
    print(f"문서 {len(urls)}건 · 문서당 청크 상한 {max_chunks or '무제한'}")
    async with AsyncSessionLocal() as session:
        use_case = get_knowledge_ingestion_use_case(session, max_chunks=max_chunks)
        summary = await use_case.ingest(IngestKnowledgeCommand(urls=tuple(urls)))
        # 유스케이스는 flush까지만 한다 — 커밋 시점은 부르는 쪽이 정한다.
        await session.commit()

    print(
        f"요청 {summary.requested} · 수집 {summary.collected} · 청크 {summary.chunks} "
        f"· 저장 {summary.stored} · 중복 {summary.duplicates} · 실패 {summary.failed} "
        f"· 계보없음 {summary.provenance_unavailable}"
    )
    code = exit_code_for(summary)
    if code == EXIT_PROVENANCE_UNAVAILABLE:
        print(
            f"계보를 확보하지 못한 문서가 {summary.provenance_unavailable}건 있습니다 "
            "— 그 문서를 인용한 예측은 시간 게이트를 통과할 수 없습니다."
        )
    return code


if __name__ == "__main__":
    argv = sys.argv[1:]
    urls = urls_from_argv(argv)
    if not urls:
        print("사용법: ingest_prediction_knowledge.py <url> [url ...] [--max-chunks=N]")
        print(f"문서당 청크 상한 기본값: {DEFAULT_MAX_CHUNKS} (0이면 무제한)")
        print("허용 도메인: " + ", ".join(sorted(ALLOWED_DOMAINS)))
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(urls, max_chunks=max_chunks_from_argv(argv))))
