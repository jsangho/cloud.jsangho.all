"""합성 규칙 테스트 — 고정 리포트 픽스처만 쓴다. LLM·DB·네트워크 호출 0회.

하네스 §10-T1의 완료 판정이 이 파일이다.
"""

from __future__ import annotations

import pytest

from kayfabe.domain.entities.agent_prediction import AgentKind, AgentReport
from kayfabe.domain.services.prediction_synthesis import (
    ReportsUnavailableError,
    synthesize,
)


def report(agent: AgentKind, pick: str | None, weight: float = 0.5) -> AgentReport:
    return AgentReport(agent=agent, pick=pick, weight=weight, summary="근거 요약")


def test_unanimous_agents_give_full_probability_and_confidence() -> None:
    reports = [
        report(AgentKind.STORYLINE, "left", 0.8),
        report(AgentKind.ODDS, "left", 0.6),
        report(AgentKind.RUMOR, "left", 0.4),
    ]

    result = synthesize(reports, agent_count=3)

    assert result.pick == "left"
    assert result.win_probability == 1.0
    assert result.confidence == 1.0


def test_split_opinion_lowers_confidence_but_heavier_side_wins() -> None:
    reports = [
        report(AgentKind.STORYLINE, "left", 0.8),
        report(AgentKind.ODDS, "left", 0.4),
        report(AgentKind.RUMOR, "right", 0.4),
    ]

    result = synthesize(reports, agent_count=3)

    assert result.pick == "left"
    # 가중 득표 1.2 / 1.6
    assert result.win_probability == pytest.approx(0.75)
    # 셋 중 둘이 동의 → 합의도 2/3
    assert result.confidence == pytest.approx(2 / 3)


def test_lone_opinion_does_not_claim_full_confidence() -> None:
    """셋 중 하나만 답했는데 확신 100%가 되면 화면이 사용자를 오도한다."""
    reports = [report(AgentKind.STORYLINE, "left", 0.9)]

    result = synthesize(reports, agent_count=3)

    assert result.win_probability == 1.0
    assert result.confidence == pytest.approx(1 / 3)


def test_agents_without_opinion_do_not_count_as_disagreement() -> None:
    """루머가 참고할 소식이 없는 것은 반대표가 아니다 — 다만 합의도는 덜 찬다."""
    reports = [
        report(AgentKind.STORYLINE, "left", 0.7),
        report(AgentKind.ODDS, "left", 0.5),
        report(AgentKind.RUMOR, None, 0.0),
    ]

    result = synthesize(reports, agent_count=3)

    assert result.pick == "left"
    assert result.win_probability == 1.0
    # 둘 다 같은 쪽이지만 답한 사람이 셋 중 둘이라 확신은 2/3
    assert result.confidence == pytest.approx(2 / 3)


def test_multi_match_picks_index_string_with_highest_share() -> None:
    """다인전의 pick은 인덱스 문자열이다 (`ple_matches.winner_pick`와 같은 형식)."""
    reports = [
        report(AgentKind.STORYLINE, "2", 0.6),
        report(AgentKind.ODDS, "0", 0.3),
        report(AgentKind.RUMOR, "2", 0.1),
    ]

    result = synthesize(reports, agent_count=3)

    assert result.pick == "2"
    assert result.win_probability == pytest.approx(0.7)


def test_tie_is_broken_deterministically() -> None:
    """같은 입력이면 같은 결과여야 재생성 때 예측이 흔들리지 않는다."""
    reports = [
        report(AgentKind.STORYLINE, "right", 0.5),
        report(AgentKind.ODDS, "left", 0.5),
    ]

    first = synthesize(reports, agent_count=2)
    second = synthesize(list(reversed(reports)), agent_count=2)

    assert first.pick == second.pick == "left"
    assert first.win_probability == pytest.approx(0.5)


def test_all_zero_weights_fall_back_to_equal_shares() -> None:
    """의견은 냈지만 확신이 0인 것은 정상 상태다 — 실패로 만들지 않는다."""
    reports = [
        report(AgentKind.STORYLINE, "left", 0.0),
        report(AgentKind.ODDS, "right", 0.0),
    ]

    result = synthesize(reports, agent_count=2)

    assert result.win_probability == pytest.approx(0.5)
    assert result.confidence == pytest.approx(0.5)


def test_no_opinion_at_all_raises_instead_of_guessing_half() -> None:
    reports = [
        report(AgentKind.STORYLINE, None, 0.0),
        report(AgentKind.ODDS, None, 0.0),
    ]

    with pytest.raises(ReportsUnavailableError):
        synthesize(reports, agent_count=2)


def test_empty_reports_raise() -> None:
    with pytest.raises(ReportsUnavailableError):
        synthesize([], agent_count=3)


def test_agent_count_must_be_positive() -> None:
    with pytest.raises(ValueError):
        synthesize([report(AgentKind.ODDS, "left")], agent_count=0)
