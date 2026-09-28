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
    SYNTHESIS_V1,
    SYNTHESIS_V2,
    SYNTHESIS_VERSION,
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


def test_v1_lone_opinion_does_not_claim_full_confidence() -> None:
    """셋 중 하나만 답했는데 확신 100%가 되면 화면이 사용자를 오도한다.

    **`v1`을 못 박는 테스트다.** 저장된 옛 예측의 승률이 이 산식에서 나왔으므로,
    이 값이 바뀌면 재현이 근거 없이 `diverged`를 말하게 된다.
    """
    reports = [report(AgentKind.STORYLINE, "left", 0.9)]

    result = synthesize(reports, agent_count=3, options=_TWO, version=SYNTHESIS_V1)

    # v1에서는 한 명뿐이면 그 사람의 분포가 그대로 결과가 된다.
    assert result.win_probability == pytest.approx(0.9)
    assert result.confidence == pytest.approx(1 / 3)


def test_v1_odds_probability_survives_when_it_is_the_only_voice() -> None:
    """오즈가 배당에서 계산한 내재 확률이 정규화에 먹히지 않는다 (`v1`)."""
    reports = [report(AgentKind.ODDS, "left", 0.62)]

    result = synthesize(reports, agent_count=3, options=_TWO, version=SYNTHESIS_V1)

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

    result = synthesize(reports, agent_count=3, options=_TWO, version=SYNTHESIS_V1)

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

    result = synthesize(reports, agent_count=3, options=_TWO, version=SYNTHESIS_V1)

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


# --- `v2` — 기권을 균등분포로 세는 산식 (2026-09-28) -------------------------


def test_v2_is_the_current_version() -> None:
    """새 예측이 어느 산식으로 기록되는지 못 박는다.

    이 값이 조용히 바뀌면 재현이 옛 예측에 새 산식을 들이대기 시작한다.
    """
    assert SYNTHESIS_VERSION == SYNTHESIS_V2


def test_v2_lone_opinion_cannot_reach_full_probability_in_a_ladder() -> None:
    """**6인 경기에 100%는 어느 각도에서도 방어가 안 된다.**

    셋 중 하나가 확신 1.0으로 답한 실제 사례(`mitb26-women`)의 수치다.
    """
    reports = [report(AgentKind.RUMOR, "1", 1.0)]
    options = tuple(str(i) for i in range(6))

    result = synthesize(reports, agent_count=3, options=options, version=SYNTHESIS_V2)

    assert result.pick == "1"
    # (1.0 + 1/6 + 1/6) / 3 — 답하지 않은 둘이 균등분포로 들어온다.
    assert result.win_probability == pytest.approx(4 / 9)
    # 확신은 v1과 같다. 그쪽은 이미 기권을 세고 있었다.
    assert result.confidence == pytest.approx(1 / 3)


def test_v2_matches_v1_when_every_agent_answers() -> None:
    """전원이 답하면 두 산식이 같은 값을 낸다 — 바뀐 것은 기권의 처리뿐이다."""
    reports = [
        report(AgentKind.STORYLINE, "left", 0.7),
        report(AgentKind.ODDS, "left", 0.6),
        report(AgentKind.RUMOR, "right", 0.8),
    ]

    v1 = synthesize(reports, agent_count=3, options=_TWO, version=SYNTHESIS_V1)
    v2 = synthesize(reports, agent_count=3, options=_TWO, version=SYNTHESIS_V2)

    assert v1.pick == v2.pick
    assert v1.win_probability == pytest.approx(v2.win_probability)
    assert v1.confidence == pytest.approx(v2.confidence)


def test_v2_abstention_pulls_toward_even_not_toward_the_other_side() -> None:
    """기권은 '모르겠다'다 — 반대편에 표를 주는 것이 아니다."""
    reports = [
        report(AgentKind.STORYLINE, "left", 0.9),
        report(AgentKind.RUMOR, None, 0.0),
        report(AgentKind.ODDS, None, 0.0),
    ]

    result = synthesize(reports, agent_count=3, options=_TWO, version=SYNTHESIS_V2)

    assert result.pick == "left"
    # (0.9 + 0.5 + 0.5) / 3 — 0.5 아래로는 내려가지 않는다.
    assert result.win_probability == pytest.approx(0.9 / 3 + 1 / 3)
    assert result.win_probability > 0.5


def test_v2_probabilities_still_sum_to_one() -> None:
    """기권을 더해도 분포는 분포다."""
    reports = [report(AgentKind.STORYLINE, "0", 0.8)]

    result = synthesize(reports, agent_count=3, options=_THREE, version=SYNTHESIS_V2)

    assert sum(result.probabilities.values()) == pytest.approx(1.0)


def test_v2_treats_a_pick_outside_the_card_as_an_abstention() -> None:
    """카드 밖 pick은 분포에 기여할 수 없으니 답하지 않은 것과 같은 자리다.

    분모에서만 빼면 존재하지 않는 선택지가 남은 표의 무게를 키운다.
    """
    reports = [
        report(AgentKind.STORYLINE, "left", 0.8),
        report(AgentKind.RUMOR, "누구세요", 0.9),
    ]

    result = synthesize(reports, agent_count=3, options=_TWO, version=SYNTHESIS_V2)

    assert result.pick == "left"
    # counted=1, 기권 2 → (0.8 + 0.5 + 0.5) / 3
    assert result.win_probability == pytest.approx(0.6)


def test_unknown_version_raises_instead_of_guessing_a_formula() -> None:
    """모르는 판본을 아무 산식으로 처리하면 재현이 거짓말을 한다."""
    reports = [report(AgentKind.STORYLINE, "left", 0.7)]

    with pytest.raises(ValueError, match="합성 판본"):
        synthesize(reports, agent_count=3, options=_TWO, version="99")
