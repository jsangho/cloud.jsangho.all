"""예측이 없는 경기를 찾아 채운다. **타이머가 부르는 입구다.**

## 왜 이 스크립트가 있는가

`generate_ai_predictions.py`는 대회 슬러그를 받아 그 대회를 만든다 — **사람이 어느
대회가 밀렸는지 알고 있어야** 부를 수 있다. 실제로는 몰랐다: 2026-09-29 실측에서
MITB 카드가 5경기인데 예측은 2건이었고(나머지 하나는 사라진 경기를 가리키는 고아),
`mitb26-whc`는 9/22에 카드에 들어왔는데 일주일이 지나도록 예측이 없었다.

대진은 위키에서 자동으로 들어오는데 예측만 사람 손을 기다리면, 새 경기는 조용히
비어 있는다. 이 스크립트가 그 틈을 메운다 — **무엇을 돌릴지 고르는 일만** 하고
생성 자체는 기존 유스케이스에 넘긴다.

## 고르는 규칙 넷

1. **다가오는 대회만.** 지난 대회에 지금 예측을 만들면 결과를 아는 상태에서 만든
   것이라 사후 재현이 된다 — 자격 판정이 `temporal_inversion`으로 실격시킬 표본을
   돈 들여 만드는 셈이다.
2. **예측이 없는 경기만.** 있는 것은 건드리지 않는다(`force`를 쓰지 않는다).
3. **`걸릴 글 없음`인 대회만.** 준비도가 실격·보류 위험을 말하면 건너뛴다. 막힐
   것을 알면서 무료 한도를 태우지 않는다.
4. **하루 상한.** 무료 등급이 모델당 하루 20요청이고 예측 하나가 두 번 부른다.
   기본값은 경기 6개(=12요청)다.

## 기본이 드라이런이다

`--apply` 없이는 무엇을 만들지만 출력한다. 이 저장소의 다른 쓰기 스크립트와 같은
규칙이다.

    cd /app/fastapi && PYTHONUTF8=1 PYTHONPATH=apps:. python \\
        apps/kayfabe/scripts/fill_missing_predictions.py
    ... --apply                # 실제로 만든다
    ... --max-matches 3        # 상한을 좁힌다

**DB가 필요하므로 컨테이너에서 돈다.** 로컬 `.env`의 `DATABASE_URL`은 빈 값이라
여기서는 아무것도 못 한다.

종료 코드: 0 정상(만들 것이 없었던 경우 포함) · 1 생성 실패가 하나라도 있음
"""

from __future__ import annotations

import sys
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402
import logging  # noqa: E402
from datetime import UTC, date, datetime  # noqa: E402

from sqlalchemy import select  # noqa: E402

from core.matrix.grid_oracle_database_manager import AsyncSessionLocal  # noqa: E402
from kayfabe.adapter.outbound.orm.agent_prediction_orm import (  # noqa: E402
    AgentPredictionModel,
)
from kayfabe.adapter.outbound.orm.ple_orm import (  # noqa: E402
    PleEventModel,
    PleMatchModel,
)
from kayfabe.adapter.outbound.pg.agent_prediction_pg_repository import (  # noqa: E402
    AgentPredictionPgRepository,
)
from kayfabe.adapter.outbound.pg.ai_lab_pg_repository import (  # noqa: E402
    AiLabPgRepository,
)
from kayfabe.adapter.outbound.repositories.prediction_knowledge_repository import (  # noqa: E402
    PredictionKnowledgeRepository,
)
from kayfabe.app.dtos.agent_prediction_dto import (  # noqa: E402
    GeneratePredictionCommand,
)
from kayfabe.app.services.ai_lab_readiness import RISK_CLEAR  # noqa: E402
from kayfabe.app.use_cases.ai_lab_interactor import AiLabInteractor  # noqa: E402
from kayfabe.dependencies.ai_prediction_provider import (  # noqa: E402
    get_ai_prediction_use_case,
)
from ontology.dependencies.gemini_generation_provider import (  # noqa: E402
    get_gemini_generation_use_case,
)

#: 한 번에 만들 경기 수 상한. 예측 하나가 모델을 두 번 부르고 무료 등급이 모델당
#: 하루 20요청이라, 여섯이면 12요청으로 여유가 남는다.
DEFAULT_MAX_MATCHES = 6

# 준비도가 `RISK_CLEAR`일 때만 만든다. 나머지(`hold_risk`·`disqualify_risk`)는 막힐
# 것이 예고된 대회다. **상수를 여기서 다시 적지 않는다** — 판정하는 쪽의 것을 쓴다.


