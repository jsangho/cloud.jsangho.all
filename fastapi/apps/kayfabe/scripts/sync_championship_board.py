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

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal

from kayfabe.adapter.outbound.pg.title_acquisitions_pg_repository import (
    TitleAcquisitionsPgRepository,
)


async def main() -> None:
    async with AsyncSessionLocal() as session:
        repo = TitleAcquisitionsPgRepository(db=session)
        board_count = await repo.sync_from_catalog()
        history_count = await repo.sync_from_real_catalog()
        await session.commit()

    print(f"championship_titles: {board_count} rows synced")
    print(f"title_acquisitions: {history_count} rows synced")


if __name__ == "__main__":
    asyncio.run(main())
