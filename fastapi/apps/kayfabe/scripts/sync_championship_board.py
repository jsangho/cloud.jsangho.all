"""current_championship_catalog.py / real_title_catalog.py 변경분을 DB에 강제 반영한다.

championship_titles·title_acquisitions 테이블은 비어 있을 때만 자동으로 재시딩되므로,
카탈로그 코드를 수정한 뒤 운영 DB에 즉시 반영하려면 이 스크립트를 실행한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio
import json

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal
from sqlalchemy import delete

from kayfabe.adapter.outbound.orm.championship_orm import ChampionshipTitleModel
from kayfabe.adapter.outbound.orm.title_history_orm import TitleAcquisitionModel
from kayfabe.app.services.current_championship_catalog import (
    CHAMPIONSHIP_AS_OF,
    WWE_BRAND_CHAMPIONS,
)
from kayfabe.app.services.real_title_catalog import (
    CATALOG_REVISION,
    individual_title_acquisitions,
)


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(ChampionshipTitleModel))
        board_count = 0
        for brand in WWE_BRAND_CHAMPIONS:
            for title in brand["titles"]:
                session.add(
                    ChampionshipTitleModel(
                        brand_id=brand["id"],
                        belt_name=title["belt_name"],
                        champions_json=json.dumps(
                            list(title["champions"]), ensure_ascii=False
                        ),
                        team_name=title.get("team_name"),
                        won_at=title["won_at"],
                        won_event=title.get("won_event"),
                        tier=title["tier"],
                        as_of=CHAMPIONSHIP_AS_OF,
                    )
                )
                board_count += 1

        await session.execute(delete(TitleAcquisitionModel))
        history_count = 0
        seen: set[tuple[str, str, str]] = set()
        source = f"real:{CATALOG_REVISION}"
        for competitor, reigns in individual_title_acquisitions().items():
            for belt_name, won_at in reigns:
                key = (competitor, belt_name, won_at)
                if key in seen:
                    continue
                seen.add(key)
                session.add(
                    TitleAcquisitionModel(
                        competitor_name=competitor,
                        belt_name=belt_name,
                        won_at=won_at,
                        source=source,
                    )
                )
                history_count += 1

        await session.commit()

    print(f"championship_titles: {board_count} rows synced")
    print(f"title_acquisitions: {history_count} rows synced")


if __name__ == "__main__":
    asyncio.run(main())
