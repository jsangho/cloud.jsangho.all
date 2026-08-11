"""브랜드별 챔피언십과 그랜드슬램 (2026-08-06 사용자 스펙, 남녀 디비전).

**계층(tier)과 벨트(title)는 다르다.** 같은 2선이라도 인터컨티넨탈과 US는 **다른 벨트**이고,
그랜드슬램은 둘 다 요구한다.

**남녀는 벨트 목록 자체가 다르다.** 이름만 다른 게 아니라 개수와 구조가 다르다 —
남성부는 브랜드별 태그팀 벨트가 따로 있지만 **여성부 태그팀은 브랜드 통합**이라 하나뿐이다.
그래서 남성부 9벨트, 여성부 8벨트다.

**브랜드가 도전 가능한 벨트를 가른다.** 그랜드슬램이 인터컨티넨탈(RAW)과 US(스맥다운)를
둘 다 요구하므로 **커리어 중 최소 한 번은 브랜드를 옮겨야** 한다 — 드래프트가 그 통로다.

커리어는 NXT에서 시작해 콜업으로 메인 로스터에 올라간다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from wwe_game.domain.value_objects.wrestler_identity import Gender


class Brand(StrEnum):
    NXT = "nxt"
    RAW = "raw"
    SMACKDOWN = "smackdown"


MAIN_ROSTER: frozenset[Brand] = frozenset({Brand.RAW, Brand.SMACKDOWN})
BOTH_SHOWS: frozenset[Brand] = MAIN_ROSTER
"""브랜드 통합 벨트(여성부 태그팀)가 걸려 있는 범위."""


class TitleTier(StrEnum):
    WORLD = "world"
    SECONDARY = "secondary"
    TAG = "tag"


class Title(StrEnum):
    # ── 남성부 · 메인 로스터 ────────────────────────────────
    UNDISPUTED_WWE_CHAMPIONSHIP = "undisputed_wwe_championship"
    WORLD_HEAVYWEIGHT_CHAMPIONSHIP = "world_heavyweight_championship"
    UNITED_STATES_CHAMPIONSHIP = "united_states_championship"
    INTERCONTINENTAL_CHAMPIONSHIP = "intercontinental_championship"
    WWE_TAG_TEAM_CHAMPIONSHIP = "wwe_tag_team_championship"
    WORLD_TAG_TEAM_CHAMPIONSHIP = "world_tag_team_championship"
    # ── 남성부 · NXT ────────────────────────────────────────
    NXT_CHAMPIONSHIP = "nxt_championship"
    NXT_NORTH_AMERICAN_CHAMPIONSHIP = "nxt_north_american_championship"
    NXT_TAG_TEAM_CHAMPIONSHIP = "nxt_tag_team_championship"
    # ── 여성부 · 메인 로스터 ────────────────────────────────
    WWE_WOMENS_CHAMPIONSHIP = "wwe_womens_championship"
    WOMENS_WORLD_CHAMPIONSHIP = "womens_world_championship"
    WWE_WOMENS_UNITED_STATES_CHAMPIONSHIP = "wwe_womens_united_states_championship"
    WWE_WOMENS_INTERCONTINENTAL_CHAMPIONSHIP = (
        "wwe_womens_intercontinental_championship"
    )
    WWE_WOMENS_TAG_TEAM_CHAMPIONSHIP = "wwe_womens_tag_team_championship"
    # ── 여성부 · NXT ────────────────────────────────────────
    NXT_WOMENS_CHAMPIONSHIP = "nxt_womens_championship"
    NXT_WOMENS_NORTH_AMERICAN_CHAMPIONSHIP = "nxt_womens_north_american_championship"
    NXT_WOMENS_TAG_TEAM_CHAMPIONSHIP = "nxt_womens_tag_team_championship"


@dataclass(frozen=True)
class TitleSpec:
    title: Title
    gender: Gender
    brands: frozenset[Brand]
    """걸려 있는 브랜드. **여성부 태그팀만 둘 이상**이다 (브랜드 통합)."""
    tier: TitleTier
    popularity_required: int
    difficulty: int
    """상대 챔피언의 수준. 종합점수와 견준다.

    스탯 상한을 100 근처까지 열자(사용자 요청) 종합점수가 90대에 들어가 벨트가 너무
    쉬워졌다 — 그랜드슬램이 83%가 됐다. **임계값(도전 자격)은 스펙대로 두고 난도만**
    올려 균형을 맞췄다. 자격은 인기도가 주고, 결과는 실력이 정한다.
    """
    popularity_reward: int
    in_ring_reward: int
    display_name: str


def _s(
    title: Title,
    gender: Gender,
    brands: frozenset[Brand] | Brand,
    tier: TitleTier,
    required: int,
    difficulty: int,
    pop: int,
    ir: int,
    name: str,
) -> TitleSpec:
    scope = brands if isinstance(brands, frozenset) else frozenset({brands})
    return TitleSpec(title, gender, scope, tier, required, difficulty, pop, ir, name)


_M, _F = Gender.MALE, Gender.FEMALE
_W, _S, _T = TitleTier.WORLD, TitleTier.SECONDARY, TitleTier.TAG

WORLD_POPULARITY_REQUIRED = 80
"""메인 로스터 월드 벨트에 도전할 수 있는 인기도 (§3-D35).

