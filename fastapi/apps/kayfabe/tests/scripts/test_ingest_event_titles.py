"""조립한 이름 확인 관문 (Phase 3-13 Stage 5).

**이 스크립트는 카드의 선수 이름으로 위키 주소를 조립한다 — 그건 추측이다.**
예전에는 빗나간 추측이 404로 걸러진다고 믿었는데 실측이 셋으로 갈렸다:

    Royce Keys → Powerhouse Hobbs   리다이렉트 — 본문은 맞고 주소만 어긋난다
    Penta      → Penta              동음이의 — 200인데 본문이 "may refer to:"다
    Clash…     → (없음)              404

여기서 붙드는 것은 넷이다.

1. 동음이의·없는 문서는 **요청조차 나가지 않는다.**
2. 리다이렉트는 **정규 제목으로** 수집한다.
3. 정규 제목이 겹치면 한 번만 — 두 번 보내면 `content_hash`에 막혀 저장 0건이
   조용히 성공으로 보고된다.
4. **확인이 실패하면 추측으로 이어가지 않고 멈춘다** (종료 코드 3).

스크립트는 `sys.path`를 직접 만지는 standalone이라 패키지로 import되지 않는다.
파일 경로로 읽어 온다 — 실제로 실행되는 그 파일을 검사하기 위해서다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/kayfabe/tests/scripts/test_ingest_event_titles.py -q
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

import pytest

from kayfabe.app.dtos.knowledge_ingestion_dto import (
    IngestionSummary,
    IngestKnowledgeCommand,
)
from ontology.app.ports.output.wiki_title_port import WikiTitle, WikiTitlePort

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ingest_event_knowledge.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_ingest_event_script", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # `@dataclass`가 어노테이션을 풀 때 `sys.modules[cls.__module__]`를 본다.
    # 등록하지 않고 exec하면 `IngestionPlan` 정의에서 깨진다.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return _load_script()


def _usable(name: str, canonical: str | None = None) -> WikiTitle:
    return WikiTitle(requested=name, canonical=canonical or name)


def _disambiguation(name: str) -> WikiTitle:
    return WikiTitle(requested=name, canonical=name, is_disambiguation=True)


def _missing(name: str) -> WikiTitle:
    return WikiTitle(requested=name, canonical=None)


class StubTitles(WikiTitlePort):
    """확인 결과를 지어낸다. `table=None`이면 조회 실패다."""

    def __init__(self, table: dict[str, WikiTitle] | None) -> None:
        self._table = table
        self.asked: list[tuple[str, ...]] = []

    async def resolve(self, titles: Sequence[str]) -> dict[str, WikiTitle] | None:
        self.asked.append(tuple(titles))
        return self._table


class RecordingIngestion:
    """받은 주소만 기록한다 — 네트워크도 DB도 타지 않는다."""

    def __init__(self) -> None:
        self.commands: list[IngestKnowledgeCommand] = []

    async def ingest(self, command: IngestKnowledgeCommand) -> IngestionSummary:
        self.commands.append(command)
        return IngestionSummary(
            requested=len(command.urls),
            collected=len(command.urls),
            chunks=10,
            stored=10,
            duplicates=0,
            failed=0,
            provenance_unavailable=0,
        )


class FakeSession:
    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def commit(self) -> None:
        return None


class TestPlan:
    def test_a_plain_name_is_collected_as_is(self, script: ModuleType) -> None:
        plan = script.plan_for(["Rhea Ripley"], {"Rhea Ripley": _usable("Rhea Ripley")})

        assert plan.urls == ("https://en.wikipedia.org/wiki/Rhea_Ripley",)
        assert plan.renamed == ()

    def test_a_redirect_is_collected_at_its_canonical_address(
        self, script: ModuleType
    ) -> None:
        """**본문은 원래 맞았다.** 고쳐야 하는 것은 그 본문을 쌓는 자리다."""
        plan = script.plan_for(
            ["Royce Keys"],
            {"Royce Keys": _usable("Royce Keys", "Powerhouse Hobbs")},
        )

        assert plan.urls == ("https://en.wikipedia.org/wiki/Powerhouse_Hobbs",)
        assert plan.renamed == (("Royce Keys", "Powerhouse Hobbs"),)

    def test_a_disambiguation_page_is_never_requested(self, script: ModuleType) -> None:
        """**이것이 코퍼스를 오염시킨 경로다** — 운영에 `Paige`·`Penta` 4청크."""
        plan = script.plan_for(["Penta"], {"Penta": _disambiguation("Penta")})

        assert plan.urls == ()
        assert plan.disambiguation == ("Penta",)

    def test_a_missing_page_is_never_requested(self, script: ModuleType) -> None:
        plan = script.plan_for(
            ["WWE Clash in Italy"],
            {"WWE Clash in Italy": _missing("WWE Clash in Italy")},
        )

        assert plan.urls == ()
        assert plan.missing == ("WWE Clash in Italy",)

    def test_an_unconfirmed_name_counts_as_missing(self, script: ModuleType) -> None:
        """표에 없는 이름을 수집으로 넘기면 이 관문이 하는 일이 없어진다."""
        plan = script.plan_for(["Nobody"], {})

        assert plan.urls == ()
        assert plan.missing == ("Nobody",)

    def test_two_names_for_one_document_are_collected_once(
        self, script: ModuleType
    ) -> None:
        """둘 다 보내면 두 번째는 `content_hash`에 막혀 저장 0건으로 돌아온다."""
        plan = script.plan_for(
            ["IYO SKY", "Iyo Sky"],
            {
                "IYO SKY": _usable("IYO SKY", "Iyo Sky"),
                "Iyo Sky": _usable("Iyo Sky"),
            },
        )

        assert plan.urls == ("https://en.wikipedia.org/wiki/Iyo_Sky",)
        assert plan.renamed == (("IYO SKY", "Iyo Sky"),)

    def test_the_order_of_the_card_is_kept(self, script: ModuleType) -> None:
        """대회 문서가 맨 앞이다 — 보고를 읽는 사람이 그 순서를 기대한다."""
        names = ["SummerSlam (2026)", "Cody Rhodes", "Penta", "Roman Reigns"]
        plan = script.plan_for(
            names,
            {
                "SummerSlam (2026)": _usable("SummerSlam (2026)"),
                "Cody Rhodes": _usable("Cody Rhodes"),
                "Penta": _disambiguation("Penta"),
                "Roman Reigns": _usable("Roman Reigns"),
            },
        )

        assert plan.urls == (
            "https://en.wikipedia.org/wiki/SummerSlam_(2026)",
            "https://en.wikipedia.org/wiki/Cody_Rhodes",
            "https://en.wikipedia.org/wiki/Roman_Reigns",
        )


class TestUrlEncoding:
    def test_an_ampersand_is_percent_encoded(self, script: ModuleType) -> None:
        """`NXT Stand & Deliver`의 실제 주소는 `NXT_Stand_%26_Deliver`다."""
        assert (
            script._wiki_url("NXT Stand & Deliver")
            == "https://en.wikipedia.org/wiki/NXT_Stand_%26_Deliver"
        )

    def test_parentheses_are_left_alone(self, script: ModuleType) -> None:
        """위키가 쓰는 모양이 그렇다 — 인코딩하면 코퍼스의 옛 주소와 어긋난다."""
        assert (
            script._wiki_url("Money in the Bank (2026)")
            == "https://en.wikipedia.org/wiki/Money_in_the_Bank_(2026)"
        )

    def test_non_ascii_keeps_the_corpus_address(self, script: ModuleType) -> None:
        assert (
            script._wiki_url("Finn Bálor")
            == "https://en.wikipedia.org/wiki/Finn_B%C3%A1lor"
        )

    def test_the_event_catalog_holds_titles_not_encoded_addresses(
        self, script: ModuleType
    ) -> None:
        """**카탈로그 값은 이제 API에 그대로 물어보는 제목이다.**

        `%26` 같은 인코딩을 도로 넣으면 위키가 그 리터럴을 찾아 `missing`을 내고,
        그 대회 문서가 조용히 빠진다.
        """
        for slug, title in script._EVENT_TITLES.items():
            assert "%" not in title, slug
            assert "_" not in title, slug


class TestRunStopsWhenUnsure:
    @pytest.mark.asyncio
    async def test_a_failed_lookup_ingests_nothing(
        self, script: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """**추측으로 이어가지 않는다.** 확인이 막혔다면 본문 요청은 더 막힌다."""
        monkeypatch.setattr(script, "_titles_for", _titles_returning(["Penta"]))
        ingestion = RecordingIngestion()
        monkeypatch.setattr(
            script, "get_knowledge_ingestion_use_case", _never(ingestion)
        )

        code = await script.main(
            "summerslam",
            dry_run=False,
            max_chunks=25,
            titles_port=StubTitles(None),
        )

        assert code == 3
        assert ingestion.commands == []

    @pytest.mark.asyncio
    async def test_a_card_of_only_bad_names_ingests_nothing(
        self, script: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            script, "_titles_for", _titles_returning(["Penta", "Nobody"])
        )
        ingestion = RecordingIngestion()
        monkeypatch.setattr(
            script, "get_knowledge_ingestion_use_case", _never(ingestion)
        )

        code = await script.main(
            "summerslam",
            dry_run=False,
            max_chunks=25,
            titles_port=StubTitles(
                {"Penta": _disambiguation("Penta"), "Nobody": _missing("Nobody")}
            ),
        )

        assert code == 1
        assert ingestion.commands == []

    @pytest.mark.asyncio
    async def test_a_dry_run_confirms_but_does_not_collect(
        self, script: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(script, "_titles_for", _titles_returning(["Cody Rhodes"]))
        ingestion = RecordingIngestion()
        monkeypatch.setattr(
            script, "get_knowledge_ingestion_use_case", _never(ingestion)
        )
        port = StubTitles({"Cody Rhodes": _usable("Cody Rhodes")})

        code = await script.main(
            "summerslam", dry_run=True, max_chunks=25, titles_port=port
        )

        assert code == 0
        assert port.asked == [("Cody Rhodes",)]
        assert ingestion.commands == []

    @pytest.mark.asyncio
    async def test_only_confirmed_addresses_reach_the_collector(
        self, script: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            script,
            "_titles_for",
            _titles_returning(["Royce Keys", "Penta", "Cody Rhodes"]),
        )
        ingestion = RecordingIngestion()
        monkeypatch.setattr(
            script, "get_knowledge_ingestion_use_case", _taking(ingestion)
        )
        monkeypatch.setattr(script, "AsyncSessionLocal", FakeSession)

        code = await script.main(
            "summerslam",
            dry_run=False,
            max_chunks=25,
            titles_port=StubTitles(
                {
                    "Royce Keys": _usable("Royce Keys", "Powerhouse Hobbs"),
                    "Penta": _disambiguation("Penta"),
                    "Cody Rhodes": _usable("Cody Rhodes"),
                }
            ),
        )

        assert code == 0
        assert [c.urls for c in ingestion.commands] == [
            (
                "https://en.wikipedia.org/wiki/Powerhouse_Hobbs",
                "https://en.wikipedia.org/wiki/Cody_Rhodes",
            )
        ]


def _titles_returning(titles: list[str]):
    async def _stub(slug: str) -> list[str]:
        return titles

    return _stub


def _taking(ingestion: RecordingIngestion):
    def _factory(db: object, *, max_chunks: int | None = None) -> RecordingIngestion:
        return ingestion

    return _factory


def _never(ingestion: RecordingIngestion):
    def _factory(db: object, *, max_chunks: int | None = None) -> RecordingIngestion:
        raise AssertionError("확인되지 않은 목록으로 수집에 들어갔다")

    return _factory
