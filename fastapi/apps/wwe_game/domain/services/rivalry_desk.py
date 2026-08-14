"""시비를 건다 — 상대를 내가 고른다 (하네스 §3-D86).

서른 해 동안 **누구와 싸울지 한 번도 못 골랐다.** `rivalry_engine.pick_rival`이
급과 브랜드가 맞는 명부에서 주사위로 뽑았고, 프로레슬링에서 가장 사람 냄새 나는
축이 통째로 자동이었다.

## 왜 이건 밸런스를 안 건드리는가

§3-D20-3(그랜드슬램 추격)을 플레이어에게 주면 달성률이 무너진다 — 그 확률이
등급을 직접 정하기 때문이다. 대립은 다르다. **대립은 스탯을 주지 않는다**:

* 상대를 정한다 (`pick_opponent`)
* 대립 단계로 열리는 이벤트 카드의 조건을 채운다 — 다만 **이벤트 예산은 그대로**라
  (§3-D5) 대립을 걸어도 사건 수가 늘지 않는다. 어떤 카드가 뜨는지가 바뀔 뿐이다
* 별점에 `FEUD_BONUS`가 붙는데, 별점은 **판정에 닿지 않는다** (§3-D56)

그래서 여기서 고르는 것은 **이야기의 방향**이지 성장의 양이 아니다.

## 급을 넘겨 고를 수는 없다

후보는 `rivalry_engine.candidate_pool` — 규칙이 뽑을 때 쓰는 것과 **같은 풀**이다.
루키가 메인이벤터에게 시비를 걸 수 없는 이유가 §3-D53과 같다: 브랜드와 급이 그림을
정하고, 그걸 넘기면 브랜드가 있다는 사실 자체가 화면에서 사라진다.

## 자리는 여전히 둘이다

`MAX_ACTIVE`를 넘겨 열 수 없다. **그것이 이 행동의 값이다** — 내가 고른 상대가
자리를 하나 먹으므로, 규칙이 데려왔을 다른 이야기는 그만큼 안 온다. 따로 비용을
붙이지 않는 이유가 그것이다(§13-Q13의 "돈이 스탯을 사면 안 된다"와도 무관해진다).

## 멈추지 않는다

§3-D85와 같은 **상시 행동**이다. 안 걸고 '다음'을 눌러도 되고, `StopReason`을
더하지 않는다.
"""

from __future__ import annotations

from wwe_game.domain.entities.career_run import CareerRun, RivalryOrigin
from wwe_game.domain.exceptions import CannotCallOutError
from wwe_game.domain.services import rivalry_engine, seeded_roll
from wwe_game.domain.services.seeded_roll import SeededRoll

MAX_CANDIDATES = 3
"""화면에 세우는 후보 수.

**전부 보여 주지 않는다.** 명부의 그 급 전체를 늘어놓으면 고르는 것이 아니라 검색이
된다 — 셋이면 "이 중 누구"가 되고, 그 셋이 주차마다 바뀌므로 미루는 것도 선택이 된다.
"""


def can_call_out(run: CareerRun) -> bool:
    """지금 시비를 걸 수 있는가. 자리가 없거나 상대가 없으면 거짓."""
    return (
        run.is_active
        and len(run.rivalries) < rivalry_engine.MAX_ACTIVE
        and bool(rivalry_engine.candidate_pool(run))
    )


def candidates(run: CareerRun) -> tuple[str, ...]:
    """지금 걸 수 있는 상대들 — 최대 `MAX_CANDIDATES`명.

    **세이브를 다시 열어도 같은 목록이다** (§3-D4). 시드와 주차로만 정해지므로
    새로고침해서 다른 후보를 뽑는 일이 생기지 않는다 — 그러면 목록을 다시 굴리는
    것이 최적 플레이가 된다.
    """
    pool = rivalry_engine.candidate_pool(run)
    if not pool or not can_call_out(run):
        return ()
    roll = SeededRoll(run.seed, run.week, seeded_roll.CALL_OUT)
    picked: list[str] = []
    remaining = list(pool)
    while remaining and len(picked) < MAX_CANDIDATES:
        chosen = roll.pick(tuple(remaining))
        picked.append(chosen)
        remaining.remove(chosen)
    return tuple(picked)


def call_out(run: CareerRun, name: str) -> CareerRun:
    """그 사람에게 시비를 건다 (§3-D86).

    **목록 밖의 이름은 거절한다.** 안 막으면 요청을 손봐 아무 이름이나 넣을 수 있고,
    그러면 급·브랜드 그림이 요청 한 줄로 무너진다(§3-D53). 체험판은 세이브를 통째로
    들고 다니므로(§3-D8) 이 검사가 특히 필요하다.
    """
    if not can_call_out(run):
        raise CannotCallOutError("지금은 시비를 걸 수 없습니다.")
    if name not in candidates(run):
        raise CannotCallOutError(f"지금 걸 수 있는 상대가 아닙니다: {name}")
    fresh = rivalry_engine.open_with(name, run.week, by=RivalryOrigin.PLAYER)
    return run.evolve(rivalries=(*run.rivalries, fresh))