**이 값은 인기도 경제에 매여 있다.** 80이던 시절은 인기도가 100까지 차오르던 때고,
§13-Q13이 경제를 다시 짠 뒤로는 커리어 최고 인기도가 **평균 68.2**다(16판 실측,
80 도달은 1판). 관문만 옛 척도에 남아 **그랜드슬램이 0%로 죽어 있었다.**

**난도(93)는 건드리지 않았다** — 스윕에서 난도를 85로 내려도 그랜드슬램이 그대로였다.
병목은 "이길 수 있느냐"가 아니라 **"도전 자리에 설 수 있느냐"** 하나였다.

인기도 상수를 다시 만지면 이 값도 함께 재야 한다.
"""

TITLES: dict[Title, TitleSpec] = {
    # ── 남성부 ──────────────────────────────────────────────
    Title.UNDISPUTED_WWE_CHAMPIONSHIP: _s(
        Title.UNDISPUTED_WWE_CHAMPIONSHIP,
        _M,
        Brand.SMACKDOWN,
        _W,
        WORLD_POPULARITY_REQUIRED,
        93,
        16,
        7,
        "언디스퓨티드 WWE 챔피언십",
    ),
    Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP: _s(
        Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP,
        _M,
        Brand.RAW,
        _W,
        WORLD_POPULARITY_REQUIRED,
        93,
        16,
        7,
        "월드 헤비웨이트 챔피언십",
    ),
    Title.UNITED_STATES_CHAMPIONSHIP: _s(
        Title.UNITED_STATES_CHAMPIONSHIP,
        _M,
        Brand.SMACKDOWN,
        _S,
        50,
        74,
        9,
        4,
        "유나이티드 스테이츠 챔피언십",
    ),
    Title.INTERCONTINENTAL_CHAMPIONSHIP: _s(
        Title.INTERCONTINENTAL_CHAMPIONSHIP,
        _M,
        Brand.RAW,
        _S,
        50,
        74,
        9,
        4,
        "인터컨티넨탈 챔피언십",
    ),
    Title.WWE_TAG_TEAM_CHAMPIONSHIP: _s(
        Title.WWE_TAG_TEAM_CHAMPIONSHIP,
        _M,
        Brand.SMACKDOWN,
        _T,
        30,
        58,
        6,
        3,
        "WWE 태그팀 챔피언십",
    ),
    Title.WORLD_TAG_TEAM_CHAMPIONSHIP: _s(
        Title.WORLD_TAG_TEAM_CHAMPIONSHIP,
        _M,
        Brand.RAW,
        _T,
        30,
        58,
        6,
        3,
        "월드 태그팀 챔피언십",
    ),
    Title.NXT_CHAMPIONSHIP: _s(
        Title.NXT_CHAMPIONSHIP, _M, Brand.NXT, _W, 40, 58, 10, 5, "NXT 챔피언십"
    ),
    Title.NXT_NORTH_AMERICAN_CHAMPIONSHIP: _s(
        Title.NXT_NORTH_AMERICAN_CHAMPIONSHIP,
        _M,
        Brand.NXT,
        _S,
        25,
        44,
        6,
        3,
        "NXT 노스 아메리칸 챔피언십",
    ),
    Title.NXT_TAG_TEAM_CHAMPIONSHIP: _s(
        Title.NXT_TAG_TEAM_CHAMPIONSHIP,
        _M,
        Brand.NXT,
        _T,
        12,
        32,
        4,
        2,
        "NXT 태그팀 챔피언십",
    ),
    # ── 여성부 ──────────────────────────────────────────────
    Title.WWE_WOMENS_CHAMPIONSHIP: _s(
        Title.WWE_WOMENS_CHAMPIONSHIP,
        _F,
        Brand.SMACKDOWN,
        _W,
        WORLD_POPULARITY_REQUIRED,
        93,
        16,
        7,
        "WWE 위민스 챔피언십",
    ),
    Title.WOMENS_WORLD_CHAMPIONSHIP: _s(
        Title.WOMENS_WORLD_CHAMPIONSHIP,
        _F,
        Brand.RAW,
        _W,
        WORLD_POPULARITY_REQUIRED,
        93,
        16,
        7,
        "위민스 월드 챔피언십",
    ),
    Title.WWE_WOMENS_UNITED_STATES_CHAMPIONSHIP: _s(
        Title.WWE_WOMENS_UNITED_STATES_CHAMPIONSHIP,
        _F,
        Brand.SMACKDOWN,
        _S,
        50,
        74,
        9,
        4,
        "WWE 위민스 유나이티드 스테이츠 챔피언십",
    ),
    Title.WWE_WOMENS_INTERCONTINENTAL_CHAMPIONSHIP: _s(
        Title.WWE_WOMENS_INTERCONTINENTAL_CHAMPIONSHIP,
        _F,
        Brand.RAW,
        _S,
        50,
        74,
        9,
        4,
        "WWE 위민스 인터컨티넨탈 챔피언십",
    ),
    Title.WWE_WOMENS_TAG_TEAM_CHAMPIONSHIP: _s(
        Title.WWE_WOMENS_TAG_TEAM_CHAMPIONSHIP,
        _F,
        BOTH_SHOWS,
        _T,
        30,
        58,
        6,
        3,
        "WWE 위민스 태그팀 챔피언십",
    ),
    Title.NXT_WOMENS_CHAMPIONSHIP: _s(
        Title.NXT_WOMENS_CHAMPIONSHIP,
        _F,
        Brand.NXT,
        _W,
        40,
        58,
        10,
        5,
        "NXT 위민스 챔피언십",
    ),
    Title.NXT_WOMENS_NORTH_AMERICAN_CHAMPIONSHIP: _s(
        Title.NXT_WOMENS_NORTH_AMERICAN_CHAMPIONSHIP,
        _F,
        Brand.NXT,
        _S,
        25,
        44,
        6,
        3,
        "NXT 위민스 노스 아메리칸 챔피언십",
    ),
    Title.NXT_WOMENS_TAG_TEAM_CHAMPIONSHIP: _s(
        Title.NXT_WOMENS_TAG_TEAM_CHAMPIONSHIP,
        _F,
        Brand.NXT,
        _T,
        12,
        32,
        4,
        2,
        "NXT 위민스 태그팀 챔피언십",
    ),
}

TIER_ORDER: tuple[TitleTier, ...] = (
    TitleTier.WORLD,
    TitleTier.SECONDARY,
    TitleTier.TAG,
)
"""1선 → 3선. 도전 대상을 위에서부터 훑을 때 쓴다."""


def titles_of(brand: Brand, gender: Gender) -> tuple[Title, ...]:
    """그 브랜드·디비전에서 도전 가능한 벨트, 1선부터."""
    rank = {tier: i for i, tier in enumerate(TIER_ORDER)}
    return tuple(
        sorted(
            (t for t, s in TITLES.items() if s.gender is gender and brand in s.brands),
            key=lambda t: rank[TITLES[t].tier],
        )
    )


def nxt_titles(gender: Gender) -> frozenset[Title]:
    return frozenset(
        t for t, s in TITLES.items() if s.gender is gender and Brand.NXT in s.brands
    )


# ── 그랜드슬램 ───────────────────────────────────────────────

_GroupSpec = tuple[tuple[str, frozenset[Title]], ...]

GRAND_SLAM_GROUPS: dict[Gender, _GroupSpec] = {
    Gender.MALE: (
        (
            "월드",
            frozenset(
                {
                    Title.UNDISPUTED_WWE_CHAMPIONSHIP,
                    Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP,
                }
            ),
        ),
        ("인터컨티넨탈", frozenset({Title.INTERCONTINENTAL_CHAMPIONSHIP})),
        ("US", frozenset({Title.UNITED_STATES_CHAMPIONSHIP})),
        (
            "태그팀",
            frozenset(
                {
                    Title.WORLD_TAG_TEAM_CHAMPIONSHIP,
                    Title.WWE_TAG_TEAM_CHAMPIONSHIP,
                }
            ),
        ),
    ),
    Gender.FEMALE: (
        (
            "월드",
            frozenset(
                {
                    Title.WWE_WOMENS_CHAMPIONSHIP,
                    Title.WOMENS_WORLD_CHAMPIONSHIP,
                }
            ),
        ),
        ("인터컨티넨탈", frozenset({Title.WWE_WOMENS_INTERCONTINENTAL_CHAMPIONSHIP})),
        ("US", frozenset({Title.WWE_WOMENS_UNITED_STATES_CHAMPIONSHIP})),
        ("태그팀", frozenset({Title.WWE_WOMENS_TAG_TEAM_CHAMPIONSHIP})),
    ),
}
"""네 그룹을 모두 채워야 그랜드슬램이다 (2026-08-06 스펙).

