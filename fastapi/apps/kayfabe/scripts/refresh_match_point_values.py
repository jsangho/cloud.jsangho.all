"""배점 상수(`ple_scoring.py`)를 바꾼 뒤 운영 DB의 `point_value`를 재계산한다.

`list_rankings()` 조회마다 자동 실행되던 걸 뗐다(`shop-point-ledger.md` §2-1) —
과거 획득액이 조회할 때마다 조용히 바뀌면 포인트 원장 잔액이 어긋나기 때문이다.
이제는 배점 상수를 수정한 뒤 이 스크립트를 의도적으로 1회 실행해야 반영된다.
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402

from kayfabe.adapter.outbound.pg.ple_events_pg_repository import (  # noqa: E402
    PleEventsPgRepository,
)


async def main() -> None:
    async with AsyncSessionLocal() as session:
        repository = PleEventsPgRepository(db=session)
        updated = await repository.refresh_all_match_point_values()
        await session.commit()

    print(f"point_value 재계산 완료 — 변경된 매치 {updated}건")


if __name__ == "__main__":
    asyncio.run(main())
