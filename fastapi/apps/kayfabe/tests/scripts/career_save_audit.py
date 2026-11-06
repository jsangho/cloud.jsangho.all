"""커리어 세이브 오프라인 감사. **파일만 읽는다 — DB 에 접속하지 않는다.**

복구 런북 §2 의 탐지 단계다. 입력은 읽기 전용 추출이 만든 백업 파일이고, 이 프로그램은
DB 드라이버를 import 하지 않으므로 운영에 닿을 수 없다. 쓰는 것도 없다.

## 왜 있나

API 로 잡히는 손상은 일부뿐이다(2026-11-06 격리 PG 실측).

    구조·타입 손상   전부 500   코덱이 거부한다
    논리 손상        전부 200   어떤 경로도 알려 주지 않는다

그래서 두 번째를 잡으려면 저장된 값을 규칙과 대조해야 한다.

## 사용

    cd fastapi
    PYTHONPATH=apps:. uv run python apps/kayfabe/tests/scripts/career_save_audit.py <백업.json>

## 종료 코드

- `0` — 문제 없음
- `1` — 문제 있음
- `2` — 입력을 읽을 수 없다

**세이브 내용을 출력하지 않는다.** career id·판본·기록 수·문제 코드·경기 id 만 나간다.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

from kayfabe.adapter.outbound.pg.career_world_codec import load
from kayfabe.app.ports.output.sandbox_career_repository import CorruptSaveError
from kayfabe.domain.services import career_match_record as records
from kayfabe.domain.services.career_world import STATE_FIELDS, WorldState

EXIT_CLEAN = 0
EXIT_DAMAGED = 1
EXIT_UNREADABLE = 2

_WINS = STATE_FIELDS.index("wins")
_LOSSES = STATE_FIELDS.index("losses")


def _record_issues(record: Any, world: WorldState) -> list[str]:
    """기록 한 장의 규칙 위반."""
    found = []
    if record.id != records.match_id(season=record.season, week=record.week):
        found.append("RECORD_ID")
    if (record.season, record.week) > (world.season, world.week):
        found.append("RECORD_FUTURE")
    since = world.match_records_since
    if since is not None and (record.season, record.week) < since:
        found.append("RECORD_BEFORE_SINCE")
    winners = record.teams[record.winner_side]
    if record.finisher is not None and record.finisher not in winners:
        found.append("RECORD_WINNER")
    pinfall = record.finish == records.PINFALL
    if pinfall != (record.scorer is not None) or pinfall != (record.pinned is not None):
        found.append("RECORD_PIN")
    if world.player not in record.teams[0]:
        found.append("RECORD_PLAYER")
    for participant in record.participants:
        won = participant.after[_WINS] - participant.before[_WINS]
        lost = participant.after[_LOSSES] - participant.before[_LOSSES]
        if (won, lost) != (
            (1, 0) if participant.side == record.winner_side else (0, 1)
        ):
            found.append("RECORD_RESULT")
            break
    return found


def _audit_world(world: WorldState) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    ids = [m.id for m in world.matches]
    if len(ids) != len(set(ids)):
        issues.append({"code": "RECORD_DUPLICATE"})
    keys = [(m.season, m.week) for m in world.matches]
    if keys != sorted(keys):
        issues.append({"code": "RECORD_ORDER"})
    if len(world.matches) > records.MAX_MATCH_RECORDS:
        issues.append({"code": "RECORD_OVER_CAP"})
    for record in world.matches:
        issues.extend(
            {"code": code, "match": record.id} for code in _record_issues(record, world)
        )
    for entry in world.log:
        if entry.kind != "match" or entry.subject != world.player:
            continue
        reason = records.missing_reason(world, season=entry.season, week=entry.week)
        if reason == records.UNEXPLAINED:
            issues.append(
                {
                    "code": "LOG_WITHOUT_RECORD",
                    "match": records.match_id(season=entry.season, week=entry.week),
                }
            )
    return issues


def audit_row(row: dict[str, Any]) -> dict[str, Any]:
    """백업 한 행. 세이브 내용은 결과에 담지 않는다."""
    raw = row["world"]
    report: dict[str, Any] = {
        "id": row.get("id"),
        "version": raw.get("version"),
        "records": 0,
        "issues": [],
    }
    try:
        world = load(copy.deepcopy(raw))
    except CorruptSaveError:
        report["issues"].append({"code": "DECODE_FAILED"})
        return report

    report["records"] = len(world.matches)
    report["issues"].extend(_audit_world(world))
    for column in ("season", "week", "phase"):
        if column in row and row[column] != raw.get(column):
            report["issues"].append({"code": "MIRROR_MISMATCH", "column": column})
    return report


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reports = [audit_row(row) for row in rows]
    damaged = [r for r in reports if r["issues"]]
    versions: dict[str, int] = {}
    for report in reports:
        key = str(report["version"])
        versions[key] = versions.get(key, 0) + 1
    return {
        "careers": len(reports),
        "versions": versions,
        "match_records": sum(r["records"] for r in reports),
        "damaged": len(damaged),
        "reports": damaged,
    }


def read_rows(path: Path) -> list[dict[str, Any]]:
    """백업 파일 또는 추출 봉투에서 career 행을 꺼낸다."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc, dict) and "careers" in doc:
        doc = doc["careers"]
    rows = doc.get("rows") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        raise ValueError("career 행 목록을 찾을 수 없다")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("backup", type=Path)
    args = parser.parse_args(argv)
    try:
        rows = read_rows(args.backup)
    except (OSError, ValueError) as e:
        print(f"UNREADABLE {type(e).__name__}", file=sys.stderr)
        return EXIT_UNREADABLE
    result = audit_rows(rows)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return EXIT_DAMAGED if result["damaged"] else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
