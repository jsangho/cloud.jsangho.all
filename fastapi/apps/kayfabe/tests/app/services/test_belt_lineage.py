"""계보표 — 벨트 이름이 조용히 사라지지 않게 잠근다.

획득 이력(`real_title_catalog`)은 **그때 그 벨트가 불리던 이름**으로 적혀 있고, 현
챔피언 보드는 **지금 이름**으로 적혀 있다. 둘을 잇는 것이 `belt_lineage`다.

여기서 지키는 것은 둘이다.

| | |
|---|---|
| 분류되지 않은 이름이 없다 | 카탈로그에 새 벨트가 들어오면 이 테스트가 **먼저** 깨진다 |
| 후신은 실재하는 벨트다 | `BELT_LINEAGE`의 값이 보드에 없으면 획득이 통째로 증발한다 |
"""

from __future__ import annotations

from kayfabe.app.services import belt_lineage
from kayfabe.app.services.real_title_catalog import REAL_TITLE_ACQUISITIONS


def _catalog_belt_names() -> set[str]:
    return {belt for reigns in REAL_TITLE_ACQUISITIONS.values() for belt, _ in reigns}


class TestEveryNameIsClassified:
    def test_no_catalog_belt_is_left_unclassified(self) -> None:
        """현 벨트·계보표·폐지표 셋 중 하나에는 들어가야 한다."""
        current = set(belt_lineage.current_belt_names())
        unclassified = {
            name
            for name in _catalog_belt_names()
            if name not in current
            and name not in belt_lineage.BELT_LINEAGE
            and name not in belt_lineage.RETIRED_BELTS
        }
        assert not unclassified, (
            f"계보표에 없는 벨트 이름: {sorted(unclassified)} — "
            "후신이 있으면 BELT_LINEAGE에, 폐지면 RETIRED_BELTS에 사유와 함께 넣는다"
        )

    def test_successors_exist_on_the_board(self) -> None:
        current = set(belt_lineage.current_belt_names())
        missing = {
            new for new in belt_lineage.BELT_LINEAGE.values() if new not in current
        }
        assert not missing, f"보드에 없는 후신: {sorted(missing)}"

    def test_a_name_is_never_both_inherited_and_retired(self) -> None:
        overlap = set(belt_lineage.BELT_LINEAGE) & set(belt_lineage.RETIRED_BELTS)
        assert not overlap, f"계보표와 폐지표에 동시에 있는 이름: {sorted(overlap)}"

    def test_every_retired_belt_states_why(self) -> None:
        assert all(reason.strip() for reason in belt_lineage.RETIRED_BELTS.values())


class TestResolve:
    def test_current_name_resolves_to_itself(self) -> None:
        assert belt_lineage.resolve_belt("NXT Championship") == "NXT Championship"

    def test_former_name_resolves_to_its_successor(self) -> None:
        assert (
            belt_lineage.resolve_belt("Raw Women's Championship")
            == "Women's World Championship"
        )

    def test_retired_name_resolves_to_nothing(self) -> None:
        assert belt_lineage.resolve_belt("ECW Championship") is None

    def test_unknown_name_resolves_to_nothing(self) -> None:
        assert belt_lineage.resolve_belt("없는 벨트") is None

    def test_former_names_are_listed_under_the_successor(self) -> None:
        assert set(belt_lineage.former_names("Undisputed WWE Championship")) == {
            "WWE Championship",
            "Universal Championship",
        }
