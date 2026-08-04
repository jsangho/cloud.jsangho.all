"""포트 계약 테스트 — 하네스 §10-T2의 완료 판정.

"전부 ABC이고 구현체 없이도 import 된다"를 기계적으로 확인한다. 구현이 하나도
없는 시점에 이 테스트가 도는 것 자체가 의존성 방향(adapter → app → domain)이
지켜졌다는 증거다.
"""

from __future__ import annotations

import inspect
from abc import ABC

import pytest

from kayfabe.app.ports.input.ai_prediction_use_case import AiPredictionUseCase
from kayfabe.app.ports.output.agent_errors import AgentUnavailableError
from kayfabe.app.ports.output.agent_prediction_repository import (
    AgentPredictionRepository,
    MatchNotFoundError,
)
from kayfabe.app.ports.output.odds_scout_port import OddsScoutPort
from kayfabe.app.ports.output.prediction_knowledge_port import (
    KnowledgeSourceUnavailableError,
    PredictionKnowledgePort,
)
from kayfabe.app.ports.output.rumor_scout_port import RumorScoutPort
from kayfabe.app.ports.output.storyline_analyst_port import StorylineAnalystPort

_PORTS = [
    AiPredictionUseCase,
    StorylineAnalystPort,
    OddsScoutPort,
    RumorScoutPort,
    PredictionKnowledgePort,
    AgentPredictionRepository,
]


@pytest.mark.parametrize("port", _PORTS, ids=lambda p: p.__name__)
def test_port_is_an_abc(port: type) -> None:
    """`Protocol`이 아니라 `ABC`다 — 가장 가까운 참조 구현을 따른다(하네스 §2-D8)."""
    assert issubclass(port, ABC)
    assert port.__abstractmethods__


@pytest.mark.parametrize("port", _PORTS, ids=lambda p: p.__name__)
def test_port_cannot_be_instantiated(port: type) -> None:
    with pytest.raises(TypeError):
        port()  # type: ignore[call-arg]


@pytest.mark.parametrize("port", _PORTS, ids=lambda p: p.__name__)
def test_port_methods_are_async(port: type) -> None:
    """전부 I/O 바운드다 — `await`할 대상이 있으므로 async다(fastapi/CLAUDE.md §9)."""
    for name in port.__abstractmethods__:
        assert inspect.iscoroutinefunction(getattr(port, name)), name


def test_use_case_separates_read_from_generation() -> None:
    """조회와 생성이 한 메서드로 합쳐지면 페이지 진입마다 LLM이 돈다(§2-D7)."""
    assert AiPredictionUseCase.__abstractmethods__ == frozenset(
        {"list_predictions", "generate"}
    )


@pytest.mark.parametrize(
    "error",
    [AgentUnavailableError, MatchNotFoundError, KnowledgeSourceUnavailableError],
    ids=lambda e: e.__name__,
)
def test_errors_are_plain_exceptions(error: type[Exception]) -> None:
    """전용 AppError 계층을 만들지 않는다. HTTP 변환은 라우터만 한다(§2-D8)."""
    assert issubclass(error, Exception)
    assert error.__mro__[1] is Exception


def test_ports_do_not_import_frameworks() -> None:
    """포트가 프레임워크를 끌어오면 의존성 방향이 뒤집힌다."""
    import kayfabe.app.ports.output.agent_prediction_repository as repo_module
    import kayfabe.app.ports.output.storyline_analyst_port as storyline_module

    for module in (repo_module, storyline_module):
        source = inspect.getsource(module)
        for forbidden in ("import sqlalchemy", "from fastapi", "google.genai"):
            assert forbidden not in source, f"{module.__name__}: {forbidden}"
