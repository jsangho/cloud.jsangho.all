"""경기 형식 — 몇 명이 붙고 어떤 규칙인가 (하네스 §3-D32).

지금까지 모든 경기가 싱글이었다. 프로레슬링에서 **대회를 대회로 만드는 것은 그
대회에만 있는 경기**다 — 로열럼블 없는 로열럼블은 그냥 1월 대회일 뿐이다
(2026-08-10 사용자 요청).

## 인원이 승률을 정한다

경기 형식이 승률에 곱하는 배수를 함께 든다. 30인 럼블에서 이길 확률이 싱글과
같으면 럼블이 아니다 — **자리가 늘수록 내 몫이 준다.** 다만 인원의 역수를 그대로
쓰지는 않는다(30분의 1이면 30년에 한 번도 못 이긴다): 주인공 보정으로 완만하게
깎는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MatchKind(StrEnum):
    SINGLES = "singles"
    TRIPLE_THREAT = "triple_threat"
    FATAL_FOUR_WAY = "fatal_four_way"
    TAG = "tag"
    BATTLE_ROYAL = "battle_royal"
    """로열럼블 — 30명이 차례로 들어와 넘어뜨린다."""
    CHAMBER = "chamber"
    """엘리미네이션 챔버 — 여섯이 철창 안에서."""
    LADDER = "ladder"
    """머니 인 더 뱅크 — 사다리 위의 가방."""
    WARGAMES = "wargames"
    """서바이버 시리즈 — 두 팀이 두 링 위에서."""
    SURVIVOR_ELIMINATION = "survivor_elimination"
    """서바이버 시리즈의 옛 얼굴 — 5 대 5로 하나씩 지워 나간다 (§3-D71)."""
    SPEED = "speed"
    """스피드 챔피언십 — **3분 안에 끝내야 한다** (§3-D72, 2026-08-13 사용자 스펙)."""
    SUDDEN_DEATH = "sudden_death"
    """3분이 지나도 안 끝났을 때 이어서 여는 경기 (§3-D72). **여기서는 무승부가 없다.**"""
    STREET_FIGHT = "street_fight"
    """노 디스퀄리피케이션 — 둘이 붙되 규칙이 없다."""
    STEEL_CAGE = "steel_cage"
    """스틸 케이지 — 도망칠 데가 없다."""
    # ── 무규칙 계열 — 반칙이 없으니 몸으로 갚는다 ──────────────
    NO_DQ = "no_dq"
    NO_HOLDS_BARRED = "no_holds_barred"
    EXTREME_RULES = "extreme_rules"
    UNSANCTIONED = "unsanctioned"
    """언생션드 — 단체가 승인하지 않은 경기. 다쳐도 보호받지 못한다."""
    HELL_IN_A_CELL = "hell_in_a_cell"
    TLC = "tlc"
    TABLES = "tables"
    LAST_MAN_STANDING = "last_man_standing"
    # ── 기술 계열 — 오래 끌되 덜 다친다 ────────────────────────
    SUBMISSION_MATCH = "submission_match"
    IRON_MAN = "iron_man"
    TWO_OUT_OF_THREE_FALLS = "two_out_of_three_falls"
    I_QUIT = "i_quit"
    # ── 머릿수 계열 — 이기기가 어렵다 ──────────────────────────
    HANDICAP = "handicap"
    GAUNTLET = "gauntlet"
    LUMBERJACK = "lumberjack"


@dataclass(frozen=True)
class MatchFormat:
    label: str
    field: int
    """참가 인원. 화면과 승률 보정이 함께 읽는다."""
    win_factor: float
    """승률 배수. 인원의 역수가 아니라 **완만한 곡선**이다 (모듈 설명 참조)."""
    wear_factor: float = 1.0
    injury_factor: float = 1.0


FORMATS: dict[MatchKind, MatchFormat] = {
    MatchKind.SINGLES: MatchFormat("싱글 매치", 2, 1.0),
    MatchKind.TRIPLE_THREAT: MatchFormat("트리플 스렛", 3, 0.72, 1.1, 1.1),
    MatchKind.FATAL_FOUR_WAY: MatchFormat("페이탈 포 웨이", 4, 0.58, 1.2, 1.2),
    MatchKind.TAG: MatchFormat("태그팀 매치", 4, 0.95),
    # 상금이 걸린 세 경기 — **주인공 보정이 없다** (§3-D36).
    #
    # 우승이 그 밤에서 끝나지 않고 레슬매니아 도전권·가방으로 이어지므로, 이기는
    # 일 자체가 드물어야 한다(2026-08-11 사용자 지침 "얻기 힘들어"). 챔버·래더는
    # 공평한 몫(1/6 · 1/8)보다도 **낮다**: 그 링에 선 나머지가 전부 정상급이라
    # 주인공이라고 유리할 이유가 없다. 럼블만 몫의 두 배인데, 1/30을 그대로 쓰면
    # 30년에 한 번도 못 이긴다.
    #
    # 실측(커리어당 우승): 럼블 0.8 · 챔버 1.2 · MITB 1.2 — 대개 한 번, 없는 커리어도 있다.
    MatchKind.BATTLE_ROYAL: MatchFormat("로열럼블 매치", 30, 0.06, 1.4, 1.3),
    MatchKind.CHAMBER: MatchFormat("엘리미네이션 챔버 매치", 6, 0.11, 1.5, 1.5),
    MatchKind.LADDER: MatchFormat("래더 매치", 8, 0.09, 1.6, 1.7),
    MatchKind.WARGAMES: MatchFormat("워게임즈 매치", 10, 0.50, 1.5, 1.4),
    # 철창이 없는 대신 머릿수가 같다 — 이기기는 비슷하고 몸은 덜 상한다 (§3-D71).
    MatchKind.SURVIVOR_ELIMINATION: MatchFormat(
        "5 대 5 일리미네이션 태그 매치", 10, 0.50, 1.3, 1.1
    ),
    # 스피드 (§3-D72). **3분이면 몸이 상할 틈이 없다** — 마모도 부상도 싱글 아래다.
    # 서든 데스는 그 3분을 이미 쓰고 다시 붙는 것이라 반대로 싱글보다 위다.
    MatchKind.SPEED: MatchFormat("스피드 매치 (3분)", 2, 1.0, 0.6, 0.5),
    MatchKind.SUDDEN_DEATH: MatchFormat("서든 데스 매치", 2, 1.0, 1.3, 1.2),
    # 둘이 붙는 특수 경기 — 승률은 싱글과 같고 몸만 더 상한다.
    MatchKind.STREET_FIGHT: MatchFormat("스트리트 파이트", 2, 1.0, 1.5, 1.6),
    MatchKind.STEEL_CAGE: MatchFormat("스틸 케이지 매치", 2, 1.0, 1.3, 1.3),
    # 무규칙 계열 — 승률은 그대로고 몸값만 오른다. 언생션드가 가장 비싸다:
    # 단체가 승인하지 않은 경기라 다쳐도 보호받지 못한다.
    MatchKind.NO_DQ: MatchFormat("노 디스퀄리피케이션 매치", 2, 1.0, 1.4, 1.5),
    MatchKind.NO_HOLDS_BARRED: MatchFormat("노 홀즈 바드 매치", 2, 1.0, 1.5, 1.6),
    MatchKind.EXTREME_RULES: MatchFormat("엑스트림 룰즈 매치", 2, 1.0, 1.6, 1.7),
    MatchKind.UNSANCTIONED: MatchFormat("언생션드 매치", 2, 1.0, 1.8, 2.1),
    MatchKind.HELL_IN_A_CELL: MatchFormat("헬 인 어 셀", 2, 1.0, 1.9, 1.9),
    MatchKind.TLC: MatchFormat("TLC 매치", 2, 1.0, 1.8, 1.8),
    MatchKind.TABLES: MatchFormat("테이블 매치", 2, 1.0, 1.4, 1.5),
    MatchKind.LAST_MAN_STANDING: MatchFormat("라스트 맨 스탠딩", 2, 1.0, 1.7, 1.6),
    # 기술 계열 — 길게 끌어 마모는 쌓이되 다치지는 않는다.
    MatchKind.SUBMISSION_MATCH: MatchFormat("서브미션 매치", 2, 1.0, 1.2, 0.8),
    MatchKind.IRON_MAN: MatchFormat("아이언맨 매치", 2, 1.0, 1.9, 0.9),
    MatchKind.TWO_OUT_OF_THREE_FALLS: MatchFormat(
        "2 아웃 오브 3 폴스", 2, 1.0, 1.5, 0.9
    ),
    MatchKind.I_QUIT: MatchFormat("아이 큇 매치", 2, 1.0, 1.4, 1.2),
    # 머릿수 계열 — 몸은 덜 상해도 이기기가 어렵다.
    MatchKind.HANDICAP: MatchFormat("핸디캡 매치", 3, 0.55, 1.3, 1.2),
    MatchKind.GAUNTLET: MatchFormat("가운틀릿 매치", 5, 0.40, 1.8, 1.3),
    MatchKind.LUMBERJACK: MatchFormat("럼버잭 매치", 2, 0.90, 1.2, 1.2),
}


SIGNATURE_MATCHES: dict[str, MatchKind] = {
    "로열럼블": MatchKind.BATTLE_ROYAL,
    "엘리미네이션 챔버": MatchKind.CHAMBER,
    "머니 인 더 뱅크": MatchKind.LADDER,
    "서바이버 시리즈: 워게임즈": MatchKind.WARGAMES,
    "서바이버 시리즈": MatchKind.SURVIVOR_ELIMINATION,
}
"""대회 이름 → 그 대회에만 있는 경기 (2026-08-10 사용자 요청).

