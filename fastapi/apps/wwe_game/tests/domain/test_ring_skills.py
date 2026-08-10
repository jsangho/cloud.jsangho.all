"""경기력의 네 축 — 가중 평균이 언제나 경기력으로 되돌아온다 (하네스 §3-D29)."""

from __future__ import annotations

import pytest
from wwe_game.domain.constants.play_styles import SKILL_PROFILES, SKILL_WEIGHT_TOTAL
from wwe_game.domain.value_objects.ring_skills import breakdown
from wwe_game.domain.value_objects.wrestler_identity import PlayStyle


def _weighted_mean(style: PlayStyle, in_ring: int) -> float:
    skills = breakdown(in_ring, style)
    axes = (skills.power, skills.speed, skills.generalship, skills.signature)
    weights = SKILL_PROFILES[style].weights
    return sum(w * a for w, a in zip(weights, axes, strict=True)) / SKILL_WEIGHT_TOTAL


class TestBreakdownAddsUp:
    @pytest.mark.parametrize("style", list(PlayStyle))
    def test_the_dropdown_never_contradicts_the_headline(
        self, style: PlayStyle
    ) -> None:
        # 머리글 숫자와 속의 숫자가 어긋나면 드롭다운이 거짓말이 된다.
        for value in range(0, 101):
            assert round(_weighted_mean(style, value)) == value

    @pytest.mark.parametrize("style", list(PlayStyle))
    def test_every_axis_stays_in_range(self, style: PlayStyle) -> None:
        for value in (0, 1, 50, 99, 100):
            skills = breakdown(value, style)
            for _, axis in skills.as_pairs:
                assert 0 <= axis <= 100

    def test_it_is_a_pure_view(self) -> None:
        # 저장하지 않고 매번 푸는 값이라, 같은 입력이면 같은 결과여야 한다.
        assert breakdown(60, PlayStyle.GIANT) == breakdown(60, PlayStyle.GIANT)

    def test_out_of_range_is_refused(self) -> None:
        with pytest.raises(ValueError, match="경기력"):
            breakdown(101, PlayStyle.BRAWLER)


class TestStyleShowsThrough:
    def test_the_same_score_looks_different_per_style(self) -> None:
        power = breakdown(60, PlayStyle.POWERHOUSE)
        flyer = breakdown(60, PlayStyle.HIGH_FLYER)
        assert power.power > power.speed
        assert flyer.speed > flyer.power
        assert power.power == flyer.speed  # 가중치가 거울상이다

    def test_the_all_rounder_is_flat(self) -> None:
        # 셋이 고르고 전용 축만 낮은 모양이 그 스타일의 정의다.
        skills = breakdown(60, PlayStyle.ALL_ROUNDER)
        assert (
            max(skills.power, skills.speed, skills.generalship)
            - min(skills.power, skills.speed, skills.generalship)
            <= 1
        )
        assert skills.signature < skills.power

    def test_the_fourth_axis_is_named_by_style(self) -> None:
        assert breakdown(50, PlayStyle.SUBMISSIONS).signature_name == "관절기"
        assert breakdown(50, PlayStyle.GIANT).signature_name == "체격"

    def test_the_first_three_names_are_fixed(self) -> None:
        # 파워·스피드·운영은 고정이고 넷째만 갈린다 (사용자 지시 6번).
        for style in PlayStyle:
            names = [name for name, _ in breakdown(50, style).as_pairs]
            assert names[:3] == ["파워", "스피드", "운영"]
