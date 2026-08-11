"""탈락 경기의 진행을 짠다 (하네스 §3-D34).

**판정은 이미 끝났다.** 승패는 `win_chance(score) × fmt.win_factor`가 정했고(§3-D32),
이 모듈은 그 결과와 **어긋나지 않는 순서**를 짤 뿐이다 — 이긴 밤이면 마지막까지
남고, 진 밤이면 어딘가에서 떨어진다. 판정과 서술을 한 덩어리로 쓰지 않는다는
§2-D8이 여기서도 그대로다: 이 함수를 통째로 바꿔도 승률은 1도 안 움직인다.

## 아직 들어오지도 않은 사람을 떨어뜨릴 수 없다

이 모듈의 유일한 어려움이다. 입장은 순차적인데 탈락은 링에 있는 사람 중에서만
일어난다.

**탈락 순서를 큐로 먼저 정하고, 리듬은 토큰이 잡는다.** 큐의 다음 사람이 아직 안
들어왔으면 입장을 당겨서 맞춘다 — 그래서 사라지는 탈락이 없다. 매 탈락마다 링에서
무작위로 고르는 방식을 먼저 썼다가 **생존자가 둘이 되는 것을 테스트가 잡았다**:
우승자와 플레이어만 남은 순간에는 고를 사람이 없어 그 탈락이 통째로 증발한다.

내 탈락 순번은 그 위에서 한 번 더 좁힌다 — 입장 슬롯까지 토큰이 만든 탈락 수보다
뒤에서만 고른다. 이건 정합성이 아니라 **그럴듯함** 때문이다: 28번으로 들어와서
첫 번째로 탈락하는 밤은 모순은 아니지만 럼블처럼 보이지 않는다.
"""

from __future__ import annotations

from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.match_kind import MatchKind, format_of
from wwe_game.domain.value_objects.match_sequence import (
    BeatKind,
    MatchBeat,
    MatchSequence,
)

ELIMINATES: frozenset[MatchKind] = frozenset(
    {MatchKind.BATTLE_ROYAL, MatchKind.CHAMBER, MatchKind.GAUNTLET}
)
"""탈락으로 줄어드는 경기."""

ENTRY_ONLY: frozenset[MatchKind] = frozenset({MatchKind.WARGAMES})
"""차례로 들어오지만 탈락은 없는 경기 — 워게임즈는 핀폴 하나로 끝난다."""

STAGED: frozenset[MatchKind] = ELIMINATES | ENTRY_ONLY

OPENING_FIELD = 2
"""몇 명으로 시작하는가. 럼블 1·2번, 챔버의 링 안 둘, 가운틀릿의 첫 두 명."""

ENTRY_BIAS = 0.62
"""다음 한 수가 입장일 확률(탈락 대신).

**1.0에 가까우면 전원이 들어온 뒤에야 탈락이 시작되고, 0.5면 링에 늘 둘만 남는다.**
0.62는 링이 열 명 안팎까지 차올랐다가 후반에 빠지는 모양을 만든다 — 실제 럼블의
리듬이고, 무엇보다 **탈락시킬 사람을 고를 여지**가 생긴다(링이 둘뿐이면 우승자와
플레이어를 빼고 나면 고를 사람이 없다).
"""


def sequence_for(
    kind: MatchKind,
    *,
    player: str,
    won: bool,
    pool: tuple[str, ...],
    roll: SeededRoll,
) -> MatchSequence | None:
    """그 경기의 진행 순서. 단계가 없는 형식이면 None.

    `pool`은 플레이어를 뺀 출전 후보다. 모자라면 있는 만큼만 세운다 — 명부가 얇은
    시점(30년 차 여성부 등)에 30인 럼블을 못 연다고 멈추는 것보다 낫다.
    """
    if kind not in STAGED:
        return None
    size = min(format_of(kind).field, len(pool) + 1)
    if size < OPENING_FIELD + 1:
        return None

    others = _draw(pool, size - 1, roll)
    entry_order = _entry_order(player, others, roll)
    player_slot = entry_order.index(player)

    if kind in ENTRY_ONLY:
        return _entries_only(entry_order, player, won, size, roll)

    winner = player if won else _winner_among(others, roll)
    tokens = _tokens(size, roll)
    before = _eliminations_before(tokens, player_slot)
    # 내가 나가는 순번. 이긴 판은 마지막까지 남으므로 해당 없음.
    player_out = 0 if won else roll.between(before + 1, size - 1)
    return _play(
        tokens,
        entry_order=entry_order,
        player=player,
        winner=winner,
        player_out=player_out,
        size=size,
        roll=roll,
    )


def _draw(pool: tuple[str, ...], count: int, roll: SeededRoll) -> tuple[str, ...]:
    """중복 없이 `count`명. **같은 사람이 두 번 입장하면 안 된다.**"""
    remaining = list(pool)
    drawn: list[str] = []
    for _ in range(count):
        if not remaining:
            break
        drawn.append(remaining.pop(roll.between(0, len(remaining) - 1)))
    return tuple(drawn)


def _entry_order(
    player: str, others: tuple[str, ...], roll: SeededRoll
) -> tuple[str, ...]:
    order = list(others)
    order.insert(roll.between(0, len(order)), player)
    return tuple(order)


def _winner_among(others: tuple[str, ...], roll: SeededRoll) -> str:
    return roll.pick(others)


