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
    unreproducible_in_event,
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


# --- mq 와 덮어쓰기 거부 (2026-10-06) ----------------------------------------
#
# **이 모양이 실제로 데이터를 잃을 뻔했다.** `mq`를 리더가 못 봐서 멀쩡한
# `mitb26-whc`가 「신규」로 잡혔고, 적용했으면 배포 뒤 `sync-from-client`가 옛
# `match_key`를 지워 예측이 CASCADE로 사라졌다.

MQ_SOURCE = """export const PLE_MATCH_CARDS: Record<PleSlug, PleMatchCard[]> = {
  "money-in-the-bank": [
    // 배당 출처: BetOnline · 2026-10-05 관측
    mm(
      "mitb26-women",
      "Women's Money in the Bank Ladder Match",
      "sideA",
      [{ name: "Sol Ruca" }, { name: "Roxanne Perez" }],
      [9.5, 1.67],
    ),
    mq(
      "mitb26-whc",
      "World Heavyweight Championship",
      "sideB",
      { name: "Roman Reigns", isChampion: true },
      { name: "LA Knight" },
      [{ book: "BetOnline", decimals: [1.07, 7.0], observedAt: "2026-09-27" }],
    ),
  ],

  "royal-rumble": [
    rumbleWinner("rr26-men", "Men's Royal Rumble", "sideA", ["Gunther", "Jey Uso"], [
      2.5, 3.0,
    ]),
  ],

  backlash: [
    m2("bl26-one", "Single Match", "sideA", { name: "Cody Rhodes" }, {
      name: "Gunther",
    }),
  ],
};
"""


class TestMqIsVisible:
    def test_an_mq_match_is_read_like_any_other(self) -> None:
        """**못 보면 「신규」가 된다** — 그 뒤가 삭제다."""
        cards = read_event_cards(MQ_SOURCE, "money-in-the-bank")

        assert cards is not None
        assert [c.id for c in cards] == ["mitb26-women", "mitb26-whc"]

    def test_the_mq_competitors_are_read(self) -> None:
        cards = read_event_cards(MQ_SOURCE, "money-in-the-bank")
        assert cards is not None
        whc = next(c for c in cards if c.id == "mitb26-whc")

        assert whc.names == ("Roman Reigns", "LA Knight")

    def test_the_prefix_still_comes_out(self) -> None:
        cards = read_event_cards(MQ_SOURCE, "money-in-the-bank")
        assert cards is not None

        assert id_prefix_of(cards) == "mitb26"


class TestUnreproducibleData:
    """렌더러가 다시 만들 수 없는 것이 있으면 **덮어쓰지 않는다.**"""

    def test_odds_quotes_and_comments_are_all_reported(self) -> None:
        found = unreproducible_in_event(MQ_SOURCE, "money-in-the-bank")

        assert "호가 여러 벌(mq)" in found
        assert "배당 배열(bookmakerDecimal)" in found
        assert "손으로 쓴 주석" in found

    def test_the_rumble_constructor_is_unreproducible_too(self) -> None:
        """`rumbleWinner`도 렌더러가 `mm`으로 바꿔 버린다."""
        found = unreproducible_in_event(MQ_SOURCE, "royal-rumble")

        assert "럼블 우승 생성자(rumbleWinner)" in found

    def test_a_comment_above_the_key_is_outside_the_block(self) -> None:
        """**블록은 `[` 다음부터다.** 키 위의 주석은 덮어써도 살아남으므로 막지 않는다."""
        source = (
            "export const X = {\n  // 이 주석은 블록 밖이다\n  backlash: [\n"
            '    m2("bl26-one", "Single Match", "sideA",'
            ' { name: "A" }, { name: "B" }),\n'
            "  ],\n};\n"
        )

        assert unreproducible_in_event(source, "backlash") == ()

    def test_a_plain_block_is_safe_to_rewrite(self) -> None:
        """평범한 블록까지 막으면 도구가 쓸모없어진다."""
        assert unreproducible_in_event(MQ_SOURCE, "backlash") == ()

    def test_an_absent_event_reports_nothing(self) -> None:
        assert unreproducible_in_event(MQ_SOURCE, "summerslam") == ()

    def test_the_url_in_a_string_is_not_a_comment(self) -> None:
        """`https://`의 `//`를 주석으로 세면 모든 블록이 막힌다."""
        source = (
            "export const X = {\n  backlash: [\n"
            '    m2("bl26-one", "Single Match", "sideA",'
            ' { name: "A", note: "https://x.test/a" }, { name: "B" }),\n'
            "  ],\n};\n"
        )

        assert unreproducible_in_event(source, "backlash") == ()
