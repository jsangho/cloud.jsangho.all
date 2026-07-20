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

# 원본 CSV 145~146행: Tank Ledger의 trainer 값(`"WWE Performance Center...`)에 닫는 따옴표가
# 누락되어, 표준 CSV 파서가 다음 줄(Tate Wilder 전체 행)까지 하나의 필드로 삼켜버린다.
# 원본 CSV는 건드리지 않고, 파싱 직후 알려진 값으로 두 행을 수동 분리한다
# (wwe-roster-database.md 3번 섹션 가정 h 참고).
_MERGED_ROW_FIX: dict[str, list[list[str]]] = {
    "Tank Ledger": [
        [
            "Tank Ledger",
            "Joe Spivak",
            "Tank Ledger",
            "Hank & Tank",
            "180cm",
            "136kg",
            "1999-10-11",
            "Chicago, Illinois",
            "Chicago, Illinois",
            "WWE Performance Center",
            "Baba Bomb | Fisherman's Spinebuster",
        ],
        [
            "Tate Wilder",
            "Case Hatch",
            "Tate Wilder",
            "",
            "182cm",
            "104kg",
            "19997-09-06",
            "Gilbert, Arizona, United States",
            "Gilbert, Arizona, United States",
            "WWE Performance Center",
            "Wild Ride",
        ],
    ]
}


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
            fix = _MERGED_ROW_FIX.get(r[0])
            if fix is None:
                raise ValueError(f"malformed CSV row (unexpected column count): {r}")
            rows.extend((brand, fixed) for fixed in fix)
            continue
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
