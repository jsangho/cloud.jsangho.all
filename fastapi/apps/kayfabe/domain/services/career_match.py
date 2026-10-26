"""경기 판정. **순수 함수로 떼어 두었다**(사용자 요구 §P0 경기 — 시드 재현).

입력은 선수 둘(또는 태그 두 팀)과 시드·키, 출력은 `MatchOutcome` 이다. 세계를
바꾸지 않는다 — 전적·인기도·관계 갱신은 `career_engine` 이 결과를 받아서 한다.
그 분리가 테스트를 "같은 초기 상태와 시드면 같은 결과" 로 만든다.

## 승률은 네 칸에서 나온다

    기량    `in_ring` 과 인기도 — 둘 다 들어간다
    컨디션  지친 선수는 진다
    체력    긴 경기에서 갈린다
    업셋    확률이 0.12~0.88 안에 머문다

**인기도만으로 정하지 않는다.** `career_run` 은 인기도 하나였고 그 독스트링이
"인기도가 나이보다 우선한다"(2026-08-06 사용자 결정)를 근거로 들었다. 그 결정은
유효하지만, 이번엔 능력치가 따로 있으므로 **인기도는 둘 중 하나의 축**이다 —
사용자 요구 §2.1 이 "능력치가 높다고 인기도가 반드시 높거나 모든 경기를 이기는
구조로 만들지 않는다" 를 요구했고, 두 축이 갈려 있어야 그게 가능하다.
"""

from __future__ import annotations

from dataclasses import dataclass

from kayfabe.domain.services.career_rng import pick, roll
from kayfabe.domain.services.career_world import Wrestler

#: 확률이 가 닿을 수 있는 경계. 업셋이 항상 남는다(`match_sim` 과 같은 규칙).
FLOOR, CEIL = 0.12, 0.88

#: 승리 방식. **서술이 아니라 분류다** — 화면이 문장을 만든다.
FINISHES = ("핀폴", "서브미션", "반칙승", "카운트아웃", "레프리 스톱")

MATCH_SINGLE = "single"
MATCH_TITLE = "title"
MATCH_TAG = "tag"


@dataclass(frozen=True)
class MatchOutcome:
    """경기 결과. **근거를 함께 돌려준다** — 화면이 확률을 적을 수 있어야 한다."""

    kind: str
    winner: str
    loser: str
    probability: float
    roll: float
    finish: str
    #: 경기 평가 0~100. 인기도 변동폭에 쓰인다.
    rating: int
    title: str | None = None
    #: 태그면 양 팀 전원.
    team_a: tuple[str, ...] = ()
    team_b: tuple[str, ...] = ()


def _power(w: Wrestler) -> float:
    """선수의 경기력 한 수치. 능력치·인기도·컨디션을 합친다."""
    skill = w.ability.in_ring / 100.0
    draw = w.popularity / 100.0
    cond = w.condition / 100.0
    stam = w.ability.stamina / 100.0
    # 기량 절반, 인기 1/4, 몸 1/4. 인기도가 혼자 정하지 않는다.
    return skill * 0.5 + draw * 0.25 + (cond * 0.6 + stam * 0.4) * 0.25


def win_probability(
    a: Wrestler, b: Wrestler, *, title_match: bool, challenger: str | None = None
) -> float:
    """`a` 가 이길 확률. **챔피언에게 이점이 있다.**

    타이틀전에서 도전자가 불리한 것은 `career_run` 의 규칙을 이었다(`-0.12`).
    벨트를 든 쪽이 챔피언이라는 사실이 확률에 들어가야 방어가 의미를 갖는다.
    """
    edge = _power(a) - _power(b)
    probability = 0.5 + edge * 0.9
    if title_match and challenger is not None:
        if challenger == a.name:
            probability -= 0.12
        else:
            probability += 0.12
    return max(FLOOR, min(CEIL, probability))


