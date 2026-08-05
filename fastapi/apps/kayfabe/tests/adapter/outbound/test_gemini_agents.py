"""서사·루머 에이전트 테스트 — 하네스 §10-T5.

**LLM을 부르지 않는다.** 페이크 생성 유스케이스가 정해진 문자열을 흘려보낸다.
여기서 고정하는 계약은 넷이다.

1. 출처 있는 자료가 없으면 **모델을 아예 부르지 않는다** (근거 없는 예측 금지 · 비용)
2. 카드에 없는 pick은 의견 없음으로 낮춘다 (없는 선택지가 득표하면 승률이 틀어진다)
3. 응답이 JSON이 아니면 `AgentUnavailableError` — 조용히 0.5를 만들지 않는다
4. 리포트에 나가는 것은 pick·확신·요약·출처뿐이다 (모델 이름·프롬프트 비노출)

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest apps/kayfabe/tests -q
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from kayfabe.adapter.outbound.agents.gemini_agent_support import MAX_SUMMARY_CHARS
from kayfabe.adapter.outbound.agents.rumor_scout_agent import GeminiRumorScout
from kayfabe.adapter.outbound.agents.storyline_gemini_agent import (
    GeminiStorylineAnalyst,
)
from kayfabe.app.dtos.agent_prediction_dto import (
    KnowledgeChunk,
    MatchContext,
    MatchOption,
)
from kayfabe.app.ports.output.agent_errors import AgentUnavailableError
from kayfabe.domain.entities.agent_prediction import AgentKind
from ontology.app.dtos.gemini_generation_dto import GeminiGenerationCommand

_CONTEXT = MatchContext(
    event_slug="summerslam",
    event_label="SummerSlam 2026",
    match_key="ss26-n2-whc",
    title="World Heavyweight Championship",
    match_format="singles",
    options=(
        MatchOption(pick="left", name="Roman Reigns", is_champion=True),
        MatchOption(pick="right", name="Cody Rhodes"),
    ),
    bookmaker_decimal=(1.6, 2.4),
)

_CHUNKS = (
    KnowledgeChunk(
        text="Roman Reigns가 타이틀 방어전을 앞두고 있다.",
        source_url="https://www.wwe.com/shows/summerslam",
        published_at=datetime(2026, 8, 1, tzinfo=UTC),
    ),
    KnowledgeChunk(
        text="Cody Rhodes는 지난달 부상에서 복귀했다.",
        source_url="https://en.wikipedia.org/wiki/Cody_Rhodes",
    ),
)


class FakeGeneration:
    """`GeminiGenerationUseCase` 대역. 무엇을 물었는지 붙잡아 둔다."""

    def __init__(self, reply: str = "", *, error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error
        self.prompts: list[str] = []

    def stream_generate(self, command: GeminiGenerationCommand) -> AsyncIterator[str]:
        self.prompts.append(command.prompt)

        async def _stream() -> AsyncIterator[str]:
            if self.error is not None:
                raise self.error
            # 스트리밍이므로 조각으로 나뉘어 온다 — 이어 붙여야 JSON이 된다.
            for index in range(0, len(self.reply), 7):
                yield self.reply[index : index + 7]

        return _stream()


def _reply(pick: object, confidence: float = 0.8, summary: str = "명분이 있다.") -> str:
    return json.dumps(
        {"pick": pick, "confidence": confidence, "summary": summary},
        ensure_ascii=False,
    )


def _storyline(generation: FakeGeneration) -> GeminiStorylineAnalyst:
    return GeminiStorylineAnalyst(generation)  # type: ignore[arg-type]


def _rumor(generation: FakeGeneration) -> GeminiRumorScout:
    return GeminiRumorScout(generation)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_storyline_reads_pick_and_sources() -> None:
    generation = FakeGeneration(_reply("left"))

    report = await _storyline(generation).analyze(_CONTEXT, _CHUNKS)

    assert report.agent is AgentKind.STORYLINE
    assert report.pick == "left"
    assert report.weight == 0.8
    assert report.summary == "명분이 있다."
    assert report.sources == (
        "https://www.wwe.com/shows/summerslam",
        "https://en.wikipedia.org/wiki/Cody_Rhodes",
    )


@pytest.mark.asyncio
async def test_prompt_carries_options_and_knowledge_but_no_urls() -> None:
    """프롬프트에 URL을 넣으면 모델이 그럴듯한 다른 주소를 지어내 요약에 섞는다."""
    generation = FakeGeneration(_reply("left"))

    await _storyline(generation).analyze(_CONTEXT, _CHUNKS)

    prompt = generation.prompts[0]
    assert "Roman Reigns" in prompt
    assert "Cody Rhodes는 지난달 부상에서 복귀했다." in prompt
    assert "https://" not in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_factory", [_storyline, _rumor])
async def test_no_knowledge_means_no_model_call(agent_factory) -> None:
    """근거가 없으면 부르지 않는다 — 비용도 들지 않는다."""
    generation = FakeGeneration(_reply("left"))

    report = await agent_factory(generation).analyze(_CONTEXT, ())

    assert generation.prompts == []
    assert report.pick is None
    assert report.weight == 0.0
    assert report.summary


@pytest.mark.asyncio
async def test_chunks_without_source_are_not_used() -> None:
    """출처를 못 붙이는 지식은 근거로 쓰지 않는다(§3-D6)."""
    generation = FakeGeneration(_reply("left"))
    anonymous = (KnowledgeChunk(text="어디서 봤는지 모를 이야기."),)

    report = await _rumor(generation).analyze(_CONTEXT, anonymous)

    assert generation.prompts == []
    assert report.pick is None


@pytest.mark.asyncio
async def test_null_pick_keeps_summary_as_no_opinion() -> None:
    """루머 에이전트의 기본값에 가깝다 — 왜 못 골랐는지도 근거다."""
    generation = FakeGeneration(_reply(None, 0.0, "출전에 영향을 줄 소식이 없다."))

    report = await _rumor(generation).analyze(_CONTEXT, _CHUNKS)

    assert report.pick is None
    assert report.weight == 0.0
    assert report.summary == "출전에 영향을 줄 소식이 없다."
    assert report.sources == ()


@pytest.mark.asyncio
async def test_name_instead_of_code_is_resolved() -> None:
    """모델이 코드 대신 이름을 답하는 일이 잦다. 카드에 있는 이름이면 받아 준다."""
    generation = FakeGeneration(_reply("Cody Rhodes"))

    report = await _storyline(generation).analyze(_CONTEXT, _CHUNKS)

    assert report.pick == "right"


@pytest.mark.asyncio
async def test_pick_outside_card_becomes_no_opinion() -> None:
    """없는 선택지가 득표를 가져가면 승률이 통째로 틀어진다."""
    generation = FakeGeneration(_reply("Seth Rollins"))

    report = await _storyline(generation).analyze(_CONTEXT, _CHUNKS)

    assert report.pick is None
    assert report.weight == 0.0


@pytest.mark.asyncio
async def test_code_fenced_json_is_accepted() -> None:
    generation = FakeGeneration(f"```json\n{_reply('left')}\n```")

    report = await _storyline(generation).analyze(_CONTEXT, _CHUNKS)

    assert report.pick == "left"


@pytest.mark.asyncio
async def test_confidence_is_clamped() -> None:
    generation = FakeGeneration(_reply("left", 7.5))

    report = await _storyline(generation).analyze(_CONTEXT, _CHUNKS)

    assert report.weight == 1.0


@pytest.mark.asyncio
async def test_long_summary_is_trimmed() -> None:
    generation = FakeGeneration(_reply("left", 0.5, "가" * 500))

    report = await _storyline(generation).analyze(_CONTEXT, _CHUNKS)

    assert len(report.summary) == MAX_SUMMARY_CHARS


@pytest.mark.asyncio
async def test_non_json_answer_is_an_error_not_a_guess() -> None:
    """판독 실패와 '우열을 못 가림'은 다른 상태다(§4-11)."""
    generation = FakeGeneration("아무래도 Roman Reigns가 이길 것 같습니다.")

    with pytest.raises(AgentUnavailableError):
        await _storyline(generation).analyze(_CONTEXT, _CHUNKS)


@pytest.mark.asyncio
async def test_broken_json_is_an_error() -> None:
    generation = FakeGeneration('{"pick": "left", "confidence":}')

    with pytest.raises(AgentUnavailableError):
        await _rumor(generation).analyze(_CONTEXT, _CHUNKS)


@pytest.mark.asyncio
async def test_engine_failure_becomes_agent_unavailable() -> None:
    generation = FakeGeneration(error=RuntimeError("quota exceeded"))

    with pytest.raises(AgentUnavailableError) as caught:
        await _storyline(generation).analyze(_CONTEXT, _CHUNKS)

    # 모델 이름·한도 초과 원문이 사용자 문구로 새지 않는다.
    assert "quota" not in str(caught.value)
    assert "gemini" not in str(caught.value).lower()
