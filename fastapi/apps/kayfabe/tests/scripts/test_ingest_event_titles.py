"""조립한 이름 확인 관문 (Phase 3-13 Stage 5).

**이 스크립트는 카드의 선수 이름으로 위키 주소를 조립한다 — 그건 추측이다.**
예전에는 빗나간 추측이 404로 걸러진다고 믿었는데 실측이 셋으로 갈렸다:

    Royce Keys → Powerhouse Hobbs   리다이렉트 — 본문은 맞고 주소만 어긋난다
    Penta      → Penta              동음이의 — 200인데 본문이 "may refer to:"다
    WWE Clash… → (없음)              404 (접두사 뺀 `Clash in Italy`는 실재한다)

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
from ontology.app.ports.output.wiki_edition_port import WikiEdition, WikiEditionPort
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


class StubEditions(WikiEditionPort):
    """회차 확인 결과를 지어낸다. `table=None`이면 조회 실패(또는 잘림)다."""

    def __init__(self, table: dict[str, WikiEdition] | None) -> None:
        self._table = table
        self.asked: list[tuple[str, ...]] = []

    async def editions(self, titles: Sequence[str]) -> dict[str, WikiEdition] | None:
        self.asked.append(tuple(titles))
        return self._table


class ForbiddenEditions(WikiEditionPort):
    """물어보면 안 되는 자리에 둔다 — 요청 낭비를 테스트가 붙든다."""

    async def editions(self, titles: Sequence[str]) -> dict[str, WikiEdition] | None:
        raise AssertionError(f"회차를 물을 이유가 없는데 물었다: {titles}")


def _edition(title: str, *years: int) -> WikiEdition:
    return WikiEdition(title=title, years=frozenset(years))


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


class TestEditionGate:
    """**총론이 회차인 척 통과하지 않는다** (Phase 3-13 Stage 7).

    Stage 5의 관문은 실재만 봤다. 총론은 실재하고 200으로 돌아오므로 그대로
    통과했고, 운영 코퍼스에 `Royal Rumble`·`Survivor Series`·`WWE Bad Blood`가
    실제로 그렇게 들어가 있었다. 총론은 **과거 회차의 결과가 적힌 문서**다.
    """

    def test_the_edition_article_of_that_year_is_collected(
        self, script: ModuleType
    ) -> None:
        plan = script.plan_for(
            ["Royal Rumble (2026)"],
            {"Royal Rumble (2026)": _usable("Royal Rumble (2026)")},
            event_title="Royal Rumble (2026)",
            event_year=2026,
            edition=_edition("Royal Rumble (2026)", 2026),
        )

        assert plan.urls == ("https://en.wikipedia.org/wiki/Royal_Rumble_(2026)",)
        assert plan.wrong_edition == ()

    def test_an_overview_article_is_never_requested(self, script: ModuleType) -> None:
        """**이것이 Stage 7이 막는 경로다.** 총론은 연도 카테고리를 갖지 않는다."""
        plan = script.plan_for(
            ["Royal Rumble"],
            {"Royal Rumble": _usable("Royal Rumble")},
            event_title="Royal Rumble",
            event_year=2026,
            edition=_edition("Royal Rumble"),
        )

        assert plan.urls == ()
        assert [w.title for w in plan.wrong_edition] == ["Royal Rumble"]
        assert plan.wrong_edition[0].expected_year == 2026
        assert plan.wrong_edition[0].years == ()

    def test_the_wrong_year_is_never_requested(self, script: ModuleType) -> None:
        """카탈로그가 시즌을 넘겨 낡으면 여기서 소리가 난다."""
        plan = script.plan_for(
            ["Royal Rumble (2025)"],
            {"Royal Rumble (2025)": _usable("Royal Rumble (2025)")},
            event_title="Royal Rumble (2025)",
            event_year=2026,
            edition=_edition("Royal Rumble (2025)", 2025),
        )

        assert plan.urls == ()
        assert plan.wrong_edition[0].years == (2025,)

    def test_an_undated_event_is_held_not_passed(self, script: ModuleType) -> None:
        """**모르는 것을 통과로 읽으면 이 관문이 없던 것이 된다.**

        `PLE_EVENT_SCHEDULE`이 날짜를 비워 두는 대회가 실제로 셋 있고, 그 셋은
        시간 게이트에서도 통과가 아니라 보류다. 같은 읽기를 여기서도 한다.
        """
        plan = script.plan_for(
            ["Survivor Series (2026)"],
            {"Survivor Series (2026)": _usable("Survivor Series (2026)")},
            event_title="Survivor Series (2026)",
            event_year=None,
            edition=_edition("Survivor Series (2026)", 2026),
        )

        assert plan.urls == ()
        assert plan.undated == ("Survivor Series (2026)",)
        assert plan.wrong_edition == ()

    def test_a_redirected_edition_is_collected_at_its_destination(
        self, script: ModuleType
    ) -> None:
        """`Survivor Series (2026)` → `Survivor Series: WarGames (2026)`.

        회차 관문을 통과한 뒤에도 **정규 주소로** 수집해야 한다 — 두 규칙이
        서로를 덮어쓰지 않는지 붙든다.
        """
        plan = script.plan_for(
            ["Survivor Series (2026)"],
            {
                "Survivor Series (2026)": _usable(
                    "Survivor Series (2026)", "Survivor Series: WarGames (2026)"
                )
            },
            event_title="Survivor Series (2026)",
            event_year=2026,
            edition=_edition("Survivor Series (2026)", 2026),
        )

        assert plan.urls == (
            "https://en.wikipedia.org/wiki/Survivor_Series:_WarGames_(2026)",
        )
        assert plan.renamed == (
            ("Survivor Series (2026)", "Survivor Series: WarGames (2026)"),
        )

    def test_the_gate_is_not_applied_to_wrestlers(self, script: ModuleType) -> None:
        """**선수 문서에 걸면 전부 거부된다** — `Rhea Ripley`의 연도는 출생 연도다.

        대회 하나만 거르고 나머지는 그대로 지나가야 한다.
        """
        plan = script.plan_for(
            ["Royal Rumble", "Rhea Ripley", "Cody Rhodes"],
            {
                "Royal Rumble": _usable("Royal Rumble"),
                "Rhea Ripley": _usable("Rhea Ripley"),
                "Cody Rhodes": _usable("Cody Rhodes"),
            },
            event_title="Royal Rumble",
            event_year=2026,
            edition=_edition("Royal Rumble"),
        )

        assert plan.urls == (
            "https://en.wikipedia.org/wiki/Rhea_Ripley",
            "https://en.wikipedia.org/wiki/Cody_Rhodes",
        )

    def test_without_an_event_title_nothing_is_gated(self, script: ModuleType) -> None:
        """대회 문서가 없는 카드(`bad-blood`)는 선수 문서만으로 간다."""
        plan = script.plan_for(
            ["Cody Rhodes"],
            {"Cody Rhodes": _usable("Cody Rhodes")},
            event_title=None,
            event_year=2026,
        )

        assert plan.urls == ("https://en.wikipedia.org/wiki/Cody_Rhodes",)
        assert plan.wrong_edition == ()
        assert plan.undated == ()

    def test_a_missing_edition_entry_is_rejected_not_assumed(
        self, script: ModuleType
    ) -> None:
        """표에 없는 대회 문서를 통과로 읽으면 관문이 조용히 비켜선다."""
        plan = script.plan_for(
            ["Royal Rumble (2026)"],
            {"Royal Rumble (2026)": _usable("Royal Rumble (2026)")},
            event_title="Royal Rumble (2026)",
            event_year=2026,
            edition=None,
        )

        assert plan.urls == ()
        assert [w.title for w in plan.wrong_edition] == ["Royal Rumble (2026)"]


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

    def test_a_colon_is_left_alone(self, script: ModuleType) -> None:
        """`%3A`도 200이지만 **둘이 서로 정규화되지 않는다**(2026-09-22 실측).

        같은 문서가 두 주소로 남으면 나중에 정규 주소로 넣을 때 `content_hash`에
        막혀 저장 0건이 조용히 성공으로 보고된다 — Stage 5가 리다이렉트에서 막은
        그 사고를 인코딩으로 다시 내는 셈이다.
        """
        assert (
            script._wiki_url("Survivor Series: WarGames (2026)")
            == "https://en.wikipedia.org/wiki/Survivor_Series:_WarGames_(2026)"
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

    def test_the_catalog_holds_no_overview_titles(self, script: ModuleType) -> None:
        """2026-09-22에 **총론임이 실측된** 제목들이다 (Phase 3-13 Stage 7).

        되돌아오면 관문이 매번 거부하느라 그 대회는 문서 없이 돌게 된다 —
        고장이 조용하지는 않지만, 고쳐야 할 곳은 관문이 아니라 이 표다.
        """
        overviews = {
            "Royal Rumble",
            "Survivor Series",
            "WWE Backlash",
            "NXT Stand & Deliver",
            "WWE Night of Champions",
            "WWE Bad Blood",
            "WWE King and Queen of the Ring",
        }

        assert overviews.isdisjoint(set(script._EVENT_TITLES.values()))

    def test_events_that_do_not_happen_have_no_document(
        self, script: ModuleType
    ) -> None:
        """**둘은 일부러 비어 있다** (2026-09-22 사용자 확정).

        `bad-blood`는 2026 회차가 없고, `king-queen-of-the-ring`은
        `night-of-champions`에 흡수됐다. 여기에 제목을 채우면 각각 총론이
        들어오거나, 같은 경기가 두 문서로 검색된다.
        """
        assert "bad-blood" not in script._EVENT_TITLES
        assert "king-queen-of-the-ring" not in script._EVENT_TITLES

    def test_the_first_edition_keeps_a_title_without_a_year(
        self, script: ModuleType
    ) -> None:
        """`Clash in Italy`는 첫 회차라 연도 접미사가 없다.

        `WWE Clash in Italy`로 물으면 `missing`이라, 한때 "없는 대회"로 잘못
        빠져 있던 자리다. 회차 관문은 제목이 아니라 선두 연도 카테고리를 보므로
        이 제목도 그대로 통과한다.
        """
        assert script._EVENT_TITLES["clash-in-italy"] == "Clash in Italy"


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


class TestRunAsksAboutTheEventOnly:
    """회차 조회를 **언제 보내고 언제 안 보내는지**를 붙든다.

    이 어댑터는 재시도하지 않는다. 쓸데없는 요청이 늘면 뒤따르는 본문·계보
    요청까지 함께 막히므로, 물을 이유가 없을 때 묻지 않는 것이 설계의 일부다.
    """

    @pytest.mark.asyncio
    async def test_only_the_event_document_is_asked_about(
        self, script: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """선수 34명을 함께 물으면 카테고리 응답이 `cllimit`에 걸려 잘린다."""
        titles = ["SummerSlam (2026)", "Cody Rhodes", "Rhea Ripley"]
        monkeypatch.setattr(script, "_titles_for", _titles_returning(titles))
        monkeypatch.setattr(script, "_event_year", _year_returning(2026))
        ingestion = RecordingIngestion()
        monkeypatch.setattr(
            script, "get_knowledge_ingestion_use_case", _taking(ingestion)
        )
        monkeypatch.setattr(script, "AsyncSessionLocal", FakeSession)
        editions = StubEditions(
            {"SummerSlam (2026)": _edition("SummerSlam (2026)", 2026)}
        )

        code = await script.main(
            "summerslam",
            dry_run=False,
            max_chunks=25,
            titles_port=StubTitles({t: _usable(t) for t in titles}),
            editions_port=editions,
        )

        assert code == 0
        assert editions.asked == [("SummerSlam (2026)",)]
        assert len(ingestion.commands[0].urls) == 3

    @pytest.mark.asyncio
    async def test_an_undated_event_is_never_asked_about(
        self, script: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """날짜를 모르면 비교할 기준이 없다 — 물어도 답을 쓸 데가 없다."""
        monkeypatch.setattr(
            script,
            "_titles_for",
            _titles_returning(["SummerSlam (2026)", "Cody Rhodes"]),
        )
        monkeypatch.setattr(script, "_event_year", _year_returning(None))
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
                    "SummerSlam (2026)": _usable("SummerSlam (2026)"),
                    "Cody Rhodes": _usable("Cody Rhodes"),
                }
            ),
            editions_port=ForbiddenEditions(),
        )

        assert code == 0
        assert [c.urls for c in ingestion.commands] == [
            ("https://en.wikipedia.org/wiki/Cody_Rhodes",)
        ]

    @pytest.mark.asyncio
    async def test_a_card_without_an_event_document_asks_nothing(
        self, script: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`bad-blood`는 2026 회차 문서가 없어 카탈로그에서 빠져 있다."""
        monkeypatch.setattr(script, "_titles_for", _titles_returning(["Cody Rhodes"]))
        ingestion = RecordingIngestion()
        monkeypatch.setattr(
            script, "get_knowledge_ingestion_use_case", _taking(ingestion)
        )
        monkeypatch.setattr(script, "AsyncSessionLocal", FakeSession)

        code = await script.main(
            "bad-blood",
            dry_run=False,
            max_chunks=25,
            titles_port=StubTitles({"Cody Rhodes": _usable("Cody Rhodes")}),
            editions_port=ForbiddenEditions(),
        )

        assert code == 0
        assert "bad-blood" not in script._EVENT_TITLES

    @pytest.mark.asyncio
    async def test_a_failed_edition_lookup_ingests_nothing(
        self, script: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """**잘린 카테고리로 판정하면 회차 문서가 거짓 거부된다.**

        선수 문서만이라도 넣고 가는 쪽이 아니라 멈추는 쪽을 골랐다 — 그 수집은
        대회 문서 없이 코퍼스를 절반만 채워 놓고 성공으로 보고된다.
        """
        monkeypatch.setattr(
            script,
            "_titles_for",
            _titles_returning(["SummerSlam (2026)", "Cody Rhodes"]),
        )
        monkeypatch.setattr(script, "_event_year", _year_returning(2026))
        ingestion = RecordingIngestion()
        monkeypatch.setattr(
            script, "get_knowledge_ingestion_use_case", _never(ingestion)
        )

        code = await script.main(
            "summerslam",
            dry_run=False,
            max_chunks=25,
            titles_port=StubTitles(
                {
                    "SummerSlam (2026)": _usable("SummerSlam (2026)"),
                    "Cody Rhodes": _usable("Cody Rhodes"),
                }
            ),
            editions_port=StubEditions(None),
        )

        assert code == 3
        assert ingestion.commands == []

    @pytest.mark.asyncio
    async def test_an_overview_never_reaches_the_collector(
        self, script: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """관문이 스크립트 끝까지 이어져 있는지 — 순수 함수 밖에서 확인한다."""
        monkeypatch.setattr(
            script,
            "_titles_for",
            _titles_returning(["SummerSlam (2026)", "Cody Rhodes"]),
        )
        monkeypatch.setattr(script, "_event_year", _year_returning(2026))
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
                    "SummerSlam (2026)": _usable("SummerSlam (2026)"),
                    "Cody Rhodes": _usable("Cody Rhodes"),
                }
            ),
            # 총론처럼 연도를 갖지 않는 응답.
            editions_port=StubEditions(
                {"SummerSlam (2026)": _edition("SummerSlam (2026)")}
            ),
        )

        assert code == 0
        assert [c.urls for c in ingestion.commands] == [
            ("https://en.wikipedia.org/wiki/Cody_Rhodes",)
        ]


def _titles_returning(titles: list[str]):
    async def _stub(slug: str) -> list[str]:
        return titles

    return _stub


def _year_returning(year: int | None):
    async def _stub(slug: str) -> int | None:
        return year

    return _stub


def _taking(ingestion: RecordingIngestion):
    def _factory(db: object, *, max_chunks: int | None = None) -> RecordingIngestion:
        return ingestion

    return _factory


def _never(ingestion: RecordingIngestion):
    def _factory(db: object, *, max_chunks: int | None = None) -> RecordingIngestion:
        raise AssertionError("확인되지 않은 목록으로 수집에 들어갔다")

    return _factory
