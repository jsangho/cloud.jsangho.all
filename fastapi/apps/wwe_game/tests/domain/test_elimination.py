"""탈락 경기의 진행 순서 (하네스 §3-D34).

**여기서 잠그는 것은 하나다: 순서가 판정과 어긋나지 않는다.** 이긴 밤에 중간에
떨어지거나, 진 밤에 끝까지 남으면 화면이 승패와 다른 이야기를 하게 된다.
"""

from __future__ import annotations

import pytest
from wwe_game.domain.services import elimination
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.match_kind import MatchKind, format_of
from wwe_game.domain.value_objects.match_sequence import BeatKind

PLAYER = "장상호"
POOL = tuple(f"선수{i:02d}" for i in range(1, 60))
STAGED = (
    MatchKind.BATTLE_ROYAL,
    MatchKind.CHAMBER,
    MatchKind.GAUNTLET,
    MatchKind.WARGAMES,
)


def _sequence(kind: MatchKind, *, won: bool, seed: int):
    return elimination.sequence_for(
        kind,
        player=PLAYER,
        won=won,
        pool=POOL,
        roll=SeededRoll(seed, 1, "elimination"),
    )


def test_stipulation_matches_have_no_sequence() -> None:
    """싱글도 헬 인 어 셀도 단계가 없다 — 둘이 붙어 한 번에 끝난다."""
    for kind in (MatchKind.SINGLES, MatchKind.HELL_IN_A_CELL, MatchKind.LADDER):
        assert _sequence(kind, won=True, seed=1) is None


@pytest.mark.parametrize("kind", STAGED)
@pytest.mark.parametrize("seed", range(40))
def test_winner_survives_and_loser_does_not(kind: MatchKind, seed: int) -> None:
    """**판정이 먼저다.** 이긴 판은 1위, 진 판은 1위가 아니다."""
    assert _sequence(kind, won=True, seed=seed).place == 1
    assert _sequence(kind, won=False, seed=seed).place > 1


@pytest.mark.parametrize("kind", (MatchKind.BATTLE_ROYAL, MatchKind.CHAMBER))
@pytest.mark.parametrize("seed", range(40))
def test_nobody_leaves_before_arriving(kind: MatchKind, seed: int) -> None:
    """아직 입장하지 않은 사람은 탈락할 수 없다. 이 모듈이 가장 틀리기 쉬운 자리다."""
    for won in (True, False):
        sequence = _sequence(kind, won=won, seed=seed)
        in_ring: set[str] = set()
        for beat in sequence.beats:
            if beat.kind is BeatKind.ENTER:
                assert beat.name not in in_ring, "같은 사람이 두 번 입장했다"
                in_ring.add(beat.name)
            elif beat.kind is BeatKind.ELIMINATE:
                assert beat.name in in_ring, f"{beat.name}이 입장 전에 탈락했다"
                in_ring.remove(beat.name)
                if beat.by is not None:
                    assert beat.by in in_ring, "링에 없는 사람이 탈락시켰다"


@pytest.mark.parametrize("kind", (MatchKind.BATTLE_ROYAL, MatchKind.CHAMBER))
@pytest.mark.parametrize("seed", range(40))
def test_exactly_one_survivor(kind: MatchKind, seed: int) -> None:
    """전원 입장하고 한 명만 남는다 — 탈락 수는 인원 −1로 정확히 맞는다."""
    for won in (True, False):
        sequence = _sequence(kind, won=won, seed=seed)
        field = format_of(kind).field
        enters = [b for b in sequence.beats if b.kind is BeatKind.ENTER]
        outs = [b for b in sequence.beats if b.kind is BeatKind.ELIMINATE]
        wins = [b for b in sequence.beats if b.kind is BeatKind.WIN]
        assert len(enters) == field
        assert len(outs) == field - 1
        assert len(wins) == 1
        assert {b.name for b in outs} | {wins[0].name} == {b.name for b in enters}


@pytest.mark.parametrize("kind", (MatchKind.BATTLE_ROYAL, MatchKind.CHAMBER))
@pytest.mark.parametrize("seed", range(40))
def test_place_matches_when_the_player_left(kind: MatchKind, seed: int) -> None:
    """요약의 순위가 실제 탈락 시점과 같다. **둘이 어긋나면 요약이 거짓말이 된다.**"""
    sequence = _sequence(kind, won=False, seed=seed)
    outs = [b for b in sequence.beats if b.kind is BeatKind.ELIMINATE]
    order = [b.name for b in outs].index(PLAYER) + 1
    assert sequence.place == sequence.field - order + 1
    assert f"{order}번째 탈락" in sequence.summary


@pytest.mark.parametrize("kind", STAGED)
def test_same_seed_same_sequence(kind: MatchKind) -> None:
    """§3-D4 — 같은 시드는 같은 밤이다."""
    first = _sequence(kind, won=False, seed=99)
    second = _sequence(kind, won=False, seed=99)
    assert first == second


def test_wargames_enters_without_eliminating() -> None:
    """워게임즈는 차례로 들어오되 탈락이 없다 — 핀폴 하나로 끝난다."""
    sequence = _sequence(MatchKind.WARGAMES, won=True, seed=3)
    assert not [b for b in sequence.beats if b.kind is BeatKind.ELIMINATE]
    assert len([b for b in sequence.beats if b.kind is BeatKind.ENTER]) == 10
    assert sequence.place == 1


def test_thin_pool_shrinks_the_field_instead_of_failing() -> None:
    """명부가 얇으면 있는 만큼 세운다. 30명이 안 찬다고 럼블을 취소하지 않는다."""
    sequence = _sequence_with_pool(MatchKind.BATTLE_ROYAL, POOL[:8])
    assert sequence.field == 9
    assert len([b for b in sequence.beats if b.kind is BeatKind.ENTER]) == 9


def test_a_pool_of_one_has_no_sequence() -> None:
    """둘로는 탈락 경기가 성립하지 않는다."""
    assert _sequence_with_pool(MatchKind.BATTLE_ROYAL, POOL[:1]) is None


def _sequence_with_pool(kind: MatchKind, pool: tuple[str, ...]):
    return elimination.sequence_for(
        kind, player=PLAYER, won=False, pool=pool, roll=SeededRoll(5, 1, "elimination")
    )
