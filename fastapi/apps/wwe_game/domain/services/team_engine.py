"""팀이 생기고 갈라진다 — 순수 함수 (하네스 §3-D30).

주차와 시드만 보고 그 주에 팀 세계에서 무슨 일이 있었는지를 돌려준다. 세이브를 고치지
않으므로 같은 시드는 언제 돌려도 같은 연대기를 만든다(§3-D4).

**정해진 전개가 먼저다.** 로스 아메리카노스의 뒷이야기(§7-1)는 굴리지 않고 달력대로
실행하고, 굴림은 그 밖의 팀들에만 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from wwe_game.domain.constants import teams as team_rules
from wwe_game.domain.constants.roster import RivalTier, active_at, tier_at
from wwe_game.domain.constants.teams import (
    KOREAN_TEAM_NAMES,
    SCRIPTED_ARCS,
    TeamKind,
)
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.team import Team
from wwe_game.domain.value_objects.wrestler_identity import Gender

WEEKS_PER_YEAR = team_rules.WEEKS_PER_YEAR


class TeamChange(StrEnum):
    FORMED = "formed"
    DISBANDED = "disbanded"
    RENAMED = "renamed"


@dataclass(frozen=True)
class TeamNews:
    """그 주차에 팀 세계에서 일어난 일 하나. 뉴스 피드가 그대로 읽는다 (§3-D31)."""

    week: int
    change: TeamChange
    team: Team
    headline: str


def korean_name(csv_name: str) -> str:
    """CSV 표기 → 한글. 표에 없으면 원문 그대로 두고 화면이 알아채게 한다."""
    return KOREAN_TEAM_NAMES.get(csv_name, csv_name)


def short_name(csv_name: str) -> str:
    """`LWO | 라티노 월드 오더`처럼 두 이름을 가진 팀의 **앞쪽(약칭)**."""
    return korean_name(csv_name).split("|")[0].strip()


def name_for(members: tuple[str, ...], roll: SeededRoll) -> str:
    """새 팀의 이름. **태그팀은 이름을 안 지을 수도 있다** (§7-2).

    빈 문자열을 돌려주면 `Team.label`이 "A & B"로 부른다. 셋 이상은 언제나 이름을
    짓는다 — 세 이름을 앰퍼샌드로 잇는 스테이블은 없다.
    """
    if len(members) <= 2 and roll.chance(team_rules.AMPERSAND_SHARE):
        return ""
    head = roll.pick(team_rules.FICTIONAL_TEAM_HEADS)
    tail = roll.pick(team_rules.FICTIONAL_TEAM_TAILS)
    return f"{head} {tail}"


def scripted_at(week: int) -> tuple[TeamNews, ...]:
    """그 주차의 **정해진 전개**. 굴림과 무관하게 언제나 같다 (§7-1)."""
    news: list[TeamNews] = []
    for arc in SCRIPTED_ARCS:
        if arc.week != week:
            continue
        if arc.disband:
            news.append(
                TeamNews(
                    week=week,
                    change=TeamChange.DISBANDED,
                    team=Team(korean_name(arc.disband), ()),
                    headline=arc.headline,
                )
            )
        if arc.form:
            news.append(
                TeamNews(
                    week=week,
                    change=TeamChange.FORMED,
                    team=Team(korean_name(arc.form), arc.members, week),
                    headline=arc.headline,
                )
            )
        if arc.renames and not (arc.disband or arc.form):
            news.append(
                TeamNews(
                    week=week,
                    change=TeamChange.RENAMED,
                    team=Team("", tuple(new for _, new in arc.renames)),
                    headline=arc.headline,
                )
            )
    return tuple(news)


def ring_name_at(name: str, week: int) -> str:
    """그 주차에 이 선수가 쓰는 링네임. **기믹을 벗으면 이름이 바뀐다** (§7-1).

    명부는 오늘의 이름을 들고 있으므로, 예약 전개가 지난 뒤에는 여기서 갈아 끼운다.
    """
    current = name
    for arc in SCRIPTED_ARCS:
        if arc.week > week:
            continue
        for old, new in arc.renames:
            if current == old:
                current = new
    return current


def roll_change(week: int, roll: SeededRoll) -> TeamNews | None:
    """정해지지 않은 팀들의 결성·해체 굴림. 한 주에 최대 하나만 일어난다.

    **연 확률을 주 확률로 나눠 쓴다** — 주마다 굴리므로 그대로 쓰면 30년에 천 번이 된다.
    """
    if roll.chance(team_rules.FORM_CHANCE_PER_YEAR / WEEKS_PER_YEAR):
        members = _pick_partners(week, roll)
        if members is None:
            return None
        team = Team(name_for(members, roll), members, week)
        noun = "태그팀" if team.kind is TeamKind.TAG_TEAM else "스테이블"
        return TeamNews(
            week=week,
            change=TeamChange.FORMED,
            team=team,
            headline=f"새 {noun}이 나왔다 — {team.label}.",
        )
    if roll.chance(team_rules.DISBAND_CHANCE_PER_YEAR / WEEKS_PER_YEAR):
        members = _pick_partners(week, roll)
        if members is None:
            return None
        team = Team(name_for(members, roll), members, week)
        return TeamNews(
            week=week,
            change=TeamChange.DISBANDED,
            team=team,
            headline=f"{team.label}, 해체를 발표했다.",
        )
    return None


def _pick_partners(
    week: int, roll: SeededRoll, gender: Gender | None = None
) -> tuple[str, ...] | None:
    """그 주차 명부에서 팀을 이룰 사람들. 같은 이름이 두 번 들어가지 않는다.

    **디비전을 섞지 않는다** (2026-08-10 버그 수정). 성별을 안 걸렀더니 "자리아 &
    그레이슨 월러" 같은 혼성 태그팀이 나왔다. 태그팀 벨트부터 남녀가 갈려 있고
    (§3-D20) 라이벌 풀도 디비전으로 나뉘는데(§3-D11) 팀만 섞이고 있었다.

    `gender`가 None이면 **한쪽을 뽑아 그쪽으로 통일한다** — NPC끼리 묶는 자리다.
    """
    if gender is None:
        gender = Gender.FEMALE if roll.chance(0.5) else Gender.MALE
    pool = [
        ring_name_at(m.name, week)
        for m in active_at(week)
        if m.gender is gender and tier_at(m, week) is not RivalTier.MAIN_EVENT
    ]
    if len(pool) < 3:
        return None
    size = 3 if roll.chance(0.25) else 2
    picked: list[str] = []
    for _ in range(size * 3):  # 중복이 나오면 다시 뽑되 반드시 멈춘다
        candidate = roll.pick(tuple(pool))
        if candidate not in picked:
            picked.append(candidate)
        if len(picked) == size:
            break
    return tuple(picked) if len(picked) == size else None


def form_for_player(
    player: str, week: int, roll: SeededRoll, gender: Gender
) -> Team | None:
    """플레이어가 들어갈 팀을 만든다 (§3-D30).

    **카드는 팀을 직접 만들지 않는다.** 선택지가 `in_tag_team`·`in_stable` 표식만 남기고,
    다음 활동 주차에 규칙이 그걸 읽어 팀을 세운다 — 깜짝 콜업과 같은 방식이다(§3-D22-1).
    덱 데이터가 명부를 알게 되면 "콘텐츠 추가에 코드 리뷰가 필요 없다"는 §3-D19의 전제가
    깨진다.
    """
    partners = _pick_partners(week, roll, gender)
    if partners is None:
        return None
    members = (player, *partners[:1]) if len(partners) == 2 else (player, *partners)
    return Team(name_for(members, roll), members, week)
