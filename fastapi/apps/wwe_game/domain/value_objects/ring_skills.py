"""경기력의 속을 여는 네 축 — 파워 · 스피드 · 운영 + 스타일 전용 (하네스 §3-D29).

화면에서 '경기력'에 마우스를 올리면 나오는 드롭다운의 내용이다 (2026-08-10 사용자 요청).

## 저장하지 않고 **경기력에서 푼다**

네 축을 따로 저장해 따로 키우는 길도 있었다. 하지 않은 이유는 하나다 — **머리글 숫자와
속의 숫자가 어긋나는 순간 드롭다운이 거짓말이 된다.** 따로 저장하면 이벤트 효과가
경기력만 올리거나 축만 올리는 경로가 생기고, 그 둘을 영원히 맞춰 줘야 한다.

여기서는 경기력 하나가 진실이고 네 축은 **그것을 스타일의 비율로 나눈 결과**다. 언제
계산해도 같은 값이 나오고, DB에 새 칸도 마이그레이션도 없다.

## 같은 60이 스타일마다 다르게 생겼다

가중치가 클수록 그 축이 크게 나온다(`aᵢ ∝ wᵢ`). 가중 평균은 언제나 경기력으로 되돌아온다.

| 스타일 | 경기력 60의 속 |
|---|---|
| 파워하우스 (5·1·2·2) | 파워 88 · 스피드 18 · 운영 35 · 완력 35 |
| 하이 플라이어 (1·5·2·2) | 파워 18 · 스피드 88 · 운영 35 · 체공 35 |
| 올라운더 (3·3·3·1) | 파워 64 · 스피드 64 · 운영 64 · 적응력 21 |

**올라운더가 이 설계의 시험지다.** 셋이 고르고 전용 축만 낮은 모양이 그 스타일의
정의를 그대로 보여 준다.
"""

from __future__ import annotations

from dataclasses import dataclass

from wwe_game.domain.constants.play_styles import (
    SKILL_PROFILES,
    SKILL_WEIGHT_TOTAL,
    SkillProfile,
)
from wwe_game.domain.value_objects.wrestler_identity import PlayStyle
from wwe_game.domain.value_objects.wrestler_stats import STAT_MAX, STAT_MIN

_SEARCH_STEPS = 40
"""배율 이분 탐색 횟수. 40번이면 0~100 구간이 1e-10까지 좁혀진다."""


@dataclass(frozen=True)
class RingSkills:
    """경기력을 네 축으로 나눈 값. **읽기 전용 파생값이다.**"""

    power: int
    speed: int
    generalship: int
    signature: int
    signature_name: str

    @property
    def as_pairs(self) -> tuple[tuple[str, int], ...]:
        """화면이 그대로 순서대로 그리는 (이름, 값). 셋은 고정, 넷째만 스타일마다 다르다."""
        return (
            ("파워", self.power),
            ("스피드", self.speed),
            ("운영", self.generalship),
            (self.signature_name, self.signature),
        )


def breakdown(in_ring: int, style: PlayStyle) -> RingSkills:
    """경기력을 스타일의 비율로 나눈다. **가중 평균은 경기력으로 되돌아온다.**"""
    if not STAT_MIN <= in_ring <= STAT_MAX:
        raise ValueError(f"경기력은 {STAT_MIN}~{STAT_MAX}여야 합니다: {in_ring}")
    profile = SKILL_PROFILES[style]
    axes = _fit(in_ring, profile)
    return RingSkills(*axes, signature_name=profile.signature_name)


def _fit(in_ring: int, profile: SkillProfile) -> tuple[int, int, int, int]:
    weights = profile.weights
    target = in_ring * SKILL_WEIGHT_TOTAL
    scale = _scale_for(target, weights)
    axes = [min(STAT_MAX, round(scale * w)) for w in weights]
    return _settle(axes, weights, target)


def _scale_for(target: int, weights: tuple[int, ...]) -> float:
    """`Σ wᵢ · min(100, c·wᵢ) = target`을 만드는 배율 c.

    상한(100)이 걸리면 넘친 몫이 나머지 축으로 밀린다 — 이분 탐색이 그 재분배를
    따로 쓰지 않고도 해 준다. 왼쪽 항이 c에 대해 단조 증가라 성립한다.
    """
    low, high = 0.0, float(STAT_MAX)
    for _ in range(_SEARCH_STEPS):
        mid = (low + high) / 2
        total = sum(w * min(STAT_MAX, mid * w) for w in weights)
        if total < target:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def _settle(
    axes: list[int], weights: tuple[int, ...], target: int
) -> tuple[int, int, int, int]:
    """반올림이 남긴 오차를 축을 ±1씩 밀어 지운다.

    **가중치가 큰 축부터 민다** — 한 칸 옮길 때 합이 그만큼 크게 움직여서, 오차를
    가장 적은 손질로 지운다. 상한·하한에 걸린 축은 건너뛴다.
    """
    order = sorted(range(len(axes)), key=lambda i: -weights[i])
    for _ in range(SKILL_WEIGHT_TOTAL):
        gap = target - sum(w * a for w, a in zip(weights, axes, strict=True))
        if gap == 0:
            break
        step = 1 if gap > 0 else -1
        for i in order:
            if abs(gap) < weights[i]:
                continue
            nudged = axes[i] + step
            if STAT_MIN <= nudged <= STAT_MAX:
                axes[i] = nudged
                break
        else:
            break
    return (axes[0], axes[1], axes[2], axes[3])
