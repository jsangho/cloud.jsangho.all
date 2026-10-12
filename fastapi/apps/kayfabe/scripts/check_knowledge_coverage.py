"""예측을 만들기 **전에** 검색이 참가자 문서를 뽑는지 본다 (하네스 §13-Q9 절차 6).

**왜 필요한가.** MITB 2026에서 수집과 생성이 같은 시간대에 섞여 돌았다 — 생성
05:59 → 수집 06:46 → 생성 07:38 → 수집 07:37(UTC). 그래서 `mitb26-reed-femi`는
Bronson Reed 문서가 코퍼스에 들어오기 **44분 전에** 만들어졌고, 그 경기 검색
1순위가 「why Bron Breakker isn't WWE world champion」이었다. 검색이 이상해서가
아니라 **더 나은 게 없어서**다. 생성 버튼을 누르기 전에 그 사실을 알 방법이 없었다.

이 스크립트가 그 자리를 채운다. **생성 경로와 같은 함수를 쓴다** — 질의는
`build_knowledge_query`, 검색은 `PredictionKnowledgeRepository`, 개수는
`KNOWLEDGE_TOP_K`다. 베껴 두면 한쪽을 고친 날 점검이 조용히 거짓말을 시작한다.

**재는 것은 검색 커버리지이지 에이전트 출력이 아니다.** 참가자 문서가 다 들어와도
루머 축은 "승자 방향을 보도한 자료가 없다"며 의견 없음을 낼 수 있고, 그것은
고장이 아니라 설계다(2026-09-30 「대진 발표를 승자 근거로 세지 말라」). 그러니
커버리지 100%는 **읽을 게 있다**는 뜻일 뿐, 세 축이 다 말한다는 뜻이 아니다.

**문서당 상한은 넣지 않았다.** 2026-10-08에 상한 0·1·2를 운영 코퍼스(1069청크)에
실측했는데 MITB 다섯 경기의 참가자 커버리지가 **셋 다 똑같았다**(각 6/6·2/2·2/2·
3/3·6/6). 바뀌는 것은 서로 다른 문서 수뿐이다(reed-femi 3→5). 같은 문서가 여러
순위를 먹는 모양은 눈에 거슬리지만 커버리지를 깎지 않으므로, 상한을 더하는 것은
지금 근거가 없는 변경이다. 재보고 싶으면 `--cap=N`으로 비교만 해 볼 수 있다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python apps/kayfabe/scripts/check_knowledge_coverage.py money-in-the-bank
    # 문서당 상한을 바꿔 비교만 해 보려면
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python apps/kayfabe/scripts/check_knowledge_coverage.py survivor-series --cap=1
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402
from kayfabe.adapter.outbound.pg.agent_prediction_pg_repository import (  # noqa: E402
    AgentPredictionPgRepository,
)
from kayfabe.adapter.outbound.repositories.prediction_knowledge_repository import (  # noqa: E402
    PredictionKnowledgeRepository,
)
from kayfabe.app.dtos.agent_prediction_dto import (  # noqa: E402
    KnowledgeChunk,
    MatchContext,
)
from kayfabe.app.use_cases.ai_prediction_interactor import (  # noqa: E402
    KNOWLEDGE_TOP_K,
    build_knowledge_query,
)

#: **참가자를 한 명도 언급하지 않은 경기가 있다.** 그 경기를 지금 생성하면 서사·루머가
#: 무관한 자료를 읽거나 의견 없음을 내고, 확신도는 오즈 하나로 굳는다. 수집을 먼저 한다.
EXIT_NO_COVERAGE = 1
#: 일부 참가자만 걸렸다. 생성해도 되지만 **무엇이 빠졌는지 알고** 누르는 것과
#: 모르고 누르는 것은 다르다.
EXIT_PARTIAL_COVERAGE = 2

_CAP_FLAG = "--cap="

#: 상한을 적용할 때 상한 전에 받아 둘 후보 수. 상한이 0이면 쓰이지 않는다.
_POOL_MULTIPLIER = 16


def _parse_args(argv: list[str]) -> tuple[str, int]:
    slug = ""
    cap = 0
    for arg in argv[1:]:
        if arg.startswith(_CAP_FLAG):
            cap = int(arg.removeprefix(_CAP_FLAG))
        elif not slug:
            slug = arg
    return slug, cap


def _mentioned(chunk: KnowledgeChunk, names: list[str]) -> list[str]:
    """청크가 언급한 참가자. **에이전트가 읽는 것과 같은 `text`를 본다**(제목+본문)."""
    low = chunk.text.lower()
    return [name for name in names if name.lower() in low]


def _apply_cap(
    chunks: list[KnowledgeChunk], cap: int, top_k: int
) -> list[KnowledgeChunk]:
    """같은 `source_url`에서 최대 `cap`청크만 남긴다. `cap<=0`이면 운영과 같다."""
    if cap <= 0:
        return chunks[:top_k]
    taken: dict[str, int] = {}
    kept: list[KnowledgeChunk] = []
    for chunk in chunks:
        key = chunk.source_url or ""
        if taken.get(key, 0) >= cap:
            continue
        taken[key] = taken.get(key, 0) + 1
        kept.append(chunk)
        if len(kept) == top_k:
            break
    return kept


def _report(context: MatchContext, chunks: list[KnowledgeChunk]) -> int:
    """한 경기를 적고 **빠진 참가자 수**를 돌려준다."""
    names = [option.name for option in context.options]
    covered: set[str] = set()
    documents: set[str] = set()
    print(f"\n  {context.match_key} — {context.title}")
    if not chunks:
        print("    검색 결과 0건 — 이 경기에 대해 코퍼스가 아는 것이 없다.")
        return len(names)

    for index, chunk in enumerate(chunks, 1):
        hit = _mentioned(chunk, names)
        covered.update(hit)
        documents.add(chunk.source_url or "")
        published = chunk.published_at.date() if chunk.published_at else "발행시각 없음"
        print(f"    {index}. {chunk.source_url or '(출처 없음)'}")
        print(f"       참가자={hit or '-'} | d={chunk.distance} | {published}")

    missing = [name for name in names if name not in covered]
    print(
        f"    → 참가자 {len(covered)}/{len(names)}명 · 서로 다른 문서 {len(documents)}개"
        + (f" · 빠짐: {', '.join(missing)}" if missing else "")
    )
    return len(missing)


async def main() -> int:
    slug, cap = _parse_args(sys.argv)
    if not slug:
        print("사용법: check_knowledge_coverage.py <event-slug> [--cap=N]")
        return EXIT_NO_COVERAGE

    top_k = KNOWLEDGE_TOP_K
    print(f"대회={slug} · top_k={top_k} · 문서당 상한={cap or '없음(운영과 같음)'}")

    async with AsyncSessionLocal() as session:
        repository = AgentPredictionPgRepository(session)
        knowledge = PredictionKnowledgeRepository(session)
        contexts = await repository.load_contexts(event_slug=slug, match_keys=[])
        if not contexts:
            print("경기를 찾지 못했다 — 슬러그를 확인한다.")
            return EXIT_NO_COVERAGE

        # 상한을 적용할 때만 더 받는다. 상한이 없으면 운영과 **같은 호출**이어야 한다.
        fetch_k = top_k * _POOL_MULTIPLIER if cap > 0 else top_k
        empty = 0
        partial = 0
        for context in contexts:
            query = build_knowledge_query(context.title, context.options)
            chunks = await knowledge.search(query=query, top_k=fetch_k)
            missing = _report(context, _apply_cap(chunks, cap, top_k))
            if missing == len(context.options):
                empty += 1
            elif missing:
                partial += 1

    print(
        f"\n경기 {len(contexts)}건 · 전부 빠진 경기 {empty}건 · 일부 빠진 경기 {partial}건"
    )
    if empty:
        print("→ 수집을 먼저 돌린다. 지금 생성하면 그 경기는 지식 없이 굳는다.")
        return EXIT_NO_COVERAGE
    if partial:
        print("→ 생성해도 되지만 무엇이 빠졌는지 위 목록을 보고 판단한다.")
        return EXIT_PARTIAL_COVERAGE
    print("→ 검색은 준비됐다. (루머 축의 의견 없음은 이것과 별개다 — 독스트링 참조)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
