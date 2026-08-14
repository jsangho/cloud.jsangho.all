"""배경 세계의 챔피언 (하네스 §3-D38).

**벨트는 늘 누군가의 것이다.** 이 파일이 잠그는 것은 그 한 문장이다 — 도전하는 밤의
상대가 대립 목록에서 뽑히면 "누구의 벨트인지"가 사라지고 벨트가 허공에서 온다.
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001
from wwe_game.domain.constants import roster
from wwe_game.domain.constants.ple_calendar import calendar_for
from wwe_game.domain.services import title_scene
from wwe_game.domain.services.week_simulation import simulate_week
from wwe_game.domain.value_objects.title import TITLES, Brand, Title, TitleTier
from wwe_game.domain.value_objects.wrestler_identity import Gender
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

WORLD = Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP
SEED = 7777

_SHOW = next(s for s in calendar_for(Brand.RAW).shows if s.name == "백래시")
MATCH_WEEK = _SHOW.week_of_year + 52 * 7
"""경기가 보장된 주차. 아무 주차나 잡으면 프로모 주차에 걸려 타이틀전이 안 열린다."""


class TestTheBeltIsAlwaysSomeones:
    @pytest.mark.parametrize("title", sorted(TITLES, key=lambda t: t.value))
    @pytest.mark.parametrize("week", [0, 200, 800, 1559])
    def test_every_belt_has_a_holder_at_every_point(
        self, title: Title, week: int
    ) -> None:
        assert title_scene.champion_at(SEED, week, title) is not None

    @pytest.mark.parametrize("title", sorted(TITLES, key=lambda t: t.value))
    def test_the_holder_is_active_and_of_the_right_division(self, title: Title) -> None:
        """은퇴한 선수가 벨트를 감고 있으면 명부의 시간 축(§3-D13-1)이 무의미해진다."""
        for week in (0, 400, 900, 1400):
            name = title_scene.champion_at(SEED, week, title)
            # 태그 벨트는 둘이 든다 (§3-D57). **옛 이름으로도 찾는다** — 명단은 그
            # 주차의 활동명을 돌려준다 (§3-D54).
            for part in title_scene.members_of(name or ""):
                member = roster.member_of(part, SEED)
                assert member is not None
                assert member.gender is TITLES[title].gender
                assert member.is_active_at(week)

    def test_same_seed_same_lineage(self) -> None:
        """§3-D4 — 저장하지 않으므로 **되짚기가 결정적이어야** 산다."""
        first = [title_scene.champion_at(SEED, w, WORLD) for w in range(0, 1560, 37)]
        second = [title_scene.champion_at(SEED, w, WORLD) for w in range(0, 1560, 37)]
        assert first == second

    def test_different_seeds_give_different_worlds(self) -> None:
        mine = [title_scene.champion_at(1, w, WORLD) for w in range(0, 1560, 37)]
        yours = [title_scene.champion_at(2, w, WORLD) for w in range(0, 1560, 37)]
        assert mine != yours

    def test_the_belt_changes_hands_but_not_every_week(self) -> None:
        """**밴드를 45~90으로 넓혔다** (2026-08-13 사용자 지시 · §3-D74).

        옛 밴드는 15~45였고 그 근거는 "재위가 짧으면 30년에 챔피언이 예순 명 지나가
        누구의 벨트인가가 흐려진다"였다. 사용자가 1선 재위를 **평균 5~6개월**로
        정하면서 그 걱정보다 현실을 택했다 — 5.2개월이면 30년에 일흔 명 남짓이다.

        **여전히 상·하한은 필요하다.** 위가 없으면 매주 바뀌는 벨트를 못 잡고,
        아래가 없으면 한 사람이 30년을 드는 것도 통과한다.
        """
        reigns = []
        prev = None
        for week in range(0, 1560):
            now = title_scene.champion_at(SEED, week, WORLD)
            if now != prev:
                reigns.append(week)
                prev = now
        assert 45 <= len(reigns) <= 90, f"30년간 챔피언 {len(reigns)}명"

    def test_the_player_never_holds_it_in_the_background(self) -> None:
        """실존 선수를 바탕으로 만들면 **내 이름이 명부에 그대로 있다** (§3-D10-1).

        빼지 않으면 자기 벨트에 도전하게 된다.
        """
        me = next(m.name for m in roster.ROSTER if m.gender is Gender.MALE)
        held = {
            title_scene.champion_at(SEED, w, WORLD, exclude=me)
            for w in range(0, 1560, 13)
        }
        assert me not in held


class TestTheTitleMatchNamesTheChampion:
    def test_challenging_puts_you_across_the_champion(self) -> None:
        week = MATCH_WEEK
        run = make_run(
            brand=Brand.RAW, week=week - 1, stats=WrestlerStats(popularity=20)
        ).evolve(title_shot=True, briefcase_week=week - 60)
        # 가방을 써서 월드 타이틀전을 확정한다 (§3-D36).
        from wwe_game.domain.constants.career_flags import CASH_IN_PENDING

        run = run.evolve(flags=frozenset({CASH_IN_PENDING}))
        report = simulate_week(run)
        assert report.title_at_stake is not None
        assert TITLES[report.title_at_stake].tier is TitleTier.WORLD
        champion = title_scene.champion_at(
            run.seed, week, report.title_at_stake, exclude=str(run.identity.name)
        )
        assert report.opponent == champion

    def test_defending_brings_a_challenger_not_the_champion(self) -> None:
        """방어전의 상대는 **도전자**다 — 내가 챔피언이니 계보에서 뽑으면 안 된다."""
        week = MATCH_WEEK
        belt = Title.WORLD_HEAVYWEIGHT_CHAMPIONSHIP
        run = (
            make_run(brand=Brand.RAW, week=week - 1, stats=WrestlerStats(popularity=20))
            .evolve(titles_held=frozenset({belt}), titles_won=(belt,))
            .evolve(briefcase_week=0)
        )
        champion = title_scene.champion_at(
            run.seed, week, belt, exclude=str(run.identity.name)
        )
        report = simulate_week(run)
        if report.title_at_stake is belt:
            assert report.opponent != champion