def _tokens(size: int, roll: SeededRoll) -> tuple[bool, ...]:
    """진행의 뼈대. `True`가 입장, `False`가 탈락이다.

    링에 둘은 있어야 누가 누구를 떨어뜨린다 — 그 조건을 여기서 지키면 뒤에서
    다시 확인할 필요가 없다.
    """
    tokens: list[bool] = []
    entered = ring = 0
    outs = 0
    while entered < size or outs < size - 1:
        if entered < size and (ring < OPENING_FIELD or roll.chance(ENTRY_BIAS)):
            tokens.append(True)
            entered += 1
            ring += 1
            continue
        tokens.append(False)
        outs += 1
        ring -= 1
    return tuple(tokens)


def _eliminations_before(tokens: tuple[bool, ...], slot: int) -> int:
    """`slot`번째 사람이 들어오기 전까지 일어난 탈락 수."""
    entered = outs = 0
    for is_entry in tokens:
        if is_entry:
            if entered == slot:
                return outs
            entered += 1
        else:
            outs += 1
    return outs


def _entries_only(
    entry_order: tuple[str, ...],
    player: str,
    won: bool,
    size: int,
    roll: SeededRoll,
) -> MatchSequence:
    """워게임즈 — 차례로 들어오고 마지막에 한 번 결판난다."""
    beats = [
        MatchBeat(kind=BeatKind.ENTER, name=name, number=i + 1)
        for i, name in enumerate(entry_order)
    ]
    winner = player if won else roll.pick(tuple(n for n in entry_order if n != player))
    beats.append(MatchBeat(kind=BeatKind.WIN, name=winner))
    slot = entry_order.index(player) + 1
    tail = "승리" if won else "패배"
    return MatchSequence(
        beats=tuple(beats),
        summary=f"{slot}번째로 입장 · {tail}",
        entry_number=slot,
        place=1 if won else 2,
        field=size,
        eliminated_by_player=0,
    )


def _play(
    tokens: tuple[bool, ...],
    *,
    entry_order: tuple[str, ...],
    player: str,
    winner: str,
    player_out: int,
    size: int,
    roll: SeededRoll,
) -> MatchSequence:
    """토큰이 리듬을 잡고, **큐가 탈락 순서를 정한다.**

    처음엔 매 탈락마다 링에서 무작위로 골랐다. 그러면 우승자와 플레이어만 남은
    순간에 **고를 사람이 없어 그 탈락이 통째로 사라지고**, 생존자가 둘이 된다.
    순서를 먼저 정해 두면 그 자리에서 "아직 안 들어온 사람"은 입장을 당겨서 맞출
    수 있다 — 사라지는 탈락이 없다.
    """
    queue = _queue(entry_order, player=player, winner=winner, at=player_out, roll=roll)
    beats: list[MatchBeat] = []
    ring: list[str] = []
    cursor = 0
    by_player = 0

    def enter() -> None:
        nonlocal cursor
        name = entry_order[cursor]
        cursor += 1
        ring.append(name)
        beats.append(MatchBeat(kind=BeatKind.ENTER, name=name, number=cursor))

    def throw_out(victim: str) -> None:
        nonlocal by_player
        # 나갈 사람이 아직 안 들어왔거나 혼자 있으면 다음 사람을 당겨 온다.
        while cursor < size and (victim not in ring or len(ring) < OPENING_FIELD):
            enter()
        ring.remove(victim)
        thrower = roll.pick(tuple(ring)) if ring else None
        if thrower == player:
            by_player += 1
        beats.append(MatchBeat(kind=BeatKind.ELIMINATE, name=victim, by=thrower))

    for is_entry in tokens:
        if is_entry and cursor < size:
            enter()
        elif queue:
            throw_out(queue.pop(0))

    while cursor < size:
        enter()
    while queue:
        throw_out(queue.pop(0))

    beats.append(MatchBeat(kind=BeatKind.WIN, name=winner))
    entry_number = entry_order.index(player) + 1
    place = 1 if winner == player else size - player_out + 1
    return MatchSequence(
        beats=tuple(beats),
        summary=_summary(entry_number, by_player, place, size),
        entry_number=entry_number,
        place=place,
        field=size,
        eliminated_by_player=by_player,
    )


def _queue(
    entry_order: tuple[str, ...],
    *,
    player: str,
    winner: str,
    at: int,
    roll: SeededRoll,
) -> list[str]:
    """나가는 순서. 우승자는 없고, 플레이어는 `at`번째다(`at`이 0이면 안 나간다)."""
    rest = [n for n in entry_order if n not in (player, winner)]
    order = [rest.pop(roll.between(0, len(rest) - 1)) for _ in range(len(rest))]
    if at:
        order.insert(at - 1, player)
    return order


def _summary(entry: int, by_player: int, place: int, size: int) -> str:
    """세이브에 남는 한 줄. **순위와 탈락 순번을 같이 적는다** — "22번째 탈락"만으로는
    그게 잘한 밤인지 알 수 없고, "9위"만으로는 몇 명짜리 경기였는지 알 수 없다.
    """
    head = f"{entry}번으로 입장"
    took = f" · {by_player}명 탈락" if by_player else ""
    if place == 1:
        return f"{head}{took} · 우승({size}인)"
    return f"{head}{took} · {size - place + 1}번째 탈락({place}위/{size}인)"
