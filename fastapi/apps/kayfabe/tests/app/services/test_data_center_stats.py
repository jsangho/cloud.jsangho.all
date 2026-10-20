"""데이터 센터 집계 — DB 없이 규칙을 잠근다 (Phase 2).

여기서 지키는 것은 셋이다.

| | |
|---|---|
| 태그팀을 사람으로 편다 | 카드에 팀 이름이 적혀 있어도 전적은 개인에게 쌓인다 |
| 못 정한 것은 만들지 않는다 | 승자를 못 되짚으면 무효 · 끝난 경기가 없으면 승률은 `None` |
| 표본이 얇으면 순위에 안 올린다 | 1승 0패 100%가 순위표 꼭대기를 먹으면 순위가 뜻을 잃는다 |
"""

from __future__ import annotations

import json

# **이 저장소에는 원래 순환 임포트가 하나 있다** (내가 만든 것이 아니다):
# `records_scoring` → 인바운드 스키마 → `api` 패키지 초기화 → `ple_matches_router`
# → 프로바이더 → `ple_matches_pg_repository` → 다시 `records_scoring`(초기화 중).
# `python -c "import kayfabe.app.services.records_scoring"` 한 줄로 재현된다.
#
# 런타임은 `main.py`가 라우터를 먼저 올려서 안전하고, 여기서만 진입 순서가 반대라
# 라우터 패키지를 한 번 깨워 둔다. 이 줄을 지우면 이 파일이 통째로 수집 에러를 낸다.
import kayfabe.adapter.inbound.api  # noqa: F401
from kayfabe.app.services import data_center_stats as stats


def _card(left: str, right: str) -> str:
    return json.dumps(
        {
            "format": "singles",
            "left": {"name": left},
            "right": {"name": right},
        }
    )


def _match(
    *,
    slug: str = "summerslam",
    key: str = "m1",
    title: str = "Single Match",
    left: str = "Cody Rhodes",
    right: str = "Seth Rollins",
    winner_pick: str | None = "left",
    winner_name: str | None = None,
    status: str = "finished",
    month: int | None = 8,
) -> stats.MatchRow:
    return stats.MatchRow(
        event_slug=slug,
        event_label=slug.title(),
        month=month,
        year=2026,
        event_status="finished",
        match_key=key,
        title=title,
        format="singles",
        card_json=_card(left, right),
        winner_pick=winner_pick,
        winner_name=winner_name,
        status=status,
    )


class TestRecordsAreCountedOnce:
    def test_a_winner_and_a_loser_come_out_of_one_match(self) -> None:
        records = stats.records_by_wrestler([_match()])
        assert records["Cody Rhodes"].wins == 1
        assert records["Cody Rhodes"].losses == 0
        assert records["Seth Rollins"].losses == 1

    def test_win_rate_is_none_before_anything_is_decided(self) -> None:
        """**0.0이 아니라 `None`이다** — 화면이 그 칸을 비워야 한다."""
        pending = _match(winner_pick=None, status="scheduled")
        records = stats.records_by_wrestler([pending])
        assert records["Cody Rhodes"].win_rate is None

    def test_win_rate_counts_only_decided_matches(self) -> None:
        rows = [
            _match(key="m1"),
            _match(key="m2", winner_pick="right"),
            _match(key="m3", winner_pick=None, status="scheduled"),
        ]
        record = stats.records_by_wrestler(rows)["Cody Rhodes"]
        assert (record.wins, record.losses, record.pending) == (1, 1, 1)
        assert record.win_rate == 0.5
        assert record.total == 3

    def test_a_tag_team_name_lands_on_the_people(self) -> None:
        """카드에는 팀 이름이 적히지만 전적은 사람에게 쌓인다."""
        row = _match(left="The Street Profits", right="Fraxiom")
        records = stats.records_by_wrestler([row])
        assert "Montez Ford" in records
        assert "Angelo Dawkins" in records
        assert records["Montez Ford"].wins == 1


class TestFacts:
    def test_a_championship_match_is_marked(self) -> None:
        fact = stats.to_fact(_match(title="Undisputed WWE Championship"))
        assert fact.is_title_match is True

    def test_an_ordinary_match_is_not(self) -> None:
        assert stats.to_fact(_match(title="Single Match")).is_title_match is False

    def test_the_winner_is_derived_from_the_pick(self) -> None:
        """`winner_name`이 비어 있어도 `winner_pick`으로 되짚는다 — 태그 경기에 흔하다."""
        fact = stats.to_fact(_match(winner_name=None, winner_pick="left"))
        assert fact.winner_name == "Cody Rhodes"

    def test_participants_are_individuals(self) -> None:
        fact = stats.to_fact(_match())
        assert set(fact.participants) == {"Cody Rhodes", "Seth Rollins"}


