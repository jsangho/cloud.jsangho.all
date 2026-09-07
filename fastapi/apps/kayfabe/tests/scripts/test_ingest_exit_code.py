"""적재 스크립트 종료 코드 (Phase 3-13 Stage 1).

**계보 없는 적재를 성공으로 보고하지 않는다.** 예전에는 `collected`만 봐서, 계보
API가 429로 통째로 막혀도 청크는 교체되고 종료 코드는 0이었다. 재수집의 목적이
계보 확보인데 그 실패가 성공처럼 보이면 아무도 다시 돌리지 않는다.

스크립트는 `sys.path`를 직접 만지는 standalone이라 패키지로 import되지 않는다.
그래서 파일 경로로 읽어 온다 — 실제로 실행되는 그 파일을 검사하기 위해서다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/kayfabe/tests/scripts -q
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from kayfabe.app.dtos.knowledge_ingestion_dto import IngestionSummary

_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "ingest_prediction_knowledge.py"
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_ingest_script", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return _load_script()


def _summary(*, collected: int, provenance_unavailable: int = 0) -> IngestionSummary:
    return IngestionSummary(
        requested=1,
        collected=collected,
        chunks=10,
        stored=10,
        duplicates=0,
        failed=0,
        provenance_unavailable=provenance_unavailable,
    )


class TestExitCode:
    def test_clean_run_succeeds(self, script: ModuleType) -> None:
        assert script.exit_code_for(_summary(collected=1)) == 0

    def test_nothing_collected_fails(self, script: ModuleType) -> None:
        assert (
            script.exit_code_for(_summary(collected=0)) == script.EXIT_NOTHING_COLLECTED
        )

    def test_missing_provenance_is_not_success(self, script: ModuleType) -> None:
        """**핵심 회귀.** 예전에는 이 조합이 exit 0이었다."""
        code = script.exit_code_for(_summary(collected=3, provenance_unavailable=1))

        assert code != 0, "계보를 못 얻었는데 성공으로 끝나면 안 된다"
        assert code == script.EXIT_PROVENANCE_UNAVAILABLE

    def test_all_documents_missing_provenance(self, script: ModuleType) -> None:
        """429가 전부 막은 상황 — 실측에서 8번째부터 이렇게 됐다."""
        code = script.exit_code_for(_summary(collected=9, provenance_unavailable=9))

        assert code == script.EXIT_PROVENANCE_UNAVAILABLE

    def test_nothing_collected_takes_precedence(self, script: ModuleType) -> None:
        """아무것도 못 받았으면 계보 이야기를 하기 전에 그것부터 알린다."""
        code = script.exit_code_for(_summary(collected=0, provenance_unavailable=0))

        assert code == script.EXIT_NOTHING_COLLECTED

    def test_exit_codes_are_distinct(self, script: ModuleType) -> None:
        """원인이 다르면 코드도 달라야 손볼 곳을 안다."""
        assert script.EXIT_NOTHING_COLLECTED != script.EXIT_PROVENANCE_UNAVAILABLE
        assert script.EXIT_NOTHING_COLLECTED != 0
        assert script.EXIT_PROVENANCE_UNAVAILABLE != 0
