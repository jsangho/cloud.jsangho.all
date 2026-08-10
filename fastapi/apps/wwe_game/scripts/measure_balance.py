"""밸런스 측정기 — 정책 4종으로 커리어를 돌려 지표를 잰다 (하네스 §13-Q13).

```
cd fastapi && PYTHONPATH=apps uv run python apps/wwe_game/scripts/measure_balance.py 25
```

**같은 방식으로 재야 비교가 된다.** 이 스크립트를 저장소에 두는 이유가 그것이다 —
문서의 수치(§3-D20-2·D-21-1·D-24)를 고칠 때마다 임시로 만들어 쓰면 정책 정의가 조금씩
달라져 "좋아졌다"가 측정 방식의 차이인지 규칙의 차이인지 알 수 없다.

정책 넷은 **극단을 잡는 자**다. 사람은 이렇게 안 놀지만, 규칙이 한쪽으로 무너지면
어느 극단이 먼저 무너지는지가 드러난다 — 인기도 포화를 찾아낸 것도 `pop`과 `safe`가
같은 값에 붙는 것을 보고서였다.

| 정책 | 고르는 법 |
|---|---|
| `safe` | 부상 위험이 가장 낮은 선택지 |
| `calc` | 인기도 + 경기력×0.5 − 위험×40 이 최대인 선택지 |
| `pop` | 인기도가 최대인 선택지 |
| `random` | 무작위 |

**시드는 고정이다**(5000부터). 규칙만 바꿔 다시 돌리면 같은 커리어가 어떻게 달라졌는지
바로 보인다.
"""

from __future__ import annotations

import random
import statistics
import sys
from collections import Counter

from wwe_game.domain.constants.countries import Country
from wwe_game.domain.constants.event_deck import BY_CODE, EventCard
from wwe_game.domain.entities.career_run import CareerRun, start_run
from wwe_game.domain.services import career_end, championship, event_draw
from wwe_game.domain.services.week_simulation import apply_week, simulate_week
from wwe_game.domain.value_objects.game_mode import game_mode_of
from wwe_game.domain.value_objects.wrestler_identity import (
    Gender,
    PlayStyle,
    RingName,
    WrestlerIdentity,
)

STYLES = list(PlayStyle)
CAREER_WEEKS = 1560
FIRST_SEED = 5000
POLICIES = ("safe", "calc", "pop", "random")


def _popularity(choice: object) -> int:
    return dict(choice.effects).get("popularity", 0)  # type: ignore[attr-defined]


def _worth(choice: object) -> float:
    effects = dict(choice.effects)  # type: ignore[attr-defined]
    return (
        effects.get("popularity", 0)
        + effects.get("inRing", 0) * 0.5
        - choice.injury_risk * 40  # type: ignore[attr-defined]
    )


def choose(card: EventCard, policy: str, rng: random.Random) -> str:
    if policy == "safe":
        return min(card.choices, key=lambda c: c.injury_risk).code
    if policy == "pop":
        return max(card.choices, key=_popularity).code
    if policy == "calc":
        return max(card.choices, key=_worth).code
    return rng.choice(card.choices).code


def run_one(seed: int, policy: str) -> tuple[CareerRun, int]:
    """커리어 하나를 끝까지. (마지막 상태, 부상 횟수)."""
    rng = random.Random(seed)
    identity = WrestlerIdentity(
        name=RingName("장상호"),
        gender=Gender.MALE,
        country=Country.KR,
        play_style=STYLES[seed % len(STYLES)],
    )
    run = start_run(
        identity=identity, mode=game_mode_of("weekly"), seed=seed, user_id=1
    )
    injuries = 0
    while run.is_active and run.week < CAREER_WEEKS:
        if run.is_blocked:
            card = BY_CODE[run.pending_event.code]  # type: ignore[union-attr]
            run = event_draw.resolve_choice(run, choose(card, policy, rng))
            run = career_end.close_if_ended(run)
            continue
        report = simulate_week(run)
        if report.injury is not None:
            injuries += 1
        run = apply_week(run, report)
        # **누적기를 빼먹으면 안 된다.** `career_advance.advance()`가 하는 일을 그대로
        # 따라 한다 — 이걸 건너뛰면 방출·부진이 영영 0건으로 나와 "은퇴 조건이
        # 죽었다"는 잘못된 결론이 난다 (2026-08-10 실제로 그렇게 오진했다).
        run = career_end.track_decline(career_end.track_release(run))
        run = career_end.close_if_ended(run)
    return run, injuries


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    ends: Counter[str] = Counter()
    for policy in POLICIES:
        rows = [run_one(s, policy) for s in range(FIRST_SEED, FIRST_SEED + count)]
        for run, _ in rows:
            ends[run.end_reason.value if run.end_reason else "?"] += 1
        runs = [run for run, _ in rows]
        slams = sum(
            1
            for r in runs
            if championship.grand_slam_level(r.titles_won, r.identity.gender) > 0
        )
        finished = sum(1 for r in runs if r.week >= CAREER_WEEKS - 5)
        print(
            f"{policy:<7}"
            f" 인기 {statistics.mean(r.stats.popularity for r in runs):5.1f}"
            f" · 경기력 {statistics.mean(r.stats.in_ring for r in runs):5.1f}"
            f" · 평판 {statistics.mean(r.stats.backstage for r in runs):5.1f}"
            f" · 대관 {statistics.mean(len(r.titles_won) for r in runs):4.1f}"
            f" · GS {slams / len(runs) * 100:3.0f}%"
            f" · 부상 {statistics.mean(i for _, i in rows):4.1f}"
            f" · 커리어 {statistics.mean(r.week / 52 for r in runs):4.1f}년"
            f" · 완주 {finished / len(runs) * 100:3.0f}%"
        )
    print("종료 사유:", dict(ends))
    return 0


if __name__ == "__main__":
    sys.exit(main())
