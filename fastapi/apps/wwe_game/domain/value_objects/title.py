"""브랜드별 챔피언십과 그랜드슬램 (2026-08-06 사용자 스펙, 남녀 디비전).

**계층(tier)과 벨트(title)는 다르다.** 같은 2선이라도 인터컨티넨탈과 US는 **다른 벨트**이고,
그랜드슬램은 둘 다 요구한다.

**남녀는 벨트 목록 자체가 다르다.** 이름만 다른 게 아니라 개수와 구조가 다르다 —
남성부는 브랜드별 태그팀 벨트가 따로 있지만 **여성부 태그팀은 브랜드 통합**이라 하나뿐이다.
그래서 남성부 10벨트, 여성부 8벨트다 (스피드 포함, §3-D72).

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
EVERY_BRAND: frozenset[Brand] = frozenset(Brand)
"""브랜드 통합 벨트(여성부 태그팀)가 걸려 있는 범위 — **세 브랜드 전부**다.

2026-08-13에 사용자가 바로잡았다("위민스 태그팀 챔피언쉽은 raw, sd, nxt 공용이야").
그전까지는 메인 둘만 걸려 있고 NXT에는 따로 `NXT 위민스 태그팀`이 있었는데, **그 벨트는
실재하지 않는다** — 사용자가 가져온 사진 18장에도 없고, 통합 벨트 한 장만 브랜드 폴더
바깥에 있었다.

**결과 하나를 기록해 둔다**: 여성부는 이제 NXT에 있는 동안에도 태그 그룹을 채울 수 있어
그랜드슬램의 마지막 칸이 메인 로스터 밖에서 열린다. 벨트가 하나뿐이라는 사실의 당연한
따름이고(같은 벨트다), 남성부는 브랜드별로 둘이라 해당 없다.
"""


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
    # ── 스피드 · 브랜드 통합 (§3-D72) ───────────────────────
    WWE_SPEED_CHAMPIONSHIP = "wwe_speed_championship"
    WWE_WOMENS_SPEED_CHAMPIONSHIP = "wwe_womens_speed_championship"


@dataclass(frozen=True)
class TitleSpec:
    title: Title
    gender: Gender
    brands: frozenset[Brand]
    """걸려 있는 브랜드. 대개 하나다.

    **셋에 걸린 벨트가 셋 있다**: 여성부 태그팀(브랜드 통합, §3-D72)과 남녀 스피드.
    다만 이유가 다르다 — 태그팀은 벨트가 하나뿐이라서고, 스피드는 브랜드가 아니라
    **선수의 급**이 자리를 정해서다(`popularity_ceiling`).
    """
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
    popularity_ceiling: int | None = None
    """이 인기도에 닿으면 **더는 도전하지 않는** 벨트 (§3-D72). 없으면 상한이 없다.

    **스피드 벨트뿐이다.** 다른 벨트에는 상한을 두지 않는다 — 정상에 오른 선수가
    아래 벨트를 주우러 가는 것은 §3-D20-3이 정한 그림이고, 그랜드슬램이 거기에
    매여 있다. 스피드만 예외인 이유는 그 벨트의 정의가 급이기 때문이다.
    """


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
    ceiling: int | None = None,
) -> TitleSpec:
    scope = brands if isinstance(brands, frozenset) else frozenset({brands})
    return TitleSpec(
        title, gender, scope, tier, required, difficulty, pop, ir, name, ceiling
    )


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

WORLD_DIFFICULTY = 97
"""메인 로스터 월드 벨트 챔피언의 수준 (2026-08-13에 93에서 올렸다 · §3-D75).

**정상은 아무나 못 간다.** 커리어의 72%가 월드 챔피언이 되고 있었는데, 실제로 월드
벨트를 감는 선수는 로스터의 극히 일부다. 관문(인기도 80)은 그대로 뒀다 — §3-D35가
"병목은 이길 수 있느냐가 아니라 도전 자리에 설 수 있느냐"라고 잡아 둔 결정이고,
관문을 더 올리면 그랜드슬램이 다시 0%로 죽는다.

**난도만으로는 부족했다** — 승률 바닥(`WIN_CHANCE_FLOOR`)에 걸려 100으로 올려도
52%였다. 함께 조인 것은 상금 경기(럼블·챔버·래더)와 가방이다.
"""

SPEED_POPULARITY_REQUIRED = 15
"""스피드 벨트에 도전할 수 있는 인기도 (§3-D72, 2026-08-13 사용자 결정).

목록에서 가장 낮은 관문이다: NXT 태그(12) 바로 위, NXT 노스 아메리칸(25) 아래.
"""

SPEED_POPULARITY_CEILING = 50
"""여기에 닿으면 **더 이상 스피드 벨트에 도전하지 않는다** (§3-D72).

사용자가 자리를 두 번에 걸쳐 잡아 줬다 — "NXT 선수와 메인 로스터 하위 티어용",
그리고 **"전 브랜드가 아니라 NXT 2선 선수 + 메인 로스터 하위 티어"**. 즉 이 벨트를
정하는 것은 **브랜드가 아니라 선수의 급**이다. 브랜드 셋에 다 걸려 있는 것은 그
결과일 뿐, 위민스 태그팀 같은 "통합 벨트"와는 성격이 다르다.

