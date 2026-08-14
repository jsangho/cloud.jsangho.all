"""피니셔 — 경기를 끝내는 그 기술 (하네스 §3-D88).

이 게임에는 **피니셔라는 개념 자체가 없었다.** 스타일(`PlayStyle`)이 생성 때 정해져
서른 해 고정이고, 경기를 끝내는 장면은 나레이션이 그때그때 무브 뱅크에서 뽑았다 —
그러니까 *내* 기술이 아니라 그 밤의 기술이었다.

## 스탯을 건드리지 않는다

§3-D29가 정한 것을 지킨다: **경기력 하나가 진실이고 네 축은 그것을 스타일 비율로 나눈
파생값**이다. 피니셔로 그 축을 재분배하면 "머리글 숫자와 속의 숫자가 어긋나는" 바로
그 문제가 생긴다.

그래서 피니셔는 **판정에 한 톨도 닿지 않는다.** 승패도 별점도 부상도 그대로다.
바뀌는 것은 **그 경기가 어떻게 끝났다고 적히는가** 하나다 — 사용자가 말한
*"피니셔 등 정보를 바꾸는 것"*이 정확히 그 자리다.

값이 없어 보이면 §3-D56을 보면 된다: 별점도 판정에 안 닿지만, 그게 있고 없고가
"좋은 밤"이라는 축의 유무를 갈랐다.

## 계열로 묶는다

스타일이 21종인데 전용 피니셔를 따로 두면 84개를 적어야 하고, 그중 대부분은 서로
구분되지 않는다. **테크니션과 서브미션이 같은 기술을 쓰는 것은 실제로도 자연스럽다** —
`PlayStyle` 열거형이 이미 주석으로 나눠 둔 여섯 계열을 그대로 쓴다.

## 두 갈래로 고른다 (2026-08-14 사용자 결정)

바꿀 때 **먼저 정하는 것은 "무엇을"이 아니라 "어느 쪽으로"다** — 기존 선수들이 쓰는
기술을 가져올지, 이름을 직접 지을지.

| 갈래 | 무엇 |
|---|---|
| 목록에서 | 계열의 여섯 중 하나. 이름과 설명이 이미 있다 |
| 직접 짓는다 | 이름을 내가 쓴다. **링네임과 같은 검증을 지난다** |

직접 지은 이름은 `finisher_name`에 그대로 담긴다. 코드 칸과 나누는 이유: 한 칸에
섞으면 *"모르는 코드"*와 *"내가 지은 이름"*을 구별할 수 없고, 그러면 오타 하나가
조용히 기본값으로 되돌아간다.

## 모두 수플렉스에서 시작한다 (2026-08-14 사용자 결정)

`finisher`가 비어 있으면 **수플렉스**다 — 계열과 무관한 기본기이고, 그래서
*"아직 내 기술이 없다"*가 그대로 읽힌다. 옛 세이브도 새 커리어도 여기서 출발하므로
고르지 않은 것과 못 고른 것을 나누지 않는다.

첫 분기가 지나야 바꿀 수 있다(`finisher_desk.COOLDOWN_WEEKS`) — 처음 바꾸는 그
순간이 **자기 기술을 갖는 장면**이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from wwe_game.domain.exceptions import InvalidFinisherNameError
from wwe_game.domain.value_objects.wrestler_identity import PlayStyle

NAME_MIN_LEN: Final = 2
NAME_MAX_LEN: Final = 20
"""직접 지은 이름의 길이. **링네임과 같은 값이다**(§3-D12) — 둘 다 서술 템플릿의
슬롯으로 들어가므로 들어오는 입구의 규칙이 같아야 한다."""

CUSTOM_CODE: Final = "custom"
"""직접 지은 피니셔의 코드. 목록의 어느 코드와도 겹치지 않는다."""


class MoveFamily(StrEnum):
    """피니셔를 나누는 계열. `PlayStyle`의 주석 구분을 값으로 옮긴 것이다."""

    GRAPPLE = "grapple"
    POWER = "power"
    AERIAL = "aerial"
    STRIKE = "strike"
    SHOW = "show"
    FREE = "free"


FAMILY_OF: Final[dict[PlayStyle, MoveFamily]] = {
    PlayStyle.TECHNICIAN: MoveFamily.GRAPPLE,
    PlayStyle.SUBMISSIONS: MoveFamily.GRAPPLE,
    PlayStyle.SHOOTER: MoveFamily.GRAPPLE,
    PlayStyle.UWF: MoveFamily.GRAPPLE,
    PlayStyle.POWERHOUSE: MoveFamily.POWER,
    PlayStyle.GIANT: MoveFamily.POWER,
    PlayStyle.MONSTER: MoveFamily.POWER,
    PlayStyle.HIGH_FLYER: MoveFamily.AERIAL,
    PlayStyle.LUCHA_LIBRE: MoveFamily.AERIAL,
    PlayStyle.STUNTMAN: MoveFamily.AERIAL,
    PlayStyle.BRAWLER: MoveFamily.STRIKE,
    PlayStyle.HARD_HITTING: MoveFamily.STRIKE,
    PlayStyle.STRONG_STYLE: MoveFamily.STRIKE,
    PlayStyle.KINGS_ROAD: MoveFamily.STRIKE,
    PlayStyle.SHOWMAN: MoveFamily.SHOW,
    PlayStyle.HEEL_STYLE: MoveFamily.SHOW,
    PlayStyle.OLD_SCHOOL: MoveFamily.SHOW,
    PlayStyle.SHOWGIRL: MoveFamily.SHOW,
    PlayStyle.HARDCORE: MoveFamily.FREE,
    PlayStyle.ALL_ROUNDER: MoveFamily.FREE,
    PlayStyle.UNDERDOG: MoveFamily.FREE,
}
"""스타일 → 계열. **21종을 하나도 빠뜨리지 않는다** — 빠지면 그 스타일은 피니셔가
없는 선수가 되고, 테스트가 그걸 잠근다."""


@dataclass(frozen=True)
class Finisher:
    """피니셔 한 종. **수치가 없다** — 판정에 닿지 않기 때문이다."""

    code: str
    name: str
    blurb: str
    """화면에 그대로 나가는 한 줄. 그 기술이 어떤 그림인지."""


def _f(code: str, name: str, blurb: str) -> Finisher:
    return Finisher(code=code, name=name, blurb=blurb)


FINISHERS: Final[dict[MoveFamily, tuple[Finisher, ...]]] = {
    MoveFamily.GRAPPLE: (
        _f("ankle_lock", "앵클 록", "발목을 잠그면 도망갈 곳이 없다."),
        _f("bridging_suplex", "브리징 수플렉스", "다리로 다리를 엮고 어깨를 붙인다."),
        _f("crossface", "크로스페이스", "얼굴을 젖혀 항복을 받아낸다."),
        _f("sleeper", "슬리퍼 홀드", "숨통을 조여 조용히 끝낸다."),
        _f("kimura", "키무라 락", "어깨 관절 하나로 경기를 접는다."),
        _f("figure_four", "피겨 포", "무릎을 묶어 놓고 기다린다."),
    ),
    MoveFamily.POWER: (
        _f("powerbomb", "파워밤", "허공에 한 번 세웠다가 매트에 꽂는다."),
        _f("chokeslam", "초크슬램", "목을 잡아 그대로 내리찍는다."),
        _f("spear", "스피어", "달려가 허리를 접어 버린다."),
        _f("f5", "회전 슬램", "어깨에 올린 뒤 반 바퀴 돌려 던진다."),
        _f("jackhammer", "잭해머", "들어 올린 채로 멈췄다가 떨어뜨린다."),
        _f("torture_rack", "토처 랙", "어깨 위에 얹고 버틴다."),
    ),
    MoveFamily.AERIAL: (
        _f("shooting_star", "슈팅 스타 프레스", "탑로프에서 한 바퀴 돌아 떨어진다."),
        _f("450_splash", "450 스플래시", "공중에서 한 바퀴 반."),
        _f("moonsault", "문설트", "등을 보인 채 뛰어 뒤로 넘는다."),
        _f("frog_splash", "프로그 스플래시", "개구리처럼 몸을 접었다 편다."),
        _f(
            "phoenix_splash",
            "피닉스 스플래시",
            "돌고 또 돈다. 성공하면 그 밤이 남는다.",
        ),
        _f("swanton", "스완톤 밤", "등부터 떨어지는 정직한 낙하."),
    ),
    MoveFamily.STRIKE: (
        _f("running_knee", "러닝 니", "무릎 하나로 끝낸다."),
        _f("lariat", "랠리어트", "달려오는 상대의 목을 팔로 지운다."),
        _f("roundhouse", "라운드하우스 킥", "한 바퀴 돌아 발등으로."),
        _f("headbutt", "다이빙 헤드벗", "머리로 머리를 친다. 몸이 먼저 닳는다."),
        _f("elbow_strike", "엘보 스트라이크", "짧게, 그러나 정확하게."),
        _f("brainbuster", "브레인버스터", "머리부터 세워 떨군다."),
    ),
    MoveFamily.SHOW: (
        _f("stunner", "스터너", "턱을 어깨에 걸고 주저앉는다. 관중이 먼저 안다."),
        _f("pedigree", "페디그리", "두 팔을 묶고 무릎을 꿇린다."),
        _f("peoples_elbow", "관중의 엘보", "링을 두 바퀴 돌고 나서야 떨어진다."),
        _f("diamond_cutter", "다이아몬드 커터", "어디서든, 언제든 나온다."),
        _f("sweet_chin", "슈퍼킥", "발끝이 턱에 닿는 순간 끝난다."),
        _f("spinebuster", "스파인버스터", "허리를 꺾어 매트에 눕힌다."),
    ),
    MoveFamily.FREE: (
        _f("small_package", "스몰 패키지", "가장 낮은 자세에서 가장 빠르게 접는다."),
        _f("roll_up", "롤업", "한 박자 빠른 마무리. 언더독의 무기다."),
        _f("chair_assisted", "철제 의자 마무리", "규칙 밖에서 끝낸다."),
        _f("double_underhook", "더블 언더훅", "팔을 묶고 앞으로 넘긴다."),
        _f("last_ride", "라스트 라이드", "높이 들어 오래 버틴 뒤 떨어뜨린다."),
        _f("backslide", "백슬라이드", "등을 맞대고 미끄러뜨린다."),
    ),
}
"""계열마다 여섯. **여섯인 이유**: 화면에 한 번에 늘어놓을 수 있고, 서른 해에 두어 번
바꾼다고 해도 고를 것이 남는다."""

DEFAULT: Final = _f(
    "suplex",
    "수플렉스",
    "허리를 감아 뒤로 넘긴다. 누구나 배우고, 그래서 아무나 쓰는 기술이다.",
)
"""**모두가 여기서 시작한다** (2026-08-14 사용자 결정).

