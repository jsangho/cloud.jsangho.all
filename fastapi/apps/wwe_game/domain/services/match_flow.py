"""모멘텀 타임라인 — 매치를 보이게 (하네스 §3-D81).

2026-08-13에 설계만 해 두고 *"구현은 §3-D80 다음"*으로 남긴 자리다.

## 2D 링을 만들지 않는 이유

레퍼런스(K리그 매니저)의 2D 필드는 **위치가 곧 정보**라서 성립한다 — 축구는 스물두
명의 좌표가 그 순간의 상황 전부다. **레슬링은 위치가 정보가 아니다.** 두 사람이 링
한가운데 있고, 좌표를 그려 봐야 점 두 개가 오가는 화면이 된다.

그 자리를 대신하는 것이 **흐름(누가 우세한가)과 스팟(무슨 기술이 나왔나)**이고,
그래서 필드가 아니라 모멘텀 타임라인이다.

## 판정을 만들지 않는다 · 되짚는다

**승패는 이미 정해진 뒤에 이 줄이 그려진다.** `won`을 받아서 그 결말로 수렴하는
흐름을 세울 뿐이다 — 흐름이 승패를 정하면 같은 시드가 다른 결과를 내고, §3-D4(되짚기가
결정적)가 그 자리에서 깨진다.

저장도 하지 않는다. §3-D34가 *"럼블 하나가 59비트라 전부 담으면 커리어당 2천 줄"*
이라며 `summary`만 저장하고 비트는 **진행 중 응답에만** 실은 것과 같은 패턴이다.

## 단계 있는 경기와 나눠 둔다

럼블·챔버는 `elimination`이 이미 입장·탈락으로 세운다(§3-D34). 여기는 **그 밖의 전부**,
곧 1:1과 소규모 경기다 — 22,398경기 중 90.6%가 여기 해당한다.
"""

from __future__ import annotations

from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.match_kind import MatchKind, format_of
from wwe_game.domain.value_objects.match_sequence import (
    BeatKind,
    MatchBeat,
    MatchSequence,
)

OPENING_MOMENTUM = 50
"""공이 울린 순간의 흐름. 팽팽하다."""

MOMENTUM_MIN = 5
MOMENTUM_MAX = 95
"""흐름의 상·하한. **0과 100을 쓰지 않는다** — 완전히 한쪽이면 그 뒤가 없고, 실제
경기도 마지막 순간까지 반대편이 한 번은 일어선다."""

MOVE_SWING = 9
"""기술 하나가 옮기는 흐름의 폭."""
REVERSAL_SWING = 18
"""받아넘김이 옮기는 폭 — 기술의 두 배다. **뒤집히는 자리라서 크다.**"""
NEARFALL_SWING = 13

BEATS_TV = 7
BEATS_MAJOR = 13
"""그 밤의 길이. 대형 대회가 두 배쯤 길다 — 20분 경기와 5분 경기의 차이가 여기다."""

NEARFALL_AT = 0.62
"""이 지점을 지나면 니어폴이 섞이기 시작한다. 경기 후반이라는 뜻이다."""

MOMENTUM_PULL = 0.5
"""흐름이 **다음 한 수를 누가 낼지에 미치는 힘**.

**1.0으로 두었더니 경기가 일방적이 됐다** (2026-08-14 실측): 흐름을 그대로 확률로
쓰면 95까지 오른 쪽이 95%로 계속 이기고, 한 번 기운 경기는 끝까지 한 사람이 다 한다.
16비트 전부가 한 이름으로 찬 출력이 나왔다.

0.5면 95에서도 상대가 넷에 한 번은 일어선다 — **주고받는 것이 경기다.**
"""

MEAN_REVERSION = 0.18
"""매 비트 흐름이 팽팽함(50)으로 되끌리는 비율.

되먹임만 있으면 흐름이 한쪽 끝에 박혀 그 뒤가 없다. 실제 경기도 몰린 쪽이 숨을
고르고 돌아온다 — **이 값이 그 숨이다.**
"""


def _clamp(value: int) -> int:
    return max(MOMENTUM_MIN, min(MOMENTUM_MAX, value))


