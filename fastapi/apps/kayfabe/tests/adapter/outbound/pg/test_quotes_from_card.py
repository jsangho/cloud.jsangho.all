"""카드 JSON → 북메이커 호가 파싱. **손으로 적는 자리라 오타를 견뎌야 한다.**

DB를 쓰지 않는다 — 순수 함수 하나를 부른다.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from kayfabe.adapter.outbound.pg.agent_prediction_pg_repository import quotes_from_card


def card(quotes: Any) -> dict[str, Any]:
    return {"format": "singles", "bookmakerQuotes": quotes}


class TestShape:
    def test_singles_accepts_the_left_right_object(self) -> None:
        parsed = quotes_from_card(
            card(
                [
                    {
                        "book": "BetOnline",
                        "decimals": {"left": 1.07, "right": 7.0},
                        "observedAt": "2026-09-27",
                        "sourceUrl": "https://example.test/a",
                    }
                ]
            ),
            2,
        )

        assert len(parsed) == 1
        assert parsed[0].book == "BetOnline"
        assert parsed[0].decimals == (1.07, 7.0)
        assert parsed[0].observed_at == date(2026, 9, 27)
        assert parsed[0].source_url == "https://example.test/a"

    def test_multi_accepts_the_plain_array(self) -> None:
        parsed = quotes_from_card(card([{"book": "A", "decimals": [2.0, 3.0, 4.0]}]), 3)

        assert parsed[0].decimals == (2.0, 3.0, 4.0)

    def test_missing_key_is_empty_not_an_error(self) -> None:
        assert quotes_from_card({"format": "singles"}, 2) == ()


class TestTolerance:
    def test_one_bad_row_does_not_lose_the_rest(self) -> None:
        """한 줄의 오타 때문에 경기 전체의 배당을 잃는 것보다 그 줄만 빠지는 편이 낫다."""
        parsed = quotes_from_card(
            card(
                [
                    {"book": "Good", "decimals": {"left": 1.5, "right": 2.5}},
                    {"book": "NoDecimals"},
                    {"decimals": {"left": 1.5, "right": 2.5}},
                    {"book": "Negative", "decimals": {"left": -1.0, "right": 2.5}},
                    {"book": "WrongCount", "decimals": [1.5, 2.5, 3.5]},
                    "not-an-object",
                ]
            ),
            2,
        )

        assert [q.book for q in parsed] == ["Good"]

    def test_unreadable_observed_date_is_none_not_today(self) -> None:
        """**모르는 관측일을 오늘로 채우지 않는다** — 옛 호가가 최신을 밀어낸다."""
        parsed = quotes_from_card(
            card(
                [
                    {
                        "book": "A",
                        "decimals": {"left": 1.5, "right": 2.5},
                        "observedAt": "2026/09/27",
                    }
                ]
            ),
            2,
        )

        assert parsed[0].observed_at is None

    def test_quotes_field_of_the_wrong_type_is_ignored(self) -> None:
        assert quotes_from_card(card({"book": "A"}), 2) == ()
        assert quotes_from_card(card("BetOnline 1.5/2.5"), 2) == ()
