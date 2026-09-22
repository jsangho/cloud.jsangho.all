"""대회 날짜 카탈로그를 이미 있는 행에 반영한다 (Phase 3-13 Stage 3-B).

**Stage 3-A가 문을 냈고 여기가 그 문을 여는 유일한 손잡이다.**
`PleEventsRepository.set_event_schedule`은 3-A에서 추가됐지만 부르는 곳이 없어,
카탈로그(`PLE_EVENT_SCHEDULE`)에 확인된 날짜가 적혀 있는데도 운영 DB의
`ple_events.start_date`는 전부 `NULL`로 남아 있었다. 그 상태에서는 평가의 계보
게이트(`_corpus`)가 `event_start_date is None`에 걸려 **판정을 못 하고 보류만** 낸다.

**왜 카드 동기화로 하지 않는가.** 날짜를 쓰는 다른 경로인 `upsert_event_from_sync`도
카탈로그를 읽지만, 그것은 날짜만 쓰지 않는다 — 페이로드에 없는 경기를 지우고
(`ple_predictions`가 CASCADE로 함께 사라진다), `status`를 갈아 끼우고, 결과가 실려
있으면 `winner_pick`까지 덮어쓴다. 날짜 두 칸을 채우자고 사용자 예측을 걸 수 없다.

## 이 스크립트가 하지 않는 것

- **카탈로그에 없는 대회를 건드리지 않는다.** `(None, None)`을 쓰지 않는다는 뜻이다.
  날짜를 비워 둔 둘(bad-blood — 2026년에 열리지 않는다 · king-queen-of-the-ring —
  대회 대응 관계 미정)에 누군가 날짜를 넣어 뒀다면 그것은 카탈로그가 모르는
  앎이므로, 지우지 않고 **보고만** 한다.
- **없는 대회를 만들지 않는다.** `set_event_schedule`이 `UPDATE`라 구조적으로 불가능하다.
- **값이 같으면 쓰지 않는다.** `updated_at`이 `onupdate`로 함께 실리므로, 무변경 쓰기는
  "이 행이 언제 바뀌었나"를 거짓으로 만든다. 그래서 다시 돌려도 안전하다(멱등).

## 종료 코드

- `0` — 카탈로그의 대회가 전부 DB에 있고 반영됐다(또는 이미 같았다).
- `1` — 카탈로그에 있는데 DB에 없는 대회가 있다. **있는 것은 반영한다** — 대회별 날짜는
  서로 독립이고 다시 돌리면 되므로, 하나 없다고 나머지를 미루지 않는다.
  **지금 `survivor-series`가 그 상태다**(2026-09-22 실측: `ple_events` 11행에 없다).
  이 스크립트를 돌리면 나머지는 반영되고 종료 코드는 `1`이 나온다 — 고장이 아니라
  "행을 아직 안 만들었다"는 보고다.
- `2` — 사용법 오류.
- `4` — `DATABASE_URL`이 비어 있다(더미 모드). Neon URL을 받기 전에는 여기서 멈춘다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python \\
        apps/kayfabe/scripts/apply_event_schedule.py --dry-run

`--dry-run`을 붙이지 않으면 실제로 쓴다. 대신 쓰기 전에 대상 전부를 before → after로
출력한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import date  # noqa: E402

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

# `outbound.mappers.__init__`가 `inbound.api`를 거쳐 다시 자신을 부르는 **기존** 순환이
# 있다. 운영에서는 `main.py`가 라우터를 먼저 임포트해 순서가 맞으므로, 여기서도 같은
# 순서를 만든다. 빠뜨리면 PG 어댑터 임포트가 깨진다.
import kayfabe.adapter.inbound.api.v1.ple_events_router  # noqa: F401,E402
from kayfabe.adapter.outbound.catalog.ple_event_schedule_catalog import (  # noqa: E402
    PLE_EVENT_SCHEDULE,
)
from kayfabe.adapter.outbound.orm.ple_orm import PleEventModel  # noqa: E402
from kayfabe.adapter.outbound.pg.ple_events_pg_repository import (  # noqa: E402
    PleEventsPgRepository,
)

EXIT_MISSING_EVENT = 1
EXIT_USAGE = 2
EXIT_NO_DATABASE = 4

#: `(시작일, 끝날)` 한 쌍.
Schedule = tuple[date | None, date | None]


@dataclass(frozen=True)
class ScheduleChange:
    """카탈로그 한 줄과 DB 한 행을 맞댄 결과."""

    slug: str
    #: DB에 그 slug의 행이 있는가. 없으면 `current`는 의미가 없다.
    found: bool
    current: Schedule
    catalog: Schedule

    @property
    def needs_write(self) -> bool:
        """행이 있고 값이 실제로 다를 때만 쓴다."""
        return self.found and self.current != self.catalog


async def collect_changes(session: AsyncSession) -> list[ScheduleChange]:
    """카탈로그에 있는 slug만, slug 순서로 현재 값과 맞댄다."""
    rows = {
        row.slug: row for row in (await session.scalars(select(PleEventModel))).all()
    }
    changes: list[ScheduleChange] = []
    for slug, (start, end) in sorted(PLE_EVENT_SCHEDULE.items()):
        row = rows.get(slug)
        changes.append(
            ScheduleChange(
                slug=slug,
                found=row is not None,
                current=(row.start_date, row.end_date)
                if row is not None
                else (None, None),
                catalog=(start, end),
            )
        )
    return changes


async def untracked_dated_events(
    session: AsyncSession,
) -> list[tuple[str, date | None, date | None]]:
    """카탈로그 밖인데 날짜가 들어 있는 대회.

    **지우지 않고 보고만 한다.** 카탈로그는 "여기 없는 대회는 모른다"고 선언하는데,
    모른다는 것이 "비어 있어야 한다"는 뜻은 아니다. 값이 있다면 카탈로그가 놓친
    사실이므로 사람이 보고 카탈로그를 고칠 일이다.
    """
    rows = (await session.scalars(select(PleEventModel))).all()
    return [
        (row.slug, row.start_date, row.end_date)
        for row in sorted(rows, key=lambda r: r.slug)
        if row.slug not in PLE_EVENT_SCHEDULE
        and (row.start_date is not None or row.end_date is not None)
    ]


def exit_code_for(changes: list[ScheduleChange]) -> int:
    """카탈로그에 적힌 대회가 DB에 없으면 알린다 — 쓰기 성공과는 별개의 사실이다."""
    if any(not change.found for change in changes):
        return EXIT_MISSING_EVENT
    return 0


async def apply_changes(
    repository: PleEventsPgRepository, changes: list[ScheduleChange]
) -> int:
    """`needs_write`인 것만 쓴다. 커밋하지 않는다 — 트랜잭션 경계는 부르는 쪽이 정한다."""
    written = 0
    for change in changes:
        if not change.needs_write:
            continue
        start, end = change.catalog
        ok = await repository.set_event_schedule(
            slug=change.slug, start_date=start, end_date=end
        )
        if not ok:
            # `collect_changes`가 행을 봤는데 쓰기에서 0행이면 그 사이에 사라진
            # 것이다. 조용히 넘기지 않는다.
            raise RuntimeError(f"대상 행이 사라졌습니다: slug={change.slug!r}")
        written += 1
    return written


def _fmt(schedule: Schedule) -> str:
    start, end = schedule
    return f"{start}~{end}" if end is not None else f"{start}"


def _report(
    changes: list[ScheduleChange],
    drift: list[tuple[str, date | None, date | None]],
) -> None:
    print(f"카탈로그 {len(changes)}건:")
    for change in changes:
        if not change.found:
            print(f"  {change.slug:<22} DB에 행이 없습니다 (만들지 않습니다)")
        elif change.needs_write:
            print(
                f"  {change.slug:<22} {_fmt(change.current)} -> {_fmt(change.catalog)}"
            )
        else:
            print(f"  {change.slug:<22} {_fmt(change.current)} (이미 같음)")

    if drift:
        print("\n카탈로그 밖인데 날짜가 있는 대회 (건드리지 않습니다):")
        for slug, start, end in drift:
            print(f"  {slug:<22} {_fmt((start, end))}")


async def main(*, dry_run: bool) -> int:
    if AsyncSessionLocal is None:
        print("DATABASE_URL이 비어 있습니다 — 더미 모드에서는 반영할 수 없습니다.")
        return EXIT_NO_DATABASE

    async with AsyncSessionLocal() as session:
        changes = await collect_changes(session)
        drift = await untracked_dated_events(session)
        _report(changes, drift)

        pending = [change for change in changes if change.needs_write]
        if dry_run:
            print(f"\n--dry-run — 아무것도 쓰지 않았습니다. 쓸 예정: {len(pending)}건")
            return exit_code_for(changes)

        if not pending:
            print("\n바꿀 것이 없습니다.")
            return exit_code_for(changes)

        written = await apply_changes(PleEventsPgRepository(session), changes)
        await session.commit()

    print(f"\n반영 완료: {written}건 (날짜 두 칸 외에는 건드리지 않았습니다)")
    return exit_code_for(changes)


if __name__ == "__main__":
    argv = sys.argv[1:]
    unknown = [arg for arg in argv if arg != "--dry-run"]
    if unknown:
        print(f"사용법: apply_event_schedule.py [--dry-run] (모르는 인자: {unknown})")
        raise SystemExit(EXIT_USAGE)
    raise SystemExit(asyncio.run(main(dry_run="--dry-run" in argv)))
