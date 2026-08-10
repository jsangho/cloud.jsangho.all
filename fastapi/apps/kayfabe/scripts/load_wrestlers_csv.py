"""wwe_active_roster_cleaned.csv를 wrestlers 테이블로 적재한다 (name 기준 upsert)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal
from sqlalchemy import select

from kayfabe.adapter.outbound.orm.wrestler_orm import WrestlerOrm

_CSV_PATH = (
    Path(__file__).resolve().parents[1] / "_docs" / "wwe_active_roster_cleaned.csv"
)

_CSV_HEADER = (
    "name",
    "real_name",
    "ring_names",
    "Stable&Team",
    "height",
    "weight",
    "birth_date",
    "birth_place",
    "billed_from",
    "trainer",
    "finisher",
)

_COLUMNS = (
    "name",
    "real_name",
    "ring_names",
    "stable_team",
    "height",
    "weight",
    "birth_date",
    "birth_place",
    "billed_from",
    "trainer",
    "finisher",
)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _read_rows() -> list[tuple[str | None, list[str]]]:
    with _CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.reader(f))

    header, *body = raw_rows
    if tuple(header) != _CSV_HEADER:
        raise ValueError(f"unexpected CSV header: {header}")

    rows: list[tuple[str | None, list[str]]] = []
    brand: str | None = None
    for r in body:
        if not r or all(not cell.strip() for cell in r):
            continue
        if len(r) == 1 and r[0].startswith("#"):
            brand = r[0][1:]
            continue
        if len(r) != len(_CSV_HEADER):
            raise ValueError(f"malformed CSV row (unexpected column count): {r}")
        rows.append((brand, r))
    return rows


async def main() -> None:
    rows = _read_rows()
    csv_names = {cells[0].strip() for _brand, cells in rows}

    inserted = 0
    updated = 0
    removed = 0
    async with AsyncSessionLocal() as session:
        # 이전 CSV(wwe_active_roster.csv)에만 있던 선수는 신규 CSV에 없으므로 삭제한다
        # (소스 CSV 자체가 교체된 것이므로 upsert만으로는 이전 로스터가 남아 잔존한다).
        stale = (
            await session.scalars(
                select(WrestlerOrm).where(WrestlerOrm.name.not_in(csv_names))
            )
        ).all()
        for row in stale:
            await session.delete(row)
            removed += 1

        for brand, cells in rows:
            record = dict(zip(_COLUMNS, cells, strict=True))
            record["brand"] = brand
            values = {col: _clean(val) for col, val in record.items()}
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
        f"wrestlers: {inserted} inserted, {updated} updated, {removed} removed "
        f"(of {len(rows)} CSV rows)"
    )


if __name__ == "__main__":
    asyncio.run(main())