class TestBeltStats:
    """**현존하는 벨트만 센다** (2026-10-07 사용자 결정).

    옛 이름(`WWE Championship`·`United States Championship`)은 후신으로 합치고,
    폐지된 이름(`ECW Championship`)은 사유와 함께 빠진다.
    """

    ROWS = [
        stats.TitleRow("John Cena", "WWE Championship", "WrestleMania 21"),
        stats.TitleRow("John Cena", "WWE Championship", "Royal Rumble 2008"),
        stats.TitleRow("Randy Orton", "WWE Championship", "SummerSlam 2007"),
        stats.TitleRow("Randy Orton", "United States Championship", "Backlash 2004"),
        stats.TitleRow("CM Punk", "ECW Championship", "ECW 2007"),
    ]

    def test_former_names_merge_into_the_current_belt(self) -> None:
        by_belt = {b.belt_name: b for b in stats.current_belt_stats(self.ROWS).belts}
        wwe = by_belt["Undisputed WWE Championship"]
        assert (wwe.reigns, wwe.holders) == (3, 2)
        assert (wwe.top_holder, wwe.top_holder_reigns) == ("John Cena", 2)
        assert "WWE Championship" in wwe.former_names

    def test_retired_belts_leave_with_a_reason(self) -> None:
        excluded = stats.current_belt_stats(self.ROWS).excluded
        by_name = {e.belt_name: e for e in excluded}
        assert "ECW Championship" in by_name
        assert by_name["ECW Championship"].reigns == 1
        assert by_name["ECW Championship"].reason
        assert "ECW Championship" not in {
            b.belt_name for b in stats.current_belt_stats(self.ROWS).belts
        }

    def test_belts_without_rows_stay_at_zero(self) -> None:
        """보드에 있는 벨트는 기록이 없어도 사라지지 않는다 — 화면이 "기록 없음"을 적는다."""
        by_belt = {b.belt_name: b for b in stats.current_belt_stats(self.ROWS).belts}
        evolve = by_belt["WWE Evolve Championship"]
        assert (evolve.reigns, evolve.holders, evolve.top_holder) == (0, 0, None)

    def test_belt_detail_keeps_the_name_of_the_day(self) -> None:
        detail = stats.belt_detail(self.ROWS, "Undisputed WWE Championship")
        assert detail is not None
        assert detail.reigns == 3
        assert [h.name for h in detail.holders] == ["John Cena", "Randy Orton"]
        assert {r.belt_name for h in detail.holders for r in h.history} == {
            "WWE Championship"
        }

    def test_belt_detail_refuses_a_belt_that_is_gone(self) -> None:
        assert stats.belt_detail(self.ROWS, "ECW Championship") is None

    def test_top_holders_count_belts_and_reigns(self) -> None:
        top = stats.top_holders(self.ROWS)
        assert top[0].name in {"John Cena", "Randy Orton"}
        by_name = {h.name: h for h in top}
        assert by_name["Randy Orton"].reigns == 2
        assert by_name["Randy Orton"].belts == 2

    def test_nothing_pretends_to_know_reign_length(self) -> None:
        """**최장 재위는 없다** (§9).

        이유는 더 이상 "자유 텍스트"가 아니다 — 2026-10-20부터 날짜가 읽힌다
        (388/388). 막혀 있는 것은 **끝난 날짜**이고, 다음 획득을 끝으로 보는 것도
        계보가 희소해서 안 된다(`BeltStat` 독스트링에 실측이 있다).
        """
        assert not hasattr(stats.BeltStat, "longest_reign_days")


class TestBrandsComeFromTheData:
    ROWS = [
        stats.WrestlerRow(name="A", brand="RAW"),
        stats.WrestlerRow(name="B", brand="RAW"),
        stats.WrestlerRow(name="C", brand="NXT"),
        stats.WrestlerRow(name="D", brand=None),
    ]

    def test_distribution_counts_every_row(self) -> None:
        assert stats.brand_distribution(self.ROWS)[0] == ("RAW", 2)

    def test_a_missing_brand_is_not_invented(self) -> None:
        counts = dict(stats.brand_distribution(self.ROWS))
        assert counts["미지정"] == 1

    def test_filter_options_exclude_the_unset_bucket(self) -> None:
        assert stats.known_brands(self.ROWS) == ["RAW", "NXT"]


