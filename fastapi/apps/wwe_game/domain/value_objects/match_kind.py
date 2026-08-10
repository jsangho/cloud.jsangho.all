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
    # 럼블·챔버·래더는 큰 무대의 경기다 — 이기기 어렵고 몸이 더 상한다.
    MatchKind.BATTLE_ROYAL: MatchFormat("로열럼블 매치", 30, 0.22, 1.4, 1.3),
    MatchKind.CHAMBER: MatchFormat("엘리미네이션 챔버 매치", 6, 0.44, 1.5, 1.5),
    MatchKind.LADDER: MatchFormat("래더 매치", 8, 0.38, 1.6, 1.7),
    MatchKind.WARGAMES: MatchFormat("워게임즈 매치", 10, 0.50, 1.5, 1.4),
}


SIGNATURE_MATCHES: dict[str, MatchKind] = {
    "로열럼블": MatchKind.BATTLE_ROYAL,
    "엘리미네이션 챔버": MatchKind.CHAMBER,
    "머니 인 더 뱅크": MatchKind.LADDER,
    "서바이버 시리즈": MatchKind.WARGAMES,
}
"""대회 이름 → 그 대회에만 있는 경기 (2026-08-10 사용자 요청).

**반드시 열린다.** 확률로 두면 로열럼블이 없는 해가 생기고, 그건 그 대회가 아니다.
`킹 앤 퀸 오브 더 링`은 토너먼트라 여기 없다 — 한 주에 끝나지 않는 형식이라
공석 토너먼트(§3-D33)와 같은 자리에서 다룬다.
"""

QUALIFIER_KINDS: tuple[MatchKind, ...] = (
    MatchKind.SINGLES,
    MatchKind.TRIPLE_THREAT,
    MatchKind.FATAL_FOUR_WAY,
)
"""예선에 쓸 수 있는 형식. 싱글부터 페이탈 포 웨이까지다 (2026-08-10 사용자 스펙)."""


def format_of(kind: MatchKind) -> MatchFormat:
    return FORMATS[kind]


for _kind in MatchKind:  # pragma: no cover - 임포트 시 구조 검증
    if _kind not in FORMATS:
        raise RuntimeError(f"경기 형식 표가 없습니다: {_kind}")