async def _missing_by_event(session, *, today: date) -> dict[str, list[str]]:
    """다가오는 대회별로 **예측이 없는** `match_key`들. 순서는 DB 순이다.

    고아 예측(경기가 사라졌는데 예측만 남은 것)은 여기 안 걸린다 — 경기 쪽에서
    시작해서 예측을 붙여 보기 때문이다. 그게 맞는 방향이다: 우리가 채우려는 것은
    **경기에 붙을 예측**이지 예측에 붙을 경기가 아니다.
    """
    rows = await session.execute(
        select(PleEventModel.slug, PleMatchModel.match_key)
        .join(PleMatchModel, PleMatchModel.event_id == PleEventModel.id)
        .outerjoin(
            AgentPredictionModel,
            (AgentPredictionModel.event_id == PleEventModel.id)
            & (AgentPredictionModel.match_key == PleMatchModel.match_key),
        )
        .where(
            AgentPredictionModel.id.is_(None),
            PleEventModel.start_date.is_not(None),
            PleEventModel.start_date >= today,
        )
        .order_by(PleEventModel.start_date, PleEventModel.slug, PleMatchModel.id)
    )
    missing: dict[str, list[str]] = {}
    for slug, match_key in rows.all():
        missing.setdefault(slug, []).append(match_key)
    return missing


async def _clear_events(session) -> tuple[set[str], dict[str, str]]:
    """준비도가 `걸릴 글 없음`인 대회들과, 그렇지 않은 대회의 사유.

    **화면과 같은 판정을 쓴다** — `/ai-lab/readiness`가 부르는 유스케이스 그대로다.
    여기서 따로 세면 화면이 "깨끗하다"고 말하는 대회를 스크립트가 건너뛰거나 그
    반대가 되고, 그때 아무도 어느 쪽이 맞는지 모른다.
    """
    # `Depends` 팩토리(`dependencies/ai_lab_provider.py`)는 요청 안에서만 쓸 수 있어
    # 손으로 조립한다 — 라우터가 얻는 것과 같은 객체다.
    interactor = AiLabInteractor(repository=AiLabPgRepository(db=session))
    readiness = await interactor.get_readiness()
    clear: set[str] = set()
    blocked: dict[str, str] = {}
    for item in readiness.events:
        if item.risk == RISK_CLEAR:
            clear.add(item.slug)
        else:
            blocked[item.slug] = item.risk
    return clear, blocked


async def main(*, apply: bool, max_matches: int) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    today = datetime.now(UTC).date()

    async with AsyncSessionLocal() as session:
        missing = await _missing_by_event(session, today=today)
        if not missing:
            print("예측이 빠진 경기가 없다 — 할 일 없음")
            return 0

        clear, blocked = await _clear_events(session)

        planned: list[tuple[str, list[str]]] = []
        budget = max_matches
        for slug, keys in missing.items():
            if slug in blocked:
                print(
                    f"{slug:22} 건너뜀 — 준비도 {blocked[slug]} ({len(keys)}경기 대기)"
                )
                continue
            if slug not in clear:
                # 준비도가 아예 모르는 대회다(날짜가 없거나 목록에 없다).
                print(f"{slug:22} 건너뜀 — 준비도가 모르는 대회 ({len(keys)}경기 대기)")
                continue
            if budget <= 0:
                print(
                    f"{slug:22} 다음으로 미룸 — 오늘 상한 도달 ({len(keys)}경기 대기)"
                )
                continue
            take = keys[:budget]
            budget -= len(take)
            planned.append((slug, take))
            left = len(keys) - len(take)
            tail = f" (남은 {left}경기는 다음 실행)" if left else ""
            print(f"{slug:22} {len(take)}경기: {', '.join(take)}{tail}")

        if not planned:
            print("만들 대상이 없다")
            return 0

        total = sum(len(keys) for _, keys in planned)
        print(
            f"\n합계 {total}경기 · 예상 모델 호출 {total * 2}회 (상한 {max_matches}경기)"
        )

        if not apply:
            print("드라이런이다 — 만들지 않았다. 실제로 만들려면 --apply")
            return 0

        use_case = get_ai_prediction_use_case(
            AgentPredictionPgRepository(db=session),
            PredictionKnowledgeRepository(session),
            get_gemini_generation_use_case(),
        )
        generated = failed = 0
        for slug, keys in planned:
            summary = await use_case.generate(
                GeneratePredictionCommand(
                    event_slug=slug, match_keys=tuple(keys), force=False
                )
            )
            generated += summary.generated
            failed += summary.failed
            print(
                f"{slug:22} 생성 {summary.generated} · 건너뜀 {summary.skipped} "
                f"· 실패 {summary.failed}"
            )
        # 유스케이스는 flush까지만 한다 — 커밋 시점은 부르는 쪽이 정한다.
        await session.commit()

    print(f"\n생성 {generated} · 실패 {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    apply_flag = "--apply" in args
    limit = DEFAULT_MAX_MATCHES
    if "--max-matches" in args:
        position = args.index("--max-matches")
        if position + 1 >= len(args):
            print("--max-matches 뒤에 숫자가 필요하다")
            raise SystemExit(2)
        limit = int(args[position + 1])
        args = args[:position] + args[position + 2 :]
    unknown = set(args) - {"--apply"}
    if unknown:
        print(f"모르는 인자: {' '.join(sorted(unknown))}")
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(apply=apply_flag, max_matches=limit)))
