"""캐릭터 생성 — 프리셋이 기본값을 깔고 명시값이 덮는다 (하네스 §3-D10-1)."""

from __future__ import annotations

import pytest
from wwe_game.domain.constants.character_presets import PRESETS, preset_for
from wwe_game.domain.constants.countries import Country
from wwe_game.domain.exceptions import InvalidCareerRunError
from wwe_game.domain.services.character_creation import (
    UnknownPresetError,
    build_identity,
)
from wwe_game.domain.value_objects.wrestler_identity import Gender, PlayStyle

BASE = "로만 레인즈"


class TestPresetTable:
    def test_the_table_is_not_empty(self) -> None:
        assert len(PRESETS) >= 150

    def test_sources_are_unique(self) -> None:
        assert len({p.source for p in PRESETS}) == len(PRESETS)

    def test_a_missing_source_is_none(self) -> None:
        assert preset_for("있을 리 없는 이름") is None

    def test_both_divisions_are_covered(self) -> None:
        genders = {p.gender for p in PRESETS}
        assert genders == set(Gender)

    def test_every_play_style_is_reachable(self) -> None:
        # 한 스타일이라도 비면 그 스타일을 바탕으로 시작할 방법이 없다.
        assert {p.play_style for p in PRESETS} == set(PlayStyle)


class TestBuildFromPreset:
    def test_a_preset_fills_everything_but_the_name(self) -> None:
        preset = preset_for(BASE)
        assert preset is not None
        identity = build_identity(name="장상호", based_on=BASE)
        assert identity.name.value == "장상호"
        assert identity.gender is preset.gender
        assert identity.play_style is preset.play_style
        assert identity.country is preset.country

    def test_the_name_is_never_inherited(self) -> None:
        # 실존 인물과 같은 이름을 만들 수 있으면 §3-D13의 고지가 무의미해진다.
        identity = build_identity(name="장상호", based_on=BASE)
        assert identity.name.value != BASE

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("gender", Gender.FEMALE),
            ("play_style", PlayStyle.HIGH_FLYER),
            ("country", Country.KR),
        ],
    )
    def test_an_explicit_value_overrides_the_preset(
        self, field: str, value: object
    ) -> None:
        identity = build_identity(name="장상호", based_on=BASE, **{field: value})
        assert getattr(identity, field) is value

    def test_every_field_can_be_overridden_at_once(self) -> None:
        identity = build_identity(
            name="장상호",
            based_on=BASE,
            gender=Gender.FEMALE,
            country=Country.JP,
            play_style=PlayStyle.TECHNICIAN,
        )
        assert identity.gender is Gender.FEMALE
        assert identity.country is Country.JP
        assert identity.play_style is PlayStyle.TECHNICIAN

    def test_an_unknown_preset_is_refused(self) -> None:
        with pytest.raises(UnknownPresetError):
            build_identity(name="장상호", based_on="있을 리 없는 이름")

    def test_an_off_list_origin_becomes_other(self) -> None:
        # 권역에 없는 나라 출신은 '기타'로 뭉친다 (2026-08-07 사용자 결정).
        misc = next((p for p in PRESETS if p.country is Country.OTHER), None)
        assert misc is not None, "기타로 묶인 프리셋이 하나도 없다"
        assert build_identity(name="장상호", based_on=misc.source).country is (
            Country.OTHER
        )

    def test_other_still_lands_in_a_region(self) -> None:
        # 권역이 없으면 이벤트 조건이 조용히 통과한다 (§11-16).
        from wwe_game.domain.constants.countries import region_of

        assert region_of(Country.OTHER) is not None

    def test_an_off_list_origin_can_still_be_overridden(self) -> None:
        misc = next(p for p in PRESETS if p.country is Country.OTHER)
        identity = build_identity(
            name="장상호", based_on=misc.source, country=Country.KR
        )
        assert identity.country is Country.KR

    def test_every_preset_carries_a_country(self) -> None:
        assert all(p.country is not None for p in PRESETS)


class TestBuildWithoutPreset:
    def test_all_four_can_be_given_directly(self) -> None:
        identity = build_identity(
            name="장상호",
            gender=Gender.MALE,
            country=Country.KR,
            play_style=PlayStyle.BRAWLER,
        )
        assert identity.country is Country.KR

    def test_a_missing_field_is_named_in_the_error(self) -> None:
        # 임의의 기본값을 채워 주면 사용자가 고르지 않은 값이 조용히 들어간다.
        with pytest.raises(InvalidCareerRunError, match="플레이스타일"):
            build_identity(name="장상호", gender=Gender.MALE, country=Country.KR)

    def test_the_ring_name_is_still_validated(self) -> None:
        from wwe_game.domain.exceptions import InvalidRingNameError

        with pytest.raises(InvalidRingNameError):
            build_identity(name="가", based_on=BASE)
