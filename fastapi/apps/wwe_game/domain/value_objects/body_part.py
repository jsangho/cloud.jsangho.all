"""부상 부위 — 무릎과 목은 같은 부상이 아니다 (하네스 §3-D43).

지금까지 부상은 **등급 셋**(경상·중상·중대)이 전부였다. 그래서 하이플라이어가 착지를
잘못한 것과 파워하우스가 허리를 삐끗한 것이 같은 사건이었고, 로그도 같은 문장을 썼다.

## 부위가 세 가지를 정한다

1. **회복 기간** — 목은 오래 걸리고 갈비뼈는 짧다
2. **누가 다치는가** — 스타일이 부위를 고른다(공중기는 무릎·발목, 파워는 허리·어깨)
3. **재발** — 한 번 다친 곳을 또 다친다. 그리고 두 번째는 더 오래 간다

3번이 이 모듈의 핵심이다. 부위가 회복 주차만 바꾸면 숫자에 이름표를 붙인 것에 지나지
않는다 — **몸이 기억해야** 커리어의 후반이 앞부분과 달라진다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from wwe_game.domain.value_objects.wrestler_identity import PlayStyle


class BodyPart(StrEnum):
    NECK = "neck"
    BACK = "back"
    KNEE = "knee"
    SHOULDER = "shoulder"
    ANKLE = "ankle"
    RIBS = "ribs"
    ARM = "arm"
    CONCUSSION = "concussion"
    """머리는 부위라기보다 상태지만, 규칙이 다루는 방식이 같아 같은 자리에 둔다."""


@dataclass(frozen=True)
class PartSpec:
    label: str
    recovery: float
    """회복 기간 배수. **목이 가장 길고 갈비뼈가 가장 짧다.**"""


PARTS: Final[dict[BodyPart, PartSpec]] = {
    BodyPart.NECK: PartSpec("목", 1.7),
    BodyPart.BACK: PartSpec("허리", 1.35),
    BodyPart.KNEE: PartSpec("무릎", 1.4),
    BodyPart.SHOULDER: PartSpec("어깨", 1.15),
    BodyPart.ANKLE: PartSpec("발목", 0.9),
    BodyPart.RIBS: PartSpec("갈비뼈", 0.7),
    BodyPart.ARM: PartSpec("팔", 0.85),
    BodyPart.CONCUSSION: PartSpec("머리", 1.2),
}
"""부위별 회복 배수. 실제 복귀 기간의 상대적 크기를 따랐다 — 목 수술은 해를 넘기고
갈비뼈는 몇 주다. 절대 길이는 `INJURY_GRADE_WEIGHTS`가 정하고 여기서는 비율만 곱한다.
"""

STYLE_PARTS: Final[dict[PlayStyle, tuple[BodyPart, ...]]] = {
    PlayStyle.HIGH_FLYER: (BodyPart.KNEE, BodyPart.ANKLE, BodyPart.CONCUSSION),
    PlayStyle.LUCHA_LIBRE: (BodyPart.KNEE, BodyPart.ANKLE, BodyPart.SHOULDER),
    PlayStyle.STUNTMAN: (BodyPart.BACK, BodyPart.NECK, BodyPart.CONCUSSION),
    PlayStyle.POWERHOUSE: (BodyPart.BACK, BodyPart.SHOULDER),
    PlayStyle.GIANT: (BodyPart.KNEE, BodyPart.BACK),
    PlayStyle.MONSTER: (BodyPart.BACK, BodyPart.KNEE),
    PlayStyle.HARDCORE: (BodyPart.CONCUSSION, BodyPart.RIBS, BodyPart.ARM),
    PlayStyle.BRAWLER: (BodyPart.ARM, BodyPart.RIBS),
    PlayStyle.HARD_HITTING: (BodyPart.RIBS, BodyPart.CONCUSSION),
    PlayStyle.STRONG_STYLE: (BodyPart.NECK, BodyPart.RIBS),
    PlayStyle.KINGS_ROAD: (BodyPart.NECK, BodyPart.BACK),
    PlayStyle.TECHNICIAN: (BodyPart.SHOULDER, BodyPart.ARM),
    PlayStyle.SUBMISSIONS: (BodyPart.ARM, BodyPart.SHOULDER),
    PlayStyle.UWF: (BodyPart.ARM, BodyPart.KNEE),
    PlayStyle.SHOOTER: (BodyPart.SHOULDER, BodyPart.ARM),
}
"""스타일 → 그 스타일이 자주 다치는 부위 (§3-D43).

**목록에 없는 스타일은 아무 데나 다친다** — 쇼맨·올드스쿨처럼 몸을 쓰는 방식이
한쪽으로 쏠리지 않는 유형이다. 21종을 다 적으면 표가 아니라 사본이 된다.

근거는 실제 경향이다: 공중에서 내려오는 사람은 무릎과 발목을, 사람을 드는 사람은
허리와 어깨를, 머리를 쓰는 스타일은 뇌진탕을 얻는다.
"""

RECURRENCE_CHANCE: Final = 0.55
"""이미 다친 적 있는 부위를 **또** 다칠 확률 (§3-D43).

몸이 기억한다. 한 번 무너진 무릎은 다음에도 무릎이고, 그래서 커리어 후반이 앞부분과
다른 모양이 된다 — 스타일이 정한 부위 목록보다 이력이 앞선다.
"""

RECURRENCE_RECOVERY: Final = 1.3
"""재발한 부위의 회복 배수. **두 번째는 더 오래 간다.**"""


def parts_for(style: PlayStyle) -> tuple[BodyPart, ...]:
    """그 스타일이 자주 다치는 부위. 정해진 게 없으면 전부."""
    return STYLE_PARTS.get(style, tuple(BodyPart))


def recovery_factor(part: BodyPart, *, again: bool) -> float:
    return PARTS[part].recovery * (RECURRENCE_RECOVERY if again else 1.0)


for _style in PlayStyle:  # pragma: no cover - 임포트 시 구조 검증
    if _style in STYLE_PARTS and not STYLE_PARTS[_style]:
        raise RuntimeError(f"부위 목록이 빈 스타일: {_style}")
