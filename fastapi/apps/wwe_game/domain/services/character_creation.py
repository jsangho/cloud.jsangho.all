"""캐릭터 생성 — 실존 선수를 바탕으로 삼되 무엇이든 바꿀 수 있다 (하네스 §3-D10-1).

**프리셋은 기본값이지 구속이 아니다**(2026-08-07 사용자 요청). 실존 선수를 고르면 그
선수의 디비전·플레이스타일·국적이 채워지고, 명시한 값은 그 위를 덮는다. 프리셋 없이
넷을 직접 정하는 길도 그대로 열려 있다.

**이름만은 물려받지 않는다.** 실존 인물의 이름을 그대로 쓰는 캐릭터를 만들 수 있게 두면
§3-D13의 고지("전개는 허구입니다")가 무의미해진다 — 이름이 같으면 그 사람의 이야기로
읽히기 때문이다. 프리셋은 "○○를 바탕으로 만든 다른 선수"까지만 만든다.
"""

from __future__ import annotations

from wwe_game.domain.constants.character_presets import CharacterPreset, preset_for
from wwe_game.domain.constants.countries import Country
from wwe_game.domain.exceptions import InvalidCareerRunError
from wwe_game.domain.value_objects.wrestler_identity import (
    Gender,
    PlayStyle,
    RingName,
    WrestlerIdentity,
)


class UnknownPresetError(InvalidCareerRunError):
    """없는 선수를 바탕으로 삼으려 할 때 (하네스 §8 → 400)."""


def build_identity(
    *,
    name: str,
    based_on: str | None = None,
    gender: Gender | None = None,
    country: Country | None = None,
    play_style: PlayStyle | None = None,
) -> WrestlerIdentity:
    """캐릭터를 만든다. 프리셋이 바닥을 깔고 명시값이 그 위를 덮는다.

    프리셋을 안 쓰면 넷을 모두 넘겨야 한다 — 기본값을 임의로 정해 주면 사용자가 고르지
    않은 값이 조용히 들어간다. 프리셋을 쓰면 세 값이 다 채워지고, 덮고 싶은 것만 넘긴다.

    목록 밖 출신은 프리셋에서 `Country.OTHER`(기타)로 들어온다(2026-08-07 사용자 결정).
    비워 두던 때에는 그 여섯 명을 고를 때마다 국적을 따로 골라야 했다.
    """
    preset = _preset_or_raise(based_on)
    resolved_gender = gender or (preset.gender if preset else None)
    resolved_style = play_style or (preset.play_style if preset else None)
    resolved_country = country or (preset.country if preset else None)

    missing = [
        label
        for label, value in (
            ("성별", resolved_gender),
            ("국가", resolved_country),
            ("플레이스타일", resolved_style),
        )
        if value is None
    ]
    if missing:
        raise InvalidCareerRunError(f"{'·'.join(missing)}를 골라 주세요.")

    assert resolved_gender is not None  # noqa: S101 - 위에서 걸러진다
    assert resolved_country is not None  # noqa: S101
    assert resolved_style is not None  # noqa: S101
    return WrestlerIdentity(
        name=RingName(name),
        gender=resolved_gender,
        country=resolved_country,
        play_style=resolved_style,
    )


def _preset_or_raise(based_on: str | None) -> CharacterPreset | None:
    if based_on is None:
        return None
    preset = preset_for(based_on)
    if preset is None:
        raise UnknownPresetError(f"선택할 수 없는 항목입니다: {based_on}")
    return preset
