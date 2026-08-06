"""라이벌·챔피언으로 쓸 실존 선수 이름 (하네스 §3-D13).

**kayfabe의 로스터를 import할 수 없다** — 스포크끼리는 못 붙는다(§2-D3). 그래서 게임용
목록을 따로 둔다. 감수하는 것은 **이중 관리**이고, 게임은 실시간성이 필요 없으므로
목록이 조금 어긋나도 치명적이지 않다는 판단이다.

담는 것은 **이름·디비전·주 활동 권역·대략적 등급** 넷뿐이다. 카드·배당 같은 kayfabe
데이터는 복제하지 않는다.

실존 인물이므로 **서술이 사실 주장처럼 읽히지 않아야** 한다 — 게임 내 가상 전개임을
생성 화면과 로그 하단에 표시한다(§3-D13).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from wwe_game.domain.constants.countries import Region
from wwe_game.domain.value_objects.wrestler_identity import Gender


class RivalTier(IntEnum):
    """대략적 등급. 대립 상대를 고를 때 플레이어 인기도와 맞춘다."""

    PROSPECT = 1
    MIDCARD = 2
    MAIN_EVENT = 3


@dataclass(frozen=True)
class RosterMember:
    name: str
    gender: Gender
    region: Region
    tier: RivalTier


_M, _F = Gender.MALE, Gender.FEMALE
_P, _MC, _ME = RivalTier.PROSPECT, RivalTier.MIDCARD, RivalTier.MAIN_EVENT
_NA, _EU, _JP, _LA, _OC = (
    Region.NA,
    Region.EU,
    Region.JP,
    Region.LATAM,
    Region.OCE,
)

ROSTER: tuple[RosterMember, ...] = (
    # ── 남성부 · 메인이벤트 ─────────────────────────────────
    RosterMember("로만 레인즈", _M, _NA, _ME),
    RosterMember("코디 로즈", _M, _NA, _ME),
    RosterMember("세스 롤린스", _M, _NA, _ME),
    RosterMember("CM 펑크", _M, _NA, _ME),
    RosterMember("드류 매킨타이어", _M, _EU, _ME),
    RosterMember("건서", _M, _EU, _ME),
    RosterMember("랜디 오턴", _M, _NA, _ME),
    RosterMember("브론 브레이커", _M, _NA, _ME),
    # ── 남성부 · 미드카드 ───────────────────────────────────
    RosterMember("데미언 프리스트", _M, _NA, _MC),
    RosterMember("핀 밸러", _M, _EU, _MC),
    RosterMember("LA 나이트", _M, _NA, _MC),
    RosterMember("케빈 오웬스", _M, _NA, _MC),
    RosterMember("새미 제인", _M, _NA, _MC),
    RosterMember("제이 우소", _M, _OC, _MC),
    RosterMember("지미 우소", _M, _OC, _MC),
    RosterMember("솔로 시코아", _M, _OC, _MC),
    RosterMember("일리야 드라구노프", _M, _EU, _MC),
    RosterMember("셰이머스", _M, _EU, _MC),
    RosterMember("AJ 스타일스", _M, _NA, _MC),
    RosterMember("바비 래슐리", _M, _NA, _MC),
    RosterMember("채드 게이블", _M, _NA, _MC),
    RosterMember("리코셰", _M, _NA, _MC),
    RosterMember("도미닉 미스테리오", _M, _LA, _MC),
    RosterMember("레이 미스테리오", _M, _LA, _MC),
    RosterMember("산토스 에스코바", _M, _LA, _MC),
    RosterMember("카멜로 헤이즈", _M, _NA, _MC),
    # ── 남성부 · 유망주 ─────────────────────────────────────
    RosterMember("트릭 윌리엄스", _M, _NA, _P),
    RosterMember("오바 페미", _M, _EU, _P),
    RosterMember("제본 에번스", _M, _NA, _P),
    RosterMember("이선 페이지", _M, _NA, _P),
    RosterMember("토니 단젤로", _M, _NA, _P),
    RosterMember("네이선 프레이저", _M, _EU, _P),
    RosterMember("오스틴 테오리", _M, _NA, _P),
    RosterMember("그레이슨 월러", _M, _OC, _P),
    # ── 여성부 · 메인이벤트 ─────────────────────────────────
    RosterMember("리아 리플리", _F, _OC, _ME),
    RosterMember("비앙카 벨에어", _F, _NA, _ME),
    RosterMember("베키 린치", _F, _EU, _ME),
    RosterMember("이요 스카이", _F, _JP, _ME),
    RosterMember("아스카", _F, _JP, _ME),
    RosterMember("제이드 카길", _F, _NA, _ME),
    # ── 여성부 · 미드카드 ───────────────────────────────────
    RosterMember("베일리", _F, _NA, _MC),
    RosterMember("카이리 세인", _F, _JP, _MC),
    RosterMember("리브 모건", _F, _NA, _MC),
    RosterMember("라켈 로드리게스", _F, _LA, _MC),
    RosterMember("티파니 스트래턴", _F, _NA, _MC),
    RosterMember("나오미", _F, _NA, _MC),
    RosterMember("젤리나 베가", _F, _LA, _MC),
    RosterMember("첼시 그린", _F, _NA, _MC),
    RosterMember("파이퍼 니븐", _F, _EU, _MC),
    RosterMember("셰이나 배즐러", _F, _NA, _MC),
    RosterMember("니아 잭스", _F, _OC, _MC),
    RosterMember("리라 발키리아", _F, _EU, _MC),
    # ── 여성부 · 유망주 ─────────────────────────────────────
    RosterMember("록산 페레즈", _F, _LA, _P),
    RosterMember("테이텀 팩슬리", _F, _NA, _P),
    RosterMember("코라 제이드", _F, _NA, _P),
    RosterMember("자이다 파커", _F, _NA, _P),
    RosterMember("솔 루카", _F, _NA, _P),
    RosterMember("팰런 헨리", _F, _NA, _P),
)


def pool_for(gender: Gender, tier: RivalTier) -> tuple[str, ...]:
    """디비전과 등급에 맞는 이름들. 성별로 라이벌 풀이 갈린다(§3-D11)."""
    return tuple(m.name for m in ROSTER if m.gender is gender and m.tier is tier)


def tier_for_popularity(popularity: int) -> RivalTier:
    """인기도에 맞는 상대 등급. **급이 맞아야 대립이 성립한다.**

    무명이 월드 챔피언과 대립하는 것도, 정상급이 유망주와 몇 달을 싸우는 것도
    이야기가 되지 않는다.
    """
    if popularity >= 60:
        return RivalTier.MAIN_EVENT
    if popularity >= 30:
        return RivalTier.MIDCARD
    return RivalTier.PROSPECT


# 어느 (디비전 × 등급) 칸도 비면 안 된다 — 비면 대립 상대를 못 고른다.
for _g in Gender:  # pragma: no cover - 임포트 시 구조 검증
    for _t in RivalTier:
        if len(pool_for(_g, _t)) < 4:
            raise RuntimeError(
                f"{_g}/{_t} 라이벌 풀이 너무 작습니다: {pool_for(_g, _t)}"
            )
