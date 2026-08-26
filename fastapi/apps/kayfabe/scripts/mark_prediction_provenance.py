"""예측 표본의 계보를 선언한다 (Phase 3-7).

**시간 컬럼으로는 말할 수 없는 것을 사람이 적는 자리다.** `ple_matches.finished_at`은
결과가 **DB에 기록된** 시각이라, 이미 끝난 경기를 나중에 예측하고 결과를 그 뒤에
입력하면 시간 규칙(`temporal_inversion`)을 통과해 버린다. 규칙이 틀린 게 아니라
시스템 밖의 앎을 볼 수 없을 뿐이다.

**HTTP가 아니라 스크립트인 이유:** 이 선언은 운영 중 반복되는 동작이 아니라 사람이
근거를 갖고 한 번 남기는 기록이다. 관리자 엔드포인트를 열면 화면에서 눌러 바꿀 수
있게 되는데, 그러면 "누가 왜 선언했는가"가 흐려진다.

**`--force` 재생성을 하면 선언이 사라진다.** `AgentPredictionPgRepository.save()`가
기존 행을 지우고 다시 넣기 때문이다(Phase 3-7에서 감수한 트레이드오프). 예측을 다시
만들었다면 **이 스크립트를 다시 돌려야 한다.**

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run python \\
        apps/kayfabe/scripts/mark_prediction_provenance.py --dry-run bad-blood bb26-cell ...

`--dry-run`이 기본 안전장치는 아니다 — 붙이지 않으면 실제로 쓴다. 대신 쓰기 전에
대상 행을 전부 출력하고, 대상이 예상과 다르면 아무것도 쓰지 않고 멈춘다.
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402
from sqlalchemy import select  # noqa: E402

from kayfabe.adapter.outbound.orm.agent_prediction_orm import (  # noqa: E402
    AgentPredictionModel,
)
from kayfabe.adapter.outbound.orm.ple_orm import (  # noqa: E402
    PleEventModel,
    PleMatchModel,
)

#: 이 문장 외의 사실을 넣지 않는다. 추정한 경기 날짜도 승자도 여기 오지 않는다.
EX_POST_NOTE = (
    "Historical/ex-post sample. Match had already occurred before prediction "
    "generation; actual match completion time is not stored in the current schema. "
    "Do not treat as genuinely ex-ante."
)


async def main(slug: str, match_keys: tuple[str, ...], *, dry_run: bool) -> int:
    if not match_keys:
        print(
            "경기 키를 하나 이상 지정해야 합니다. 전체 일괄 선언은 지원하지 않습니다."
        )
        return 2

    async with AsyncSessionLocal() as session:
        event = await session.scalar(
            select(PleEventModel).where(PleEventModel.slug == slug)
        )
        if event is None:
            print(f"이벤트를 찾을 수 없습니다: {slug}")
            return 2

        rows = (
            await session.scalars(
                select(AgentPredictionModel)
                .where(
                    AgentPredictionModel.event_id == event.id,
                    AgentPredictionModel.match_key.in_(match_keys),
                )
                .order_by(AgentPredictionModel.id)
            )
        ).all()

        found = {row.match_key for row in rows}
        missing = [key for key in match_keys if key not in found]
        if missing:
            # 일부만 선언하면 표본이 반쪽이 된다. 하나라도 없으면 아무것도 쓰지 않는다.
            print(f"예측을 찾을 수 없는 경기가 있습니다: {missing}")
            return 1

        # 경기 쪽 결과 컬럼도 함께 찍는다. **이 스크립트는 그 값을 쓰지 않지만**,
        # 쓰지 않았다는 것을 눈으로 확인할 수 있어야 한다.
        matches = {
            m.match_key: m
            for m in (
                await session.scalars(
                    select(PleMatchModel).where(
                        PleMatchModel.event_id == event.id,
                        PleMatchModel.match_key.in_(match_keys),
                    )
                )
            ).all()
        }

        print(f"대상 {len(rows)}건 ({slug}):")
        for row in rows:
            match = matches.get(row.match_key)
            print(
                f"  {row.match_key:<22} generated_at={row.generated_at.isoformat()}"
                f"\n      현재 outcome_known_externally={row.outcome_known_externally!r}"
                f" provenance_note={row.provenance_note!r}"
                f"\n      경기: winner_pick={match.winner_pick!r}"
                f" winner_name={match.winner_name!r}"
                f" finished_at={match.finished_at!r}"
                f" status={match.status!r}"
                if match is not None
                else f"  {row.match_key:<22} (경기 행 없음)"
            )

        if dry_run:
            print("\n--dry-run — 아무것도 쓰지 않았습니다.")
            return 0

        for row in rows:
            row.outcome_known_externally = True
            row.provenance_note = EX_POST_NOTE

        await session.commit()

    print(f"\n선언 완료: {len(rows)}건에 outcome_known_externally=True")
    # 결과 컬럼은 건드리지 않는다 — 선언과 결과 입력은 다른 단계다.
    print("winner_pick·winner_name·finished_at은 건드리지 않았습니다.")
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    dry_run = "--dry-run" in argv
    args = [a for a in argv if a != "--dry-run"]
    if not args:
        print(
            "사용법: mark_prediction_provenance.py <slug> <match_key ...> [--dry-run]"
        )
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(args[0], tuple(args[1:]), dry_run=dry_run)))
