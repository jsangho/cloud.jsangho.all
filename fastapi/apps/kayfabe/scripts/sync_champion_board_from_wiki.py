"""위키 `List of current champions in WWE`로 챔피언 보드 기준선을 갱신한다.

## 왜 이 스크립트가 있는가

`championship_titles` 행은 사람이 적은 카탈로그에서 나왔고 `as_of`에 기준일이 박혀
있다. 보드 읽기 경로는 그 기준선 위에 **PLE 결과만** 얹으므로(`apply_results`),
Raw·SmackDown·하우스쇼에서 바뀐 타이틀은 아무도 반영하지 않는다. 2026-09-28 전수
대조에서 22개 벨트 중 13개가 그래서 틀려 있었다.

이 스크립트가 넓은 축이다. 위키 표를 읽어 기준선 자체를 갱신하고 `as_of`를 읽은 날로
올린다. 그 뒤 PLE 결과는 여전히 즉시 얹히고, **그 이전 결과는 기준일 관문이 건너뛴다**
— 위키가 이미 반영한 것을 두 번 얹지 않는다.

## 기본이 드라이런이다

운영 DB에 쓰는 스크립트이고, 되돌리려면 옛 챔피언·날짜를 사람이 다시 찾아야 한다.
그래서 `--apply` 없이는 무엇을 쓸지만 출력한다.

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python apps/kayfabe/scripts/sync_champion_board_from_wiki.py
    ... --apply     # 실제로 쓴다

## 같은 날 열린 PLE는 건너뛰게 된다

`as_of`는 읽은 날(UTC)이다. 오늘 열린 PLE의 결과가 DB에 들어와도 관문(`<=`)이 그것을
기준일 이전으로 보아 건너뛴다. 위키가 그 결과를 이미 실었다면 맞는 동작이고, 아직
안 실었다면 그 한 경기가 다음 동기화까지 안 보인다. 그날 보드를 맞춰야 하면 이
스크립트를 대회 **전에** 돌린다.

종료 코드: 0 정상 · 1 위키 읽기/파싱 실패 · 2 보드 행이 없음
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402
import json  # noqa: E402
from datetime import UTC, datetime  # noqa: E402

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402
from sqlalchemy import select  # noqa: E402

from kayfabe.adapter.outbound.orm.championship_orm import (  # noqa: E402
    ChampionshipTitleModel,
)
from kayfabe.app.services.wiki_belt_names import (  # noqa: E402
    WIKI_BELT_ALIASES,
    WIKI_CHAMPIONS_ARTICLE,
    WIKI_CHAMPIONS_SECTION,
)
from kayfabe.domain.services.champion_board_sync import (  # noqa: E402
    WikiSyncPlan,
    plan_wiki_sync,
)
from kayfabe.domain.services.champion_table_parser import (  # noqa: E402
    WikiChampionRow,
    parse_champion_table,
)
from kayfabe.domain.services.championship_succession import TitleReign  # noqa: E402
from ontology.app.ports.output.wiki_article_port import WikiArticlePort  # noqa: E402
from ontology.dependencies.wiki_article_provider import (  # noqa: E402
    get_wiki_article_port,
)


async def read_wiki_rows(port: WikiArticlePort) -> tuple[WikiChampionRow, ...] | None:
    """현 챔피언 절을 읽어 파싱한다. 읽지 못하면 `None` — 빈 표로 이어가지 않는다.

    **절 번호를 상수로 박지 않는다.** 문서가 절을 하나 얻으면 번호가 전부 밀리고, 그때
    엉뚱한 절을 표로 읽으면 행이 0건이 되는 대신 조용히 다른 값이 나올 수 있다.
    """
    sections = await port.sections(WIKI_CHAMPIONS_ARTICLE)
    if not sections:
        print(f"[fail] 목차를 읽지 못했다: {WIKI_CHAMPIONS_ARTICLE}")
        return None

    index = next(
        (
            s.index
            for s in sections
            if s.line.casefold() == WIKI_CHAMPIONS_SECTION.casefold()
        ),
        None,
    )
    if index is None:
        print(f"[fail] 절을 찾지 못했다: {WIKI_CHAMPIONS_SECTION}")
        return None

    section = await port.read_section(WIKI_CHAMPIONS_ARTICLE, index)
    if section is None:
        print(f"[fail] 절 본문을 읽지 못했다: {WIKI_CHAMPIONS_SECTION}(index={index})")
        return None

    rows = parse_champion_table(section.text)
    print(
        f"위키 {WIKI_CHAMPIONS_ARTICLE} · 개정본 {section.revision_id} · {len(rows)}행"
    )
    return rows or None


def print_plan(plan: WikiSyncPlan) -> None:
    for update in plan.updated:
        before, after = update.before, update.after
        print(f"  [갱신] {update.belt_name}")
        print(
            f"         {', '.join(before.champions)} ({before.won_at}) → "
            f"{', '.join(after.champions)} ({after.won_at})"
        )
        if after.team_name:
            print(f"         팀 {after.team_name}")
        print(f"         대회 {before.won_event or '-'} → {after.won_event or '-'}")
    if plan.missing_on_wiki:
        print(f"  [위키에 없음] {', '.join(plan.missing_on_wiki)}")
    if plan.unmatched_wiki:
        print(f"  [보드에 없음] {', '.join(plan.unmatched_wiki)}")
    print(
        f"기준일 {plan.as_of} · 갱신 {len(plan.updated)} · 그대로 {len(plan.unchanged)} · "
        f"위키에 없음 {len(plan.missing_on_wiki)} · 보드에 없음 {len(plan.unmatched_wiki)}"
    )


async def main(*, apply: bool) -> int:
    rows = await read_wiki_rows(get_wiki_article_port())
    if rows is None:
        return 1

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ChampionshipTitleModel).order_by(
                ChampionshipTitleModel.brand_id, ChampionshipTitleModel.id
            )
        )
        board = list(result.scalars().all())
        if not board:
            print(
                "[fail] championship_titles가 비어 있다. sync_championship_board.py를 먼저 돌린다"
            )
            return 2

        plan = plan_wiki_sync(
            [
                TitleReign(
                    belt_name=row.belt_name,
                    champions=tuple(json.loads(row.champions_json)),
                    team_name=row.team_name,
                    won_at=row.won_at,
                    won_event=row.won_event,
                )
                for row in board
            ],
            rows,
            as_of=datetime.now(UTC).date().isoformat(),
            aliases=WIKI_BELT_ALIASES,
        )
        print_plan(plan)

        if not apply:
            print("드라이런이다 — 쓰지 않았다. 반영하려면 --apply")
            return 0

        changed = {update.belt_name: update.after for update in plan.updated}
        for row in board:
            after = changed.get(row.belt_name)
            if after is not None:
                row.champions_json = json.dumps(
                    list(after.champions), ensure_ascii=False
                )
                row.team_name = after.team_name
                row.won_at = after.won_at
                row.won_event = after.won_event
            # **기준일은 모든 행에 적는다.** 읽기 경로가 `rows[0].as_of` 하나를 기준선으로
            # 쓰므로, 갱신된 행에만 적으면 어느 행이 0번이냐에 따라 관문이 흔들린다.
            row.as_of = plan.as_of
        await session.commit()

    print(f"championship_titles: {len(plan.updated)}행 갱신 · 기준일 {plan.as_of}")
    return 0


if __name__ == "__main__":
    flags = set(sys.argv[1:])
    unknown = flags - {"--apply"}
    if unknown:
        print(f"모르는 인자: {' '.join(sorted(unknown))}")
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(apply="--apply" in flags)))
