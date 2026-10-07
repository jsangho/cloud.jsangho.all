"""끝난 대회의 결과 미기록 경기를 위키에서 확인해 `winner_pick`을 채운다.

**이 저장소의 첫 진짜 에이전트를 돌리는 진입점이다.** 무엇이 에이전트인지·왜 이 자리
인지는 `app/use_cases/result_verification_interactor.py`와
`domain/entities/result_verification.py`의 독스트링에 적혀 있다.

## 엔진 둘 — 기본은 모델이 아니다 (2026-10-07)

위키의 결과 절은 산문이 아니라 `{{Pro wrestling results table}}` 템플릿이고 승자가
파라미터 안에 있다(`|match5 = Drew McIntyre (c) defeated Sami Zayn by pinfall`).
그래서 **먼저 정규식으로 읽고**, 못 읽은 경기만 모델에게 넘긴다.

실측(2026년 대회 12개): 83경기 전부가 이 문법을 따랐고, 운영 DB에 이미 확정돼 있던
63건을 **100% 재현**했다(승자 불일치 0). 모델 호출이 경기당 2~6회에서 **0회**로
떨어지므로, 무료 등급의 하루 한도가 더는 처리량의 천장이 아니다.

모델을 지우지 않는 이유는 폴백이 실제로 필요하기 때문이다 — `Results` 절이 없는
문서가 있고(실측: `wrestlepalooza`), 무승부·노컨테스트는 승자를 안 적는다.

    --engine wiki      기본. 위키를 먼저 읽고 못 읽은 것만 모델에게 넘긴다
    --engine gemini    모델만 쓰는 예전 경로. 두 엔진의 답을 견줄 때 쓴다

**어느 엔진이 읽었는지는 보고에 적힌다**(`엔진=위키` · `엔진=모델`). 관문은 둘 다
같다 — 결정론이라고 인용 대조·카드 대조를 건너뛰지 않는다.

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
        apps/kayfabe/scripts/verify_match_results.py \\
        --event money-in-the-bank --limit 5 --apply

**`--event`는 슬러그가 정확히 일치해야 한다**(`slug == event_slug`, ILIKE가 아니다).
줄여 쓰면(`--event mitb`) 조용히 **대상 0건**이 되어 "확정할 게 없다"로 읽힌다 —
슬러그는 `ple_events.slug`에서 확인한다(MITB는 `money-in-the-bank`이고
`match_key`만 `mitb26-*`이다).

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

#: 엔진 둘. **기본은 `wiki`** — 결과 표가 템플릿이라 모델 없이 읽힌다
#: (2026-10-07 실측: 운영 확정값 63건 100% 재현). `gemini`는 모델만 쓰는 예전 경로로,
#: 두 엔진의 답을 견줄 때만 쓴다.
ENGINES = ("wiki", "gemini")
DEFAULT_ENGINE = "wiki"


def _engine_of(match: MatchVerification) -> str:
    """이 경기를 무엇이 읽었나. **모델 호출 0회가 곧 결정론 경로다.**"""
    return "위키" if match.tool_calls == 0 else "모델"


def _line(match: MatchVerification) -> str:
    head = f"  {match.event_slug}/{match.match_key:<18}"
    if match.pick is not None:
        mark = "기록" if match.written else "드라이런"
        return (
            f"{head} {match.winner_name} (pick={match.pick}) "
            f"[{mark}] 엔진={_engine_of(match)} 호출={match.tool_calls} "
            f"출처={match.source_title}@{match.source_revision_id or '판본미상'}"
        )
    return f"{head} 보류({match.hold}) 엔진={_engine_of(match)} 호출={match.tool_calls}"


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
    *,
    apply: bool,
    event_slug: str | None = None,
    limit: int = DEFAULT_LIMIT,
    engine: str = DEFAULT_ENGINE,
) -> int:
    if AsyncSessionLocal is None:
        print("DATABASE_URL이 비어 있습니다 — 더미 모드에서는 확인할 수 없습니다.")
        return EXIT_NO_DATABASE

    async with AsyncSessionLocal() as session:
        use_case = get_result_verification_use_case(
            session, use_wiki_engine=engine == "wiki"
        )
        run = await use_case.verify(
            VerifyResultsCommand(event_slug=event_slug, limit=limit, apply=apply)
        )
        if apply and run.written:
            await session.commit()

    _report(run)
    return 0


def _parse(argv: list[str]) -> tuple[bool, str | None, int, str] | None:
    apply = False
    event_slug: str | None = None
    limit = DEFAULT_LIMIT
    engine = DEFAULT_ENGINE

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
        elif arg == "--engine":
            if not rest:
                return None
            engine = rest.pop(0)
            if engine not in ENGINES:
                return None
        else:
            return None
    return apply, event_slug, limit, engine


if __name__ == "__main__":
    parsed = _parse(sys.argv[1:])
    if parsed is None:
        print(
            "사용법: verify_match_results.py [--event <slug>] [--limit <n>] "
            f"[--engine {'|'.join(ENGINES)}] [--apply]"
        )
        raise SystemExit(EXIT_USAGE)

    _apply, _event, _limit, _engine = parsed
    raise SystemExit(
        asyncio.run(main(apply=_apply, event_slug=_event, limit=_limit, engine=_engine))
    )
