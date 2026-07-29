"""경기 유형별 배점 테스트.

실행 방법은 `tests/adapter/outbound/pg/test_ple_match_pick_ranking.py` 상단 참고.
"""

from __future__ import annotations

import pytest

from kayfabe.app.services.ple_scoring import (
    POINTS_CHAMPIONSHIP_BONUS,
    POINTS_ELIMINATION_CHAMBER,
    POINTS_FATAL_FOUR_WAY,
    POINTS_MITB_LADDER,
    POINTS_ROYAL_RUMBLE,
    POINTS_SINGLE_OR_TAG,
    POINTS_TRIPLE_THREAT,
    derive_match_point_value,
    points_for_prediction,
)


class TestFormatPointValue:
    @pytest.mark.parametrize(
        ("title", "fmt", "expected"),
        [
            ("Single Match", "singles", POINTS_SINGLE_OR_TAG),
            ("Tag Team Match", "singles", POINTS_SINGLE_OR_TAG),
            ("Triple Threat Match", "multi", POINTS_TRIPLE_THREAT),
            ("Fatal 4-Way Match", "multi", POINTS_FATAL_FOUR_WAY),
            ("Elimination Chamber Match", "multi", POINTS_ELIMINATION_CHAMBER),
            ("Money in the Bank Ladder Match", "multi", POINTS_MITB_LADDER),
            ("Royal Rumble Match", "multi", POINTS_ROYAL_RUMBLE),
        ],
    )
    def test_format_sets_base_points(self, title: str, fmt: str, expected: int):
        assert derive_match_point_value(title, fmt) == expected

    def test_rumble_is_five_times_a_singles_match(self):
        """난이도를 반영하되 꼬리를 압축한다 — 역배당이면 15배가 된다."""
        assert POINTS_ROYAL_RUMBLE == POINTS_SINGLE_OR_TAG * 5

    def test_chamber_outranks_fatal_four_way(self):
        """참가자 6명 vs 4명 — 이전 배점은 둘 다 같아서 구분되지 않았다."""
        assert POINTS_ELIMINATION_CHAMBER > POINTS_FATAL_FOUR_WAY

    @pytest.mark.parametrize(
        ("count", "expected"),
        [(3, POINTS_TRIPLE_THREAT), (4, POINTS_FATAL_FOUR_WAY)],
    )
    def test_competitor_count_decides_when_title_is_vague(
        self, count: int, expected: int
    ):
        assert (
            derive_match_point_value("Grudge Match", "multi", competitor_count=count)
            == expected
        )

    def test_unknown_title_falls_back_to_singles(self):
        assert derive_match_point_value("Mystery Bout", "singles") == (
            POINTS_SINGLE_OR_TAG
        )


class TestChampionshipBonus:
    def test_singles_title_match_gets_bonus(self):
        assert derive_match_point_value("WWE Championship Match", "singles") == (
            POINTS_SINGLE_OR_TAG + POINTS_CHAMPIONSHIP_BONUS
        )

    def test_tag_title_match_gets_bonus(self):
        assert derive_match_point_value("Tag Team Championship Match", "singles") == (
            POINTS_SINGLE_OR_TAG + POINTS_CHAMPIONSHIP_BONUS
        )

    def test_multi_title_match_gets_bonus(self):
        """회귀 테스트 — 이전에는 우선순위 사다리가 먼저 반환해 타이틀 가산이 누락됐다."""
        assert derive_match_point_value(
            "World Heavyweight Championship Triple Threat Match", "multi"
        ) == (POINTS_TRIPLE_THREAT + POINTS_CHAMPIONSHIP_BONUS)

    def test_non_title_match_gets_no_bonus(self):
        assert derive_match_point_value("Grudge Match", "singles") == (
            POINTS_SINGLE_OR_TAG
        )


class TestPointsForPrediction:
    def test_correct_pick_earns_full_value(self):
        assert points_for_prediction(True, POINTS_ROYAL_RUMBLE) == POINTS_ROYAL_RUMBLE

    def test_wrong_pick_earns_nothing(self):
        assert points_for_prediction(False, POINTS_ROYAL_RUMBLE) == 0

    def test_ungraded_pick_earns_nothing(self):
        assert points_for_prediction(None, POINTS_ROYAL_RUMBLE) == 0
