"""연승 집계. **한 경기씩 세는 규칙과 기록을 다시 세는 규칙이 같은 함수다.**

엔진은 경기마다 `step` 을 부르고(`career_engine._apply_outcome`), 세이브 업그레이드는
남아 있는 경기 로그를 `replay` 로 다시 센다(`career_world_codec._upgrade_v1_to_v2`).
`replay` 가 `step` 을 접는 것뿐이라 둘이 어긋날 수 없다 — 업그레이드한 세이브와
처음부터 새 코드로 돈 세이브가 같은 값을 갖는 이유다(골든 테스트가 확인한다).

총 경기 수는 여기 없다. `wins + losses` 와 같으므로 `Wrestler.match_count` 가
저장 없이 계산한다.
"""

from __future__ import annotations

from collections.abc import Iterable


def step(*, current: int, best: int, won: bool) -> tuple[int, int]:
    """경기 하나 뒤의 `(현재 연승, 최장 연승)`. 지면 현재 연승이 0이 된다."""
    current = current + 1 if won else 0
    return current, max(best, current)


def replay(results: Iterable[bool]) -> tuple[int, int]:
    """경기 결과를 처음부터 순서대로 다시 센다. 결과가 없으면 `(0, 0)`."""
    current = best = 0
    for won in results:
        current, best = step(current=current, best=best, won=won)
    return current, best
