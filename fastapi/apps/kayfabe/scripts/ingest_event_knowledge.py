"""PLE 하나에 필요한 지식을 카드에서 뽑아 적재한다 (하네스 §10-T3).

**대회마다 URL을 손으로 찾지 않기 위한 스크립트다.** 저장된 카드에서 대회명과 출전
선수를 읽어 위키백과 주소를 만들고, 허용 도메인 목록을 통과한 것만 수집한다.

서사 에이전트가 의견을 내려면 그 경기에 대한 자료가 검색돼야 한다. 대회 문서만
넣으면 경기마다 같은 문단이 뽑히므로, **선수 문서까지 넣어 경기별로 다른 근거**가
잡히게 한다.

`--max-chunks`로 문서당 청크 수를 제한한다. 위키 인물 문서는 대부분이 타이틀 이력과
각주라, 앞부분(요약·최근 활동)만 담아도 예측 근거로는 충분하고 임베딩 시간이 크게 준다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python apps/kayfabe/scripts/ingest_event_knowledge.py money-in-the-bank
    ... --dry-run    # 주소만 확인하고 요청은 보내지 않는다
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
from urllib.parse import quote  # noqa: E402

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402

from kayfabe.app.dtos.knowledge_ingestion_dto import (  # noqa: E402
    IngestKnowledgeCommand,
)
from kayfabe.dependencies.knowledge_ingestion_provider import (  # noqa: E402
    get_knowledge_ingestion_use_case,
)

_WIKI = "https://en.wikipedia.org/wiki/"

#: 대회 문서 주소는 사람이 붙인 이름 규칙을 따른다 — 못 맞히면 404로 조용히 넘어간다.
_EVENT_TITLES: dict[str, str] = {
    "royal-rumble": "Royal_Rumble",
    "elimination-chamber": "Elimination_Chamber_(2026)",
    "stand-and-deliver": "NXT_Stand_%26_Deliver",
    "wrestlemania": "WrestleMania_42",
    "backlash": "WWE_Backlash",
    "clash-in-italy": "WWE_Clash_in_Italy",
    "night-of-champions": "WWE_Night_of_Champions",
    "summerslam": "SummerSlam_(2026)",
    "money-in-the-bank": "Money_in_the_Bank_(2026)",
    "king-queen-of-the-ring": "WWE_King_and_Queen_of_the_Ring",
    "bad-blood": "WWE_Bad_Blood",
    "survivor-series": "Survivor_Series",
}


def _wiki_url(title: str) -> str:
    return _WIKI + quote(title.replace(" ", "_"), safe="_(),%&")


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
            # 팀 이름·스테이블은 인물 문서가 없을 때가 많지만, 없으면 404로 걸러진다.
            if name and name not in names:
                names.append(name)
    return names


async def _urls_for(slug: str) -> list[str]:
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

    urls: list[str] = []
    event_title = _EVENT_TITLES.get(slug)
    if event_title:
        urls.append(_wiki_url(event_title))
    for (card_json,) in rows:
        for name in _competitor_names(card_json):
            url = _wiki_url(name)
            if url not in urls:
                urls.append(url)
    return urls


async def main(slug: str, *, dry_run: bool, max_chunks: int | None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    urls = await _urls_for(slug)
    if not urls:
        print(f"카드를 찾지 못했습니다: {slug}")
        return 1

    print(f"대상 {len(urls)}건")
    for url in urls:
        print(f"  {url}")
    if dry_run:
        return 0

    async with AsyncSessionLocal() as session:
        use_case = get_knowledge_ingestion_use_case(session, max_chunks=max_chunks)
        summary = await use_case.ingest(IngestKnowledgeCommand(urls=tuple(urls)))
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
