"""보드의 현 재위를 획득 이력에 채운다.

## 왜 있는가

`title_acquisitions`는 손으로 쓴 `REAL_TITLE_ACQUISITIONS`의 거울이라, 보드가 갱신돼도
행이 늘지 않았다. 2026-10-07 운영 실측에서 **보드 재위 24건 중 21건이 이력에 없었고**,
그래서 벨트 페이지의 획득 횟수가 낡은 값을 보였다 — Sami Zayn의 Undisputed WWE가
2회인데 1회로 나온 것이 그 증상이다.

판정 규칙은 `app/services/reign_history.py`에 있다. **여기에 규칙을 적지 않는다.**

## 언제 돌리나

- **위키 동기화 뒤** — `sync_champion_board_from_wiki.py --apply`가 보드를 바꾸면
  그 재위가 이력에 없다. 둘을 이어서 돌린다.
- **PLE 결과 확정 뒤** — `verify_match_results.py --apply`로 타이틀 매치가 확정되면
  보드가 읽기 시점에 승계를 반영한다. 그 재위도 여기서 들어온다.

**여러 번 돌려도 안전하다.** 이미 있는 재위는 날짜로 걸러 다시 넣지 않는다.

## 못 하는 것

보드는 벨트마다 **현 재위 하나**만 들고 있다. 두 번 돌리는 사이에 벨트가 A → B → C로
옮겨 갔다면 B는 어디에도 안 남는다 — 지나간 재위는 위키를 다시 읽어야 복원된다.
**빠진 것을 채울 뿐 없는 것을 지어내지 않는다.**

## 종료 코드

- `0` — 정상(채울 것이 없어도 `0`).
- `2` — 사용법 오류.
- `4` — `DATABASE_URL`이 비어 있다(더미 모드).

실행 — **기본이 드라이런이고, 쓰려면 `--apply`를 붙인다:**

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python \\
        apps/kayfabe/scripts/backfill_board_reigns.py
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python \\
        apps/kayfabe/scripts/backfill_board_reigns.py --apply
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402

# `outbound.mappers.__init__`가 `inbound.api`를 거쳐 다시 자신을 부르는 **기존** 순환이
# 있다. 운영에서는 `main.py`가 라우터를 먼저 임포트해 순서가 맞으므로 여기서도 같은
# 순서를 만든다. 빠뜨리면 PG 어댑터 임포트가 깨진다.
import kayfabe.adapter.inbound.api.v1.ple_events_router  # noqa: F401,E402
from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402
from kayfabe.adapter.outbound.pg.title_acquisitions_pg_repository import (  # noqa: E402
    TitleAcquisitionsPgRepository,
)

EXIT_USAGE = 2
EXIT_NO_DATABASE = 4


async def main(*, apply: bool) -> int:
    if AsyncSessionLocal is None:
        print("DATABASE_URL이 비어 있습니다 — 더미 모드에서는 돌릴 수 없습니다.")
        return EXIT_NO_DATABASE

    async with AsyncSessionLocal() as session:
        repository = TitleAcquisitionsPgRepository(session)
        added = await repository.record_board_reigns()
        if apply and added:
            await session.commit()
        else:
            await session.rollback()

    print(f"이력에 없던 보드 재위: {len(added)}건")
    for competitor, belt, won_at in added:
        print(f"  {competitor:<22} {belt:<42} {won_at}")

    if not added:
        print("\n채울 것이 없습니다 — 보드와 이력이 이미 맞습니다.")
    elif apply:
        print(f"\n반영 완료: {len(added)}건 (source='board')")
    else:
        print("\n드라이런 — 아무것도 쓰지 않았습니다. 쓰려면 --apply")
    return 0


def _parse(argv: list[str]) -> bool | None:
    apply = False
    for arg in argv:
        if arg == "--apply":
            apply = True
        else:
            return None
    return apply


if __name__ == "__main__":
    parsed = _parse(sys.argv[1:])
    if parsed is None:
        print(__doc__)
        raise SystemExit(EXIT_USAGE)
    raise SystemExit(asyncio.run(main(apply=parsed)))
