"""wwe_active_roster.csv를 wrestlers 테이블로 적재한다 (name 기준 upsert)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio

from sqlalchemy import select

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal
from kayfabe.adapter.outbound.orm.wrestler_orm import WrestlerOrm

_CSV_PATH = Path(__file__).resolve().parents[1] / "_docs" / "wwe_active_roster.csv"

_COLUMNS = (
    "wikipedia_title",
    "name",
    "real_name",
    "ring_names",
    "height",
    "weight",
    "birth_date",
    "birth_place",
    "resides",
    "billed_from",
    "trainer",
    "debut",
    "retired",
    "finisher",
)


def _clean(value: str) -> str | None:
    value = value.strip()
    return value or None


async def main() -> None:
    with _CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    inserted = 0
    updated = 0
    async with AsyncSessionLocal() as session:
        for row in rows:
            values = {col: _clean(row[col]) for col in _COLUMNS}
            existing = await session.scalar(
                select(WrestlerOrm).where(WrestlerOrm.name == values["name"])
            )
            if existing is not None:
                for col, val in values.items():
                    setattr(existing, col, val)
                updated += 1
            else:
                session.add(WrestlerOrm(**values))
                inserted += 1
        await session.commit()

    print(
        f"wrestlers: {inserted} inserted, {updated} updated (of {len(rows)} CSV rows)"
    )


if __name__ == "__main__":
    asyncio.run(main())