def _rating(a: Wrestler, b: Wrestler, seed: int, key: str) -> int:
    """경기 평가. 기량·인기도가 높고 컨디션이 좋으면 좋은 경기가 된다."""
    base = (a.ability.in_ring + b.ability.in_ring) / 2
    draw = (a.popularity + b.popularity) / 2
    cond = (a.condition + b.condition) / 2
    jitter = roll(seed, key, "rating") * 20 - 10
    return max(10, min(100, int(base * 0.5 + draw * 0.3 + cond * 0.2 + jitter)))


def simulate_single(
    a: Wrestler,
    b: Wrestler,
    *,
    seed: int,
    key: str,
    title: str | None = None,
    challenger: str | None = None,
) -> MatchOutcome:
    """싱글 경기. `title` 이 있으면 타이틀전이다.

    **비교를 이름 순서로 고정한다.** `roll < probability` 로 바로 비교하면 같은
    두 선수인데 인수 순서만 바꿔도 승자가 뒤집힌다 — `match_sim` 이 실측으로
    잡아 둔 함정이고(확률은 대칭인데 부등호가 대칭이 아니다) 여기서도 같다.
    """
    title_match = title is not None
    probability = win_probability(a, b, title_match=title_match, challenger=challenger)
    r = roll(seed, key, "match", *sorted((a.name, b.name)))

    first = min(a.name, b.name)
    a_is_first = a.name == first
    p_first = probability if a_is_first else 1.0 - probability
    first_wins = r < p_first
    a_wins = first_wins == a_is_first

    winner, loser = (a, b) if a_wins else (b, a)
    finish = pick(seed, FINISHES, key, "finish", winner.name) or FINISHES[0]
    return MatchOutcome(
        kind=MATCH_TITLE if title_match else MATCH_SINGLE,
        winner=winner.name,
        loser=loser.name,
        probability=probability,
        roll=r,
        finish=finish,
        rating=_rating(a, b, seed, key),
        title=title,
        team_a=(a.name,),
        team_b=(b.name,),
    )


def simulate_tag(
    team_a: tuple[Wrestler, ...],
    team_b: tuple[Wrestler, ...],
    *,
    seed: int,
    key: str,
) -> MatchOutcome:
    """태그팀 경기. **팀의 힘은 평균이고 최저치가 끌어내린다.**

    평균만 쓰면 강자 하나가 약자를 완전히 가린다. 프로레슬링은 약한 쪽이 핀을
    당해서 지므로 최저치가 들어가야 한다.
    """
    if not team_a or not team_b:
        raise ValueError("태그 경기에는 양 팀 모두 선수가 필요합니다")

    def team_power(team: tuple[Wrestler, ...]) -> float:
        powers = [_power(w) for w in team]
        return sum(powers) / len(powers) * 0.7 + min(powers) * 0.3

    edge = team_power(team_a) - team_power(team_b)
    probability = max(FLOOR, min(CEIL, 0.5 + edge * 0.9))

    names_a = tuple(w.name for w in team_a)
    names_b = tuple(w.name for w in team_b)
    r = roll(seed, key, "tag", *sorted(names_a + names_b))

    first = min(names_a[0], names_b[0])
    a_is_first = names_a[0] == first
    p_first = probability if a_is_first else 1.0 - probability
    a_wins = (r < p_first) == a_is_first

    win_team, lose_team = (team_a, team_b) if a_wins else (team_b, team_a)
    # 핀을 따낸 쪽과 당한 쪽. **약한 쪽이 당한다.**
    scorer = max(win_team, key=_power)
    eaten = min(lose_team, key=_power)
    finish = pick(seed, FINISHES, key, "finish", scorer.name) or FINISHES[0]
    return MatchOutcome(
        kind=MATCH_TAG,
        winner=scorer.name,
        loser=eaten.name,
        probability=probability,
        roll=r,
        finish=finish,
        rating=_rating(scorer, eaten, seed, key),
        title=None,
        team_a=names_a,
        team_b=names_b,
    )
