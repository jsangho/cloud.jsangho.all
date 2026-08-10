"""태그팀·스테이블 — 이름표와 시계 (하네스 §3-D30).

**팀은 사람이 아니라 관계다.** 명부(`roster.py`)가 누가 있는지를 말한다면 여기는
누가 누구와 묶여 있는지를 말한다. 30년이면 팀도 사람만큼 갈린다 (2026-08-10 사용자 지시
7·7-1·7-2번).

## 이름표는 손으로, 시계는 규칙으로

한글 표기는 사용자가 정한 표를 그대로 쓴다. 팀이 언제 갈라지고 언제 새로 묶이는지는
규칙이 굴린다 — 서른 해치를 손으로 적으면 뒤로 갈수록 성의가 떨어진다(가상 선수 이름을
조합으로 만든 것과 같은 이유, §3-D13-1).

**예외가 하나 있다**: 로스 아메리카노스의 뒷이야기는 사용자가 직접 정해 왔다(§7-1).
정해진 전개는 굴리지 않고 `SCRIPTED_ARCS`에 적어 둔다 — 규칙으로 흉내 내면 세 사람이
각자 다른 방향으로 흩어져 그 이야기가 사라진다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

WEEKS_PER_YEAR = 52


class TeamKind(StrEnum):
    """둘이면 태그팀, 셋 이상이면 스테이블. **부르는 법이 다르다.**"""

    TAG_TEAM = "tag_team"
    STABLE = "stable"


def kind_for(size: int) -> TeamKind:
    return TeamKind.TAG_TEAM if size <= 2 else TeamKind.STABLE


KOREAN_TEAM_NAMES: dict[str, str] = {
    # ── RAW ───────────────────────────────────────────────────
    "Judgement Day": "저지먼트 데이",
    "The Vision": "더 비전",
    "Bloodline": "블러드라인",
    "The Usos": "우소즈",
    "Latino World Order": "LWO | 라티노 월드 오더",
    "Creed Brothers": "크리드 브라더스",
    "Los Americanos": "로스 아메리카노스",
    "Street Profits": "스트리트 프로피츠",
    "Alpha Academy": "알파 아카데미",
    "War Raiders": "워 레이더스",
    "Bella Twins": "벨라 트윈스",
    # ── SmackDown ─────────────────────────────────────────────
    "The Tongans": "더 통간스",
    "Los Garza": "로스 가르자",
    "Pretty Deadly": "프리티 데들리",
    "Fraxiom": "프랙시옴",
    "The Irresistible Forces": "이러지즈터블 포시즈",
    "Fatal Influence": "페이탈 인플루언스",
    # ── NXT ───────────────────────────────────────────────────
    "Hank & Tank": "행크 & 탱크",
    "Out The Mud": "아웃 더 머드 | OTM",
    "DarkState": "다크스테이트",
    "Birthright": "버스라이트",
    "The Vanity Project": "더 배니티 프로젝트",
    "The Culling": "더 컬링",
    # ── 규칙이 만드는 팀 ───────────────────────────────────────
    "New Catch Republic": "뉴 캐치 리퍼블릭",
}
"""로스터 CSV의 `Stable&Team` 값 → 한글 표기 (2026-08-10 사용자 지정).

`|`가 들어간 값은 **약칭과 정식 명칭을 함께 쓴다**는 뜻이다(LWO · OTM). 화면이 좁으면
앞을, 넓으면 뒤를 쓴다.

