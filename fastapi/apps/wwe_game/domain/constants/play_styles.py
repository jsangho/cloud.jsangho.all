"""경기 유형 21종의 표 — 한글 표기 · 경기력 구성 · 위험도 (하네스 §3-D27).

**스타일에 딸린 값은 전부 여기 모은다.** 흩어 두면 스타일을 하나 늘릴 때 어느 표를
빠뜨렸는지 문자열 검색으로 찾게 되고, 그 검색이 놓친 것이 죽은 표식 21종이었다(§3-D26).
아래 세 표는 임포트 시점에 21종을 빠짐없이 덮는지 검증한다.

## 경기력은 하나가 아니라 넷이다 (2026-08-10 사용자 요청)

화면의 '경기력'(`in_ring`)은 **파워 · 스피드 · 운영** 세 고정 축과 스타일마다 다른
**전용 축** 하나의 가중 평균이다. 같은 경기력 60이라도 자이언트는 파워로, 루차
리브레는 스피드로 채운 60이다.

전용 축을 계열이 아니라 **스타일마다** 따로 두는 이유: 계열로 묶으면 서브미션과
슈터가 같은 축을 쓰게 되는데, 이 둘을 가르는 것이 정확히 그 축이다.
"""

from __future__ import annotations

from dataclasses import dataclass

from wwe_game.domain.value_objects.wrestler_identity import PlayStyle, StyleFamily

KOREAN_STYLE_NAMES: dict[PlayStyle, str] = {
    PlayStyle.BRAWLER: "브롤러",
    PlayStyle.HIGH_FLYER: "하이 플라이어",
    PlayStyle.TECHNICIAN: "테크니션",
    PlayStyle.OLD_SCHOOL: "올드스쿨",
    PlayStyle.SUBMISSIONS: "서브미션",
    PlayStyle.POWERHOUSE: "파워하우스",
    PlayStyle.GIANT: "자이언트",
    PlayStyle.MONSTER: "몬스터",
    PlayStyle.SHOWMAN: "쇼맨",
    PlayStyle.HEEL_STYLE: "힐 스타일",
    PlayStyle.STUNTMAN: "스턴트맨",
    PlayStyle.HARDCORE: "하드코어",
    PlayStyle.SHOOTER: "슈터",
    PlayStyle.HARD_HITTING: "하드 히팅",
    PlayStyle.LUCHA_LIBRE: "루차 리브레",
    PlayStyle.STRONG_STYLE: "스트롱 스타일",
    PlayStyle.UWF: "U계",
    PlayStyle.KINGS_ROAD: "왕도 스타일",
    PlayStyle.ALL_ROUNDER: "올라운더",
    PlayStyle.UNDERDOG: "언더독",
    PlayStyle.SHOWGIRL: "쇼걸",
}
"""화면에 쓰는 한글 표기 (2026-08-10 사용자 지정).

앞 열여덟은 사용자가 준 목록 그대로다. 뒤 셋(올라운더·언더독·쇼걸)은 로스터 CSV가
실제로 쓰는데 목록에 없어 이번에 더했다 — 특히 올라운더는 178명 중 53명으로 최다다.
"""

KOREAN_FAMILY_NAMES: dict[StyleFamily, str] = {
    StyleFamily.GRAPPLE: "그래플 계열",
    StyleFamily.POWER: "파워 계열",
    StyleFamily.AERIAL: "공중 계열",
    StyleFamily.STRIKE: "타격 계열",
    StyleFamily.SHOW: "쇼 계열",
    StyleFamily.FREE: "자유 계열",
}


@dataclass(frozen=True)
class SkillProfile:
    """한 스타일이 경기력을 어떻게 나눠 갖는지.

    네 가중치의 합은 10이다. **합을 고정하는 이유는 비교 가능성이다** — 합이 다르면
    스타일을 바꾸는 것만으로 같은 경기력이 다른 값이 된다.
    """

    power: int
    speed: int
    generalship: int
    signature: int
    signature_name: str
    """전용 축의 한글 이름. 드롭다운 네 번째 줄에 그대로 나간다."""

    def __post_init__(self) -> None:
        total = self.power + self.speed + self.generalship + self.signature
        if total != SKILL_WEIGHT_TOTAL:
            raise ValueError(
                f"{self.signature_name}: 가중치 합이 {total}입니다 "
                f"({SKILL_WEIGHT_TOTAL}이어야 합니다)"
            )

    @property
    def weights(self) -> tuple[int, int, int, int]:
        return (self.power, self.speed, self.generalship, self.signature)


SKILL_WEIGHT_TOTAL = 10

