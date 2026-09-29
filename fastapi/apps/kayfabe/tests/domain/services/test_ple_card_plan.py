"""대진 계획 테스트.

**이 계획이 지키는 것은 하나다 — 기존 경기의 id는 바뀌지 않는다.** id에 DB 행과
사용자 예측이 걸려 있어서, 한 글자만 달라져도 `sync-from-client`가 그 경기를 지우고
예측이 CASCADE로 따라 사라진다.
"""

from __future__ import annotations

from kayfabe.domain.services.ple_card_parser import (
    WikiCompetitor,
    WikiMatchRow,
)
from kayfabe.domain.services.ple_card_plan import (
    ExistingCard,
    plan_cards,
)


def _row(number: int, *names: str, stipulation: str = "Singles match") -> WikiMatchRow:
    competitors = tuple(
        WikiCompetitor(
            name=n.removesuffix(" (c)"),
            is_champion=n.endswith(" (c)"),
        )
        for n in names
    )
    return WikiMatchRow(
        number=number,
        raw=" vs. ".join(names),
        stipulation=stipulation,
        is_card=True,
        competitors=competitors,
    )


class TestIdPreservation:
    def test_a_match_already_in_the_fixture_keeps_its_id(self) -> None:
        plan = plan_cards(
            "money-in-the-bank",
            (_row(1, "Roman Reigns (c)", "LA Knight"),),
            (ExistingCard("mitb26-whc", ("Roman Reigns", "LA Knight")),),
            id_prefix="mitb26",
        )
        assert [c.id for c in plan.cards] == ["mitb26-whc"]
        assert plan.cards[0].id_inherited is True
        assert plan.added == ()

    def test_adding_a_match_does_not_disturb_the_existing_ones(self) -> None:
        """MITB 실측 그대로 — 위키가 3경기에서 5경기로 늘었다."""
        plan = plan_cards(
            "money-in-the-bank",
            (
                _row(1, "Bron Breakker", "CM Punk"),
                _row(2, "Roman Reigns (c)", "LA Knight"),
                _row(3, "Bronson Reed", "Oba Femi"),
            ),
            (
                ExistingCard("mitb26-men", ("Bron Breakker", "CM Punk")),
                ExistingCard("mitb26-whc", ("Roman Reigns", "LA Knight")),
            ),
            id_prefix="mitb26",
        )
        assert [c.id for c in plan.cards][:2] == ["mitb26-men", "mitb26-whc"]
        assert plan.kept == 2
        assert [c.id for c in plan.added] == ["mitb26-reed-femi"]

    def test_the_wiki_order_wins_without_renaming_anything(self) -> None:
        """위키가 순서를 바꿔도 id는 따라다닌다 — 순서는 표시용이다."""
        plan = plan_cards(
            "backlash",
            (
                _row(1, "Roman Reigns (c)", "Jacob Fatu"),
                _row(2, "Bron Breakker", "Seth Rollins"),
            ),
            (
                ExistingCard("bl26-opener", ("Bron Breakker", "Seth Rollins")),
                ExistingCard("bl26-whc", ("Roman Reigns", "Jacob Fatu")),
            ),
            id_prefix="bl26",
        )
        assert [c.id for c in plan.cards] == ["bl26-whc", "bl26-opener"]
        assert plan.added == ()


class TestLooseNameMatching:
    def test_a_hand_written_team_label_still_matches(self) -> None:
        """실측: 픽스처는 `"Lucha Brothers — Penta & Rey Fénix"` 한 칸으로 적는다.

        정확 일치로 맞추면 한 건도 안 맞고 기존 id가 통째로 갈린다.
        """
        plan = plan_cards(
            "worlds-collide",
            (
                _row(
                    1, "The Lucha Brothers (Penta and Rey Fenix)", "Los Perros del Mal"
                ),
            ),
            (
                ExistingCard(
                    "wc26-tag",
                    ("Lucha Brothers — Penta & Rey Fénix", "Los Perros del Mal — Daga"),
                ),
            ),
            id_prefix="wc26",
        )
        assert [c.id for c in plan.cards] == ["wc26-tag"]

    def test_one_shared_word_is_not_enough(self) -> None:
        """흔한 성 하나로 엉뚱한 경기에 붙으면 남의 id를 빼앗는다."""
        plan = plan_cards(
            "backlash",
            (_row(1, "Dominik Mysterio", "John Cena"),),
            (ExistingCard("bl26-rey", ("Rey Mysterio", "Logan Paul")),),
            id_prefix="bl26",
        )
        assert plan.cards[0].id_inherited is False
        assert plan.only_in_fixture == ("bl26-rey",)


class TestMissingIsReportedNotDeleted:
    def test_a_fixture_only_match_is_reported(self) -> None:
        plan = plan_cards(
            "survivor-series",
            (),
            (ExistingCard("ss26-ic", ("Dominik Mysterio", "John Cena")),),
            id_prefix="ss26",
        )
        assert plan.only_in_fixture == ("ss26-ic",)
        assert plan.cards == ()

    def test_nothing_in_the_plan_proposes_a_deletion(self) -> None:
        """계획에는 '지운다'는 칸이 없다 — 위키 누락과 실제 취소를 구별할 수 없다."""
        plan = plan_cards(
            "survivor-series",
            (),
            (ExistingCard("ss26-ic", ("Dominik Mysterio", "John Cena")),),
            id_prefix="ss26",
        )
        assert not hasattr(plan, "removed")


class TestSuggestedIds:
    def test_an_undetermined_side_is_left_out_of_the_suggested_id(self) -> None:
        """`Becky Lynch or Liv Morgan`을 id에 넣으면 확정되는 날 id가 바뀐다."""
        row = WikiMatchRow(
            number=1,
            raw="Stephanie Vaquer (c) vs. Becky Lynch or Liv Morgan",
            stipulation="Singles match for the Women's World Championship",
            is_card=True,
            competitors=(
                WikiCompetitor("Stephanie Vaquer", is_champion=True),
                WikiCompetitor("Becky Lynch or Liv Morgan", undetermined=True),
            ),
        )
        plan = plan_cards("money-in-the-bank", (row,), (), id_prefix="mitb26")
        assert plan.cards[0].id == "mitb26-vaquer"

    def test_a_suggested_id_never_collides_with_an_existing_one(self) -> None:
        plan = plan_cards(
            "backlash",
            (_row(1, "Bronson Reed", "Oba Femi"), _row(2, "Bronson Reed", "Oba Femi")),
            (),
            id_prefix="bl26",
        )
        assert [c.id for c in plan.cards] == ["bl26-reed-femi", "bl26-reed-femi-2"]

    def test_accents_fold_so_the_id_stays_ascii(self) -> None:
        plan = plan_cards(
            "worlds-collide",
            (_row(1, "Rey Fénix", "Dragon Lee"),),
            (),
            id_prefix="wc26",
        )
        assert plan.cards[0].id == "wc26-fenix-lee"
