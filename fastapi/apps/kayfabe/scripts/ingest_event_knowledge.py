"""PLE 하나에 필요한 지식을 카드에서 뽑아 적재한다 (하네스 §10-T3).

**대회마다 URL을 손으로 찾지 않기 위한 스크립트다.** 저장된 카드에서 대회명과 출전
선수를 읽어 위키백과 주소를 만들고, 허용 도메인 목록을 통과한 것만 수집한다.

서사 에이전트가 의견을 내려면 그 경기에 대한 자료가 검색돼야 한다. 대회 문서만
넣으면 경기마다 같은 문단이 뽑히므로, **선수 문서까지 넣어 경기별로 다른 근거**가
잡히게 한다.

**조립한 이름은 추측이라 보내기 전에 확인한다** (Phase 3-13 Stage 5). 예전에는
빗나간 이름이 404로 걸러진다고 믿고 그대로 보냈는데, 실측이 그 믿음을 깼다 —
`Penta`는 동음이의 문서("Penta may refer to:")로 200을 돌려주고, `Royce Keys`는
`Powerhouse Hobbs`로 넘어간다. 앞은 내용 없는 목록이 근거 자리를 차지하게 하고,
뒤는 정규 주소가 아닌 자리에 본문을 쌓아 **나중에 정규 이름으로 다시 넣을 때
`content_hash` 유니크에 막혀 저장 0건이 조용히 성공으로 보고되게** 한다.

그래서 위키에 먼저 한 번 묻는다. 정규 제목으로 바꿔 수집하고, 동음이의와 없는
문서는 요청조차 보내지 않는다. **확인에 실패하면 추측으로 이어가지 않고 멈춘다.**

`--max-chunks`로 문서당 청크 수를 제한한다. 위키 인물 문서는 대부분이 타이틀 이력과
각주라, 앞부분(요약·최근 활동)만 담아도 예측 근거로는 충분하고 임베딩 시간이 크게 준다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python apps/kayfabe/scripts/ingest_event_knowledge.py money-in-the-bank
    ... --dry-run    # 확인만 하고 수집 요청은 보내지 않는다

종료 코드: 0 정상 · 1 카드 없음/수집 0건 · 2 사용법 · **3 주소 확인 실패**
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
from collections.abc import Sequence  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from urllib.parse import quote  # noqa: E402

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402

from kayfabe.app.dtos.knowledge_ingestion_dto import (  # noqa: E402
    IngestKnowledgeCommand,
)
from kayfabe.dependencies.knowledge_ingestion_provider import (  # noqa: E402
    get_knowledge_ingestion_use_case,
)
from ontology.app.ports.output.wiki_title_port import (  # noqa: E402
    WikiTitle,
    WikiTitlePort,
)
from ontology.dependencies.wiki_title_provider import (  # noqa: E402
    get_wiki_title_port,
)

_WIKI = "https://en.wikipedia.org/wiki/"

#: 대회 문서 제목. **주소가 아니라 제목이다** — 인코딩은 `_wiki_url`이 하고,
#: 실재 여부는 위키에 물어 확인한다.
_EVENT_TITLES: dict[str, str] = {
    "royal-rumble": "Royal Rumble",
    "elimination-chamber": "Elimination Chamber (2026)",
    "stand-and-deliver": "NXT Stand & Deliver",
    "wrestlemania": "WrestleMania 42",
    "backlash": "WWE Backlash",
    "clash-in-italy": "WWE Clash in Italy",
    "night-of-champions": "WWE Night of Champions",
    "summerslam": "SummerSlam (2026)",
    "money-in-the-bank": "Money in the Bank (2026)",
    "king-queen-of-the-ring": "WWE King and Queen of the Ring",
    "bad-blood": "WWE Bad Blood",
    "survivor-series": "Survivor Series",
}


def _wiki_url(title: str) -> str:
    """제목을 위키 주소로 바꾼다.

    `&`·`%`를 그대로 두지 않는다 — `NXT Stand & Deliver`의 실제 주소는
    `NXT_Stand_%26_Deliver`이고, 인코딩을 건너뛰면 경로가 그 자리에서 끊긴다.
    괄호는 남긴다: `Money_in_the_Bank_(2026)`이 위키가 쓰는 모양이다.
    """
    return _WIKI + quote(title.replace(" ", "_"), safe="_(),")


def _competitor_names(card_json: str) -> list[str]:
    """카드에서 사람 이름만 뽑는다. 팀 표기(`A & B`)는 각각으로 나눈다."""
    card = json.loads(card_json or "{}")
    raw: list[str] = []
    if card.get("format") == "multi":
        raw = [c.get("name", "") for c in card.get("competitors", [])]
    else:
        raw = [
            card.get("left", {}).get("name", ""),
            card.get("right", {}).get("name", ""),
        ]

    names: list[str] = []
    for entry in raw:
        for part in entry.replace(" and ", " & ").split("&"):
            name = part.strip()
            # 팀 이름·스테이블은 인물 문서가 없을 때가 많다. 없는 문서는 위키
            # 확인 단계에서 걸러지고 요청은 나가지 않는다.
            if name and name not in names:
                names.append(name)
    return names


async def _titles_for(slug: str) -> list[str]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    "select m.card_json from ple_matches m "
                    "join ple_events e on e.id = m.event_id where e.slug = :slug "
                    "order by m.sort_order, m.id"
                ),
                {"slug": slug},
            )
        ).all()

    titles: list[str] = []
    event_title = _EVENT_TITLES.get(slug)
    if event_title:
        titles.append(event_title)
    for (card_json,) in rows:
        for name in _competitor_names(card_json):
            if name not in titles:
                titles.append(name)
    return titles


@dataclass(frozen=True)
class IngestionPlan:
    """무엇을 수집하고 무엇을 왜 버렸는지."""

    urls: tuple[str, ...] = ()
    #: `(물어본 이름, 정규 제목)` — 리다이렉트거나 표기가 다른 것.
    renamed: tuple[tuple[str, str], ...] = ()
    #: 본문이 아니라 같은 이름의 문서 목록이라 버린 것.
    disambiguation: tuple[str, ...] = ()
    #: 위키에 없어서 버린 것.
    missing: tuple[str, ...] = ()


def plan_for(titles: Sequence[str], resolved: dict[str, WikiTitle]) -> IngestionPlan:
    """확인 결과를 수집 계획으로 옮긴다. **DB도 네트워크도 모르는 순수 함수다.**

    표에 없는 이름은 **없는 문서로 본다.** 확인되지 않은 이름을 수집으로 넘기면
    이 관문이 하는 일이 없어진다.

    정규 제목이 겹치면 한 번만 수집한다 — `IYO SKY`와 `Iyo Sky`가 같은 문서라
    둘 다 보내면 두 번째는 `content_hash`에 막혀 저장 0건으로 돌아온다.
    """
    urls: list[str] = []
    renamed: list[tuple[str, str]] = []
    disambiguation: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()

    for title in titles:
        entry = resolved.get(title)
        if entry is None or entry.canonical is None:
            missing.append(title)
            continue
        if entry.is_disambiguation:
            disambiguation.append(title)
            continue
        if entry.is_renamed:
            renamed.append((title, entry.canonical))
        if entry.canonical in seen:
            continue
        seen.add(entry.canonical)
        urls.append(_wiki_url(entry.canonical))

    return IngestionPlan(
        urls=tuple(urls),
        renamed=tuple(renamed),
        disambiguation=tuple(disambiguation),
        missing=tuple(missing),
    )


def _report(plan: IngestionPlan) -> None:
    print(f"수집 대상 {len(plan.urls)}건")
    for url in plan.urls:
        print(f"  {url}")
    for requested, canonical in plan.renamed:
        print(f"  정규 주소로 바꿈: {requested} → {canonical}")
    for title in plan.disambiguation:
        print(f"  동음이의라 버림: {title}")
    for title in plan.missing:
        print(f"  위키에 없어 버림: {title}")


async def main(
    slug: str,
    *,
    dry_run: bool,
    max_chunks: int | None,
    titles_port: WikiTitlePort | None = None,
) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    titles = await _titles_for(slug)
    if not titles:
        print(f"카드를 찾지 못했습니다: {slug}")
        return 1

    resolved = await (titles_port or get_wiki_title_port()).resolve(titles)
    if resolved is None:
        # 추측한 주소로 이어가지 않는다. 확인이 막혔다면 뒤따를 문서별 요청은
        # 더 심하게 막힌다 — 잠시 뒤 다시 돌리는 것이 맞다.
        print("위키에 문서를 확인하지 못했습니다. 수집하지 않고 멈춥니다.")
        return 3

    plan = plan_for(titles, resolved)
    _report(plan)
    if not plan.urls:
        print("수집할 문서가 없습니다.")
        return 1
    if dry_run:
        return 0

    async with AsyncSessionLocal() as session:
        use_case = get_knowledge_ingestion_use_case(session, max_chunks=max_chunks)
        summary = await use_case.ingest(IngestKnowledgeCommand(urls=plan.urls))
        await session.commit()

    print(
        f"요청 {summary.requested} · 수집 {summary.collected} · 청크 {summary.chunks} "
        f"· 저장 {summary.stored} · 중복 {summary.duplicates} · 실패 {summary.failed}"
    )
    return 0 if summary.collected else 1


if __name__ == "__main__":
    argv = sys.argv[1:]
    positional = [a for a in argv if not a.startswith("--")]
    if not positional:
        print("사용법: ingest_event_knowledge.py <slug> [--dry-run] [--max-chunks=N]")
        raise SystemExit(2)

    limit_arg = next((a for a in argv if a.startswith("--max-chunks=")), None)
    raise SystemExit(
        asyncio.run(
            main(
                positional[0],
                dry_run="--dry-run" in argv,
                max_chunks=int(limit_arg.split("=")[1]) if limit_arg else 25,
            )
        )
    )
