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


class TestMaxChunks:
    """**핵심 회귀.** 상한 없이 돌면 재수집이 코퍼스를 몇 배로 불린다.

    2026-09-21에 실제로 그렇게 돌렸다 — 6문서에 30분이 걸렸고, 31문서면 몇 시간짜리가
    된다. 분량이 바뀌면 `top_k=5` 검색이 뽑는 것도 달라지므로, 계보를 얻으려던 작업이
    검색 거동까지 바꾼다.
    """

    def test_default_matches_the_corpus_that_exists(self, script: ModuleType) -> None:
        """현재 코퍼스가 25로 쌓였다 — 기본값이 그것과 달라지면 안 된다."""
        assert script.max_chunks_from_argv([]) == 25
        assert script.DEFAULT_MAX_CHUNKS == 25

    def test_urls_alone_do_not_change_the_cap(self, script: ModuleType) -> None:
        assert script.max_chunks_from_argv(["https://en.wikipedia.org/wiki/X"]) == 25

    def test_explicit_value_wins(self, script: ModuleType) -> None:
        argv = ["https://en.wikipedia.org/wiki/X", "--max-chunks=50"]

        assert script.max_chunks_from_argv(argv) == 50

    def test_zero_means_unlimited(self, script: ModuleType) -> None:
        """무제한은 적을 자리가 필요하지만, 숫자를 직접 적어야만 닿는다."""
        assert script.max_chunks_from_argv(["--max-chunks=0"]) is None

    def test_negative_is_rejected(self, script: ModuleType) -> None:
        with pytest.raises(ValueError):
            script.max_chunks_from_argv(["--max-chunks=-1"])

    def test_flags_are_not_urls(self, script: ModuleType) -> None:
        """`--max-chunks=25`가 URL 목록에 섞여 들어가면 허용 도메인 경고만 남는다."""
        argv = [
            "https://en.wikipedia.org/wiki/X",
            "--max-chunks=25",
            "https://en.wikipedia.org/wiki/Y",
        ]

        assert script.urls_from_argv(argv) == [
            "https://en.wikipedia.org/wiki/X",
            "https://en.wikipedia.org/wiki/Y",
        ]