CSV의 표기 흔들림(`The Tongas`·`Darkstate`)은 원본 쪽을 `The Tongans`·`DarkState`로
통일해 없앴다 — 같은 팀이 두 이름으로 들어오면 여기서 한쪽이 조용히 빠진다.
"""


@dataclass(frozen=True)
class ScriptedArc:
    """정해진 전개 한 토막. 굴림이 아니라 달력이 실행한다."""

    week: int
    """이 주차에 일어난다."""
    disband: str = ""
    """이 팀이 해체된다. 빈 값이면 해체 없이 결성만 있는 토막이다."""
    form: str = ""
    """이 이름으로 팀이 생긴다."""
    members: tuple[str, ...] = ()
    """새 팀의 구성원 (한글 표기, `roster.py`와 같은 이름)."""
    renames: tuple[tuple[str, str], ...] = ()
    """(옛 링네임, 새 링네임). 기믹을 벗고 본래 이름으로 돌아오는 자리다."""
    headline: str = ""
    """뉴스 피드에 그대로 실리는 한 줄 (§3-D31)."""


SCRIPTED_ARCS: tuple[ScriptedArc, ...] = (
    ScriptedArc(
        week=3 * WEEKS_PER_YEAR,
        disband="Los Americanos",
        headline="로스 아메리카노스가 해체를 발표했다. 세 사람은 각자의 길을 간다.",
    ),
    ScriptedArc(
        week=6 * WEEKS_PER_YEAR,
        form="New Catch Republic",
        members=("피트 던", "타일러 베이트"),
        renames=(
            ("피트 던 | 라요 아메리카노", "피트 던"),
            ("타일러 베이트 | 브라보 아메리카노", "타일러 베이트"),
        ),
        headline=(
            "라요와 브라보가 가면을 벗었다. 피트 던과 타일러 베이트가 "
            "뉴 캐치 리퍼블릭으로 다시 뭉친다."
        ),
    ),
    ScriptedArc(
        week=8 * WEEKS_PER_YEAR,
        renames=(("엘 그란데 아메리카노 | 루드비히 카이저", "루드비히 카이저"),),
        headline="엘 그란데 아메리카노가 몇 해를 더 뛴 끝에 루드비히 카이저로 돌아왔다.",
    ),
)
"""사용자가 정해 온 전개 (2026-08-10 지시 7-1번).

**해체가 먼저, 복귀가 나중이다.** 셋이 동시에 원래 이름으로 돌아오면 "몇 년 더
활동하다가"라는 조건이 사라진다 — 엘 그란데가 가장 늦게(8년차) 돌아오는 것이 그
지시의 핵심이다.

이름을 되돌리는 일(`renames`)을 팀 해체와 분리한 이유: 로스 아메리카노스가 깨져도
세 사람은 한동안 그 기믹으로 뛴다. 팀이 없어지는 것과 기믹을 벗는 것은 다른 사건이다.
"""

FICTIONAL_TEAM_HEADS: tuple[str, ...] = (
    "블랙",
    "아이언",
    "새비지",
    "리버티",
    "미드나이트",
    "선더",
    "로열",
    "새비지",
    "크림슨",
    "노스",
    "실버",
    "레드",
)
FICTIONAL_TEAM_TAILS: tuple[str, ...] = (
    "다이너스티",
    "브리게이드",
    "클럽",
    "오더",
    "컬렉티브",
    "소사이어티",
    "익스프레스",
    "커넥션",
    "카르텔",
    "유니온",
    "머신",
    "코어",
)
"""규칙이 만드는 팀 이름 조각. 앞뒤를 곱해 144가지가 나온다.

가상 선수 이름과 같은 방식이다(§3-D13-1) — 서른 해 동안 스무 팀 남짓이 생기고 사라지는데
그만큼을 손으로 쓰면 뒤로 갈수록 성의가 떨어진다.
"""

AMPERSAND_SHARE = 0.35
"""이름을 짓지 않고 **"A & B"로 부르는 비율** (2026-08-10 사용자 지시 7-2번).

실제로도 절반 가까운 태그팀이 그냥 두 이름을 붙여 부른다(행크 & 탱크). 전부 이름을
지으면 조합 이름만 서른 개가 쌓여 오히려 이름값이 사라진다.

**태그팀에만 쓴다** — 셋 이상을 앰퍼샌드로 부르는 스테이블은 없다.
"""

FORM_CHANCE_PER_YEAR = 0.9
DISBAND_CHANCE_PER_YEAR = 0.35
"""해마다 팀이 생기고 갈라지는 확률.

결성이 해체보다 높다 — 명부가 30년 동안 통째로 갈리므로(§3-D13-1) 팀도 그만큼
새로 나야 한다. 반대로 잡으면 20년차에 팀이 하나도 안 남는다.
"""

MIN_TEAM_LIFE_WEEKS = 2 * WEEKS_PER_YEAR
"""결성하고 이만큼은 간다. 반년 만에 깨지는 팀은 팀이 아니라 사고다."""

INVITE_CHANCE_PER_YEAR = 0.55
"""플레이어가 팀 제안을 받는 확률. 30년이면 열몇 번쯤 온다."""

DECLINE_HEAT = 14
"""거절이 남기는 열기 (2026-08-10 사용자 지시 7-2번).

**거절은 손해가 아니라 이야기다.** 함께 하자는 제안을 뿌리치면 그 사람과의 관계가
없어지는 게 아니라 다른 방향으로 뜨거워진다.
"""