월드는 두 벨트 중 하나면 되고, 인터컨티넨탈과 US는 각각 필요하다.

**남녀의 차이는 태그팀 그룹이다.** 남성부는 브랜드별 두 벨트 중 하나면 되지만,
여성부는 브랜드 통합 벨트가 하나뿐이라 선택지가 없다 — 대신 어느 브랜드에 있든
도전할 수 있어 난도는 비슷하다.

**NXT 벨트는 포함되지 않는다.** 그랜드슬램은 메인 로스터의 업적이다.
"""


def group_counts(won: Sequence[Title], gender: Gender) -> dict[str, int]:
    """그룹별 획득 횟수 합계. 같은 그룹 안에서는 어느 벨트든 합산한다."""
    return {
        name: sum(won.count(t) for t in group)
        for name, group in GRAND_SLAM_GROUPS[gender]
    }


def grand_slam_level(won: Sequence[Title], gender: Gender) -> int:
    """0 미달 · 1 그랜드슬램 · 2 더블 그랜드슬램 · 그 이상도 같은 식.

    네 그룹 중 **가장 적게 채운 그룹**이 등급을 정한다. 월드 벨트를 다섯 번 감아도
    US가 없으면 0이다.
    """
    return min(group_counts(won, gender).values())


def missing_groups(
    won: Sequence[Title], gender: Gender, *, level: int = 1
) -> tuple[str, ...]:
    return tuple(n for n, c in group_counts(won, gender).items() if c < level)


def titles_for_group(name: str, gender: Gender) -> frozenset[Title]:
    for group_name, group in GRAND_SLAM_GROUPS[gender]:
        if group_name == name:
            return group
    raise KeyError(name)  # pragma: no cover


# ── 임포트 시 구조 검증 ──────────────────────────────────────

for _g in Gender:  # pragma: no cover
    for _b in Brand:
        _tiers = {TITLES[t].tier for t in titles_of(_b, _g)}
        if _tiers != set(TIER_ORDER):
            raise RuntimeError(f"{_g}/{_b}에 1선·2선·태그가 다 있지 않습니다: {_tiers}")
    _slam = {t for _, grp in GRAND_SLAM_GROUPS[_g] for t in grp}
    if _slam & nxt_titles(_g):
        raise RuntimeError(f"{_g} 그랜드슬램에 NXT 벨트가 섞였습니다")
    if any(TITLES[t].gender is not _g for t in _slam):
        raise RuntimeError(f"{_g} 그랜드슬램에 다른 디비전 벨트가 섞였습니다")

for _spec in TITLES.values():  # pragma: no cover
    if _spec.popularity_reward == _spec.in_ring_reward:
        raise RuntimeError(f"{_spec.title}: 인기도와 경기력 보상이 같습니다")
