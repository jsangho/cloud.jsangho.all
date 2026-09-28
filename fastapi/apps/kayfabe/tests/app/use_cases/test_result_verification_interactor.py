"""결과 확정 에이전트 루프 테스트.

**모델도 위키도 DB도 부르지 않는다.** 페이크 도구 유스케이스가 정해진 걸음을 순서대로
내놓는다.

여기서 고정하는 계약 일곱:

1. 모델에게 **쓰기 도구가 없다** — 도구 목록에 읽기 둘뿐이다
2. 드라이런은 쓰지 않는다 (pick이 있어도)
3. 걸음·도구 호출 상한을 넘기면 보류로 끝난다 (루프가 비용으로 가지 않는다)
4. 없는 도구를 불러도 그 경기가 끝나지 않는다 — 실패를 적어 돌려주고 모델이 회복한다
5. 증거는 **자른 뒤의 문자열**이다 — 보여 주지 않은 구절을 인용하면 떨어진다
6. 호출 사이 간격을 벌린다 (무료 등급 한도)
7. 대상이 없으면 모델을 부르지 않는다 (비용)

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/kayfabe/tests -q
"""

from __future__ import annotations

import json

import pytest

from kayfabe.app.dtos.result_verification_dto import VerifyResultsCommand
from kayfabe.app.ports.output.match_result_writer import MatchResultWriter
from kayfabe.app.ports.output.pending_result_repository import PendingResultRepository
from kayfabe.app.use_cases.result_verification_interactor import (
    _TOOLS,
    MAX_SECTION_CHARS,
    MAX_STEPS_PER_MATCH,
    MAX_TOOL_CALLS_PER_MATCH,
    MIN_CALL_INTERVAL_SECONDS,
    ResultVerificationInteractor,
)
from kayfabe.domain.entities.result_verification import (
    HoldReason,
    MatchUnderReview,
    ReviewOption,
)
from ontology.app.dtos.gemini_tool_dto import (
    ToolCall,
    ToolStep,
    ToolStepCommand,
)
from ontology.app.ports.input.gemini_tool_use_case import GeminiToolUseCase
from ontology.app.ports.output.gemini_tool_errors import ToolCallUnavailableError
from ontology.app.ports.output.wiki_article_port import (
    WikiArticlePort,
    WikiSection,
    WikiSectionText,
)
from ontology.app.ports.output.wiki_title_port import WikiTitle, WikiTitlePort

_MATCH = MatchUnderReview(
    event_slug="summerslam",
    event_label="SummerSlam 2026",
    match_key="ss26-whc",
    title="World Heavyweight Championship",
    options=(
        ReviewOption(pick="left", name="Roman Reigns"),
        ReviewOption(pick="right", name="Cody Rhodes"),
    ),
)

_ARTICLE = "SummerSlam (2026)"
_SECTION_TEXT = "Reigns defeated Rhodes by pinfall after a spear."


class FakePending(PendingResultRepository):
    def __init__(self, matches: tuple[MatchUnderReview, ...]) -> None:
        self._matches = matches

    async def list_pending(self, *, event_slug=None, limit=None):
        found = [m for m in self._matches if event_slug in (None, m.event_slug)]
        return tuple(found[:limit] if limit is not None else found)


class FakeWriter(MatchResultWriter):
    def __init__(self, *, ok: bool = True) -> None:
        self.calls: list[dict] = []
        self._ok = ok

    async def record_winner(self, *, event_slug, match_key, pick, winner_name):
        self.calls.append(
            {
                "event_slug": event_slug,
                "match_key": match_key,
                "pick": pick,
                "winner_name": winner_name,
            }
        )
        return self._ok


class FakeTools(GeminiToolUseCase):
    """정해진 걸음을 순서대로 낸다. 다 쓰면 `repeat`을 계속 낸다."""

    def __init__(
        self, steps: list[ToolStep], *, repeat: ToolStep | None = None
    ) -> None:
        self._steps = list(steps)
        self._repeat = repeat
        self.commands: list[ToolStepCommand] = []

    async def next_step(self, command: ToolStepCommand) -> ToolStep:
        self.commands.append(command)
        if self._steps:
            return self._steps.pop(0)
        if self._repeat is not None:
            return self._repeat
        return ToolStep(text="{}")


