"""배경 세계의 챔피언 — 벨트는 늘 누군가의 것이다 (하네스 §3-D38).

지금까지 이 게임에 **챔피언이 없었다.** 벨트는 "걸려 있다 / 내가 갖고 있다" 두 상태
뿐이라, 레슬매니아에서 로만 레인즈와 붙는데 **벨트는 허공에서 왔다.** 실제 타이틀전은
"코디 로즈의 벨트에 도전한다"이지 "벨트에 도전한다"가 아니다.

## 저장하지 않는다

시드와 주차에서 매번 되짚는다 — `team_engine.chronicle`과 같은 방식이다(§3-D30).
재위 목록을 세이브에 담으면, 진행 한 번이 세이브를 통째로 다시 쓰는 구조(§3-D6)에서
표가 계속 커진다. 되짚는 비용은 벨트당 30~60번의 굴림이고 그 정도는 싸다.

## 플레이어는 이 계보에 없다

배경 계보는 **플레이어가 없는 세계**를 그린다. 플레이어가 벨트를 감고 있으면 그
기간의 챔피언은 플레이어이고, 그건 `CareerRun.titles_held`가 이미 안다 — 두 곳이 같은
사실을 들고 있으면 어긋난다. 여기서는 "내가 아니었다면 누구였을까"만 답한다.
"""

from __future__ import annotations

from typing import Final

from wwe_game.domain.constants import roster
from wwe_game.domain.constants.roster import RivalTier
from wwe_game.domain.services import seeded_roll
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.title import TITLES, Title, TitleTier

TIER_OF: Final[dict[TitleTier, RivalTier]] = {
    TitleTier.WORLD: RivalTier.MAIN_EVENT,
    TitleTier.SECONDARY: RivalTier.MIDCARD,
    TitleTier.TAG: RivalTier.MIDCARD,
}
"""벨트 계층 → 그 벨트를 감을 만한 선수 등급.

태그 벨트를 중간급에 두는 이유: 명부는 팀을 모른다. 태그 챔피언을 정상급에서 뽑으면
월드 챔피언과 같은 사람이 겹쳐 나온다.
"""

REIGN_WEEKS: Final[dict[TitleTier, tuple[int, int]]] = {
    TitleTier.WORLD: (26, 78),
    TitleTier.SECONDARY: (13, 45),
    TitleTier.TAG: (13, 40),
}
"""계층별 재위 기간(주). **위로 갈수록 길다.**

월드 벨트가 6개월~1년 반이라는 것은 실제 평균에 맞춘 값이다. 짧게 두면 30년 커리어에
챔피언이 60명 지나가 "누구의 벨트인가"가 다시 흐려진다 — 이 모듈을 만든 이유가 그것이다.
"""


def champion_at(seed: int, week: int, title: Title, *, exclude: str = "") -> str | None:
    """그 주차에 이 벨트를 감고 있는 사람. 명부가 비면 None.

    `exclude`는 플레이어의 링네임이다. 실존 선수를 바탕으로 만든 커리어는(§3-D10-1)
    **자기 이름이 명부에 그대로 있을 수 있고**, 그러면 자기 벨트에 도전하게 된다.
    """
    spec = TITLES[title]
    tier = TIER_OF[spec.tier]
    low, high = REIGN_WEEKS[spec.tier]
    channel = f"{seeded_roll.TITLE_SCENE}:{title.value}"

    cursor = 0
    holder: str | None = None
    while True:
        roll = SeededRoll(seed, cursor, channel)
        pool = tuple(
            n
            for n in roster.pool_for(spec.gender, tier, cursor)
            if n != holder and n != exclude
        )
        if pool:
            holder = roll.pick(pool)
        reign = roll.between(low, high)
        if cursor + reign > week:
            return holder
        cursor += reign
