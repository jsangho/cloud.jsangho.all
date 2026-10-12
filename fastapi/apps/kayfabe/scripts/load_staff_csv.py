"""wwe_non_wrestler.csv를 `wwe_staff` 표로 적재한다 (name 기준 upsert).

`load_wrestlers_csv.py`와 같은 모양이고 다른 점이 셋이다.

1. **`#` 구역이 브랜드가 아니다.** 선수 CSV의 `#RAW`는 소속 브랜드지만 이 파일은
   `# Executives` · `# Raw Referee` · `#Producer (M)`처럼 **직군이 섞여 있다.**
   그래서 `brand`가 아니라 `group_label`에 그대로 넣는다 — 해석은 읽는 쪽이 한다.
2. **칸이 하나 모자란 행을 받아 준다.** 실측으로 한 행(`Jason Ayers`)이 마지막
   칸(`Wrestler&Team&Stable`)을 통째로 빠뜨렸다. **마지막 한 칸이 모자랄 때만**
   빈 값으로 채우고 그 사실을 출력한다 — 두 칸 이상이면 정렬이 어긋났다는 뜻이라
   멈춘다.
3. **CSV에 없는 행을 지우지 않는다.** 선수 로더는 로스터가 통째로 교체되는 표라
   잔존 행을 지우지만, 이 표는 지금 이 CSV가 유일한 입력이고 수동으로 더한 행이
   생길 수 있다. 지우는 판단은 사람 몫으로 남긴다.

실행 — **로컬은 더미 모드라 닿지 않는다. EC2 컨테이너 안에서 돌린다:**

    cd /app/fastapi && PYTHONUTF8=1 PYTHONPATH=apps:. python \\
        apps/kayfabe/scripts/load_staff_csv.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402

from sqlalchemy import select  # noqa: E402

from core.matrix.grid_oracle_database_manager import (  # noqa: E402
    AsyncSessionLocal,
)
from kayfabe.adapter.outbound.orm.staff_orm import StaffOrm  # noqa: E402

_CSV_PATH = Path(__file__).resolve().parents[1] / "_docs" / "wwe_non_wrestler.csv"

_CSV_HEADER = (
    "Name",
    "real_name",
    "ring_name",
    "korean_ring_name",
    "role",
    "gender",
    "birth_date",
    "birth_place",
    "wrestling_experience",
    "Wrestler&Team&Stable",
)

_COLUMNS = (
    "name",
    "real_name",
    "ring_name",
    "korean_ring_name",
    "role",
    "gender",
    "birth_date",
    "birth_place",
    "wrestling_experience",
    "wrestler_team_stable",
)

EXIT_NO_DATABASE = 4


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _read_rows() -> tuple[list[tuple[str | None, list[str]]], int]:
    """`(구역, 칸들)` 목록과 **채워 넣은 행 수**."""
    with _CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.reader(f))

    header, *body = raw_rows
    if tuple(header) != _CSV_HEADER:
        raise ValueError(f"unexpected CSV header: {header}")

    rows: list[tuple[str | None, list[str]]] = []
    padded = 0
    group: str | None = None
    for r in body:
        if not r or all(not cell.strip() for cell in r):
            continue
        if len(r) == 1 and r[0].startswith("#"):
            group = r[0][1:].strip()
            continue
        if len(r) == len(_CSV_HEADER) - 1:
            # 마지막 칸만 빠졌다 — 정렬은 어긋나지 않았다.
            r = [*r, ""]
            padded += 1
        if len(r) != len(_CSV_HEADER):
            raise ValueError(f"malformed CSV row (unexpected column count): {r}")
        rows.append((group, r))
    return rows, padded


async def main() -> int:
    if AsyncSessionLocal is None:
        print("DATABASE_URL이 비어 있습니다 — 더미 모드에서는 적재할 수 없습니다.")
        return EXIT_NO_DATABASE

    rows, padded = _read_rows()
    if padded:
        print(f"마지막 칸이 비어 있던 행 {padded}개를 빈 값으로 채웠습니다.")

    inserted = 0
    updated = 0
    async with AsyncSessionLocal() as session:
        for group, cells in rows:
            record = dict(zip(_COLUMNS, cells, strict=True))
            values = {col: _clean(val) for col, val in record.items()}
            values["group_label"] = _clean(group)
            existing = await session.scalar(
                select(StaffOrm).where(StaffOrm.name == values["name"])
            )
            if existing is not None:
                for col, val in values.items():
                    setattr(existing, col, val)
                updated += 1
            else:
                session.add(StaffOrm(**values))
                inserted += 1
        await session.commit()

    dated = sum(
        1
        for _g, cells in rows
        if len((cells[6] or "").strip()) == 10 and "?" not in cells[6]
    )
    print(
        f"wwe_staff: {inserted} inserted, {updated} updated "
        f"(of {len(rows)} CSV rows · 생년월일이 완전한 행 {dated})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
