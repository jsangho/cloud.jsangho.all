"""끝난 대회의 결과 미기록 경기를 위키에서 확인해 `winner_pick`을 채운다.

**이 저장소의 첫 진짜 에이전트를 돌리는 진입점이다.** 무엇이 에이전트인지·왜 이 자리
인지는 `app/use_cases/result_verification_interactor.py`와
`domain/entities/result_verification.py`의 독스트링에 적혀 있다.

## 이 스크립트가 하지 않는 것

- **대회 `status`를 건드리지 않는다.** 대상은 이미 `finished`인 대회뿐이다. 날짜가
  지났는데 `upcoming`인 대회를 넘기는 것은 `close_past_events.py`의 일이므로,
  **그것을 먼저 돌린다** — 안 돌리면 이 스크립트에 대상이 안 잡힌다.
- **`finished_at`을 직접 쓰지 않는다.** `set_match_result`가 경기 행에 박고, 대회 행의
  `finished_at`은 `mark_event_finished`의 몫이다.
- **없는 경기를 만들지 않는다.** `UPDATE`라 구조적으로 불가능하다.
- **예측을 건드리지 않는다.** `ple_agent_predictions`·`ple_predictions`를 읽지도 쓰지도
  않는다. 채점은 `winner_pick`이 채워지면 기존 집계가 알아서 한다
  (`point_aggregation`).
- **코퍼스에 아무것도 넣지 않는다.** 읽은 위키 본문은 판정에만 쓰고 버린다 —
  pgvector에 들어가면 그것이 곧 누수다(`ai_lab_leakage`).

## 보류가 정상이다

승자를 못 찾거나 근거가 약하면 쓰지 않고 이유를 적는다. 보류 사유는 일곱 가지이고
(`HoldReason`), 그중 `no_winner`는 **무승부·노컨테스트에서 정답**이다.
`quote_not_found`가 보이면 모델이 인용을 지어낸 것이니 그 경기는 사람이 본다.

## 종료 코드

- `0` — 정상. 보류가 남아 있어도 `0`이다.
- `2` — 사용법 오류.
- `4` — `DATABASE_URL`이 비어 있다(더미 모드).

실행 — **기본이 드라이런이고, 쓰려면 `--apply`를 붙인다:**

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python \\
        apps/kayfabe/scripts/verify_match_results.py
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python \\
        apps/kayfabe/scripts/verify_match_results.py --event mitb --limit 5 --apply

`close_past_events.py`와 기본값을 맞췄다. 쓰는 값이 **모델이 읽은 문서에서** 나오므로,
아무 플래그 없이 운영 DB에 들어가지 않게 한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402

# `outbound.mappers.__init__`가 `inbound.api`를 거쳐 다시 자신을 부르는 **기존** 순환이
# 있다. 운영에서는 `main.py`가 라우터를 먼저 임포트해 순서가 맞으므로, 여기서도 같은
# 순서를 만든다. 빠뜨리면 PG 어댑터 임포트가 깨진다.
import kayfabe.adapter.inbound.api.v1.ple_events_router  # noqa: F401,E402
from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402
from kayfabe.app.dtos.result_verification_dto import (  # noqa: E402
    MatchVerification,
    VerificationRun,
    VerifyResultsCommand,
)
from kayfabe.dependencies.result_verification_provider import (  # noqa: E402
    get_result_verification_use_case,
)

EXIT_USAGE = 2
EXIT_NO_DATABASE = 4

DEFAULT_LIMIT = 20


def _line(match: MatchVerification) -> str:
    head = f"  {match.event_slug}/{match.match_key:<18}"
    if match.pick is not None:
        mark = "기록" if match.written else "드라이런"
        return (
            f"{head} {match.winner_name} (pick={match.pick}) "
            f"[{mark}] 호출={match.tool_calls} "
            f"출처={match.source_title}@{match.source_revision_id or '판본미상'}"
        )
    return f"{head} 보류({match.hold}) 호출={match.tool_calls}"


def _report(run: VerificationRun) -> None:
    print(f"결과 미기록 경기 {run.found}건 · 이번에 본 것 {len(run.matches)}건:")
    for match in run.matches:
        print(_line(match))

    if run.found > len(run.matches):
        print(
            f"\n{run.found - len(run.matches)}건은 이번 실행에서 보지 않았습니다 "
            f"(--limit). 다시 돌리면 이어서 봅니다."
        )

    print(
        f"\n쓸 수 있음 {run.writable}건 · 보류 {run.held}건 · "
        f"도구 호출 {run.tool_calls}회"
    )
    if run.applied:
        print(
            f"반영 완료: {run.written}건 (winner_pick·winner_name·status·finished_at)"
        )
    else:
        print(
            f"드라이런 — 아무것도 쓰지 않았습니다. "
            f"쓸 예정: {run.writable}건 (쓰려면 --apply)"
        )

    quoted = [m for m in run.matches if m.pick is not None and m.quote]
    if quoted:
        print("\n근거:")
        for match in quoted:
            print(f"  {match.match_key}: {match.quote[:200]}")


async def main(
    *, apply: bool, event_slug: str | None = None, limit: int = DEFAULT_LIMIT
) -> int:
    if AsyncSessionLocal is None:
        print("DATABASE_URL이 비어 있습니다 — 더미 모드에서는 확인할 수 없습니다.")
        return EXIT_NO_DATABASE

    async with AsyncSessionLocal() as session:
        use_case = get_result_verification_use_case(session)
        run = await use_case.verify(
            VerifyResultsCommand(event_slug=event_slug, limit=limit, apply=apply)
        )
        if apply and run.written:
            await session.commit()

    _report(run)
    return 0


def _parse(argv: list[str]) -> tuple[bool, str | None, int] | None:
    apply = False
    event_slug: str | None = None
    limit = DEFAULT_LIMIT

    rest = list(argv)
    while rest:
        arg = rest.pop(0)
        if arg == "--apply":
            apply = True
        elif arg == "--event":
            if not rest:
                return None
            event_slug = rest.pop(0)
        elif arg == "--limit":
            if not rest:
                return None
            try:
                limit = int(rest.pop(0))
            except ValueError:
                return None
            if limit <= 0:
                return None
        else:
            return None
    return apply, event_slug, limit


if __name__ == "__main__":
    parsed = _parse(sys.argv[1:])
    if parsed is None:
        print(
            "사용법: verify_match_results.py [--event <slug>] [--limit <n>] [--apply]"
        )
        raise SystemExit(EXIT_USAGE)

    _apply, _event, _limit = parsed
    raise SystemExit(asyncio.run(main(apply=_apply, event_slug=_event, limit=_limit)))
