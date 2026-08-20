"""위상과 성향 — 명부의 두 축 (하네스 §3-D95).

**예전에는 한 축이 셋을 겸했다.** `RivalTier`가 위상이자 브랜드였고(유망주 = NXT),
성향은 아예 없었다. 2026-08-19에 사용자가 179명의 표를 주며 셋을 갈랐다 —
브랜드는 `develops`, 위상은 `card`, 성향은 `alignment`다.

여기서 지키는 것은 넷이다.

| | |
|---|---|
| 표가 원본이다 | 0주차 명부는 CSV의 `card`·`alignment` 칸과 한 글자도 안 어긋난다 |
| 위상은 움직인다 | 3년마다 오르내리고, 마지막 두 해는 한 칸 내려온다 |
| 성향은 굴러가고 뒤집힌다 | 안 정해진 사람은 굴려서 정하고, 여섯 해마다 한 번 뒤집힐 수 있다 |
| 가끔 위를 본다 | 대립·벨트가 열에 두 번쯤 한 칸 위를 넘본다 |
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from pathlib import Path

import pytest
from _helpers import make_run
from wwe_game.domain.constants import roster
from wwe_game.domain.constants.roster import (
    CAREER_WEEKS,
    WEEKS_PER_YEAR,
    Alignment,
    RivalTier,
)
from wwe_game.domain.services import rivalry_desk, rivalry_engine
from wwe_game.domain.value_objects.title import Brand
from wwe_game.domain.value_objects.wrestler_identity import Gender
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

SEEDS = (0, 1, 7, 42)
YEARS = tuple(range(0, CAREER_WEEKS + 1, WEEKS_PER_YEAR))

GAME_DATA = Path(roster.__file__).parents[2] / "_docs" / "roster_game_data.csv"
"""사용자가 준 표 (§3-D95). **생성기가 읽는 그 파일이다** — 명부는 여기서 찍혀 나온다."""

CARD_OF = {
    "upper": RivalTier.UPPER_CARD,
    "mid": RivalTier.MID_CARD,
    "low": RivalTier.LOW_CARD,
}
ALIGNMENT_OF = {
    "face": Alignment.FACE,
    "tweener": Alignment.TWEENER,
    "heel": Alignment.HEEL,
}


def _table() -> list[dict[str, str]]:
    text = GAME_DATA.read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


class TestTheTableIsTheSource:
    """**0주차 명부는 표와 같아야 한다** (§3-D95).

    `roster.py`는 생성기가 찍는 파일이라 손으로 고칠 일이 없다 — 그런데 손으로 고쳐도
    아무 데서도 안 걸린다. 표와 어긋난 위상·성향은 화면에 그대로 나가고, 다음 생성에서
    조용히 되돌아간다. 여기가 그 어긋남을 잡는 자리다.
    """

    def test_every_row_of_the_table_stands_in_the_roster(self) -> None:
        listed = {m.name for m in roster.ROSTER if m.slot < 0}
        for row in _table():
            # `|`는 개명 규약이다 (§3-D54) — 앞이 처음 활동명이고 명부의 이름이다.
            korean = row["korean_name"].split("|")[0].strip()
            assert korean in listed, f"표에는 있는데 명부에 없다: {korean}"

    def test_the_card_position_matches_the_table(self) -> None:
        by_name = {m.name: m for m in roster.ROSTER if m.slot < 0}
        for row in _table():
            korean = row["korean_name"].split("|")[0].strip()
            member = by_name[korean]
            assert member.start_tier is CARD_OF[row["card"].strip()], korean

    def test_the_alignment_matches_the_table(self) -> None:
        """**빈 칸은 빈 채로 온다** — Evolve의 열둘은 콜업 때 굴린다(사용자 결정)."""
        by_name = {m.name: m for m in roster.ROSTER if m.slot < 0}
        for row in _table():
            korean = row["korean_name"].split("|")[0].strip()
            given = row["alignment"].strip()
            want = ALIGNMENT_OF[given] if given else None
            assert by_name[korean].alignment is want, korean

    def test_the_undecided_are_the_developmental_and_the_invented(self) -> None:
        """성향이 안 정해진 사람은 **육성과 가상 선수뿐**이다 (§3-D95)."""
        for member in roster.ROSTER:
            if member.alignment is None:
                assert member.develops or member.slot >= 0, member.name


class TestStatusMoves:
    """**위상을 고정하면 두 번 틀린다** — 오늘의 신인이 서른 해 뒤에도 신인이고,
    은퇴로 빈 어퍼카드 자리를 아무도 안 채운다 (§3-D95).
    """

    def test_somebody_climbs_and_somebody_falls(self) -> None:
        rose = fell = 0
        for member in roster.ROSTER:
            first = roster.tier_at(member, member.debut_week, 7)
            last_week = (member.retire_week or CAREER_WEEKS) - 1
            if last_week <= member.debut_week:
                continue
            last = roster.tier_at(member, last_week, 7)
            rose += last > first
            fell += last < first
        assert rose > 0, "서른 해 동안 아무도 안 올라갔다"
        assert fell > 0, "서른 해 동안 아무도 안 내려왔다"

    def test_the_last_two_years_step_down(self) -> None:
        """은퇴 직전 두 해는 한 칸 아래다 — 그 구간은 후배를 올려 주는 자리다.

        **경계 주차에서 잰다.** 그 뒤로도 3년 굴림은 계속 돌기 때문에(`tier_at`)
        은퇴 직전 주차와 비교하면 그 사이에 오른 사람이 섞인다.
        """
        checked = 0
        for member in roster.ROSTER:
            if member.retire_week is None:
                continue
            edge = member.retire_week - roster.DECLINE_BEFORE
            if edge - 1 <= member.debut_week:
                continue
            before = roster.tier_at(member, edge - 1, 7)
            if before is RivalTier.LOW_CARD:
                continue  # 더 내려갈 칸이 없다
            checked += 1
            assert roster.tier_at(member, edge, 7) < before, member.name
        assert checked > 0

    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_roster_does_not_turn_into_all_upper_card(self, seed: int) -> None:
        """**오르기만 하면 서른 해 뒤 명부가 통째로 어퍼카드가 된다** (§3-D95).

        0주차 표에서 어퍼는 30/180(17%)이다. 콜업 강등(§3-D95, 2026-08-20)이 붙기
        전에는 이 값이 **37%까지** 부풀었다 — 육성에는 내려가는 굴림이 없어 거기서
        다들 꼭대기까지 오르고 그 상태로 메인에 쏟아졌기 때문이다. 지금은 서른 해
        내내 16~19%에 눕고 실측 최대가 25.9%다.
        """
        for week in YEARS:
            active = roster.active_at(week)
            upper = sum(
                1
                for m in active
                if roster.tier_at(m, week, seed) is RivalTier.UPPER_CARD
            )
            share = upper / len(active)
            assert share <= 0.30, f"{week // WEEKS_PER_YEAR}년차 어퍼 {share:.0%}"

    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_main_roster_almost_always_has_a_top(self, seed: int) -> None:
        """메인 로스터의 어퍼카드 칸은 **거의 언제나 차 있다** — 벨트가 거기서 난다.

        **비는 해가 아주 없지는 않다.** 여성부는 세 브랜드로 나누면 칸이 얇아, 시드에
        따라 몇 해쯤 RAW 여성부 정상이 비는 세계가 있다(실측 1.6%). 그건 사고가 아니라
        *정상이 얇은 시기*이고, 그동안 벨트는 한 칸 아래에서 주인을 찾는다
        (`title_scene`의 fallback). 사고가 되는 것은 **자주 비는 것**이라 빈도를 잰다.
        """
        empty = 0
        seen = 0
        for brand in (Brand.RAW, Brand.SMACKDOWN):
            for gender in Gender:
                for week in YEARS:
                    seen += 1
                    if not roster.pool_for(
                        gender, RivalTier.UPPER_CARD, week, brand, seed
                    ):
                        empty += 1
        assert empty / seen <= 0.05, f"시드 {seed}: 빈 해 {empty}/{seen}"

    @pytest.mark.parametrize("seed", SEEDS)
    def test_the_developmental_top_never_starves(self, seed: int) -> None:
        """**육성 안은 이 규칙이 안 건드린다** (§3-D95, 2026-08-20).

        콜업 강등은 *올라온 뒤*에만 걸린다 — NXT의 꼭대기는 그대로여야 그 브랜드의
        챔피언이 신인 중에서 뽑히던 자리로 돌아가지 않는다.
        """
        tops = [
            len(roster.pool_for(gender, RivalTier.UPPER_CARD, week, Brand.NXT, seed))
            for gender in Gender
            for week in YEARS
        ]
        assert sum(tops) / len(tops) >= 2.0, tops


class TestTheCallUpStartsOver:
    """**육성의 정상은 메인의 정상이 아니다** (§3-D95, 2026-08-20).

    이 규칙이 없을 때 어퍼카드가 명부의 17%에서 37%까지 부풀었고, 세어 보니 그 어퍼의
    **68~76%가 육성 출신**이었다 — 육성 표에는 내려가는 굴림이 없어(`NXT_RISE_CHANCE`)
    거기서는 다들 꼭대기까지 오르고 그 상태로 메인에 쏟아졌다.
    """

    @staticmethod
    def _climbers(seed: int) -> list:
        """육성에서 **올라간** 사람들 — 표가 적어 준 자리보다 높이 선 채 콜업된다."""
        found = []
        for member in roster.ROSTER:
            if not member.develops:
                continue
            leaves = roster.call_up_week(member, seed)
            if leaves is None or not member.is_active_at(leaves):
                continue
            if roster._climbed(member, leaves, seed) > member.start_tier:  # noqa: SLF001
                found.append((member, leaves))
        return found

    def test_somebody_climbs_inside_developmental(self) -> None:
        assert self._climbers(7), "육성에서 아무도 안 올라갔다면 잴 것이 없다"

    def test_they_arrive_no_higher_than_midcard(self) -> None:
        for member, leaves in self._climbers(7):
            assert roster.tier_at(member, leaves, 7) <= RivalTier.MID_CARD, member.name

    def test_the_table_still_wins(self) -> None:
        """**표가 적어 준 자리 밑으로는 안 내린다** — 그레이슨 월러는 올라와서도 어퍼다."""
        listed = [
            m
            for m in roster.ROSTER
            if m.develops and m.start_tier is RivalTier.UPPER_CARD
        ]
        assert listed, "표에 NXT 어퍼카드가 하나도 없다"
        for member in listed:
            leaves = roster.call_up_week(member, 7)
            assert leaves is not None
            if member.is_active_at(leaves):
                assert roster.tier_at(member, leaves, 7) is RivalTier.UPPER_CARD

    def test_the_ladder_goes_on_after_the_call_up(self) -> None:
        """**미드에서 다시 굴려 정상에 갈 수 있다** — 강등이 천장은 아니다."""
        risen = 0
        for member, leaves in self._climbers(7):
            later = min(leaves + 10 * WEEKS_PER_YEAR, CAREER_WEEKS - 1)
            if not member.is_active_at(later):
                continue
            risen += roster.tier_at(member, later, 7) is RivalTier.UPPER_CARD
        assert risen > 0, "콜업된 뒤 다시 정상에 오른 사람이 하나도 없다"

    def test_nothing_moves_before_the_call_up(self) -> None:
        """콜업 전 주차는 강등 없는 사다리와 **한 칸도 다르지 않다**."""
        for member, leaves in self._climbers(7)[:40]:
            for week in range(member.debut_week, leaves, WEEKS_PER_YEAR):
                assert roster.tier_at(member, week, 7) is roster._climbed(  # noqa: SLF001
                    member, week, 7
                )

    def test_the_main_roster_is_untouched(self) -> None:
        """메인에서 시작한 사람에게는 이 규칙이 없다 — 콜업 자체가 없다."""
        for member in roster.ROSTER:
            if member.develops:
                continue
            assert roster.call_up_week(member, 7) is None
            for week in (0, 300, 900):
                if (
                    member.retire_week is None
                    or week < member.retire_week - roster.DECLINE_BEFORE
                ):
                    assert roster.tier_at(member, week, 7) is roster._climbed(  # noqa: SLF001
                        member, week, 7
                    )


class TestAlignmentRolls:
    """성향은 세 층이다 (§3-D95): 표 → 콜업 때 굴림 → 여섯 해마다 뒤집힘."""

    def test_the_table_decides_the_first_night(self) -> None:
        for member in roster.ROSTER:
            if member.alignment is None:
                continue
            assert roster.alignment_at(member, member.debut_week, 7) is member.alignment

    def test_the_undecided_get_one_of_the_three(self) -> None:
        rolled = [m for m in roster.ROSTER if m.alignment is None]
        assert rolled, "굴려서 정할 사람이 하나도 없다"
        for member in rolled:
            assert roster.alignment_at(member, member.debut_week, 7) in tuple(Alignment)

    def test_the_same_night_gives_the_same_answer(self) -> None:
        """§3-D4 — 세이브를 다시 열어도 같은 성향이다."""
        member = roster.ROSTER[0]
        for week in (0, 300, 900):
            assert roster.alignment_at(member, week, 7) is roster.alignment_at(
                member, week, 7
            )

    def test_a_different_world_can_turn_differently(self) -> None:
        """시드가 다르면 뒤집히는 사람이 다르다 — 판마다 같은 얼굴이면 굴림이 아니다."""
        weeks = range(0, CAREER_WEEKS, WEEKS_PER_YEAR)
        one = [roster.alignment_at(m, w, 0) for m in roster.ROSTER for w in weeks]
        other = [roster.alignment_at(m, w, 7) for m in roster.ROSTER for w in weeks]
        assert one != other

    def test_nobody_turns_more_than_a_few_times(self) -> None:
        """**커리어에 한두 번이면 사건이고, 해마다면 소음이다** (§3-D95).

        여섯 해마다 0.35로 굴리므로 서른 해에 다섯 번 굴려 기댓값이 1.75다.
        """
        for member in roster.ROSTER:
            weeks = [w for w in YEARS if member.is_active_at(w)]
            seen = [roster.alignment_at(member, w, 7) for w in weeks]
            turns = sum(1 for a, b in zip(seen, seen[1:], strict=False) if a is not b)
            assert turns <= 5, f"{member.name}: {turns}번 뒤집혔다"

    def test_the_two_sides_stay_the_majority(self) -> None:
        """**트위너는 드물다** (사용자 표: 180명 중 여섯).

        뒤집힘이 트위너를 거쳐 가므로 시간이 갈수록 그 칸이 두꺼워진다 — 그래도
        어느 쪽도 아닌 사람이 다수가 되면 성향 축이 뜻을 잃는다.
        """
        for week in YEARS:
            counted = Counter(
                roster.alignment_at(m, week, 7) for m in roster.active_at(week)
            )
            tweeners = counted[Alignment.TWEENER]
            assert tweeners < sum(counted.values()) / 3, f"{week}주차: {counted}"


class TestReachingUp:
    """*"가끔씩 미드카드가 어퍼카드 챔피언십을 노리고 (…) 대립도 같이"* (사용자)."""

    def test_the_top_has_nowhere_to_reach(self) -> None:
        for week in YEARS:
            assert (
                roster.reaching_tier(RivalTier.UPPER_CARD, week, 7)
                is RivalTier.UPPER_CARD
            )

    @pytest.mark.parametrize("tier", (RivalTier.LOW_CARD, RivalTier.MID_CARD))
    def test_it_happens_about_one_week_in_five(self, tier: RivalTier) -> None:
        weeks = range(CAREER_WEEKS)
        up = sum(1 for w in weeks if roster.reaching_tier(tier, w, 7) is not tier)
        share = up / len(weeks)
        assert abs(share - roster.REACH_UP_CHANCE) < 0.05, share

    def test_it_never_reaches_two_steps(self) -> None:
        for week in YEARS:
            for tier in RivalTier:
                reach = roster.reaching_tier(tier, week, 7)
                assert reach - tier <= 1


class TestFacingRivals:
    """**대립은 얼굴이 갈려야 이야기가 된다** (§3-D95, 2026-08-20).

    명부에 성향이 생겼는데 상대를 급과 브랜드로만 뽑으면, 그 축은 화면에 적힌 글자일
    뿐 아무것도 정하지 않는다.
    """

    @staticmethod
    def _share(alignment: int, want: Alignment) -> float:
        """후보 중 그 성향이 차지하는 몫. **주차를 넓게 훑어 잰다** — 굴림이 주차마다
        서므로 한 주만 보면 기울었는지 안 기울었는지 알 수 없다.
        """
        wanted = everyone = 0
        for week in range(1, 520, 7):
            run = make_run(
                seed=7,
                week=week,
                stats=WrestlerStats(popularity=40, alignment=alignment),
            )
            pool = rivalry_engine.candidate_pool(run)
            everyone += len(pool)
            wanted += sum(1 for n in pool if roster.alignment_of(n, week, 7) is want)
        assert everyone > 0
        return wanted / everyone

    def test_a_face_mostly_meets_heels(self) -> None:
        share = self._share(60, Alignment.HEEL)
        assert share > 0.6, share

    def test_a_heel_mostly_meets_faces(self) -> None:
        share = self._share(-60, Alignment.FACE)
        assert share > 0.6, share

    def test_the_lean_is_not_absolute(self) -> None:
        """**열에 셋은 안 기운다** (`FACING_CHANCE`). 성향이 상대를 통째로 정하면
        같은 위상·같은 브랜드에서 볼 수 있는 얼굴이 절반으로 줄어든다.
        """
        share = self._share(60, Alignment.FACE)
        assert share > 0.05, share

    def test_a_divided_crowd_leans_nowhere(self) -> None:
        """어느 쪽도 아니면(-19~19) 기울이지 않는다 — "마주 본다"가 성립하지 않는다."""
        for week in (1, 100, 400, 900):
            neutral = make_run(
                seed=7, week=week, stats=WrestlerStats(popularity=40, alignment=0)
            )
            pool = rivalry_engine.candidate_pool(neutral)
            counted = Counter(roster.alignment_of(n, week, 7) for n in pool)
            assert len(counted) > 1, f"{week}주차에 한 성향만 남았다: {counted}"

    def test_the_pool_is_never_empty_because_of_alignment(self) -> None:
        """**성향 때문에 상대가 없는 주차를 만들지 않는다.**"""
        for week in range(1, CAREER_WEEKS, 53):
            for alignment in (-80, 0, 80):
                run = make_run(
                    seed=7,
                    week=week,
                    stats=WrestlerStats(popularity=40, alignment=alignment),
                )
                assert rivalry_engine.candidate_pool(run), (week, alignment)

    def test_the_screen_sees_the_same_pool(self) -> None:
        """§3-D86 — 시비 걸 목록도 같은 풀에서 온다."""
        run = make_run(
            seed=7, week=200, stats=WrestlerStats(popularity=40, alignment=60)
        )
        pool = set(rivalry_engine.candidate_pool(run))
        assert pool
        assert set(rivalry_desk.candidates(run)) <= pool
