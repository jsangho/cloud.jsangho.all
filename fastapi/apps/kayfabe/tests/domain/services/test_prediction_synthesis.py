"""합성 규칙 테스트 — 고정 리포트 픽스처만 쓴다. LLM·DB·네트워크 호출 0회.

하네스 §10-T1의 완료 판정이 이 파일이다.

**승률은 선택지들이 나눠 갖는다.** 예전 규칙(가중 득표 비중)은 의견을 낸 에이전트가
전원 같은 쪽이면 무조건 100%가 나와, 오즈가 배당에서 계산해 온 확률이 사라졌다.
지금은 각 리포트를 분포로 펴서 평균한다.
"""

from __future__ import annotations

import pytest

from kayfabe.domain.entities.agent_prediction import AgentKind, AgentReport
from kayfabe.domain.services.prediction_synthesis import (
    ReportsUnavailableError,
    synthesize,
)

_TWO = ("left", "right")
_THREE = ("0", "1", "2")


def report(agent: AgentKind, pick: str | None, weight: float = 0.5) -> AgentReport:
    return AgentReport(agent=agent, pick=pick, weight=weight, summary="근거 요약")


def test_unanimous_agents_do_not_reach_full_probability() -> None:
    """전원이 같은 쪽이어도 100%가 아니다 — 상대가 가진 몫이 남는다."""
    reports = [
        report(AgentKind.STORYLINE, "left", 0.8),
        report(AgentKind.ODDS, "left", 0.6),
        report(AgentKind.RUMOR, "left", 0.4),
    ]

    result = synthesize(reports, agent_count=3, options=_TWO)

    assert result.pick == "left"
    # 0.8 · 0.6 · (0.4→균등 0.5)의 평균
    assert result.win_probability == pytest.approx(0.6333, abs=1e-4)
    assert result.probabilities["right"] == pytest.approx(0.3667, abs=1e-4)
    assert result.confidence == 1.0


def test_probabilities_sum_to_one() -> None:
    reports = [
        report(AgentKind.STORYLINE, "2", 0.6),
        report(AgentKind.ODDS, "0", 0.5),
    ]

    result = synthesize(reports, agent_count=3, options=_THREE)

    assert sum(result.probabilities.values()) == pytest.approx(1.0)
    assert set(result.probabilities) == set(_THREE)


def test_split_opinion_lowers_confidence_but_heavier_side_wins() -> None:
    reports = [
        report(AgentKind.STORYLINE, "left", 0.8),
        report(AgentKind.ODDS, "left", 0.4),
        report(AgentKind.RUMOR, "right", 0.4),
    ]

    result = synthesize(reports, agent_count=3, options=_TWO)

    assert result.pick == "left"
    assert result.win_probability == pytest.approx(0.6)
    # 셋 중 둘이 동의 → 합의도 2/3
    assert result.confidence == pytest.approx(2 / 3)


def test_lone_opinion_does_not_claim_full_confidence() -> None:
    """셋 중 하나만 답했는데 확신 100%가 되면 화면이 사용자를 오도한다."""
    reports = [report(AgentKind.STORYLINE, "left", 0.9)]

    result = synthesize(reports, agent_count=3, options=_TWO)

    # 한 명뿐이라 그 사람의 분포가 그대로 결과가 된다.
    assert result.win_probability == pytest.approx(0.9)
    assert result.confidence == pytest.approx(1 / 3)


def test_odds_probability_survives_when_it_is_the_only_voice() -> None:
    """오즈가 배당에서 계산한 내재 확률이 정규화에 먹히지 않는다."""
    reports = [report(AgentKind.ODDS, "left", 0.62)]

    result = synthesize(reports, agent_count=3, options=_TWO)

    assert result.win_probability == pytest.approx(0.62)
    assert result.probabilities["right"] == pytest.approx(0.38)


