"""프론트 픽스처 읽기·쓰기 테스트.

**본문은 실제 `wwe-ple-matches.ts`의 모양 그대로다** — 다인전이 참가자 배열
(`[...]`)을 품고 있어서 대괄호를 세지 않으면 첫 경기 중간에서 끊긴다.
"""

from __future__ import annotations

from kayfabe.app.services.ple_fixture_file import (
    id_prefix_of,
    read_event_cards,
    render_event_block,
    replace_event_block,
)

SOURCE = """export const PLE_MATCH_CARDS: Record<PleSlug, PleMatchCard[]> = {
  "money-in-the-bank": [
    mm("mitb26-men", "Men's Money in the Bank Ladder Match", "sideB", [
      { name: "Bron Breakker" },
      { name: "CM Punk" },
      { name: BRACKET_LABELS.tbd },
    ]),
    m2(
      "mitb26-whc",
      "World Heavyweight Championship",
      "sideB",
      { name: "Roman Reigns", isChampion: true },
      { name: "LA Knight" },
    ),
  ],

  "survivor-series": [
    m2("ss26-ic", "Intercontinental", "sideA", { name: "Dominik Mysterio" }, {
      name: "John Cena",
    }),
  ],

  wrestlemania: [
    m2("wm42-n1-six", "Six-Man Tag Match", "sideA", { name: "LA Knight" }, {
      name: "IShowSpeed",
    }),
  ],
};
"""


class TestReading:
    def test_each_match_is_found_with_its_id(self) -> None:
        cards = read_event_cards(SOURCE, "money-in-the-bank")
        assert cards is not None
        assert [c.id for c in cards] == ["mitb26-men", "mitb26-whc"]

    def test_a_nested_competitor_array_does_not_end_the_event_early(self) -> None:
        """첫 `]`로 자르면 `mitb26-men`의 배열에서 끊겨 두 번째 경기를 놓친다."""
        cards = read_event_cards(SOURCE, "money-in-the-bank")
        assert cards is not None and len(cards) == 2

    def test_names_come_out_without_the_label_placeholder(self) -> None:
        cards = read_event_cards(SOURCE, "money-in-the-bank")
        assert cards is not None
        assert cards[0].names == ("Bron Breakker", "CM Punk")

    def test_a_missing_event_is_none_not_empty(self) -> None:
        """항목이 없는 것과 경기가 없는 것은 다르다."""
        assert read_event_cards(SOURCE, "halloween-havoc") is None

    def test_an_unquoted_key_is_found_too(self) -> None:
        """**실측 회귀.** 한 낱말 슬러그는 prettier가 따옴표를 뗀다 —
        `wrestlemania:`·`backlash:`·`summerslam:`가 그렇다. 따옴표를 요구하면
        그 대회들이 통째로 "픽스처에 항목이 없다"로 보고된다."""
        cards = read_event_cards(SOURCE, "wrestlemania")
        assert cards is not None
        assert [c.id for c in cards] == ["wm42-n1-six"]

    def test_the_id_prefix_is_read_not_derived(self) -> None:
        cards = read_event_cards(SOURCE, "money-in-the-bank")
        assert cards is not None
        assert id_prefix_of(cards) == "mitb26"

    def test_an_unknown_prefix_is_none(self) -> None:
        assert id_prefix_of(()) is None


class TestRendering:
    def test_two_sided_matches_use_m2(self) -> None:
        block = render_event_block(
            [
                (
                    "mitb26-whc",
                    "World Heavyweight Championship",
                    "sideB",
                    [("Roman Reigns", True, False), ("LA Knight", False, False)],
                )
            ]
        )
        assert "m2(" in block and "mm(" not in block
        assert '{ name: "Roman Reigns", isChampion: true }' in block

    def test_more_than_two_uses_mm_with_an_array(self) -> None:
        block = render_event_block(
            [
                (
                    "mitb26-men",
                    "Ladder",
                    "sideB",
                    [("A", False, False), ("B", False, False), ("1 TBD", False, True)],
                )
            ]
        )
        assert "mm(" in block
        assert "BRACKET_LABELS.tbd" in block

    def test_an_undetermined_name_that_is_not_tbd_keeps_its_text(self) -> None:
        """`Becky Lynch or Liv Morgan`은 자리 표시가 아니라 실제 문구다."""
        block = render_event_block(
            [
                (
                    "x",
                    "T",
                    "sideA",
                    [
                        ("Stephanie Vaquer", True, False),
                        ("Becky Lynch or Liv Morgan", False, True),
                    ],
                )
            ]
        )
        assert '{ name: "Becky Lynch or Liv Morgan" }' in block


class TestReplacing:
    def test_only_the_named_event_is_touched(self) -> None:
        updated = replace_event_block(SOURCE, "money-in-the-bank", "\n    NEW\n  ")
        assert updated is not None
        assert "NEW" in updated
        # 다른 대회는 글자 하나 안 바뀐다.
        assert '"ss26-ic"' in updated
        assert "mitb26-whc" not in updated

    def test_replacing_an_absent_event_is_none(self) -> None:
        assert replace_event_block(SOURCE, "halloween-havoc", "x") is None
