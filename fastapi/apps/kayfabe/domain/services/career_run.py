"""가상 선수 키우기 — NXT에서 월챔까지. **순수 함수 하나로 한 주를 넘긴다.**

## 왜 이 모양인가

이전 커리어 시뮬레이터(`wwe_game`)는 **38,326줄로 불어나 버려졌다**(`f7a678f`).
2026-10-20에 해부해 보니 터진 곳이 분명했다 — 게임 로직은 `career_rules`·
`career_run`·`career_advance`·`match_flow` 넷을 합쳐 **1,404줄**이었고, 불어난 것은
`domain/constants` **18,994줄**(이벤트 카드 덱 21개)과 그 테스트 11,346줄이었다.

**그래서 덱을 만들지 않는다.** 한 주의 결과는 카드가 아니라 아래 수치 표에서
나온다. 덱이 없으면 "이벤트 하나 더" 가 파일 하나 더가 되지 않는다.

## 저장하지 않는다

커리어 게임은 상태가 필요한데, 그 저장이 지난번 붕괴의 시작이었다 —
`career_runs` 테이블이 생기자 세이브·불러오기·버전 호환·진행도·트로피가 전부
따라왔다. 그래서 **상태를 들고 다니는 쪽은 브라우저**이고 여기는 순수 함수다.

## 끝은 은퇴뿐이다

월챔을 들어도 런이 끝나지 않는다(2026-10-20 사용자 결정). **벨트는 중간 목표이고
점수는 역대 재위 수**다 — 월챔 3회가 1회보다 낫다. 들고 있으면 방어하고, 잃으면
다시 도전한다. `MAX_WEEKS` 를 넘기면 은퇴한다.

`advance(state, choice)` 가 새 상태를 돌려줄 뿐 어디에도 쓰지 않는다. 뽑기도
**상태에서 파생**되므로(`_roll`), 같은 상태에 같은 선택이면 항상 같은 결과다 —
클라이언트가 다시 보내서 주사위를 굴리는 일이 구조적으로 안 된다.

## 축은 인기도다

옛 `career_rules.py` 가 적어 둔 결정을 그대로 가져왔다 — **"인기도가 나이보다
우선한다"**(2026-08-06 사용자 결정). 프로레슬링은 경기력만으로 굴러가지 않아서,
관중이 보고 싶어 하는 선수가 메인에 선다. 이 판본에는 나이가 아예 없고 인기도가
승률·승격·타이틀 자격을 전부 정한다.

## 안 만드는 것

덱 · 백스테이지/프로모 세그먼트 · 계약·급여·경비 · 라이벌 엔진 · 피니셔·아스널
상점 · 부상 등급(여기서는 "결장 N주" 하나) · 다인전·엘리미네이션 · 서술 템플릿
뱅크(문장은 화면이 만든다).

**더하고 싶은 것이 생기면 이 목록에 왜 없는지 먼저 적는다.**
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace

from kayfabe.domain.services.career_world import SEASON_WEEKS

#: 한 런의 최대 주차. 넘으면 커리어가 끝난다.
#:
#: **40 이었다가 52 로 올렸다**(2026-10-20 사용자 요구 §1 — "한 시즌은 정확히
#: 52주"). 숫자를 여기 또 적지 않고 `career_world.SEASON_WEEKS` 를 가져오는 것은
#: 의도다 — 시즌 길이가 두 곳에 적히면 화면과 서버가 갈라진다.
#:
#: 이 무상태 경로는 **시즌이 하나뿐**이다. 시즌을 넘기며 이어지는 커리어는
#: `career_engine` 쪽이고, 이쪽은 "52주 한 번 돌리는 장난감" 으로 남는다.
MAX_WEEKS = SEASON_WEEKS

#: 인기도 범위. **바닥이 0이 아니라 10이다.**
#:
#: 0까지 떨어지면 승률이 `0.39` 로 굳어 **빠져나올 수 없는 나선**이 된다 —
#: 첫 시험 런이 그래서 인기도 0에 갇혀 1승 4패로 은퇴했다. 바닥을 10으로 올리면
#: 최악에서도 거의 반반이라 천천히 회복된다.
MIN_POPULARITY = 10
MAX_POPULARITY = 100

#: 메인 로스터로 올라가는 인기도.
PROMOTION_POPULARITY = 55

#: 타이틀 도전이 열리는 인기도 (벨트 단계별).
SHOT_POPULARITY = {
    "NXT Championship": 40,
    "Intercontinental Championship": 65,
    "World Heavyweight Championship": 85,
}

#: 벨트 단계. 앞의 것을 들어야 다음이 열린다.
BELT_LADDER = (
    "NXT Championship",
    "Intercontinental Championship",
    "World Heavyweight Championship",
)

#: 스타일별 승률 보정.
STYLE_BONUS = {"파워": 0.04, "테크니션": 0.02, "하이플라이어": 0.00}

#: 스타일별 **승리 시 추가 인기도.** 이 칸이 없으면 하이플라이어가 승률도 낮고
#: 부상도 잦아 **순수 열등**이 된다 — 고를 이유가 없는 선택지는 선택지가 아니다.
#: 화려한 쪽이 빨리 알려지는 것으로 갚는다.
STYLE_POPULARITY = {"파워": 0, "테크니션": 1, "하이플라이어": 3}

#: 스타일별 부상 위험. 셋의 트레이드오프가 여기서 닫힌다 —
#: 파워=잘 이긴다 · 테크니션=안전하다 · 하이플라이어=빨리 뜨고 자주 다친다.
STYLE_INJURY = {"파워": 0.07, "테크니션": 0.04, "하이플라이어": 0.09}

#: 승리·패배가 인기도를 움직이는 폭.
#:
#: **`6`/`-4` 였다가 고쳤다.** 반반 승률에서 주당 기대값이 `+1` 이라 승격(55)까지
#: 35주가 걸렸고, 40주 안에 월챔(85)이 구조적으로 불가능했다. `+2.5` 로 올려
#: 승격 ~14주 · 월챔 ~26주가 되게 했다. (52주로 늘린 뒤에도 이 값은 그대로다 —
#: 주차가 늘었으니 사다리를 더 여유롭게 오른다.)
WIN_POPULARITY = 8
LOSS_POPULARITY = -3
#: 타이틀전은 크게 움직인다.
TITLE_WIN_POPULARITY = 14
TITLE_LOSS_POPULARITY = -8
#: 방어 성공은 획득보다 작다 — 지키는 것이 빼앗는 것보다 덜 극적이다.
TITLE_DEFENSE_POPULARITY = 7
#: **`휴식` 은 넣지 않았다.** 부상이 아닐 때 쉬면 인기도만 깎이고 얻는 것이 없어서
#: 고를 이유가 없는 함정이었다(첫 시험 런이 거기 갇혔다). 쉬는 주차는 부상이
#: 강제하므로 선택지로 둘 필요가 없다.
CHOICES = ("경기", "도전")


@dataclass(frozen=True)
class CareerState:
    """런 하나의 전부. **직렬화 가능해야 한다** — 브라우저가 들고 다닌다."""

    name: str
    style: str
    week: int = 1
    brand: str = "NXT"
    popularity: int = 20
    wins: int = 0
    losses: int = 0
    #: **역대 획득 기록.** 같은 벨트를 여러 번 들면 여러 번 들어간다 — 커리어의
    #: 점수가 이것이다(월챔 3회가 1회보다 낫다).
    reigns: tuple[str, ...] = ()
    #: **지금 들고 있는 벨트.** 하나만 든다. `None` 이면 도전할 수 있고, 들고
    #: 있으면 방어한다.
    held: str | None = None
    #: 남은 결장 주차. 0이면 출전 가능.
    out_weeks: int = 0
    #: `None` 이면 진행 중. **끝은 은퇴뿐이다** — 월챔은 끝이 아니라 중간 목표다
    #: (2026-10-20 사용자 결정).
    outcome: str | None = None


@dataclass(frozen=True)
class WeekReport:
    """그 주에 **일어난 일만**. 문장은 화면이 만든다(템플릿 뱅크를 두지 않는다)."""

    week: int
    kind: str
    #: 경기를 했으면 승패, 아니면 `None`.
    won: bool | None = None
    opponent: str | None = None
    belt: str | None = None
    promoted_to: str | None = None
    injured_weeks: int = 0
    popularity_delta: int = 0


@dataclass(frozen=True)
class StepResult:
    state: CareerState
    report: WeekReport


def _roll(state: CareerState, salt: str) -> float:
    """상태에서 0~1을 만든다. **같은 상태·같은 선택이면 항상 같은 값이다.**

    `hash()` 를 쓰면 프로세스마다 달라져 재기동 뒤 다른 결과가 난다
    (`match_sim` 에서 같은 함정을 적어 뒀다). `sha256` 으로 고정한다.
    """
    key = "\x00".join(
        (
            state.name.strip().casefold(),
            state.style,
            str(state.week),
            state.brand,
            str(state.popularity),
            str(len(state.reigns)),
            state.held or "-",
            salt,
        )
    )
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def _clamp_popularity(value: int) -> int:
    return max(MIN_POPULARITY, min(MAX_POPULARITY, value))


def win_chance(state: CareerState, *, title_match: bool) -> float:
    """이길 확률. **인기도가 주축이고 스타일이 거든다.**

    타이틀전은 더 어렵다 — 벨트를 든 쪽이 챔피언이다. 확률은 `0.10`~`0.85` 안에
    머문다(업셋이 항상 남는다 · `match_sim` 과 같은 규칙).
    """
    base = 0.35 + state.popularity / 250.0 + STYLE_BONUS.get(state.style, 0.0)
    if title_match:
        base -= 0.12
    return max(0.10, min(0.85, base))


def _belt_open(state: CareerState, belt: str) -> bool:
    """그 벨트에 설 수 있는가. 인기도와 브랜드가 **둘 다** 맞아야 한다."""
    if state.popularity < SHOT_POPULARITY[belt]:
        return False
    if belt == "NXT Championship":
        return state.brand == "NXT"
    return state.brand != "NXT"


def next_belt(state: CareerState) -> str | None:
    """이번 주 타이틀전의 벨트. 없으면 `None`.

    **들고 있으면 그 벨트를 방어한다.** 아니면 사다리를 순서대로 오르되, 이미 전부
    들어 봤다면 **자격이 되는 가장 높은 벨트에 다시 도전한다** — 월챔이 끝이 아니라
    은퇴까지 가므로, 사다리 끝에서 도전할 것이 없어지면 남은 주차가 빈다.
    """
    if state.held is not None:
        return state.held
    won_before = set(state.reigns)
    for belt in BELT_LADDER:
        if belt in won_before:
            continue
        if belt == "NXT Championship" and state.brand != "NXT":
            # **지나온 벨트는 건너뛴다.** 이 줄이 없으면 NXT 벨트를 못 들고 승격한
            # 선수가 영구히 아무 타이틀에도 도전할 수 없다 — 승격은 인기도 55,
            # NXT 벨트는 40이라 그 창을 놓치는 일이 실제로 생긴다(테스트가 잡았다).
            continue
        if belt != "NXT Championship" and state.brand == "NXT":
            # 아직 못 간다 — 승격이 먼저다.
            return None
        return belt if state.popularity >= SHOT_POPULARITY[belt] else None
    for belt in reversed(BELT_LADDER):
        if _belt_open(state, belt):
            return belt
    return None


def is_defense(state: CareerState) -> bool:
    """이번 타이틀전이 방어인가. 화면이 문구를 가른다."""
    return state.held is not None


def advance(
    state: CareerState, *, choice: str, opponent: str | None = None
) -> StepResult:
    """한 주를 넘긴다. **이 함수가 게임의 전부다.**

    끝난 런은 그대로 돌려준다 — 부르는 쪽이 끝을 확인하지 않아도 안전하다.
    """
    if state.outcome is not None:
        return StepResult(state, WeekReport(week=state.week, kind="종료"))

    if state.out_weeks > 0:
        healed = replace(state, out_weeks=state.out_weeks - 1, week=state.week + 1)
        return _finish_if_over(
            healed,
            WeekReport(week=state.week, kind="결장", injured_weeks=state.out_weeks),
        )

    belt = next_belt(state) if choice == "도전" else None
    title_match = belt is not None
    defending = title_match and is_defense(state)
    won = _roll(state, "match") < win_chance(state, title_match=title_match)

    if defending:
        delta = TITLE_DEFENSE_POPULARITY if won else TITLE_LOSS_POPULARITY
    elif title_match:
        delta = TITLE_WIN_POPULARITY if won else TITLE_LOSS_POPULARITY
    else:
        delta = WIN_POPULARITY if won else LOSS_POPULARITY
    if won:
        delta += STYLE_POPULARITY.get(state.style, 0)

    # **방어는 역대 기록을 늘리지 않는다** — 지킨 것은 새 재위가 아니다.
    # 반대로 방어에 지면 벨트를 잃는다(기록은 남는다).
    reigns = state.reigns
    held = state.held
    if title_match and belt is not None:
        if defending:
            held = belt if won else None
        elif won:
            reigns = reigns + (belt,)
            held = belt
    popularity = _clamp_popularity(state.popularity + delta)

    injured = 0
    if _roll(state, "injury") < STYLE_INJURY.get(state.style, 0.05):
        injured = 1 + int(_roll(state, "injury_len") * 3)

    moved = state.brand
    promoted_to = None
    if state.brand == "NXT" and popularity >= PROMOTION_POPULARITY:
        # 메인 로스터는 둘이고 **상태에서 갈린다** — 지어낸 선택지를 더하지 않는다.
        moved = "Raw" if _roll(state, "brand") < 0.5 else "SmackDown"
        promoted_to = moved

    nxt = replace(
        state,
        week=state.week + 1,
        brand=moved,
        popularity=popularity,
        wins=state.wins + (1 if won else 0),
        losses=state.losses + (0 if won else 1),
        reigns=reigns,
        held=held,
        out_weeks=injured,
    )
    report = WeekReport(
        week=state.week,
        kind="방어전" if defending else ("타이틀전" if title_match else "경기"),
        won=won,
        opponent=opponent,
        belt=belt,
        promoted_to=promoted_to,
        injured_weeks=injured,
        popularity_delta=delta,
    )

    # **월챔을 들어도 끝나지 않는다** (2026-10-20 사용자 결정). 끝은 은퇴뿐이고,
    # 그 뒤 주차는 방어와 재도전으로 채워진다 — 그래서 `next_belt` 가 사다리 끝에서
    # 다시 가장 높은 벨트를 가리킨다.
    return _finish_if_over(nxt, report)


def _finish_if_over(state: CareerState, report: WeekReport) -> StepResult:
    """주차 상한을 넘겼으면 커리어를 닫는다. **월챔 전에 끝나면 패배다.**"""
    if state.week > MAX_WEEKS:
        return StepResult(replace(state, outcome="retired"), report)
    return StepResult(state, report)
