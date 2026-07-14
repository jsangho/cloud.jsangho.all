"""stadium/team/schedule/player의 NULL embedding을 bge-m3(Keymaker)로 채운다."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

from soccer.adapter.outbound.orm.player_orm import PlayerOrm
from soccer.adapter.outbound.orm.schedule_orm import ScheduleOrm
from soccer.adapter.outbound.orm.stadium_orm import StadiumOrm
from soccer.adapter.outbound.orm.team_orm import TeamOrm
from sqlalchemy import select

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal
from core.matrix.vault_keymaker_secret_manager import get_keymaker


def _stadium_text(row: StadiumOrm) -> str:
    parts = [
        row.statdium_name,
        row.address,
        f"홈팀 {row.hometeam_id}" if row.hometeam_id else None,
    ]
    return " ".join(p for p in parts if p)


def _team_text(row: TeamOrm) -> str:
    parts = [row.team_name, row.e_team_name, row.region_name, row.address]
    return " ".join(p for p in parts if p)


def _schedule_text(row: ScheduleOrm) -> str:
    parts = [
        row.sche_date,
        row.gubun,
        f"{row.hometeam_id} vs {row.awayteam_id}"
        if row.hometeam_id or row.awayteam_id
        else None,
        f"{row.home_score}:{row.away_score}" if row.home_score is not None else None,
    ]
    return " ".join(p for p in parts if p)


def _player_text(row: PlayerOrm) -> str:
    parts = [
        row.player_name,
        row.e_player_name,
        row.nickname,
        row.position,
        row.nation,
        f"{row.team_id} 소속" if row.team_id else None,
    ]
    return " ".join(p for p in parts if p)


_TARGETS = (
    (StadiumOrm, _stadium_text),
    (TeamOrm, _team_text),
    (ScheduleOrm, _schedule_text),
    (PlayerOrm, _player_text),
)


async def _backfill_table(orm_cls, build_text) -> int:
    keymaker = get_keymaker()
    filled = 0
    async with AsyncSessionLocal() as session:
        rows = (
            await session.scalars(select(orm_cls).where(orm_cls.embedding.is_(None)))
        ).all()
        for row in rows:
            text = build_text(row)
            if not text:
                continue
            row.embedding = await asyncio.to_thread(keymaker.embed_text, text)
            filled += 1
        await session.commit()
    return filled


async def main() -> None:
    for orm_cls, build_text in _TARGETS:
        filled = await _backfill_table(orm_cls, build_text)
        print(f"{orm_cls.__tablename__}: {filled} rows embedded")


if __name__ == "__main__":
    asyncio.run(main())
