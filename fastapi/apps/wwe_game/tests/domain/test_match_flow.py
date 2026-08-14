"""모멘텀 타임라인 (하네스 §3-D81).

2026-08-13에 설계만 해 두고 *"구현은 §3-D80 다음"*으로 남긴 자리다. 그때까지 진행이
있는 경기는 **22,398경기 중 9.4%**뿐이었다 — 럼블·챔버만 입장·탈락으로 세워졌고
1:1은 결과 한 줄이 전부였다.

여기서 지키는 것 다섯:

1. **흐름이 승패를 만들지 않는다** — 판정이 끝난 뒤에 그려진다 (§3-D4)
2. **결말로 수렴한다** — 마지막은 이긴 쪽의 피니셔다
3. **내 피니셔는 이긴 밤에만 이름을 갖는다** (§3-D88)
4. 되짚기가 결정적이다 — 같은 시드는 같은 경기다
5. 니어폴은 후반에만 나온다
"""

from __future__ import annotations

import pytest
from wwe_game.domain.services import match_flow, seeded_roll
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.match_kind import MatchKind
from wwe_game.domain.value_objects.match_sequence import BeatKind

PLAYER = "장상호"
RIVAL = "건서"
FINISHER = "붉은 낙인"
MOVES = ("암바", "저먼 수플렉스", "테이크다운", "헤드록", "레그록")


def flow(*, won: bool = True, major: bool = True, seed: int = 42):
    return match_flow.sequence_for(
        MatchKind.SINGLES,
        player=PLAYER,
        opponent=RIVAL,
        won=won,
        finisher=FINISHER,
        moves=MOVES,
        major=major,
        roll=SeededRoll(seed, 300, seeded_roll.ELIMINATION),
    )


class TestItDoesNotDecideAnything:
    """**판정이 끝난 뒤에 그려진다** — 흐름이 승패를 만들면 같은 시드가 다른 결과를 낸다."""

    @pytest.mark.parametrize("won", [True, False])
    def test_the_result_it_is_given_is_the_result_it_draws(self, won: bool) -> None:
        seq = flow(won=won)
        assert seq.won is won
        assert seq.beats[-1].kind is BeatKind.WIN
        assert seq.beats[-1].name == (PLAYER if won else RIVAL)

    def test_the_same_seed_draws_the_same_match(self) -> None:
        assert flow(seed=7) == flow(seed=7)

    def test_a_different_seed_draws_a_different_match(self) -> None:
        assert flow(seed=7) != flow(seed=8)


class TestItEndsWithAFinisher:
    def test_the_last_move_is_the_finisher(self) -> None:
        seq = flow(won=True)
        assert seq.beats[-2].kind is BeatKind.FINISHER

    def test_my_finisher_is_named_when_i_win(self) -> None:
        """§3-D88이 고른 이름이 여기 실린다."""
        seq = flow(won=True)
        assert seq.beats[-2].by == FINISHER
        assert seq.beats[-2].name == PLAYER

    def test_it_is_not_named_when_i_lose(self) -> None:
        """**못 끝낸 밤에 내 기술 이름이 나오면 고른 것의 뜻이 사라진다.**"""
        seq = flow(won=False)
        assert seq.beats[-2].by is None
        assert seq.beats[-2].name == RIVAL


class TestTheMomentum:
    def test_it_starts_even(self) -> None:
        assert flow().beats[0].momentum != 0

    def test_it_stays_inside_the_rails(self) -> None:
        """**0과 100을 쓰지 않는다** — 완전히 한쪽이면 그 뒤가 없다."""
        for seed in range(1, 40):
            for beat in flow(seed=seed).beats:
                assert (
                    match_flow.MOMENTUM_MIN <= beat.momentum <= match_flow.MOMENTUM_MAX
                )

    def test_it_lands_on_the_winner(self) -> None:
        assert flow(won=True).beats[-1].momentum == match_flow.MOMENTUM_MAX
        assert flow(won=False).beats[-1].momentum == match_flow.MOMENTUM_MIN

    def test_it_actually_swings(self) -> None:
        """한 방향으로만 흐르면 그건 흐름이 아니라 카운터다."""
        values = [b.momentum for b in flow(seed=11).beats]
        assert len(set(values)) > 3


class TestTheMoveNames:
    """**"기술을 걸었다"만 반복하면 로그지 경기가 아니다** (§3-D81-4)."""

    def test_every_move_carries_a_name(self) -> None:
        for beat in flow().beats:
            if beat.kind in (BeatKind.MOVE, BeatKind.REVERSAL):
                assert beat.by in MOVES, "무슨 기술인지가 실려야 한다"

    def test_the_names_vary(self) -> None:
        """다섯 수가 전부 같은 이름이면 고친 뜻이 없다."""
        names = [b.by for b in flow(seed=5).beats if b.kind is BeatKind.MOVE]
        assert len(set(names)) > 1


class TestTheShape:
    def test_a_major_night_runs_longer(self) -> None:
        """20분 경기와 5분 경기의 차이가 여기다."""
        assert len(flow(major=True).beats) > len(flow(major=False).beats)

    def test_a_kickout_always_follows_a_nearfall(self) -> None:
        for seed in range(1, 30):
            beats = flow(seed=seed).beats
            for i, beat in enumerate(beats):
                if beat.kind is BeatKind.NEARFALL:
                    assert beats[i + 1].kind is BeatKind.KICKOUT

    def test_nearfalls_only_come_late(self) -> None:
        """첫 1분에 투 카운트가 나오는 경기는 없다."""
        beats = flow(seed=3).beats
        spots = [i for i, b in enumerate(beats) if b.kind is BeatKind.NEARFALL]
        if spots:
            assert min(spots) > len(beats) * 0.4

    def test_the_summary_survives_without_the_beats(self) -> None:
        """비트는 저장하지 않는다 (§3-D34) — 다시 열면 이 한 줄만 남는다."""
        seq = flow(won=True)
        assert RIVAL in seq.summary
        assert "승리" in seq.summary