**50은 2선 벨트의 관문값이다**(인터컨티넨탈·US). 그 선을 넘으면 위를 보라는 뜻이고,
그래서 상한과 하위 벨트의 하한이 한 숫자로 맞물린다. 상한이 없으면 인기도 90짜리
챔피언이 스피드 벨트를 감아, 이 벨트가 가리키던 자리가 사라진다.
"""

SPEED_DIFFICULTY = 36
"""스피드 벨트 챔피언의 수준. NXT 태그(32)와 NXT 노스 아메리칸(44) 사이다.

**세 브랜드에 다 걸려 있어 도전 기회 자체는 흔하다** — 난도까지 낮추면 커리어마다
열 번씩 감는 벨트가 된다.
"""

TITLES: dict[Title, TitleSpec] = {
    # ── 남성부 ──────────────────────────────────────────────
    Title.UNDISPUTED_WWE_CHAMPIONSHIP: _s(
        Title.UNDISPUTED_WWE_CHAMPIONSHIP,
        _M,
        Brand.SMACKDOWN,
        _W,
        WORLD_POPULARITY_REQUIRED,
        WORLD_DIFFICULTY,
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
        WORLD_DIFFICULTY,
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
        WORLD_DIFFICULTY,
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
        WORLD_DIFFICULTY,
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
        EVERY_BRAND,
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
    # ── 스피드 (§3-D72) ─────────────────────────────────────
    Title.WWE_SPEED_CHAMPIONSHIP: _s(
        Title.WWE_SPEED_CHAMPIONSHIP,
        _M,
        EVERY_BRAND,
        _S,
        SPEED_POPULARITY_REQUIRED,
        SPEED_DIFFICULTY,
        5,
        3,
        "WWE 스피드 챔피언십",
        SPEED_POPULARITY_CEILING,
    ),
    Title.WWE_WOMENS_SPEED_CHAMPIONSHIP: _s(
        Title.WWE_WOMENS_SPEED_CHAMPIONSHIP,
        _F,
        EVERY_BRAND,
        _S,
        SPEED_POPULARITY_REQUIRED,
        SPEED_DIFFICULTY,
        5,
        3,
        "WWE 위민스 스피드 챔피언십",
        SPEED_POPULARITY_CEILING,
    ),
}

SPEED_TITLES: frozenset[Title] = frozenset(
    {Title.WWE_SPEED_CHAMPIONSHIP, Title.WWE_WOMENS_SPEED_CHAMPIONSHIP}
)
"""**3분 제한이 걸리는 벨트** (§3-D72, 2026-08-13 사용자 스펙).

급이 아니라 이름으로 짚는다. 급(`TitleTier`)은 세 가지 일을 한꺼번에 하는데 —
난도·경기 형식·챔피언 머릿수 — 스피드에 필요한 것은 그중 어느 것도 아니다.
특히 `TitleTier.TAG`는 **둘이 드는 벨트**라는 뜻이라(`title_scene` 재위 인원 2)
스피드에 붙이면 싱글 벨트가 팀 벨트가 된다. 그래서 2선으로 두고 숫자만 낮췄다.
"""

TIER_ORDER: tuple[TitleTier, ...] = (
    TitleTier.WORLD,
    TitleTier.SECONDARY,
    TitleTier.TAG,
)
"""1선 → 3선. 도전 대상을 위에서부터 훑을 때 쓴다."""


def titles_of(brand: Brand, gender: Gender) -> tuple[Title, ...]:
    """그 브랜드·디비전에서 도전 가능한 벨트, **높은 것부터.**

    **급이 아니라 관문값으로 줄 세운다** (§3-D72에서 바뀌었다). 기존 열여섯 벨트에서는
    두 기준이 같은 순서를 냈지만 — 월드 80/40 · 2선 50/25 · 태그 30/12 — 스피드가
    들어오면서 갈렸다. 스피드는 2선이면서 **사다리의 맨 아래**여야 한다.

    급으로 세우면 인기도 30짜리 선수가 태그 벨트 대신 스피드 벨트를 잡는다. 그건
    이 사다리가 답해야 하는 질문("지금 닿는 가장 높은 벨트")의 답이 아니다.

    `TitleTier`는 그대로 남는다 — 재위 인원·경기 형식·급여 배수가 그것을 읽는다.
    """
    return tuple(
        sorted(
            (t for t, s in TITLES.items() if s.gender is gender and brand in s.brands),
            key=lambda t: (
                -TITLES[t].popularity_required,
                -TITLES[t].difficulty,
                t.value,
            ),
        )
    )


def nxt_titles(gender: Gender) -> frozenset[Title]:
    """**NXT에만** 걸린 벨트 (§3-D72에서 뜻이 좁아졌다).

    "NXT에서 도전할 수 있는 벨트"가 아니라 "NXT의 벨트"다. 세 호출부가 전부 이 뜻으로
    읽는다 — 콜업 조건(모두 감았는가) · 콜업 때 반납 · 그랜드슬램에서 배제.

    **통합 벨트가 생기면서 둘이 갈렸다.** 위민스 태그팀과 스피드는 NXT에서도 걸리지만
    NXT의 것이 아니다. 넓은 뜻으로 두면 메인에 올라갈 때 그 벨트를 **빼앗기고**,
    NXT 벨트 석권 조건에도 통합 벨트가 끼어든다.
    """
    return frozenset(
        t
        for t, s in TITLES.items()
        if s.gender is gender and s.brands == frozenset({Brand.NXT})
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