def test_low_confidence_never_votes_against_its_own_pick() -> None:
    """확신이 낮다는 것은 '잘 모르겠다'이지 '내 pick이 진다'가 아니다."""
    reports = [report(AgentKind.RUMOR, "left", 0.1)]

    result = synthesize(reports, agent_count=3, options=_TWO)

    # 균등 아래로는 내려가지 않는다 — 0.1이 그대로 반영되면 left가 10%가 된다.
    assert result.win_probability == pytest.approx(0.5)


def test_agents_without_opinion_do_not_count_as_disagreement() -> None:
    """루머가 참고할 소식이 없는 것은 반대표가 아니다 — 다만 합의도는 덜 찬다."""
    reports = [
        report(AgentKind.STORYLINE, "left", 0.7),
        report(AgentKind.ODDS, "left", 0.5),
        report(AgentKind.RUMOR, None, 0.0),
    ]

    result = synthesize(reports, agent_count=3, options=_TWO)

    assert result.pick == "left"
    assert result.win_probability == pytest.approx(0.6)
    # 둘 다 같은 쪽이지만 답한 사람이 셋 중 둘이라 확신은 2/3
    assert result.confidence == pytest.approx(2 / 3)


def test_multi_match_picks_index_string_with_highest_share() -> None:
    """다인전의 pick은 인덱스 문자열이다 (`ple_matches.winner_pick`와 같은 형식)."""
    reports = [
        report(AgentKind.STORYLINE, "2", 0.6),
        report(AgentKind.ODDS, "0", 0.3),
        report(AgentKind.RUMOR, "2", 0.1),
    ]

    result = synthesize(reports, agent_count=3, options=_THREE)

    assert result.pick == "2"
    # 오즈·루머는 확신이 균등(1/3) 이하라 아무 쪽도 밀지 못한다.
    assert result.win_probability == pytest.approx(0.4222, abs=1e-4)


def test_pick_outside_options_is_ignored() -> None:
    """카드에 없는 pick은 코디네이터가 걸러 보내지만, 남아도 분포를 흔들지 않는다."""
    reports = [
        report(AgentKind.STORYLINE, "left", 0.8),
        report(AgentKind.RUMOR, "누구세요", 0.9),
    ]

    result = synthesize(reports, agent_count=3, options=_TWO)

    assert result.pick == "left"
    assert result.win_probability == pytest.approx(0.8)


def test_tie_is_broken_deterministically() -> None:
    """같은 입력이면 같은 결과여야 재생성 때 예측이 흔들리지 않는다."""
    reports = [
        report(AgentKind.STORYLINE, "right", 0.5),
        report(AgentKind.ODDS, "left", 0.5),
    ]

    first = synthesize(reports, agent_count=2, options=_TWO)
    second = synthesize(list(reversed(reports)), agent_count=2, options=_TWO)

    assert first.pick == second.pick == "left"
    assert first.win_probability == pytest.approx(0.5)


def test_all_zero_weights_fall_back_to_equal_shares() -> None:
    """의견은 냈지만 확신이 0인 것은 정상 상태다 — 실패로 만들지 않는다."""
    reports = [
        report(AgentKind.STORYLINE, "left", 0.0),
        report(AgentKind.ODDS, "right", 0.0),
    ]

    result = synthesize(reports, agent_count=2, options=_TWO)

    assert result.win_probability == pytest.approx(0.5)
    assert result.confidence == pytest.approx(0.5)


def test_no_opinion_at_all_raises_instead_of_guessing_half() -> None:
    reports = [
        report(AgentKind.STORYLINE, None, 0.0),
        report(AgentKind.ODDS, None, 0.0),
    ]

    with pytest.raises(ReportsUnavailableError):
        synthesize(reports, agent_count=2, options=_TWO)


def test_empty_reports_raise() -> None:
    with pytest.raises(ReportsUnavailableError):
        synthesize([], agent_count=3, options=_TWO)


def test_agent_count_must_be_positive() -> None:
    with pytest.raises(ValueError):
        synthesize([report(AgentKind.ODDS, "left")], agent_count=0, options=_TWO)


def test_options_must_not_be_empty() -> None:
    with pytest.raises(ValueError):
        synthesize([report(AgentKind.ODDS, "left")], agent_count=3, options=())
