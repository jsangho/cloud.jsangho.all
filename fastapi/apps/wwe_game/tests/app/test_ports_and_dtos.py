"""T7 포트·DTO — **구현체 0개 상태에서의 추상성 검증** (하네스 §10-T7).

이 단위의 완료 판정이 특이한 이유: 산출물이 전부 인터페이스라 "돌려 보는" 것으로는
아무것도 확인되지 않는다. 대신 **경계가 실제로 경계인지**를 본다.

1. 추상 메서드를 하나라도 빼면 인스턴스가 안 만들어진다
2. app 레이어가 프레임워크·어댑터를 import하지 않는다
3. 응답 자료형에 내부 수치가 새지 않는다 (§11-14)
"""

from __future__ import annotations

import ast
import inspect
from abc import ABC
from pathlib import Path

import pytest
from _helpers import make_run  # noqa: I001  (tests 트리에 __init__.py가 없다)
from wwe_game.app.dtos import career_dto
from wwe_game.app.dtos.career_dto import (
    AdvanceResult,
    CareerLogPage,
    ChoiceView,
    StepMode,
    StopReason,
    WeekReportView,
)
from wwe_game.app.ports.input.career_use_case import CareerUseCase
from wwe_game.app.ports.output.career_repository import CareerRepository
from wwe_game.app.ports.output.narration_port import NarrationPort
from wwe_game.domain.value_objects.week_report import WeekKind, WeekReport

PORTS = (CareerUseCase, CareerRepository, NarrationPort)
APP_DIR = Path(career_dto.__file__).parents[1]

FORBIDDEN_IMPORTS = ("fastapi", "sqlalchemy", "sqlmodel", "pydantic", "httpx")
"""app 레이어가 알면 안 되는 것들. `adapter`는 아래에서 따로 본다."""


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
            if node.module.startswith("wwe_game."):
                roots.add(".".join(node.module.split(".")[:2]))
    return roots


class TestPortsAreAbstract:
    @pytest.mark.parametrize("port", PORTS)
    def test_a_port_cannot_be_instantiated(self, port: type[ABC]) -> None:
        with pytest.raises(TypeError):
            port()  # type: ignore[abstract]

    @pytest.mark.parametrize("port", PORTS)
    def test_every_method_is_abstract(self, port: type[ABC]) -> None:
        # 하나라도 구현이 섞여 있으면 그 규칙이 포트에 눌러앉는다 — 포트는 계약만 든다.
        declared = {
            name
            for name, value in vars(port).items()
            if not name.startswith("_") and callable(value)
        }
        assert declared == port.__abstractmethods__

    def test_a_partial_implementation_still_fails(self) -> None:
        class HalfNarrator(NarrationPort):
            pass

        with pytest.raises(TypeError):
            HalfNarrator()  # type: ignore[abstract]

    def test_the_rule_narrator_satisfies_the_port(self) -> None:
        from wwe_game.adapter.outbound.narration.rule_narrator import RuleNarrator

        assert issubclass(RuleNarrator, NarrationPort)
        assert RuleNarrator()  # 추상 메서드가 다 채워졌으면 만들어진다

    @pytest.mark.parametrize("port", PORTS)
    def test_every_abstract_method_is_documented(self, port: type[ABC]) -> None:
        # 구현이 없는 계약이라, 문서가 없으면 무엇을 지켜야 하는지 알 길이 없다.
        for name in port.__abstractmethods__:
            assert inspect.getdoc(getattr(port, name)), f"{port.__name__}.{name}"


class TestAppLayerKnowsNothingOutward:
    def test_no_framework_reaches_the_app_layer(self) -> None:
        for path in sorted(APP_DIR.rglob("*.py")):
            roots = _imported_roots(path)
            leaked = roots & set(FORBIDDEN_IMPORTS)
            assert not leaked, f"{path.name}: {sorted(leaked)}"

    def test_the_app_layer_never_imports_an_adapter(self) -> None:
        # 의존성은 안쪽을 향한다. `lint-imports`도 같은 것을 보지만, 그쪽은 앱 전체
        # 계약이라 위반 지점이 어느 파일인지 알려주지 않는다.
        for path in sorted(APP_DIR.rglob("*.py")):
            assert "wwe_game.adapter" not in _imported_roots(path), path.name

    def test_ports_import_only_dtos_and_domain(self) -> None:
        for port_module in ("career_use_case", "career_repository", "narration_port"):
            path = next(APP_DIR.rglob(f"{port_module}.py"))
            wwe_roots = {r for r in _imported_roots(path) if r.startswith("wwe_game.")}
            assert wwe_roots <= {"wwe_game.app", "wwe_game.domain"}, path.name


class TestDtosCarryNoInternals:
    def test_a_choice_shows_only_its_label(self) -> None:
        # 카드의 risk·injury_risk는 판정 수치다. 내보내면 최적해가 드러난다 (§11-14).
        fields = set(ChoiceView.__dataclass_fields__)
        assert fields == {"code", "label"}

    def test_the_advance_result_defaults_to_an_empty_week_list(self) -> None:
        result = AdvanceResult(run=make_run())
        assert result.weeks == ()
        assert result.pending_event is None
        assert not result.ended

    def test_the_end_reason_comes_from_the_run(self) -> None:
        from wwe_game.domain.entities.career_run import EndReason

        closed = make_run().ended(EndReason.AGE_50)
        result = AdvanceResult(run=closed, stop_reason=StopReason.ENDED)
        assert result.ended
        assert result.end_reason is EndReason.AGE_50

    def test_a_week_view_borrows_the_domain_report(self) -> None:
        # DTO가 리포트를 베끼지 않는다 — 필드가 늘 때 두 곳을 고치게 되기 때문이다.
        report = WeekReport(week=7, kind=WeekKind.PROMO)
        view = WeekReportView(report=report, narration="한 줄")
        assert view.week == 7
        assert view.report is report

    def test_a_log_page_knows_when_more_remains(self) -> None:
        report = WeekReport(week=1, kind=WeekKind.PROMO)
        entries = (WeekReportView(report=report, narration="한 줄"),)
        assert CareerLogPage(entries=entries, total=10, offset=0).has_more
        assert not CareerLogPage(entries=entries, total=1, offset=0).has_more

    def test_step_and_stop_are_closed_sets(self) -> None:
        assert {m.value for m in StepMode} == {"auto", "tick"}
        assert {r.value for r in StopReason} == {
            "event",
            "ple",
            "ended",
            "tick",
            "max_weeks",
            "ready",
        }

    def test_the_dto_reuses_the_domain_enums(self) -> None:
        # 같은 이름의 열거형을 두 레이어에 두면 값이 갈릴 때 어느 쪽이 맞는지 알 수 없다.
        from wwe_game.domain.value_objects import advance_outcome

        assert StepMode is advance_outcome.StepMode
        assert StopReason is advance_outcome.StopReason