class FakeTitles(WikiTitlePort):
    def __init__(self, table: dict[str, WikiTitle] | None = None) -> None:
        self._table = table

    async def resolve(self, titles):
        if self._table is None:
            return None
        return {
            name: self._table.get(name, WikiTitle(requested=name, canonical=None))
            for name in titles
        }


class FakeArticles(WikiArticlePort):
    def __init__(self, *, text: str = _SECTION_TEXT) -> None:
        self._text = text
        self.reads: list[tuple[str, str]] = []

    async def sections(self, title):
        if title != _ARTICLE:
            return None
        return (
            WikiSection(index="1", line="Background", level=2),
            WikiSection(index="3", line="Results", level=2),
        )

    async def read_section(self, title, index):
        self.reads.append((title, index))
        if title != _ARTICLE or index != "3":
            return None
        return WikiSectionText(
            title=_ARTICLE,
            index=index,
            line="Results",
            text=self._text,
            revision_id="777",
        )


def _interactor(
    tools: FakeTools,
    *,
    writer: FakeWriter | None = None,
    matches: tuple[MatchUnderReview, ...] = (_MATCH,),
    articles: FakeArticles | None = None,
    sleeps: list[float] | None = None,
) -> ResultVerificationInteractor:
    return ResultVerificationInteractor(
        pending=FakePending(matches),
        writer=writer or FakeWriter(),
        tools=tools,
        titles=FakeTitles(
            {_ARTICLE: WikiTitle(requested=_ARTICLE, canonical=_ARTICLE)}
        ),
        articles=articles or FakeArticles(),
        sleep=_recorder(sleeps if sleeps is not None else []),
        # 시간이 흐르지 않는 시계 — 간격 벌리기가 항상 걸린다.
        monotonic=lambda: 0.0,
    )


def _recorder(sink: list[float]):
    async def _sleep(seconds: float) -> None:
        sink.append(seconds)

    return _sleep


def _answer(winner: str | None, quote: str) -> ToolStep:
    return ToolStep(
        text=json.dumps({"winner_name": winner, "quote": quote}), model="fake-model"
    )


def _happy_steps(
    *, winner: str = "Roman Reigns", quote: str = "Reigns defeated Rhodes"
) -> list[ToolStep]:
    return [
        ToolStep(
            calls=(ToolCall(name="find_wiki_article", arguments={"name": _ARTICLE}),),
            model="fake-model",
        ),
        ToolStep(
            calls=(
                ToolCall(
                    name="read_wiki_section",
                    arguments={"title": _ARTICLE, "index": "3"},
                ),
            ),
            model="fake-model",
        ),
        _answer(winner, quote),
    ]


class TestToolSurface:
    def test_model_has_no_write_tool(self) -> None:
        """이 검사가 깨지면 모델이 DB에 닿는 경로가 생긴 것이다."""
        assert {tool.name for tool in _TOOLS} == {
            "find_wiki_article",
            "read_wiki_section",
        }


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_finds_reads_and_writes(self) -> None:
        writer = FakeWriter()
        tools = FakeTools(_happy_steps())

        run = await _interactor(tools, writer=writer).verify(
            VerifyResultsCommand(apply=True)
        )

        assert run.written == 1
        assert writer.calls == [
            {
                "event_slug": "summerslam",
                "match_key": "ss26-whc",
                "pick": "left",
                "winner_name": "Roman Reigns",
            }
        ]

    @pytest.mark.asyncio
    async def test_reports_provenance_and_model(self) -> None:
        run = await _interactor(FakeTools(_happy_steps())).verify(
            VerifyResultsCommand(apply=True)
        )
        match = run.matches[0]

        assert match.source_title == _ARTICLE
        assert match.source_revision_id == "777"
        assert match.model == "fake-model"
        assert match.tool_calls == 2

    @pytest.mark.asyncio
    async def test_dry_run_writes_nothing(self) -> None:
        writer = FakeWriter()

        run = await _interactor(FakeTools(_happy_steps()), writer=writer).verify(
            VerifyResultsCommand(apply=False)
        )

        assert writer.calls == []
        assert run.written == 0
        # 쓸 수 있다는 판정 자체는 살아 있어야 한다 — 그것이 드라이런의 쓸모다.
        assert run.writable == 1
        assert run.matches[0].written is False

    @pytest.mark.asyncio
    async def test_exchanges_ride_along_each_step(self) -> None:
        """허브에 상태가 없으므로 부르는 쪽이 매 걸음 전체를 다시 보낸다."""
        tools = FakeTools(_happy_steps())

        await _interactor(tools).verify(VerifyResultsCommand())

        assert [len(command.exchanges) for command in tools.commands] == [0, 1, 2]


