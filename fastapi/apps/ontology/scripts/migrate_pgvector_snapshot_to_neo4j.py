"""pgvector(wrestlers·player·team·stadium·schedule)를 Neo4j로 1회성 스냅샷 복사한다.

demo_users/demo_jobs가 Neo4j Browser에 이미 들어있는 것과 같은 성격의 작업이다.
PG가 여전히 원본(system of record)이고 벡터 검색도 그대로 pgvector `<=>` 코사인
검색으로 수행된다(langgraph-strategy.md §1-2 — 벡터 검색 계층 이전은 반대).
이 스크립트는 실행 시점의 데이터를 Neo4j에 한 번 복사할 뿐, 이후 PG 데이터가
바뀌어도 자동으로 갱신되지 않는다 — 최신화하려면 다시 실행한다.

임베딩(vector(1024)) 컬럼은 옮기지 않는다 — 벡터 검색은 pgvector 담당이고,
Neo4j 그래프는 관계 탐색·시각화 용도로만 쓴다.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402

from core.matrix.grid_architect_graph_manager import (  # noqa: E402
    dispose_neo4j_driver,
    driver,
)
from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402


def _to_jsonable(row: dict[str, Any]) -> dict[str, Any]:
    return {
        k: (v.isoformat() if isinstance(v, date) else v)
        for k, v in row.items()
        if k != "embedding"
    }


async def _fetch(sql: str) -> list[dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(sql))
        return [_to_jsonable(dict(row)) for row in result.mappings()]


async def main() -> None:
    if driver is None:
        raise RuntimeError("NEO4J_URI가 설정되지 않았습니다.")

    wrestlers = await _fetch("SELECT * FROM wrestlers")
    stadiums = await _fetch("SELECT * FROM stadium")
    teams = await _fetch("SELECT * FROM team")
    players = await _fetch("SELECT * FROM player")
    schedules = await _fetch("SELECT * FROM schedule")

    async with driver.session() as session:
        await session.run(
            """
            UNWIND $rows AS row
            MERGE (w:Wrestler {id: row.id})
            SET w.name = row.name, w.real_name = row.real_name,
                w.ring_names = row.ring_names, w.stable_team = row.stable_team,
                w.height = row.height, w.weight = row.weight,
                w.birth_date = row.birth_date, w.birth_place = row.birth_place,
                w.billed_from = row.billed_from, w.trainer = row.trainer,
                w.finisher = row.finisher, w.brand = row.brand
            """,
            rows=wrestlers,
        )

        await session.run(
            """
            UNWIND $rows AS row
            MERGE (s:Stadium {stadium_id: row.stadium_id})
            SET s.name = row.statdium_name, s.hometeam_id = row.hometeam_id,
                s.seat_count = row.seat_count, s.address = row.address,
                s.tel = row.tel
            """,
            rows=stadiums,
        )

        await session.run(
            """
            UNWIND $rows AS row
            MERGE (t:Team {team_id: row.team_id})
            SET t.name = row.team_name, t.e_name = row.e_team_name,
                t.region_name = row.region_name, t.orig_yyyy = row.orig_yyyy,
                t.address = row.address, t.homepage = row.homepage
            """,
            rows=teams,
        )
        await session.run(
            """
            UNWIND $rows AS row
            MATCH (t:Team {team_id: row.team_id})
            MATCH (s:Stadium {stadium_id: row.stadium_id})
            MERGE (t)-[:PLAYS_AT]->(s)
            """,
            rows=[t for t in teams if t.get("stadium_id")],
        )

        await session.run(
            """
            UNWIND $rows AS row
            MERGE (p:Player {player_id: row.player_id})
            SET p.name = row.player_name, p.e_name = row.e_player_name,
                p.nickname = row.nickname, p.position = row.position,
                p.back_no = row.back_no, p.nation = row.nation,
                p.birth_date = row.birth_date, p.height = row.height,
                p.weight = row.weight, p.join_yyyy = row.join_yyyy
            """,
            rows=players,
        )
        await session.run(
            """
            UNWIND $rows AS row
            MATCH (p:Player {player_id: row.player_id})
            MATCH (t:Team {team_id: row.team_id})
            MERGE (p)-[:BELONGS_TO]->(t)
            """,
            rows=[p for p in players if p.get("team_id")],
        )

        await session.run(
            """
            UNWIND $rows AS row
            MERGE (m:Schedule {id: row.id})
            SET m.sche_date = row.sche_date, m.gubun = row.gubun,
                m.home_score = row.home_score, m.away_score = row.away_score
            """,
            rows=schedules,
        )
        await session.run(
            """
            UNWIND $rows AS row
            MATCH (m:Schedule {id: row.id})
            MATCH (s:Stadium {stadium_id: row.stadium_id})
            MERGE (m)-[:AT_STADIUM]->(s)
            """,
            rows=[s for s in schedules if s.get("stadium_id")],
        )
        await session.run(
            """
            UNWIND $rows AS row
            MATCH (m:Schedule {id: row.id})
            MATCH (t:Team {team_id: row.hometeam_id})
            MERGE (m)-[:HOME_TEAM]->(t)
            """,
            rows=[s for s in schedules if s.get("hometeam_id")],
        )
        await session.run(
            """
            UNWIND $rows AS row
            MATCH (m:Schedule {id: row.id})
            MATCH (t:Team {team_id: row.awayteam_id})
            MERGE (m)-[:AWAY_TEAM]->(t)
            """,
            rows=[s for s in schedules if s.get("awayteam_id")],
        )

    print(
        f"완료 — Wrestler {len(wrestlers)} · Stadium {len(stadiums)} · "
        f"Team {len(teams)} · Player {len(players)} · Schedule {len(schedules)}"
    )
    await dispose_neo4j_driver()


if __name__ == "__main__":
    asyncio.run(main())