계열의 첫 기술을 기본값으로 두면 데뷔하자마자 자기 색이 있는 셈이 된다. 수플렉스는
계열을 안 가리는 기본기라, *"아직 내 기술이 없다"*가 그대로 읽힌다 — 첫 분기가 지나
처음 바꾸는 순간이 **자기 기술을 갖는 장면**이 된다.

계열 목록에 넣지 않는다. 어느 계열에도 속하지 않는 것이 이 기술의 자리이고,
`options_for`가 앞에 세워 준다."""

BY_CODE: Final[dict[str, Finisher]] = {
    f.code: f for pool in FINISHERS.values() for f in pool
} | {DEFAULT.code: DEFAULT}


def custom(name: str) -> Finisher:
    """직접 지은 피니셔 (§3-D88).

    **링네임과 같은 검증을 지난다**(§3-D12): 앞뒤 공백을 자르고 2~20자, 제어문자
    금지. 이 이름이 서술 템플릿의 `{finisher}` 슬롯으로 들어가기 때문이다 — 개행이
    섞이면 그 주차의 문장 한 줄이 두 줄로 깨진다.
    """
    if not isinstance(name, str):
        raise InvalidFinisherNameError("기술 이름은 문자열이어야 합니다.")
    stripped = name.strip()
    if any(not ch.isprintable() for ch in stripped):
        raise InvalidFinisherNameError("기술 이름에 제어문자를 넣을 수 없습니다.")
    if not NAME_MIN_LEN <= len(stripped) <= NAME_MAX_LEN:
        raise InvalidFinisherNameError(
            f"기술 이름은 {NAME_MIN_LEN}~{NAME_MAX_LEN}자로 입력해 주세요."
        )
    return Finisher(code=CUSTOM_CODE, name=stripped, blurb="내가 이름 붙인 기술이다.")


MOVES: Final[dict[MoveFamily, tuple[str, ...]]] = {
    MoveFamily.GRAPPLE: (
        "암바",
        "저먼 수플렉스",
        "테이크다운",
        "헤드록",
        "레그록",
        "체인 레슬링",
        "롤업",
        "그라운드 컨트롤",
    ),
    MoveFamily.POWER: (
        "숄더 태클",
        "바디슬램",
        "벨리 투 벨리",
        "코너 스플래시",
        "프레스 슬램",
        "백브레이커",
        "고릴라 프레스",
        "파워슬램",
    ),
    MoveFamily.AERIAL: (
        "드롭킥",
        "허리케인라나",
        "토페 수이시다",
        "스프링보드 크로스바디",
        "아사이 문설트",
        "탑로프 미사일킥",
        "플란차",
        "코너 텀블링",
    ),
    MoveFamily.STRIKE: (
        "치프 킥",
        "엘보 스매시",
        "러닝 드롭킥",
        "니 스트라이크",
        "포어암",
        "빅 부트",
        "백핸드 촙",
        "슈퍼맨 펀치",
    ),
    MoveFamily.SHOW: (
        "네크브레이커",
        "이르시 위프",
        "플라잉 엘보",
        "관중 어필 뒤 태클",
        "드롭 토홀드",
        "스냅 수플렉스",
        "클로스라인",
        "베어 허그",
    ),
    MoveFamily.FREE: (
        "롤링 엘보",
        "스냅 메어",
        "코너 클로스라인",
        "슬링샷 세네턴",
        "암 드래그",
        "레그 스윕",
        "숄더 브레이커",
        "행맨",
    ),
}
"""평범한 한 수의 이름들 (§3-D81-4).