class TestHold:
    @pytest.mark.asyncio
    async def test_step_budget_exceeded_holds(self) -> None:
        """도구만 계속 부르는 모델. 루프가 비용으로 가지 않는다."""
        forever = ToolStep(
            calls=(ToolCall(name="find_wiki_article", arguments={"name": _ARTICLE}),),
            model="fake-model",
        )
        tools = FakeTools([], repeat=forever)
        writer = FakeWriter()

        run = await _interactor(tools, writer=writer).verify(
            VerifyResultsCommand(apply=True)
        )

        assert run.matches[0].hold is HoldReason.NO_CLAIM
        assert writer.calls == []
        assert len(tools.commands) == MAX_STEPS_PER_MATCH

    @pytest.mark.asyncio
    async def test_tool_call_budget_exceeded_holds(self) -> None:
        """한 걸음에 호출을 몰아 넣는 경우 — 걸음 수로는 막히지 않는다."""
        flood = ToolStep(
            calls=tuple(
                ToolCall(name="find_wiki_article", arguments={"name": _ARTICLE})
                for _ in range(MAX_TOOL_CALLS_PER_MATCH + 3)
            ),
            model="fake-model",
        )
        tools = FakeTools([flood], repeat=flood)

        run = await _interactor(tools).verify(VerifyResultsCommand(apply=True))

        assert run.matches[0].hold is HoldReason.NO_CLAIM
        assert run.matches[0].tool_calls == MAX_TOOL_CALLS_PER_MATCH

    @pytest.mark.asyncio
    async def test_non_json_answer_holds(self) -> None:
        steps = _happy_steps()
        steps[-1] = ToolStep(text="찾아봤는데 잘 모르겠습니다.", model="fake-model")

        run = await _interactor(FakeTools(steps)).verify(
            VerifyResultsCommand(apply=True)
        )

        assert run.matches[0].hold is HoldReason.NO_CLAIM

    @pytest.mark.asyncio
    async def test_truncated_text_is_the_evidence(self) -> None:
        """보여 주지 않은 구절을 인용하면 위조로 걸린다."""
        hidden = "Reigns defeated Rhodes by pinfall."
        articles = FakeArticles(text="가" * MAX_SECTION_CHARS + hidden)
        tools = FakeTools(_happy_steps(quote=hidden))

        run = await _interactor(tools, articles=articles).verify(
            VerifyResultsCommand(apply=True)
        )

        assert run.matches[0].hold is HoldReason.QUOTE_NOT_FOUND


class TestToolFailures:
    @pytest.mark.asyncio
    async def test_unknown_tool_does_not_end_the_match(self) -> None:
        """모델이 쓰기 도구를 지어내 부르는 경우. 실패를 적어 주고 계속 간다."""
        steps = [
            ToolStep(
                calls=(
                    ToolCall(
                        name="record_result", arguments={"winner": "Roman Reigns"}
                    ),
                ),
                model="fake-model",
            ),
            *_happy_steps(),
        ]
        tools = FakeTools(steps)
        writer = FakeWriter()

        run = await _interactor(tools, writer=writer).verify(
            VerifyResultsCommand(apply=True)
        )

        # 지어낸 호출은 오류로 돌아갔고, 그 뒤 정상 경로가 이어져 결국 쓰였다.
        assert "error" in tools.commands[1].exchanges[0].result
        assert run.written == 1
        assert len(writer.calls) == 1

    @pytest.mark.asyncio
    async def test_missing_article_ends_in_hold(self) -> None:
        steps = [
            ToolStep(
                calls=(
                    ToolCall(name="find_wiki_article", arguments={"name": "없는 대회"}),
                ),
                model="fake-model",
            ),
            _answer(None, ""),
        ]

        run = await _interactor(FakeTools(steps)).verify(
            VerifyResultsCommand(apply=True)
        )

        assert run.matches[0].hold is HoldReason.NO_WINNER

    @pytest.mark.asyncio
    async def test_zero_row_write_raises(self) -> None:
        """`list_pending`이 본 경기가 사라진 것이다. 조용히 넘기지 않는다."""
        writer = FakeWriter(ok=False)

        with pytest.raises(RuntimeError, match="사라졌습니다"):
            await _interactor(FakeTools(_happy_steps()), writer=writer).verify(
                VerifyResultsCommand(apply=True)
            )


