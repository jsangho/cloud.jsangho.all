"""에이전트 실행 조건 기록 (Phase 4).

이 파일이 붙드는 주장은 하나다 — **두 예측이 다르면 무엇이 달랐는지 말할 수 있어야
한다.** 같은 경기에서 어제와 오늘의 예측이 갈렸을 때, 코퍼스가 바뀐 것인지 우리가
질문을 바꾼 것인지 구분되지 않으면 그 차이는 아무것도 설명하지 못한다.

그래서 고정하는 계약은 다섯이다.

1. **지시문이 바뀌면 `prompt_version`이 바뀐다** — 파생값이라 손으로 못 속인다.
   페르소나·조립 틀·출력 규칙 셋 다 해시에 들어간다.
2. **해시가 못 보는 자리는 골든이 막는다** — `describe_match`·`describe_knowledge`의
   조립 형식은 함수 안에 있어 해시에 안 잡힌다. 조립된 프롬프트 전문을 박아 둔다.
3. **기록하는 모델은 실제로 답한 모델이다** — 예비 모델로 넘어갔으면 예비 쪽이다.
   설정값을 적으면 주 모델이 혼잡했던 날의 기록이 통째로 거짓이 된다.
4. **없는 값을 만들지 않는다** — 모델을 고정하지 않은 호출, LLM을 안 쓰는 오즈,
   모델을 부르지 않은 "자료 없음"은 그 칸이 비어 있는 것이 사실이다.
5. **API 경계는 그대로다** — 모델 이름이 경계 DTO에 없어서 라우터가 실수로도
   내보낼 수 없다(하네스 §11-6).

**LLM을 부르지 않는다.** 페이크 생성 유스케이스가 정해진 문자열을 흘려보낸다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest \
        apps/kayfabe/tests/adapter/outbound/test_agent_runtime_versions.py -q
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from kayfabe.adapter.outbound.agents import gemini_agent_support
from kayfabe.adapter.outbound.agents.gemini_agent_support import (
    RateGate,
    build_prompt,
    prompt_version,
)
from kayfabe.adapter.outbound.agents.odds_scout_agent import (
    AGENT_VERSION as ODDS_AGENT_VERSION,
)
from kayfabe.adapter.outbound.agents.odds_scout_agent import BookmakerOddsScout
from kayfabe.adapter.outbound.agents.rumor_scout_agent import (
    AGENT_VERSION as RUMOR_AGENT_VERSION,
)
from kayfabe.adapter.outbound.agents.rumor_scout_agent import (
    PROMPT_VERSION as RUMOR_PROMPT_VERSION,
)
from kayfabe.adapter.outbound.agents.rumor_scout_agent import GeminiRumorScout
from kayfabe.adapter.outbound.agents.storyline_gemini_agent import (
    _PERSONA as STORYLINE_PERSONA,
)
from kayfabe.adapter.outbound.agents.storyline_gemini_agent import (
    AGENT_VERSION as STORYLINE_AGENT_VERSION,
)
from kayfabe.adapter.outbound.agents.storyline_gemini_agent import (
    PROMPT_VERSION as STORYLINE_PROMPT_VERSION,
)
from kayfabe.adapter.outbound.agents.storyline_gemini_agent import (
    GeminiStorylineAnalyst,
)
from kayfabe.app.dtos.agent_prediction_dto import (
    AgentReportDto,
    KnowledgeChunk,
    MatchContext,
    MatchOption,
)
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
    """`GeminiGenerationUseCase` 대역. 무엇을 어느 모델에 물었는지 붙잡아 둔다."""

    def __init__(self, reply: str, *, fail_times: int = 0) -> None:
        self.reply = reply
        #: 앞의 N번은 실패시킨다 — 벤더 일시 장애(503) 재현용.
        self.fail_times = fail_times
        self.models: list[str | None] = []

    def stream_generate(self, command: GeminiGenerationCommand) -> AsyncIterator[str]:
        self.models.append(command.model)

        async def _stream() -> AsyncIterator[str]:
            if self.fail_times > 0:
                self.fail_times -= 1
                raise RuntimeError("503 UNAVAILABLE")
            yield self.reply

        return _stream()


def _reply(pick: object = "left") -> str:
    return json.dumps(
        {"pick": pick, "confidence": 0.8, "summary": "명분이 있다."},
        ensure_ascii=False,
    )


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """재시도 간격을 없앤다 — 검증 대상은 대기 시간이 아니라 어느 모델이 답했는가다."""
    monkeypatch.setattr(gemini_agent_support, "RETRY_BACKOFF_SECONDS", (0.0, 0.0))


def _open_gate() -> RateGate:
    """한도를 기다리지 않는다 — 여기서 재는 것은 페이싱이 아니다."""
    return RateGate(10_000)


# ---------------------------------------------------------------------------
# 1. 지시문이 바뀌면 판이 바뀐다
# ---------------------------------------------------------------------------


def test_persona_change_changes_prompt_version() -> None:
    """**페르소나 한 글자만 달라도 값이 달라진다.** 파생값의 존재 이유다."""
    before = prompt_version(STORYLINE_PERSONA)
    after = prompt_version(STORYLINE_PERSONA + " 한 문장을 덧붙였습니다.")

    assert before != after
    # 같은 입력은 언제나 같은 값이다 — 실행마다 흔들리면 대조할 수 없다.
    assert before == prompt_version(STORYLINE_PERSONA)


def test_different_agents_have_different_prompt_versions() -> None:
    """서사와 루머는 다른 것을 묻는다. 같은 값이 나오면 해시가 페르소나를 안 본 것이다."""
    assert STORYLINE_PROMPT_VERSION != RUMOR_PROMPT_VERSION


def test_output_rule_change_changes_prompt_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """출력 규칙도 지시문이다. JSON 형식을 바꾸면 모델의 답이 달라진다."""
    before = prompt_version(STORYLINE_PERSONA)
    monkeypatch.setattr(
        gemini_agent_support, "_JSON_RULE", "아무 말이나 자유롭게 쓰세요."
    )

    assert prompt_version(STORYLINE_PERSONA) != before


def test_layout_change_changes_prompt_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """**자료를 경기 앞에 두는 것도 지시문의 일부다.** 틀을 상수로 꺼내 둔 이유다."""
    before = prompt_version(STORYLINE_PERSONA)
    monkeypatch.setattr(
        gemini_agent_support,
        "_PROMPT_LAYOUT",
        "{persona}\n\n[자료]\n{knowledge}\n\n[경기]\n{match}\n\n{rule}",
    )

    assert prompt_version(STORYLINE_PERSONA) != before


# ---------------------------------------------------------------------------
# 2. 해시가 못 보는 자리 — 조립 형식 골든
# ---------------------------------------------------------------------------

#: `describe_match`·`describe_knowledge`가 사실을 적는 **방식**을 통째로 박아 둔다.
#: 이 둘은 함수 안에 있어 `prompt_version`의 해시가 보지 못한다. 형식을 바꾸면
#: 여기가 먼저 깨지고, 그때 사람이 "지시문이 바뀌었으니 판도 올려야 하는가"를 본다.
#:
#: **깨졌다고 기대값을 갈아 끼우는 것으로 끝내지 않는다.** 무엇이 왜 바뀌었는지
#: 먼저 적고, 모델에 다르게 묻게 된 것이 의도인지 확인한다.
_GOLDEN_STORYLINE_PROMPT = (
    "당신은 WWE 각본의 흐름을 오래 지켜본 분석가입니다. "
    "아래 [자료]에 있는 사실만 근거로 이 경기의 승자를 추론하세요. "
    "판단 기준은 대립 각본의 진행 방향, 타이틀의 명분, 최근 푸시 흐름입니다. "
    "[자료]에 없는 내용을 지어내지 마세요.\n"
    "\n"
    "[경기]\n"
    "대회: SummerSlam 2026\n"
    "경기: World Heavyweight Championship\n"
    "형식: 단일전\n"
    "선택지:\n"
    "- 코드 left = Roman Reigns (현 챔피언)\n"
    "- 코드 right = Cody Rhodes\n"
    "\n"
    "[자료]\n"
    "[1] (2026-08-01) Roman Reigns가 타이틀 방어전을 앞두고 있다.\n"
    "[2] (날짜 미상) Cody Rhodes는 지난달 부상에서 복귀했다.\n"
    "\n"
    "반드시 아래 JSON 하나만 출력하세요. 코드블록·설명·인사말을 붙이지 마세요.\n"
    '{"pick": "<선택지 코드 또는 null>", "confidence": <0.0~1.0>, '
    '"summary": "<한국어 2~3문장 근거>"}\n'
    "근거가 부족하면 pick을 null로, confidence를 0으로 두세요. "
    "**추측으로 한쪽을 고르지 마세요.**"
)


def test_rendered_prompt_is_pinned() -> None:
    assert build_prompt(STORYLINE_PERSONA, _CONTEXT, _CHUNKS) == (
        _GOLDEN_STORYLINE_PROMPT
    )


def test_prompt_never_carries_source_urls() -> None:
    """출처는 우리가 붙인다 — 프롬프트에 URL을 넣으면 모델이 다른 주소를 지어낸다.

    골든이 이미 덮지만 따로 못 박는다. 골든은 "형식이 바뀌었다"를 알려 줄 뿐,
    바뀐 형식이 URL을 흘리는지까지는 말해 주지 않는다.
    """
    prompt = build_prompt(STORYLINE_PERSONA, _CONTEXT, _CHUNKS)

    for chunk in _CHUNKS:
        assert chunk.source_url is not None
        assert chunk.source_url not in prompt


# ---------------------------------------------------------------------------
# 3. 기록하는 모델은 실제로 답한 모델이다
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_records_the_model_that_answered() -> None:
    generation = FakeGeneration(_reply())
    agent = GeminiStorylineAnalyst(
        generation,  # type: ignore[arg-type]
        model="gemini-3.5-flash",
        rate_gate=_open_gate(),
    )

    report = await agent.analyze(_CONTEXT, _CHUNKS)

    assert report.runtime is not None
    assert report.runtime.model == "gemini-3.5-flash"
    assert report.runtime.prompt_version == STORYLINE_PROMPT_VERSION
    assert report.runtime.agent_version == STORYLINE_AGENT_VERSION


@pytest.mark.asyncio
async def test_records_fallback_model_when_primary_fails() -> None:
    """**주 모델이 혼잡해 예비가 답한 날.**

    설정값(`gemini-3.5-flash`)을 적으면 그 기록은 거짓이다 — 그 예측을 만든 것은
    예비 모델이고, 나중에 "왜 이 예측만 달랐나"를 물을 때 답이 사라진다.
    """
    # 마지막 시도만 남기고 전부 실패시킨다 — 그 시도가 예비 모델로 간다.
    generation = FakeGeneration(
        _reply(), fail_times=gemini_agent_support.MAX_ATTEMPTS - 1
    )
    agent = GeminiStorylineAnalyst(
        generation,  # type: ignore[arg-type]
        model="gemini-3.5-flash",
        fallback_model="gemini-3.6-flash",
        rate_gate=_open_gate(),
    )

    report = await agent.analyze(_CONTEXT, _CHUNKS)

    assert generation.models == [
        "gemini-3.5-flash",
        "gemini-3.5-flash",
        "gemini-3.6-flash",
    ]
    assert report.runtime is not None
    assert report.runtime.model == "gemini-3.6-flash"


# ---------------------------------------------------------------------------
# 4. 없는 값을 만들지 않는다
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unpinned_model_stays_none() -> None:
    """모델을 지정하지 않으면 허브 기본값이 쓰인다. 그 이름을 여기서 지어내지 않는다.

    `None`은 "모른다"가 아니라 **"우리가 고정하지 않았다"** 는 사실이다.
    """
    generation = FakeGeneration(_reply())
    agent = GeminiRumorScout(generation, rate_gate=_open_gate())  # type: ignore[arg-type]

    report = await agent.analyze(_CONTEXT, _CHUNKS)

    assert report.runtime is not None
    assert report.runtime.model is None
    assert report.runtime.agent_version == RUMOR_AGENT_VERSION


@pytest.mark.asyncio
async def test_no_knowledge_records_agent_version_only() -> None:
    """모델을 부르지 않았다 — 모델·프롬프트 칸은 비고, 판만 남는다."""
    generation = FakeGeneration(_reply())
    agent = GeminiStorylineAnalyst(generation, rate_gate=_open_gate())  # type: ignore[arg-type]

    # 출처 없는 청크뿐이라 모델을 부르지 않는다(하네스 §3-D6).
    report = await agent.analyze(_CONTEXT, (KnowledgeChunk(text="출처 없음"),))

    assert generation.models == []
    assert report.pick is None
    assert report.runtime is not None
    assert report.runtime.agent_version == STORYLINE_AGENT_VERSION
    assert report.runtime.model is None
    assert report.runtime.prompt_version is None


@pytest.mark.asyncio
async def test_silent_report_after_real_call_keeps_runtime() -> None:
    """카드에 없는 pick이라 의견 없음으로 낮춘 경우.

    **모델은 실제로 불렸다.** 그 사실을 지우면 "못 고른 것"과 "부르지 않은 것"이
    같은 기록이 되어, 어느 판의 지시문이 답을 못 냈는지 추적할 수 없다.
    """
    generation = FakeGeneration(_reply("Seth Rollins"))
    agent = GeminiStorylineAnalyst(
        generation,  # type: ignore[arg-type]
        model="gemini-3.5-flash",
        rate_gate=_open_gate(),
    )

    report = await agent.analyze(_CONTEXT, _CHUNKS)

    assert report.pick is None
    assert report.runtime is not None
    assert report.runtime.model == "gemini-3.5-flash"
    assert report.runtime.prompt_version == STORYLINE_PROMPT_VERSION


@pytest.mark.asyncio
async def test_odds_scout_has_version_but_no_model() -> None:
    """**LLM을 쓰지 않는 축.** 모델·프롬프트는 영구히 비어 있는 것이 사실이다.

    그래도 판은 남긴다 — 오버라운드 제거 방식이 바뀌면 같은 배당에서 다른 확신도가
    나오고, 그때 이 값이 유일한 단서다.
    """
    report = await BookmakerOddsScout().analyze(_CONTEXT)

    assert report.runtime is not None
    assert report.runtime.agent_version == ODDS_AGENT_VERSION
    assert report.runtime.model is None
    assert report.runtime.prompt_version is None


@pytest.mark.asyncio
async def test_odds_scout_without_odds_still_records_version() -> None:
    """배당이 없어 판단하지 않은 경우도 어느 판이 그렇게 판단했는지는 남는다."""
    report = await BookmakerOddsScout().analyze(
        dataclasses.replace(_CONTEXT, bookmaker_decimal=None)
    )

    assert report.pick is None
    assert report.runtime is not None
    assert report.runtime.agent_version == ODDS_AGENT_VERSION


# ---------------------------------------------------------------------------
# 5. API 경계는 그대로다 (하네스 §11-6)
# ---------------------------------------------------------------------------


def test_boundary_dto_carries_no_runtime() -> None:
    """**경계 DTO가 §11-6을 지킨다.**

    실행 조건은 기록이지 응답이 아니다. `AgentReportDto`에 이 칸들이 없으면 라우터가
    실수로도 모델 이름을 내보낼 수 없다 — 규율이 아니라 타입이 막는다.

    Phase 9에서 감사 화면에 노출할지는 그때 따로 결정한다. 지금 조용히 열어 두지
    않는다.
    """
    fields = {field.name for field in dataclasses.fields(AgentReportDto)}

    assert fields == {"agent", "pick", "weight", "summary", "sources"}
