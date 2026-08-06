"""도메인 테스트 공용 픽스처 빌더.

`tests/` 트리에 `__init__.py`를 두지 않기 때문에(conftest 참조) 상대 임포트를 쓸 수 없다.
pytest가 테스트 파일의 디렉터리를 `sys.path`에 넣어 주므로 평범한 모듈로 둔다.
"""

from __future__ import annotations

from wwe_game.domain.constants.countries import Country
from wwe_game.domain.entities.career_run import CareerRun, start_run
from wwe_game.domain.value_objects.condition import Condition
from wwe_game.domain.value_objects.game_mode import game_mode_of
from wwe_game.domain.value_objects.title import Brand, Title
from wwe_game.domain.value_objects.wrestler_identity import (
    Gender,
    PlayStyle,
    RingName,
    WrestlerIdentity,
)
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats


def make_run(
    *,
    seed: int = 42,
    week: int = 0,
    stats: WrestlerStats | None = None,
    condition: Condition | None = None,
    style: PlayStyle = PlayStyle.TECHNICIAN,
    gender: Gender = Gender.MALE,
    mode: str = "weekly",
    brand: Brand = Brand.RAW,
    titles_won: tuple[Title, ...] = (),
    titles_held: frozenset[Title] | None = None,
    rivalries: tuple = (),
) -> CareerRun:
    identity = WrestlerIdentity(
        name=RingName("장상호"),
        gender=gender,
        country=Country.KR,
        play_style=style,
    )
    run = start_run(identity=identity, mode=game_mode_of(mode), seed=seed, user_id=1)
    changes: dict[str, object] = {"week": week}
    if stats is not None:
        changes["stats"] = stats
    if condition is not None:
        changes["condition"] = condition
    changes["brand"] = brand
    changes["titles_won"] = titles_won
    changes["rivalries"] = rivalries
    if titles_held is not None:
        changes["titles_held"] = titles_held
    return run.evolve(**changes)
