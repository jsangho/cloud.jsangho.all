"""날짜가 지난 대회의 `status`를 `finished`로 넘긴다 (Phase 3-13 Stage 8).

**이 드리프트에는 장치가 없었다.** `mark_event_finished`는 결과 동기화
(`sync_event`)에서만 불리고, 그것도 `FINISHED_EVENT_SLUGS`에 이름이 적힌 대회에만
걸린다. 그래서 **결과를 넣지 않는 대회는 날짜가 아무리 지나도 영영 `upcoming`으로
남는다.** 2026-09-22에 `clash-in-italy`(5.31)·`night-of-champions`(6.27) 둘을
손으로 UPDATE해 고쳤는데, 손으로 고치는 한 같은 일이 계속 생긴다.

## 이 스크립트가 하지 않는 것

- **`finished_at`을 쓰지 않는다.** 기존 `finished` 대회의 `finished_at`은 전부
  카드 동기화가 돌던 시각, 즉 이 저장소에서 그 칸의 뜻은 "결과가 기록된 시각"이다.
  날짜가 지났다는 사실은 결과가 기록됐다는 뜻이 아니므로 그것을 지어낼 수 없다.
  **`finished` + `finished_at IS NULL`이 "끝났지만 결과 미기록"을 정확히 말한다.**
- **경기를 건드리지 않는다.** `mark_event_finished`는 `winner_pick`이 있는 경기를
  함께 `FINISHED`로 넘기지만, 결과가 없는 대회에서는 넘길 근거가 없다.
  `set_event_status`는 `ple_matches`를 읽지도 쓰지도 않는다.
- **날짜를 모르는 대회를 판정하지 않는다.** `start_date`가 `NULL`이면 통과가 아니라
  **보류**다. `bad-blood`(2026에 안 열림)·`king-queen-of-the-ring`
  (`night-of-champions`에 흡수됨)이 그 자리이고, 둘은 영구히 보류가 정상이다.
- **`finished`를 되돌리지 않는다.** 한 방향으로만 흐른다.
- **없는 대회를 만들지 않는다.** `set_event_status`가 `UPDATE`라 구조적으로 불가능하다.
- **값이 같으면 쓰지 않는다.** `updated_at`이 `onupdate`로 함께 실리므로, 무변경
  쓰기는 "이 행이 언제 바뀌었나"를 거짓으로 만든다. 다시 돌려도 안전하다(멱등).

## 날짜는 DB에서 읽는다 — 카탈로그가 아니다

Stage 7의 회차 관문과 같은 이유다. 판정 기준이 카탈로그에 매달려 있으면 카탈로그를
고치는 순간 `status`와 시간 게이트가 서로 다른 날짜를 보게 된다. `ple_events`의
`start_date`가 두 축의 공통 출처다 — 그 칸을 채우는 것은
`apply_event_schedule.py`의 일이므로, **그것을 먼저 돌린다.**

`end_date`가 있으면 그쪽이 마지막 날이다(SummerSlam은 8/1~8/2 이틀짜리다).
"지났다"는 **마지막 날 < 오늘(UTC)** 이다 — 당일에는 넘기지 않는다. 대회는 각자의
현지 시각에 열리므로, 하루를 양보하는 편이 열리지도 않은 대회를 끝난 것으로
표시하는 것보다 안전하다.

## 종료 코드

- `0` — 정상. 보류가 남아 있어도 `0`이다(영구 보류가 정상인 대회가 있다).
- `2` — 사용법 오류.
- `4` — `DATABASE_URL`이 비어 있다(더미 모드).

실행 — **기본이 드라이런이고, 쓰려면 `--apply`를 붙인다:**

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python \\
        apps/kayfabe/scripts/close_past_events.py
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python \\
        apps/kayfabe/scripts/close_past_events.py --apply

> **형제 스크립트와 기본값이 반대다.** `apply_event_schedule.py`는 `--dry-run`을
> 붙여야 안 쓴다. 이쪽을 뒤집은 이유는 쓰는 대상이 다르기 때문이다 — 날짜는
> 카탈로그라는 사람이 확인한 출처가 있지만, 여기서 `finished`는 **오늘 날짜로부터
> 파생**된다. 파생된 판정이 아무 플래그 없이 운영 DB에 들어가지 않게 한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import UTC, date, datetime  # noqa: E402

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

# `outbound.mappers.__init__`가 `inbound.api`를 거쳐 다시 자신을 부르는 **기존** 순환이
# 있다. 운영에서는 `main.py`가 라우터를 먼저 임포트해 순서가 맞으므로, 여기서도 같은
# 순서를 만든다. 빠뜨리면 PG 어댑터 임포트가 깨진다.
import kayfabe.adapter.inbound.api.v1.ple_events_router  # noqa: F401,E402
from kayfabe.adapter.outbound.orm.ple_orm import (  # noqa: E402
    PleEventModel,
    PleEventStatus,
)
from kayfabe.adapter.outbound.pg.ple_events_pg_repository import (  # noqa: E402
    PleEventsPgRepository,
)

EXIT_USAGE = 2
EXIT_NO_DATABASE = 4


@dataclass(frozen=True)
class StatusChange:
    """대회 한 행을 오늘과 맞댄 결과."""

    slug: str
    status: str
    start_date: date | None
    end_date: date | None
    today: date

    @property
    def last_day(self) -> date | None:
        """대회의 마지막 날. 이틀짜리면 `end_date`가 그것이다."""
        return self.end_date or self.start_date

    @property
    def held(self) -> bool:
        """날짜를 모르면 판정하지 않는다 — 통과가 아니라 보류다."""
        return self.last_day is None

    @property
    def is_past(self) -> bool:
        """마지막 날이 오늘보다 앞설 때만 지난 것이다. 당일은 아니다."""
        last = self.last_day
        return last is not None and last < self.today

    @property
    def needs_write(self) -> bool:
        """`finished`가 아닌 채로 날짜가 지난 행만 쓴다.

        `upcoming`뿐 아니라 `live`도 대상이다 — 둘 다 "아직 안 끝났다"는 주장이고
        날짜가 지났으면 거짓이다. `finished`는 어느 쪽으로도 되돌리지 않는다.
        """
        return self.status != PleEventStatus.FINISHED and self.is_past


async def collect_changes(session: AsyncSession, *, today: date) -> list[StatusChange]:
    """`ple_events` 전체를 slug 순서로 오늘과 맞댄다.

    카탈로그로 거르지 않는다 — `status`는 **행의 사실**이지 카탈로그의 사실이 아니다.
    화면에서 감춘 대회(`unlisted`)도 DB에는 그대로 있고, 그 행의 상태도 참이어야 한다.
    """
    rows = (await session.scalars(select(PleEventModel))).all()
    return [
        StatusChange(
            slug=row.slug,
            status=row.status,
            start_date=row.start_date,
            end_date=row.end_date,
            today=today,
        )
        for row in sorted(rows, key=lambda r: r.slug)
    ]


async def apply_changes(
    repository: PleEventsPgRepository, changes: list[StatusChange]
) -> int:
    """`needs_write`인 것만 쓴다. 커밋하지 않는다 — 트랜잭션 경계는 부르는 쪽이 정한다."""
    written = 0
    for change in changes:
        if not change.needs_write:
            continue
        ok = await repository.set_event_status(
            slug=change.slug, status=PleEventStatus.FINISHED
        )
        if not ok:
            # `collect_changes`가 행을 봤는데 쓰기에서 0행이면 그 사이에 사라진
            # 것이다. 조용히 넘기지 않는다.
            raise RuntimeError(f"대상 행이 사라졌습니다: slug={change.slug!r}")
        written += 1
    return written


def _fmt(change: StatusChange) -> str:
    if change.end_date is not None:
        return f"{change.start_date}~{change.end_date}"
    return f"{change.start_date}"


def _report(changes: list[StatusChange], *, today: date) -> None:
    print(f"오늘(UTC) {today} 기준 · 대회 {len(changes)}건:")
    for change in changes:
        if change.held:
            print(f"  {change.slug:<22} 날짜 미상 — 보류 ({change.status})")
        elif change.needs_write:
            print(f"  {change.slug:<22} {_fmt(change)} {change.status} -> finished")
        elif change.status == PleEventStatus.FINISHED:
            print(f"  {change.slug:<22} {_fmt(change)} 이미 finished")
        else:
            print(f"  {change.slug:<22} {_fmt(change)} 아직 안 지남 ({change.status})")


async def main(*, apply: bool, today: date | None = None) -> int:
    if AsyncSessionLocal is None:
        print("DATABASE_URL이 비어 있습니다 — 더미 모드에서는 반영할 수 없습니다.")
        return EXIT_NO_DATABASE

    today = today or datetime.now(UTC).date()

    async with AsyncSessionLocal() as session:
        changes = await collect_changes(session, today=today)
        _report(changes, today=today)

        pending = [change for change in changes if change.needs_write]
        if not apply:
            print(
                f"\n드라이런 — 아무것도 쓰지 않았습니다. "
                f"쓸 예정: {len(pending)}건 (쓰려면 --apply)"
            )
            return 0

        if not pending:
            print("\n바꿀 것이 없습니다.")
            return 0

        written = await apply_changes(PleEventsPgRepository(session), changes)
        await session.commit()

    print(f"\n반영 완료: {written}건 (status 한 칸 외에는 건드리지 않았습니다)")
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    unknown = [arg for arg in argv if arg != "--apply"]
    if unknown:
        print(f"사용법: close_past_events.py [--apply] (모르는 인자: {unknown})")
        raise SystemExit(EXIT_USAGE)
    raise SystemExit(asyncio.run(main(apply="--apply" in argv)))