class TestWinRateRanking:
    def test_a_thin_sample_never_tops_the_chart(self) -> None:
        records = {
            "One Match Wonder": stats.RecordCount(wins=1),
            "Real Contender": stats.RecordCount(wins=4, losses=1),
        }
        rated = stats.top_win_rates(records)
        assert [r.name for r in rated] == ["Real Contender"]

    def test_the_threshold_is_the_documented_constant(self) -> None:
        records = {"Borderline": stats.RecordCount(wins=stats.MIN_MATCHES_FOR_RATE)}
        assert stats.top_win_rates(records)[0].name == "Borderline"


class TestEventStats:
    def test_events_without_a_month_go_last(self) -> None:
        facts = stats.to_facts(
            [
                _match(slug="bad-blood", key="b1", month=None),
                _match(slug="royal-rumble", key="r1", month=1),
            ]
        )
        assert [e.slug for e in stats.event_stats(facts)] == [
            "royal-rumble",
            "bad-blood",
        ]

    def test_finished_and_title_matches_are_counted(self) -> None:
        facts = stats.to_facts(
            [
                _match(key="m1", title="Undisputed WWE Championship"),
                _match(key="m2", winner_pick=None, status="scheduled"),
            ]
        )
        stat = stats.event_stats(facts)[0]
        assert (stat.matches, stat.finished, stat.title_matches) == (2, 1, 1)


class TestFirstBeltAges:
    """첫 벨트를 든 나이 (2026-10-20).

    **추론이 없다** — 생일과 첫 획득일 둘 다 기록된 값일 때만 센다. 둘 중 하나가
    없으면 그 사람은 빠지고, 분모(`title_holders`)가 그 사실을 드러낸다.
    """

    def _rows(self):
        wrestlers = [
            stats.WrestlerRow(name="Paige", birth_date="1992-08-17"),
            stats.WrestlerRow(name="Tama Tonga", birth_date="1982-11-15"),
            # 연도를 모른다 — 나이를 못 센다
            stats.WrestlerRow(name="Old Timer", birth_date="????-07-16"),
            # 타이틀이 없다 — 이 축에 안 나온다
            stats.WrestlerRow(name="No Belt", birth_date="2000-01-01"),
        ]
        titles = [
            stats.TitleRow(
                competitor_name="Paige",
                belt_name="NXT Women's Championship",
                won_at="NXT — June 20, 2013",
            ),
            # 더 늦은 획득 — 첫 획득이 아니므로 무시돼야 한다
            stats.TitleRow(
                competitor_name="Paige",
                belt_name="Divas Championship",
                won_at="Raw — April 7, 2014",
            ),
            stats.TitleRow(
                competitor_name="Tama Tonga",
                belt_name="WWE Tag Team Championship",
                won_at="SmackDown — August 14, 2026",
            ),
            stats.TitleRow(
                competitor_name="Old Timer",
                belt_name="WWE Championship",
                won_at="Raw — March 1, 2010",
            ),
            # 날짜를 못 읽는 행 — 건너뛴다
            stats.TitleRow(
                competitor_name="Paige",
                belt_name="Unknown Belt",
                won_at="어딘가",
            ),
        ]
        return wrestlers, titles

    def test_uses_the_earliest_acquisition(self) -> None:
        board = stats.first_belt_ages(*self._rows())
        paige = next(e for e in board.entries if e.name == "Paige")
        assert paige.won_on == "2013-06-20"
        assert paige.age == 20
        assert paige.belt_name == "NXT Women's Championship"

    def test_sorted_youngest_first(self) -> None:
        board = stats.first_belt_ages(*self._rows())
        assert [e.age for e in board.entries] == sorted(e.age for e in board.entries)

    def test_partial_birth_date_is_skipped(self) -> None:
        """`????-07-16`은 날짜로는 쓰이지만 **나이로는 못 쓴다**."""
        board = stats.first_belt_ages(*self._rows())
        assert all(e.name != "Old Timer" for e in board.entries)

    def test_denominator_counts_all_title_holders(self) -> None:
        """분모는 **타이틀 보유자 전원**이다 — 생일을 몰라 빠진 사람도 센다."""
        board = stats.first_belt_ages(*self._rows())
        assert board.sample == 2
        assert board.title_holders == 3

    def test_no_titles_means_empty_board(self) -> None:
        wrestlers, _ = self._rows()
        board = stats.first_belt_ages(wrestlers, [])
        assert board.entries == ()
        assert board.sample == 0
        assert board.title_holders == 0