**반드시 열린다.** 확률로 두면 로열럼블이 없는 해가 생기고, 그건 그 대회가 아니다.
토너먼트는 여기 없다 — 한 주에 끝나지 않는 형식이라 공석 토너먼트(§3-D33)와 같은
자리에서 다룬다.

**서바이버 시리즈가 두 줄인 이유** (§3-D71): 그 밤은 해마다 얼굴이 갈리고, 이름이 곧
그 손잡이다. 워게임즈인 해와 전통 제거 매치인 해는 링 위의 형식도 달라야 한다.
"""

STIPULATION_ODDS: tuple[tuple[MatchKind, int], ...] = (
    # 흔한 것부터. 트리플 스렛은 TV에서도 자주 보이고, 헬 인 어 셀은 한 해에
    # 한두 번 있을까 말까다.
    (MatchKind.TRIPLE_THREAT, 30),
    (MatchKind.NO_DQ, 22),
    (MatchKind.STEEL_CAGE, 18),
    (MatchKind.STREET_FIGHT, 18),
    (MatchKind.SUBMISSION_MATCH, 16),
    (MatchKind.FATAL_FOUR_WAY, 14),
    (MatchKind.LUMBERJACK, 12),
    (MatchKind.NO_HOLDS_BARRED, 12),
    (MatchKind.TABLES, 11),
    (MatchKind.TWO_OUT_OF_THREE_FALLS, 10),
    (MatchKind.EXTREME_RULES, 10),
    (MatchKind.LADDER, 10),
    (MatchKind.LAST_MAN_STANDING, 8),
    (MatchKind.HANDICAP, 7),
    (MatchKind.I_QUIT, 6),
    (MatchKind.TLC, 6),
    (MatchKind.GAUNTLET, 5),
    (MatchKind.IRON_MAN, 4),
    (MatchKind.HELL_IN_A_CELL, 3),
    (MatchKind.UNSANCTIONED, 2),
)
"""평범한 주차가 특수 경기로 바뀔 때의 가중치 (2026-08-10 사용자 요청).