**"기술을 걸었다"만 반복하면 경기를 보는 화면이 아니라 로그가 된다** — 실측 화면에서
같은 문장이 다섯 번 연속 나왔다(2026-08-14 사용자 지적).

피니셔와 같은 계열 표(`FAMILY_OF`)를 쓴다. 나레이션의 `MOVES`(어댑터)와 다른 뱅크인
이유: 저쪽은 **주차 한 줄의 서술 슬롯**이고 이쪽은 **경기 안의 한 수**다. 도메인이
어댑터를 import할 수도 없다(§2 의존 방향).
"""


def moves_for(style: PlayStyle) -> tuple[str, ...]:
    """그 스타일이 경기 중에 쓰는 기술 이름들."""
    return MOVES[family_of(style)]


def family_of(style: PlayStyle) -> MoveFamily:
    return FAMILY_OF[style]


def options_for(style: PlayStyle) -> tuple[Finisher, ...]:
    """그 스타일이 고를 수 있는 피니셔들 — 기본기 하나 + 계열 전부.

    **수플렉스가 목록에 남는다.** 바꾼 뒤에 돌아올 수 있어야 하고, 무엇보다 지금 무엇을
    쓰고 있는지가 목록에서 읽혀야 한다.
    """
    return (DEFAULT, *FINISHERS[family_of(style)])


def default_for(style: PlayStyle) -> Finisher:
    """아직 안 골랐을 때의 피니셔 — **스타일과 무관하게 수플렉스다.**

    비어 있는 것과 못 고른 것을 나누지 않는다: 옛 세이브도 새 커리어도 여기서 시작한다.
    """
    return DEFAULT


def resolve(code: str, name: str, style: PlayStyle) -> Finisher:
    """저장된 값 → 피니셔. **이름 칸이 먼저다** — 직접 지은 것이 있으면 그것이다.

    **모르는 코드에 예외를 던지지 않는다.** 옛 세이브·손댄 세이브가 계열 밖 코드를
    들고 올 수 있고 그때 화면이 죽으면 안 된다 — 피니셔는 판정에 안 닿으므로 조용히
    기본값으로 돌아가는 편이 옳다.

    직접 지은 이름도 같은 방침이다: 검증을 통과 못 하는 값이 저장돼 있으면 기본값으로
    읽는다. 입구(`custom`)에서 이미 막았으므로 여기 오는 것은 손댄 세이브뿐이다.
    """
    if code == CUSTOM_CODE and name:
        try:
            return custom(name)
        except InvalidFinisherNameError:
            return default_for(style)
    found = BY_CODE.get(code)
    if found is None or found not in options_for(style):
        return default_for(style)
    return found
