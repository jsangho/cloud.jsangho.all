"""결과가 기록됐는데 `finished_at`이 빈 대회 행을 경기 시각으로 메꾼다.

**`close_past_events.py`와 `sync_event`가 만나면 이 구멍이 생긴다.** `sync_event`는
`status != finished`일 때만 `mark_event_finished`를 부른다. 그런데 날짜가 지난 대회는
`close_past_events.py`가 먼저 `finished`로 넘겨 놓으므로, 그 뒤에 결과를 넣으면
**경기 행에는 `finished_at`이 박히는데 대회 행에는 안 박힌다.**

그래서 두 문서가 주장하는 불변식이 깨져 있었다 — `close_past_events.py` 모듈 주석과
`ple_events_repository.py`의 `set_event_status` 주석이 `finished` + `finished_at IS NULL`을
**"끝났지만 결과 미기록"** 이라고 말하지만, 2026-09-28 운영 실측에서 세 대회가
결과를 온전히 갖고도 그 모양이었다: `clash-in-italy`(5/5) · `night-of-champions`(6/6) ·
`worlds-collide`(7/7).

## 값을 지어내지 않는다 — `max(경기 finished_at)`을 쓴다

`now()`를 넣으면 2026-08-04에 적재된 결과에 오늘 날짜를 씌우게 된다. 그 칸의 뜻은
**"결과가 기록된 시각"** 이고, 그 시각은 이미 경기 행이 들고 있다.

기존 대회들이 실제로 그 모양이다(2026-09-28 실측). `backlash`는 대회
`06:58:40.410595`, 경기 최대 `06:58:40.409709` — 대회 행을 경기 다음에 썼기 때문에
밀리초만큼 뒤다. 그래서 **최대값**이 가장 가까운 재구성이다.

`summerslam` 하나는 대회 시각이 경기 최소값보다 **앞선다**(`.785494` < `.854098`).
쓰기 순서가 반대였던 적이 있다는 뜻인데, 그 행은 이미 값이 있어 이 스크립트의 대상이
아니다. **값이 있는 행은 어떤 경우에도 덮어쓰지 않는다.**

## 이 스크립트가 하지 않는 것

- **`status`를 바꾸지 않는다.** 대상이 이미 `finished`인 행뿐이다. 넘기는 일은
  `close_past_events.py`가 한다.
- **결과가 없는 대회를 건드리지 않는다.** `winner_pick`이 하나도 없으면 그 행의
  `finished_at IS NULL`은 결함이 아니라 **불변식이 제대로 동작하는 것**이다
  (`vengeance-day`·`great-american-bash`·`heatwave`가 그 자리다).
- **결과가 일부만 있는 대회도 건드리지 않는다.** 아직 다 안 들어온 것과 다 들어온 것을
  같은 시각으로 봉인하면 나중에 구분할 수 없다. 보류로 남기고 수만 알린다.
- **경기 행을 바꾸지 않는다.** `mark_event_finished`는 `winner_pick`이 있는데 아직
  `finished`가 아닌 경기만 넘기는데, 이 스크립트의 대상은 전 경기가 이미 `finished`인
  대회뿐이라 그 분기에 걸리는 행이 없다.
- **`finished_at`을 모르는 대회를 판정하지 않는다.** 경기에 `finished_at`이 없으면
  재구성할 재료가 없으므로 보류다.

## 종료 코드

- `0` — 정상. 보류가 남아 있어도 `0`이다(영구 보류가 정상인 대회가 있다).
- `2` — 사용법 오류.
- `4` — `DATABASE_URL`이 비어 있다(더미 모드).

실행 — **기본이 드라이런이고, 쓰려면 `--apply`를 붙인다** (`close_past_events.py`와
같은 이유다: 값이 다른 행에서 파생되므로 아무 플래그 없이 운영에 들어가지 않게 한다):

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python \\
        apps/kayfabe/scripts/backfill_event_finished_at.py
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python \\
        apps/kayfabe/scripts/backfill_event_finished_at.py --apply
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import datetime  # noqa: E402

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

# `outbound.mappers.__init__`가 `inbound.api`를 거쳐 다시 자신을 부르는 **기존** 순환이
# 있다. 운영에서는 `main.py`가 라우터를 먼저 임포트해 순서가 맞으므로, 여기서도 같은
# 순서를 만든다. 빠뜨리면 PG 어댑터 임포트가 깨진다.
import kayfabe.adapter.inbound.api.v1.ple_events_router  # noqa: F401,E402
from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402
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
class Backfill:
    """대회 한 행과 그 경기들을 맞댄 결과."""

    event_id: int
    slug: str
    finished_at: datetime | None
    match_count: int
    with_winner: int
    latest_match_finished_at: datetime | None

    @property
    def has_results(self) -> bool:
        """전 경기에 승자가 있어야 "결과가 온전히 들어왔다"고 말한다."""
        return self.match_count > 0 and self.with_winner == self.match_count

    @property
    def needs_write(self) -> bool:
        """값이 비어 있고, 결과가 온전하고, 재구성할 시각이 있을 때만 쓴다."""
        return (
            self.finished_at is None
            and self.has_results
            and self.latest_match_finished_at is not None
        )

    @property
    def reason(self) -> str:
        """왜 대상이 아닌지 — 보류를 침묵으로 넘기지 않는다."""
        if self.finished_at is not None:
            return "이미 값이 있음"
        if self.match_count == 0:
            return "경기 없음 — 결과 미기록이 맞다"
        if self.with_winner == 0:
            return "승자 없음 — 결과 미기록이 맞다"
        if not self.has_results:
            return f"결과 일부만 있음 ({self.with_winner}/{self.match_count}) — 보류"
        return "경기에 finished_at이 없어 재구성 불가 — 보류"


async def collect_backfills(session: AsyncSession) -> list[Backfill]:
    """`finished` 대회 전체를 slug 순서로 모은다.

    `status`가 `finished`가 아닌 행은 애초에 대상이 아니다 — 끝나지도 않은 대회에
    "결과가 기록된 시각"을 적을 수는 없다.
    """
    rows = (
        await session.scalars(
            select(PleEventModel)
            .where(PleEventModel.status == PleEventStatus.FINISHED)
            .options(selectinload(PleEventModel.matches))
        )
    ).all()

    backfills = []
    for row in rows:
        stamps = [m.finished_at for m in row.matches if m.finished_at is not None]
        backfills.append(
            Backfill(
                event_id=row.id,
                slug=row.slug,
                finished_at=row.finished_at,
                match_count=len(row.matches),
                with_winner=sum(1 for m in row.matches if m.winner_pick),
                latest_match_finished_at=max(stamps) if stamps else None,
            )
        )
    return sorted(backfills, key=lambda b: b.slug)


async def apply_backfills(
    repository: PleEventsPgRepository, backfills: list[Backfill]
) -> int:
    """`needs_write`인 것만 쓴다. 커밋하지 않는다 — 트랜잭션 경계는 부르는 쪽이 정한다."""
    written = 0
    for backfill in backfills:
        if not backfill.needs_write:
            continue
        # `latest_match_finished_at`은 `needs_write`가 None을 걸러 준다.
        assert backfill.latest_match_finished_at is not None
        await repository.mark_event_finished(
            event_id=backfill.event_id,
            finished_at=backfill.latest_match_finished_at,
        )
        written += 1
    return written


def _report(backfills: list[Backfill]) -> None:
    print(f"finished 대회 {len(backfills)}건:")
    for backfill in backfills:
        if backfill.needs_write:
            print(
                f"  {backfill.slug:<22} NULL -> {backfill.latest_match_finished_at} "
                f"(경기 {backfill.with_winner}/{backfill.match_count})"
            )
        else:
            print(f"  {backfill.slug:<22} {backfill.reason}")


async def main(*, apply: bool) -> int:
    if AsyncSessionLocal is None:
        print("DATABASE_URL이 비어 있습니다 — 더미 모드에서는 반영할 수 없습니다.")
        return EXIT_NO_DATABASE

    async with AsyncSessionLocal() as session:
        backfills = await collect_backfills(session)
        _report(backfills)

        pending = [b for b in backfills if b.needs_write]
        if not apply:
            print(
                f"\n드라이런 — 아무것도 쓰지 않았습니다. "
                f"쓸 예정: {len(pending)}건 (쓰려면 --apply)"
            )
            return 0

        written = await apply_backfills(PleEventsPgRepository(session), backfills)
        await session.commit()
        print(
            f"\n반영 완료: {written}건 (finished_at 한 칸 외에는 건드리지 않았습니다)"
        )
        return 0


def _parse_args(argv: list[str]) -> bool:
    extra = [arg for arg in argv if arg != "--apply"]
    if extra:
        print(f"알 수 없는 인자: {extra} — 쓰는 옵션은 `--apply` 하나입니다.")
        sys.exit(EXIT_USAGE)
    return "--apply" in argv


if __name__ == "__main__":
    sys.exit(asyncio.run(main(apply=_parse_args(sys.argv[1:]))))