def _edge(momentum: int) -> float:
    """흐름이 기운 쪽이 다음 수를 낼 확률. **흐름을 그대로 쓰지 않는다.**

    그대로 쓰면(`momentum / 100`) 95까지 오른 쪽이 95%로 계속 이겨 경기가 한 사람의
    것이 된다 — 실측에서 16비트가 전부 한 이름이었다. `MOMENTUM_PULL`이 그 힘을
    반으로 줄여, 몰린 쪽도 넷에 한 번은 일어선다.
    """
    return 0.5 + (momentum - OPENING_MOMENTUM) / 100 * MOMENTUM_PULL


def beat_count(kind: MatchKind, *, major: bool) -> int:
    """그 경기의 비트 수. 여럿이 붙는 경기는 조금 더 길다."""
    base = BEATS_MAJOR if major else BEATS_TV
    return base + (2 if format_of(kind).field > 2 else 0)


def sequence_for(
    kind: MatchKind,
    *,
    player: str,
    opponent: str,
    won: bool,
    finisher: str,
    major: bool,
    roll: SeededRoll,
) -> MatchSequence:
    """1:1(과 소규모) 경기의 흐름 (§3-D81).

    **결말로 수렴한다.** 마지막 비트는 이긴 쪽의 피니셔이고, 그 앞의 흐름은 그
    결말이 그럴듯해 보이도록 흔들린다 — 판정이 아니라 **판정을 읽는 방식**이다.

    `finisher`는 §3-D88이 정한 내 기술의 이름이다. **진 밤에는 안 쓴다** — 못 끝낸
    밤에 그 이름이 나오면 고른 것의 뜻이 사라진다.
    """
    total = beat_count(kind, major=major)
    beats: list[MatchBeat] = []
    momentum = OPENING_MOMENTUM
    nearfalls = 0

    for index in range(total - 1):
        # **팽팽함으로 되끌린다.** 안 그러면 흐름이 한쪽 끝에 박혀 그 뒤가 없다.
        momentum = _clamp(
            round(momentum + (OPENING_MOMENTUM - momentum) * MEAN_REVERSION)
        )
        late = index / max(1, total - 1) >= NEARFALL_AT
        # **후반에만 니어폴이 나온다.** 첫 1분에 투 카운트가 나오는 경기는 없다.
        if late and roll.chance(0.45):
            mine = roll.chance(_edge(momentum))
            momentum = _clamp(momentum + (NEARFALL_SWING if mine else -NEARFALL_SWING))
            beats.append(
                MatchBeat(
                    kind=BeatKind.NEARFALL,
                    name=player if mine else opponent,
                    momentum=momentum,
                )
            )
            beats.append(
                MatchBeat(
                    kind=BeatKind.KICKOUT,
                    name=opponent if mine else player,
                    momentum=momentum,
                )
            )
            nearfalls += 1
            continue
        # 흐름이 기운 쪽이 다음 수를 낼 확률이 높다 — 다만 뒤집기가 늘 남아 있다.
        mine = roll.chance(_edge(momentum))
        reversal = roll.chance(0.24)
        swing = REVERSAL_SWING if reversal else MOVE_SWING
        momentum = _clamp(momentum + (swing if mine else -swing))
        beats.append(
            MatchBeat(
                kind=BeatKind.REVERSAL if reversal else BeatKind.MOVE,
                name=player if mine else opponent,
                momentum=momentum,
            )
        )

    winner = player if won else opponent
    momentum = MOMENTUM_MAX if won else MOMENTUM_MIN
    beats.append(
        MatchBeat(
            kind=BeatKind.FINISHER,
            name=winner,
            # **내 피니셔는 내가 이겼을 때만 이름을 갖는다** (§3-D88).
            by=finisher if won else None,
            momentum=momentum,
        )
    )
    beats.append(MatchBeat(kind=BeatKind.WIN, name=winner, momentum=momentum))

    return MatchSequence(
        beats=tuple(beats),
        summary=_summary(opponent, won=won, nearfalls=nearfalls),
        entry_number=0,
        place=1 if won else 2,
        field=format_of(kind).field,
        eliminated_by_player=0,
    )


def _summary(opponent: str, *, won: bool, nearfalls: int) -> str:
    """세이브에 남는 한 줄. **비트는 안 남는다** — 다시 열 때 되짚는다(§3-D34).

    니어폴 수를 넣는 이유: 별점이 왜 그 별점인지를 읽는 근거가 된다(§3-D56). 그 밤을
    다시 열었을 때 남아 있는 유일한 단서이기도 하다.
    """
    tail = f" · 니어폴 {nearfalls}회" if nearfalls else ""
    return f"{opponent} 상대로 {'승리' if won else '패배'}{tail}"