SKILL_PROFILES: dict[PlayStyle, SkillProfile] = {
    # ── 그래플 계열 ────────────────────────────────────────────
    PlayStyle.TECHNICIAN: SkillProfile(2, 2, 3, 3, "정교함"),
    PlayStyle.SUBMISSIONS: SkillProfile(2, 1, 3, 4, "관절기"),
    PlayStyle.SHOOTER: SkillProfile(3, 2, 2, 3, "그래플링"),
    PlayStyle.UWF: SkillProfile(3, 2, 2, 3, "실전성"),
    # ── 파워 계열 ──────────────────────────────────────────────
    PlayStyle.POWERHOUSE: SkillProfile(5, 1, 2, 2, "완력"),
    PlayStyle.GIANT: SkillProfile(4, 1, 2, 3, "체격"),
    PlayStyle.MONSTER: SkillProfile(4, 2, 1, 3, "위압"),
    # ── 공중 계열 ──────────────────────────────────────────────
    PlayStyle.HIGH_FLYER: SkillProfile(1, 5, 2, 2, "체공"),
    PlayStyle.LUCHA_LIBRE: SkillProfile(1, 4, 2, 3, "연계"),
    PlayStyle.STUNTMAN: SkillProfile(1, 4, 1, 4, "무모함"),
    # ── 타격 계열 ──────────────────────────────────────────────
    PlayStyle.BRAWLER: SkillProfile(4, 2, 2, 2, "난투"),
    PlayStyle.HARD_HITTING: SkillProfile(4, 1, 2, 3, "강타"),
    PlayStyle.STRONG_STYLE: SkillProfile(3, 2, 2, 3, "맷집"),
    PlayStyle.KINGS_ROAD: SkillProfile(3, 1, 3, 3, "축적"),
    # ── 쇼 계열 ────────────────────────────────────────────────
    PlayStyle.SHOWMAN: SkillProfile(2, 2, 3, 3, "쇼맨십"),
    PlayStyle.HEEL_STYLE: SkillProfile(2, 2, 3, 3, "반칙"),
    PlayStyle.OLD_SCHOOL: SkillProfile(2, 1, 4, 3, "심리"),
    PlayStyle.SHOWGIRL: SkillProfile(1, 3, 3, 3, "무대 장악"),
    # ── 자유 계열 ──────────────────────────────────────────────
    PlayStyle.HARDCORE: SkillProfile(3, 2, 2, 3, "흉기 활용"),
    PlayStyle.ALL_ROUNDER: SkillProfile(3, 3, 3, 1, "적응력"),
    PlayStyle.UNDERDOG: SkillProfile(1, 3, 3, 3, "근성"),
}
"""스타일마다 다른 경기력 구성 (2026-08-10 사용자 요청).

**올라운더의 전용 축만 1이다.** 셋을 고르게 갖는 것이 그 스타일의 정의라, 전용 축이
크면 "고르게 갖는데 남다른 무기도 있다"가 되어 다른 스무 종이 열등해진다.
"""

INJURY_STYLE_MULTIPLIER: dict[PlayStyle, float] = {
    PlayStyle.TECHNICIAN: 0.80,
    PlayStyle.SUBMISSIONS: 0.85,
    PlayStyle.SHOOTER: 0.90,
    PlayStyle.UWF: 1.00,
    PlayStyle.POWERHOUSE: 1.10,
    PlayStyle.GIANT: 1.00,
    PlayStyle.MONSTER: 1.15,
    PlayStyle.HIGH_FLYER: 1.60,
    PlayStyle.LUCHA_LIBRE: 1.50,
    PlayStyle.STUNTMAN: 1.90,
    PlayStyle.BRAWLER: 1.30,
    PlayStyle.HARD_HITTING: 1.35,
    PlayStyle.STRONG_STYLE: 1.40,
    PlayStyle.KINGS_ROAD: 1.25,
    PlayStyle.SHOWMAN: 0.90,
    PlayStyle.HEEL_STYLE: 0.85,
    PlayStyle.OLD_SCHOOL: 0.80,
    PlayStyle.SHOWGIRL: 0.90,
    PlayStyle.HARDCORE: 1.80,
    PlayStyle.ALL_ROUNDER: 1.05,
    PlayStyle.UNDERDOG: 1.45,
}
"""스타일별 부상 위험도 (§5).

**몸을 던지는 순서**다 — 스턴트맨·하드코어가 가장 높고, 관절을 잠그는 쪽과 마이크로
버는 쪽이 가장 낮다. 다섯 종이던 시절의 값(하이플라이어 1.6 · 브롤러 1.3 · 파워하우스
1.1 · 쇼맨 0.9 · 테크니션 0.8)을 그대로 두고 나머지를 그 사이에 끼웠다 — 기존 밸런스
측정치(커리어당 부상 7.9회)를 새로 재지 않아도 되는 자리를 지킨다.
"""


for _table, _label in (
    (KOREAN_STYLE_NAMES, "한글 표기"),
    (SKILL_PROFILES, "경기력 구성"),
    (INJURY_STYLE_MULTIPLIER, "부상 배수"),
):  # pragma: no cover - 임포트 시 구조 검증
    _missing = sorted(set(PlayStyle) - set(_table))
    if _missing:
        raise RuntimeError(f"{_label}가 없는 플레이스타일: {_missing}")

if set(KOREAN_FAMILY_NAMES) != set(StyleFamily):  # pragma: no cover
    raise RuntimeError("계열 한글 표기가 빠졌습니다")
