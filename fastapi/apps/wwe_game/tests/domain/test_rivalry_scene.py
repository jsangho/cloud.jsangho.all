"""배경 세계의 대립 — 나 말고도 사람이 산다 (하네스 §3-D44).

인박스는 "세계선의 사건"을 표방하는데(§3-D31) 흐르는 것은 **내 일과 팀 소식뿐**이었다.
§3-D38로 벨트에 주인이 생겼지만 그 챔피언은 아무와도 싸우지 않았다 — 내가 도전하러
갈 때만 존재하는 사람이었다.
"""

from __future__ import annotations

from collections import Counter

from wwe_game.domain.constants import roster
from wwe_game.domain.constants.roster import RivalTier
from wwe_game.domain.services import rivalry_scene
from wwe_game.domain.services.rivalry_scene import RivalryBeat
from wwe_game.domain.value_objects.wrestler_identity import Gender

SEED = 5000
FULL = 1560


def scene(seed: int = SEED, weeks: int = FULL, exclude: str = "장상호"):
    return rivalry_scene.chronicle(seed, weeks, Gender.MALE, exclude=exclude)


class TestTheWorldKeepsMoving:
    def test_feuds_start_and_end(self) -> None:
        beats = Counter(n.beat for n in scene())
        assert beats[RivalryBeat.STARTED] > 0
        assert beats[RivalryBeat.SETTLED] + beats[RivalryBeat.BETRAYED] > 0

    def test_nothing_ends_that_never_started(self) -> None:
        """**살아 있는 목록을 들고 걷는다** — 팀 연대기가 2026-08-10에 겪은 버그다.

        시작 기록 없이 끝나는 대립이 있으면 인박스에 결말만 뜬다.
        """
        started: Counter[tuple[str, str]] = Counter()
        for item in scene():
            if item.beat is RivalryBeat.STARTED:
                started[item.names] += 1
            else:
                assert started[item.names] > 0, f"시작 없이 끝났다: {item.names}"
                started[item.names] -= 1

    def test_same_seed_same_world(self) -> None:
        """§3-D4 — 저장하지 않으므로 되짚기가 결정적이어야 산다."""
        assert scene() == scene()

    def test_different_seeds_diverge(self) -> None:
        assert scene(seed=1) != scene(seed=2)

    def test_a_shorter_walk_is_a_prefix_of_a_longer_one(self) -> None:
        """중간까지 걸은 연대기는 끝까지 걸은 것의 앞부분이다 — 되짚기가 안정적이라는 뜻."""
        early = scene(weeks=400)
        assert scene(weeks=FULL)[: len(early)] == early


class TestItStaysBackground:
    def test_the_inbox_is_not_buried(self) -> None:
        """**내 뉴스는 커리어당 28줄이다.**

        처음 `START_CHANCE`를 0.055로 뒀더니 배경만 174줄이 나와, 인박스를 열면 남의
        이야기가 3분의 2였다 — 이 모듈의 설명이 경고한 상황을 그 값이 만들었다.
        """
        assert len(scene()) < 60

    def test_only_main_eventers_make_headlines(self) -> None:
        """중견들의 대립은 헤드라인이 아니다 — 육성 브랜드 이름이 인박스에 올라왔었다.

        **등급은 그 주차의 것으로 본다.** 명부에 시간 축이 있어(§3-D13-1) 5년차의
        정상급과 20년차의 정상급이 다르다 — 몇 시점만 표본으로 잡으면 틀린다.
        """
        for item in scene():
            if item.beat is not RivalryBeat.STARTED:
                continue  # 끝은 시작할 때의 등급을 따른다
            main = set(roster.pool_for(Gender.MALE, RivalTier.UPPER_CARD, item.week))
            assert set(item.names) <= main, f"정상급이 아닌 대립: {item.names}"

    def test_at_most_three_run_at_once(self) -> None:
        live = 0
        peak = 0
        for item in scene():
            live += 1 if item.beat is RivalryBeat.STARTED else -1
            peak = max(peak, live)
        assert peak <= rivalry_scene.MAX_ACTIVE


class TestThePlayerIsNotInIt:
    def test_i_never_feud_with_myself_in_the_background(self) -> None:
        """실존 선수를 바탕으로 만들면 내 이름이 명부에 있다 (§3-D10-1)."""
        me = next(
            m.name
            for m in roster.ROSTER
            if m.gender is Gender.MALE and m.is_active_at(0)
        )
        for item in scene(exclude=me):
            assert me not in item.names

    def test_a_feud_is_between_two_different_people(self) -> None:
        for item in scene():
            assert item.names[0] != item.names[1]