**시그니처와 다르다.** 시그니처는 그 대회에만 있는 경기라 달력이 반드시 실행하고,
이쪽은 아무 경기나 가끔 특별해지는 것이다 — 실제로도 래더나 케이지는 MITB가
아닌 밤에도 걸린다.

럼블·챔버·워게임즈는 여기 없다. 그 셋은 무대 장치가 그 대회의 것이라, 5월
백래시에서 엘리미네이션 챔버가 열리면 챔버가 특별할 이유가 사라진다.

가중치는 **자주 볼수록 높다** — 트리플 스렛이 가장 흔하고 래더가 가장 드물다.
"""

STIPULATION_CHANCE = 0.035
"""경기 한 번이 특수 경기가 될 기본 확률. 커리어당 서른 번쯤 나온다."""

STIPULATION_PLE_MULTIPLIER = 3.0
"""대회에서는 세 배. **특수 경기는 큰 밤의 것**이라 주간 방송에서는 드물어야 한다."""

STYLE_AFFINITY: dict[str, tuple[MatchKind, ...]] = {
    "hardcore": (
        MatchKind.NO_DQ,
        MatchKind.NO_HOLDS_BARRED,
        MatchKind.EXTREME_RULES,
        MatchKind.TLC,
        MatchKind.TABLES,
        MatchKind.STREET_FIGHT,
        MatchKind.UNSANCTIONED,
    ),
    "stuntman": (MatchKind.LADDER, MatchKind.TLC, MatchKind.TABLES),
    "submissions": (MatchKind.SUBMISSION_MATCH, MatchKind.I_QUIT),
    "technician": (MatchKind.SUBMISSION_MATCH, MatchKind.IRON_MAN),
    "uwf": (MatchKind.SUBMISSION_MATCH, MatchKind.I_QUIT),
    "kings_road": (MatchKind.IRON_MAN, MatchKind.TWO_OUT_OF_THREE_FALLS),
    "monster": (MatchKind.HANDICAP, MatchKind.LAST_MAN_STANDING),
    "giant": (MatchKind.HANDICAP, MatchKind.GAUNTLET),
    "heel_style": (MatchKind.LUMBERJACK, MatchKind.STEEL_CAGE),
}
"""경기 유형 → 그 선수에게 더 자주 걸리는 특수 경기 (2026-08-10).

