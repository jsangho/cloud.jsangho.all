"""오즈 에이전트 테스트 — LLM·네트워크 호출 0회. 배당 숫자만 본다."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kayfabe.adapter.outbound.agents.odds_scout_agent import BookmakerOddsScout
from kayfabe.app.dtos.agent_prediction_dto import MatchContext, MatchOption
from kayfabe.domain.entities.agent_prediction import AgentKind
from kayfabe.domain.services.odds_consensus import BookmakerQuote


def context(
    odds: tuple[float, ...] | None, options: tuple[MatchOption, ...] | None = None
) -> MatchContext:
    return MatchContext(
        event_slug="summerslam",
        event_label="SummerSlam",
        match_key="ss26-n2-whc",
        title="World Heavyweight Championship",
        match_format="singles",
        options=options
        or (
            MatchOption(pick="left", name="Roman Reigns"),
            MatchOption(pick="right", name="Seth Rollins"),
        ),
        bookmaker_decimal=odds,
    )


@pytest.mark.asyncio
async def test_picks_the_lowest_odds_with_implied_probability_as_weight() -> None:
    report = await BookmakerOddsScout().analyze(context((1.14, 5.0)))

    assert report.agent is AgentKind.ODDS
    assert report.pick == "left"
    # 1/1.14 = 0.877, 1/5.0 = 0.2 → 정규화 0.814
    assert report.weight == pytest.approx(0.8144, abs=1e-3)
    assert "Roman Reigns" in report.summary


@pytest.mark.asyncio
async def test_overround_is_removed_so_confidence_is_not_inflated() -> None:
    """역수 합이 1을 넘는다(북메이커 마진). 그대로 쓰면 확신이 부풀어 오른다."""
    report = await BookmakerOddsScout().analyze(context((1.9, 1.9)))

    # 정규화 전이면 0.526, 후에는 정확히 0.5
    assert report.weight == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_even_odds_leave_the_decision_to_other_agents() -> None:
    """배당이 팽팽하면 확신 0.5 — 서사·루머가 결과를 가른다."""
    report = await BookmakerOddsScout().analyze(context((2.0, 2.0)))

    assert report.pick == "left"
    assert report.weight == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_multi_match_uses_index_pick() -> None:
    options = (
        MatchOption(pick="0", name="Kevin Owens"),
        MatchOption(pick="1", name="Finn Bálor"),
        MatchOption(pick="2", name="Gunther"),
    )
    report = await BookmakerOddsScout().analyze(context((4.0, 2.0, 6.0), options))

    assert report.pick == "1"
    assert report.weight == pytest.approx(0.5455, abs=1e-3)


@pytest.mark.asyncio
@pytest.mark.parametrize("odds", [None, (), (0.0, 2.0), (-1.0, 2.0)])
async def test_missing_or_invalid_odds_is_no_opinion_not_a_guess(
    odds: tuple[float, ...] | None,
) -> None:
    report = await BookmakerOddsScout().analyze(context(odds))

    assert report.pick is None
    assert report.weight == 0.0
    assert report.has_opinion is False


@pytest.mark.asyncio
async def test_odds_count_mismatch_is_no_opinion() -> None:
    """선택지 3개인데 배당 2개면 어느 쪽 배당인지 알 수 없다."""
    options = (
        MatchOption(pick="0", name="A"),
        MatchOption(pick="1", name="B"),
        MatchOption(pick="2", name="C"),
    )
    report = await BookmakerOddsScout().analyze(context((1.5, 2.5), options))

    assert report.pick is None


@pytest.mark.asyncio
async def test_report_cites_no_external_source() -> None:
    """배당은 카드에 실려 온 값이라 인용할 URL이 없다 — 없는 출처를 지어내지 않는다."""
    report = await BookmakerOddsScout().analyze(context((1.5, 2.5)))

    assert report.sources == ()


def with_quotes(*quotes: BookmakerQuote) -> MatchContext:
    ctx = context(None)
    return replace(ctx, bookmaker_quotes=quotes)


@pytest.mark.asyncio
async def test_several_books_are_merged_and_named_in_the_summary() -> None:
    report = await BookmakerOddsScout().analyze(
        with_quotes(
            BookmakerQuote(book="BetOnline", decimals=(1.5, 2.5)),
            BookmakerQuote(book="Bovada", decimals=(1.6, 2.4)),
        )
    )

    assert report.pick == "left"
    # 요약이 몇 곳인지·어디인지를 말한다 — 확률만 적으면 근거가 사라진다.
    assert "2곳" in report.summary
    assert "BetOnline" in report.summary and "Bovada" in report.summary


@pytest.mark.asyncio
async def test_quotes_win_over_the_single_card_odds() -> None:
    """둘 다 있으면 호가가 이긴다 — 합의가 더 많은 사실을 본 값이다."""
    ctx = replace(
        context((1.01, 30.0)),
        bookmaker_quotes=(
            BookmakerQuote(book="A", decimals=(3.0, 1.4)),
            BookmakerQuote(book="B", decimals=(3.2, 1.38)),
        ),
    )

    report = await BookmakerOddsScout().analyze(ctx)

    # 카드의 배당만 봤다면 left를 0.97로 골랐을 자리다.
    assert report.pick == "right"


@pytest.mark.asyncio
async def test_source_urls_on_quotes_become_report_sources() -> None:
    report = await BookmakerOddsScout().analyze(
        with_quotes(
            BookmakerQuote(book="A", decimals=(1.5, 2.5), source_url="https://x/1"),
            BookmakerQuote(book="B", decimals=(1.6, 2.4), source_url="https://x/1"),
            BookmakerQuote(book="C", decimals=(1.55, 2.45), source_url="https://x/2"),
        )
    )

    # 중복은 접고 적힌 순서를 지킨다.
    assert report.sources == ("https://x/1", "https://x/2")


@pytest.mark.asyncio
async def test_unusable_quotes_fall_back_to_no_opinion() -> None:
    report = await BookmakerOddsScout().analyze(
        with_quotes(BookmakerQuote(book="A", decimals=(0.0, 2.0)))
    )

    assert report.pick is None
    assert report.has_opinion is False
