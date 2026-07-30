"""stadium/team/schedule/player의 NULL embedding을 bge-m3(Keymaker)로 채운다."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal
from core.matrix.vault_keymaker_secret_manager import get_keymaker
from soccer.adapter.outbound.orm.player_orm import PlayerOrm
from soccer.adapter.outbound.orm.schedule_orm import ScheduleOrm
from soccer.adapter.outbound.orm.stadium_orm import StadiumOrm
from soccer.adapter.outbound.orm.team_orm import TeamOrm
from sqlalchemy import select


def _team_label(team_id: str | None, team_names: dict[str, str]) -> str | None:
    """FK 코드(K06) 대신 사람이 쓰는 이름(아이파크)을 임베딩에 넣기 위한 해소.

    코드만 넣으면 "아이파크 소속 수비수" 같은 질문이 선수 행과 절대 매칭되지
    않는다 — 벡터에 팀 이름 문자열이 아예 없기 때문이다.
    """
    if not team_id:
        return None
    return team_names.get(team_id) or team_id


def _stadium_text(row: StadiumOrm, team_names: dict[str, str]) -> str:
    home = _team_label(row.hometeam_id, team_names)
    parts = [
        row.statdium_name,
        row.address,
        f"홈팀 {home}" if home else None,
        f"좌석수 {row.seat_count}" if row.seat_count else None,
    ]
    return " ".join(p for p in parts if p)


def _team_text(row: TeamOrm, team_names: dict[str, str]) -> str:
    parts = [row.team_name, row.e_team_name, row.region_name, row.address]
    return " ".join(p for p in parts if p)


def _schedule_text(row: ScheduleOrm, team_names: dict[str, str]) -> str:
    home = _team_label(row.hometeam_id, team_names)
    away = _team_label(row.awayteam_id, team_names)
    parts = [
        row.sche_date,
        row.gubun,
        f"{home} vs {away}" if home or away else None,
        f"{row.home_score}:{row.away_score}" if row.home_score is not None else None,
    ]
    return " ".join(p for p in parts if p)


def _player_text(row: PlayerOrm, team_names: dict[str, str]) -> str:
    team = _team_label(row.team_id, team_names)
    parts = [
        row.player_name,
        row.e_player_name,
        row.nickname,
        row.position,
        row.nation,
        f"{team} 소속" if team else None,
        f"등번호 {row.back_no}" if row.back_no else None,
        f"신장 {row.height}cm" if row.height else None,
        f"체중 {row.weight}kg" if row.weight else None,
        f"{row.birth_date.year}년생" if row.birth_date else None,
    ]
    return " ".join(p for p in parts if p)


_TARGETS = (
    (StadiumOrm, _stadium_text),
    (TeamOrm, _team_text),
    (ScheduleOrm, _schedule_text),
    (PlayerOrm, _player_text),
)


async def _team_name_lookup(session) -> dict[str, str]:
    rows = (await session.execute(select(TeamOrm.team_id, TeamOrm.team_name))).all()
    return {tid: name for tid, name in rows if name}


async def _backfill_table(orm_cls, build_text) -> int:
    keymaker = get_keymaker()
    filled = 0
    async with AsyncSessionLocal() as session:
        team_names = await _team_name_lookup(session)
        rows = (
            await session.scalars(select(orm_cls).where(orm_cls.embedding.is_(None)))
        ).all()
        for row in rows:
            text = build_text(row, team_names)
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