**하드코어 선수에게 서브미션 매치만 걸리면 그 스타일을 고른 의미가 없다.** 자기
색깔에 맞는 무대가 더 자주 오는 편이 맞고, 그렇다고 다른 경기가 막히지는 않는다 —
가중치를 곱할 뿐이다.
"""

STYLE_AFFINITY_MULTIPLIER = 3
"""자기 계열 특수 경기의 가중치 배수."""

QUALIFIER_KINDS: tuple[MatchKind, ...] = (
    MatchKind.SINGLES,
    MatchKind.TRIPLE_THREAT,
    MatchKind.FATAL_FOUR_WAY,
)
"""예선에 쓸 수 있는 형식. 싱글부터 페이탈 포 웨이까지다 (2026-08-10 사용자 스펙)."""


def format_of(kind: MatchKind) -> MatchFormat:
    return FORMATS[kind]


def stipulation_odds(play_style: str) -> tuple[tuple[MatchKind, int], ...]:
    """그 스타일이 겪는 특수 경기 가중치. 자기 계열이 세 배로 자주 온다."""
    favored = set(STYLE_AFFINITY.get(play_style, ()))
    return tuple(
        (kind, weight * STYLE_AFFINITY_MULTIPLIER if kind in favored else weight)
        for kind, weight in STIPULATION_ODDS
    )


for _kind in MatchKind:  # pragma: no cover - 임포트 시 구조 검증
    if _kind not in FORMATS:
        raise RuntimeError(f"경기 형식 표가 없습니다: {_kind}")
