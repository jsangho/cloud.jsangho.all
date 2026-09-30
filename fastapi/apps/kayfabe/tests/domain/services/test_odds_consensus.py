"""배당 합의 테스트 — 순수 함수라 픽스처도 네트워크도 없다."""

from __future__ import annotations

from datetime import date

import pytest

from kayfabe.domain.services.odds_consensus import (
    BookmakerQuote,
    confidence_from,
    consensus,
    implied_probabilities,
    latest_per_book,
)


def quote(book: str, *decimals: float, observed: date | None = None) -> BookmakerQuote:
    return BookmakerQuote(book=book, decimals=decimals, observed_at=observed)


class TestConsensus:
    def test_single_book_matches_the_old_single_quote_maths(self) -> None:
        """**호가가 한 곳이면 `odds@1`과 같은 값이어야 한다.**

        배당을 한 곳만 적어 둔 경기가 아직 많고, 그쪽 판단이 이 변경으로 달라지면
        "합의를 도입했더니 옛 예측이 재현되지 않는다"가 된다.
        """
        merged = consensus((quote("BetOnline", 1.14, 5.0),), 2)

        assert merged is not None
        assert merged.probabilities[0] == pytest.approx(0.8144, abs=1e-3)
        assert merged.dispersion == 0.0
        assert confidence_from(merged, 0) == pytest.approx(0.8144, abs=1e-3)

    def test_two_books_are_averaged_and_renormalized(self) -> None:
        merged = consensus(
            (quote("A", 1.5, 2.5), quote("B", 1.8, 2.0)),
            2,
        )

        assert merged is not None
        # A: 0.625 / 0.375, B: 0.5263 / 0.4737 → 중앙값(=둘의 평균) 0.5757 / 0.4243
        assert merged.probabilities[0] == pytest.approx(0.5757, abs=1e-3)
        assert sum(merged.probabilities) == pytest.approx(1.0)
        assert merged.books == ("A", "B")

    def test_median_ignores_a_single_mispriced_book(self) -> None:
        """**중앙값을 쓰는 이유가 이것이다.** 한 곳이 라인을 잘못 걸어도 축이 안 흔들린다."""
        sane = (quote("A", 1.5, 2.5), quote("B", 1.52, 2.45))
        with_outlier = (*sane, quote("C", 6.0, 1.15))

        without = consensus(sane, 2)
        withc = consensus(with_outlier, 2)

        assert without is not None and withc is not None
        # 이상치가 섞여도 favorite은 그대로고 확률도 거의 안 움직인다.
        assert withc.probabilities[0] == pytest.approx(
            without.probabilities[0], abs=0.02
        )

    def test_disagreement_between_books_is_reported_as_dispersion(self) -> None:
        merged = consensus((quote("A", 1.1, 8.0), quote("B", 2.0, 1.8)), 2)

        assert merged is not None
        # A는 favorite을 0.879로, B는 0.474로 본다.
        assert merged.dispersion == pytest.approx(0.405, abs=1e-2)

    def test_dispersion_pulls_confidence_toward_the_uniform_split(self) -> None:
        """의견이 갈리면 시장은 **모르는 것이다.** 0이 아니라 1/n 쪽으로 당긴다."""
        merged = consensus((quote("A", 1.1, 8.0), quote("B", 2.0, 1.8)), 2)

        assert merged is not None
        favorite = max(range(2), key=lambda i: merged.probabilities[i])
        confidence = confidence_from(merged, favorite)

        assert confidence < merged.probabilities[favorite]
        # 균등분포(0.5)를 넘어 반대편으로 가지 않는다 — 시장이 한 적 없는 말이다.
        assert confidence > 0.5

    def test_quote_whose_length_disagrees_with_the_card_is_dropped(self) -> None:
        """참가자가 추가된 뒤 남아 있는 옛 호가가 엉뚱한 선수에게 붙으면 안 된다."""
        merged = consensus((quote("A", 1.5, 2.5), quote("B", 2.0, 3.0, 4.0)), 3)

        assert merged is not None
        assert merged.books == ("B",)

    def test_no_usable_quote_is_none_not_a_guess(self) -> None:
        assert consensus((), 2) is None
        assert consensus((quote("A", 0.0, 2.0),), 2) is None
        assert consensus((quote("A", 1.5, 2.5),), 3) is None


class TestLatestPerBook:
    def test_same_book_twice_votes_once(self) -> None:
        """라인이 움직인 기록은 표본이 아니다 — 세 번 적힌 곳이 합의를 지배하면 안 된다."""
        quotes = (
            quote("BetOnline", 1.17, 4.5, observed=date(2026, 9, 26)),
            quote("BetOnline", 1.07, 7.0, observed=date(2026, 9, 27)),
        )

        latest = latest_per_book(quotes)

        assert len(latest) == 1
        assert latest[0].decimals == (1.07, 7.0)

    def test_undated_quote_never_displaces_a_dated_one(self) -> None:
        quotes = (
            quote("A", 1.5, 2.5, observed=date(2026, 9, 27)),
            quote("A", 9.9, 1.01),
        )

        assert latest_per_book(quotes)[0].decimals == (1.5, 2.5)

    def test_books_come_back_in_name_order(self) -> None:
        quotes = (quote("Zed", 1.5, 2.5), quote("Ace", 1.6, 2.4))

        assert [q.book for q in latest_per_book(quotes)] == ["Ace", "Zed"]


class TestImpliedProbabilities:
    def test_overround_is_removed(self) -> None:
        probabilities = implied_probabilities((1.9, 1.9))

        assert probabilities == (pytest.approx(0.5), pytest.approx(0.5))

    @pytest.mark.parametrize("decimals", [(), (0.0, 2.0), (-1.0, 2.0)])
    def test_unusable_odds_are_none(self, decimals: tuple[float, ...]) -> None:
        assert implied_probabilities(decimals) is None
