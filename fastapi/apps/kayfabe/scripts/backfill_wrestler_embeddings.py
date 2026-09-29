"""wrestlers의 NULL embedding을 bge-m3(Keymaker)로 채운다."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

from sqlalchemy import select

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal
from core.matrix.vault_keymaker_secret_manager import get_keymaker
from kayfabe.adapter.outbound.orm.wrestler_orm import WrestlerOrm


def _wrestler_text(row: WrestlerOrm) -> str:
    parts = [
        row.name,
        f"본명 {row.real_name}" if row.real_name else None,
        f"링네임 {row.ring_names}" if row.ring_names else None,
        f"소속 스테이블/팀 {row.stable_team}" if row.stable_team else None,
        f"브랜드 {row.brand}" if row.brand else None,
        f"신장 {row.height}" if row.height else None,
        f"체중 {row.weight}" if row.weight else None,
        f"출신 {row.birth_place}" if row.birth_place else None,
        f"연고지 {row.billed_from}" if row.billed_from else None,
        f"트레이너 {row.trainer}" if row.trainer else None,
        f"피니셔 {row.finisher}" if row.finisher else None,
    ]
    return " ".join(p for p in parts if p)


async def main() -> None:
    keymaker = get_keymaker()
    filled = 0
    async with AsyncSessionLocal() as session:
        rows = (
            await session.scalars(
                select(WrestlerOrm).where(WrestlerOrm.embedding.is_(None))
            )
        ).all()
        for row in rows:
            text = _wrestler_text(row)
            if not text:
                continue
            row.embedding = await asyncio.to_thread(keymaker.embed_text, text)
            filled += 1
        await session.commit()
    print(f"wrestlers: {filled} rows embedded")


if __name__ == "__main__":
    asyncio.run(main())