class TestPacingAndCost:
    @pytest.mark.asyncio
    async def test_calls_are_paced_apart(self) -> None:
        """첫 호출은 기다리지 않고, 이후는 한도에 맞춰 기다린다."""
        sleeps: list[float] = []

        await _interactor(FakeTools(_happy_steps()), sleeps=sleeps).verify(
            VerifyResultsCommand()
        )

        assert sleeps == [MIN_CALL_INTERVAL_SECONDS, MIN_CALL_INTERVAL_SECONDS]

    @pytest.mark.asyncio
    async def test_no_targets_means_no_model_call(self) -> None:
        tools = FakeTools(_happy_steps())

        run = await _interactor(tools, matches=()).verify(VerifyResultsCommand())

        assert tools.commands == []
        assert run.found == 0

    @pytest.mark.asyncio
    async def test_limit_does_not_hide_remaining_count(self) -> None:
        second = MatchUnderReview(
            event_slug="summerslam",
            event_label="SummerSlam 2026",
            match_key="ss26-wwe",
            title="WWE Championship",
            options=_MATCH.options,
        )
        tools = FakeTools(_happy_steps())

        run = await _interactor(tools, matches=(_MATCH, second)).verify(
            VerifyResultsCommand(limit=1)
        )

        assert run.found == 2
        assert len(run.matches) == 1


class FailingTools(GeminiToolUseCase):
    """정해진 횟수만 장애를 내고 그 뒤로는 정상 응답을 낸다."""

    def __init__(self, fail_on: set[int], steps: list[ToolStep]) -> None:
        self._fail_on = fail_on
        self._steps = list(steps)
        self.commands: list[ToolStepCommand] = []

    async def next_step(self, command: ToolStepCommand) -> ToolStep:
        self.commands.append(command)
        if len(self.commands) in self._fail_on:
            raise ToolCallUnavailableError("모델에게 물어볼 수 없었습니다.")
        return self._steps.pop(0) if self._steps else ToolStep(text="{}")


class TestEngineOutage:
    """2026-09-28 운영 실측: 넷째 경기의 503이 앞선 셋의 작업까지 날렸다."""

    @pytest.mark.asyncio
    async def test_outage_becomes_a_hold_not_a_crash(self) -> None:
        tools = FailingTools(fail_on={1}, steps=[])

        run = await _interactor(tools).verify(VerifyResultsCommand(apply=True))

        assert run.matches[0].hold is HoldReason.ENGINE_UNAVAILABLE
        assert run.matches[0].written is False

    @pytest.mark.asyncio
    async def test_later_matches_still_run_after_an_outage(self) -> None:
        """첫 경기가 막혀도 둘째는 정상으로 끝나야 한다 — 그게 이 수정의 요점이다."""
        second = MatchUnderReview(
            event_slug="summerslam",
            event_label="SummerSlam 2026",
            match_key="ss26-wwe",
            title="WWE Championship",
            options=_MATCH.options,
        )
        tools = FailingTools(fail_on={1}, steps=_happy_steps())
        writer = FakeWriter()

        run = await _interactor(tools, writer=writer, matches=(_MATCH, second)).verify(
            VerifyResultsCommand(apply=True)
        )

        assert run.matches[0].hold is HoldReason.ENGINE_UNAVAILABLE
        assert run.matches[1].pick == "left"
        assert run.written == 1
        assert [c["match_key"] for c in writer.calls] == ["ss26-wwe"]

    @pytest.mark.asyncio
    async def test_outage_is_not_confused_with_no_claim(self) -> None:
        """ "묻지 못했다"와 "물어봤는데 못 골랐다"는 다른 보류다."""
        outage = await _interactor(FailingTools(fail_on={1}, steps=[])).verify(
            VerifyResultsCommand()
        )
        steps = _happy_steps()
        steps[-1] = ToolStep(text="모르겠습니다.", model="fake-model")
        no_claim = await _interactor(FakeTools(steps)).verify(VerifyResultsCommand())

        assert outage.matches[0].hold is HoldReason.ENGINE_UNAVAILABLE
        assert no_claim.matches[0].hold is HoldReason.NO_CLAIM
