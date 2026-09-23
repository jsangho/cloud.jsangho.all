"""서사·루머 에이전트가 함께 쓰는 프롬프트 조립과 응답 판독.

두 에이전트는 **묻는 것만 다르고 다루는 위험은 같다**: 모델이 카드에 없는 이름을
고르거나, JSON이 아닌 말을 하거나, 근거 없이 확신하는 경우다. 그 처리를 한곳에 둔다.

여기서 정한 원칙 둘.
1. **출처 있는 지식이 없으면 모델을 부르지 않는다.** 근거 없는 예측은 만들지 않는다
   (하네스 §3-D6). 부르지 않으면 비용도 들지 않는다.
2. **모델 이름·프롬프트 원문은 API 응답으로 나가지 않는다**(§4-10 · §11-6). 응답에
   실리는 것은 pick·확신·요약·출처 URL뿐이다.

**Phase 4가 2번의 경계를 정확히 했다.** 모델 이름과 프롬프트 해시는 이제
`AgentRuntime`으로 리포트에 붙어 **DB까지 간다** — 어떤 조건에서 나온 의견인지
사후에 물을 수 있어야 하기 때문이다. §11-6이 막는 것은 *응답*이지 *기록*이 아니고,
경계는 경계 DTO(`AgentReportDto`)가 지킨다: 그쪽에는 이 값들이 없어서 라우터가
실수로도 내보낼 수 없다. **프롬프트 원문은 어디에도 저장하지 않는다** — 남는 것은
되돌릴 수 없는 해시뿐이다.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Sequence
from typing import Any

from kayfabe.app.dtos.agent_prediction_dto import KnowledgeChunk, MatchContext
from kayfabe.app.ports.output.agent_errors import AgentUnavailableError
from kayfabe.domain.entities.agent_prediction import (
    AgentKind,
    AgentReport,
    AgentRuntime,
)
from ontology.app.dtos.gemini_generation_dto import GeminiGenerationCommand
from ontology.app.ports.input.gemini_generation_use_case import GeminiGenerationUseCase

logger = logging.getLogger("uvicorn.error")

#: 화면 한 줄에 들어갈 분량. 넘치면 자른다 — 모델이 장문을 쓰는 날이 있다.
MAX_SUMMARY_CHARS = 300

#: 프롬프트에 넣는 지식 조각 수. 검색이 더 많이 줘도 여기서 끊는다.
MAX_KNOWLEDGE_ITEMS = 5

#: 리포트에 붙이는 출처 수.
MAX_SOURCES = 5

#: 한 리포트를 얻기 위한 최대 시도 수. 마지막 시도는 예비 모델로 간다.
#:
#: 벤더의 일시 장애(503 "high demand")가 실제로 관측됐고, 그때 서사 에이전트가
#: 통째로 빠져 경기가 오즈 단독으로 확정됐다. **재시도는 한도 초과(429)가 아니라
#: 이 일시 장애를 위한 것이다** — 페이싱으로 429는 이미 막고 있다.
MAX_ATTEMPTS = 3

#: 재시도 간격(초). 몰아치지 않도록 뒤로 갈수록 늘린다.
RETRY_BACKOFF_SECONDS = (3.0, 8.0)

#: 분당 허용 호출 수. 무료 등급 한도는 5회이고, 1회는 승부예측 외의 경로
#: (선수 챗 등) 몫으로 남긴다. 넘기면 429가 나고 그 경기는 오즈 한 표로 확정된다.
MAX_CALLS_PER_MINUTE = 4

_RATE_WINDOW_SECONDS = 60.0

_JSON_RULE = (
    "반드시 아래 JSON 하나만 출력하세요. 코드블록·설명·인사말을 붙이지 마세요.\n"
    '{"pick": "<선택지 코드 또는 null>", "confidence": <0.0~1.0>, '
    '"summary": "<한국어 2~3문장 근거>"}\n'
    "근거가 부족하면 pick을 null로, confidence를 0으로 두세요. "
    "**추측으로 한쪽을 고르지 마세요.**"
)


class RateGate:
    """분당 호출 수를 맞춰 429를 애초에 만들지 않는다.

    **재시도가 아니라 페이싱이다.** 429를 맞고 다시 던지면 상대 서버에 두 번 부담을
    주고, 그 사이 다른 경기 호출까지 밀린다. 속도를 맞추면 그 상황이 오지 않는다.

    프로세스 안에서만 유효하다 — 워커가 여럿이면 그 수만큼 곱해진다. 지금 생성
    경로는 스크립트 하나(또는 관리자 요청 하나)라 이 범위로 충분하다.
    """

    def __init__(self, max_per_minute: int) -> None:
        self._max = max_per_minute
        self._lock = asyncio.Lock()
        self._recent: list[float] = []

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                self._recent = [
                    t for t in self._recent if now - t < _RATE_WINDOW_SECONDS
                ]
                if len(self._recent) < self._max:
                    self._recent.append(now)
                    return
                wait = _RATE_WINDOW_SECONDS - (now - self._recent[0])
                logger.info("[kayfabe.agent] 호출 한도 대기 | %.1f초", wait)
                await asyncio.sleep(wait)


#: 두 LLM 에이전트가 공유한다 — 한도는 모델 단위이지 에이전트 단위가 아니다.
shared_rate_gate = RateGate(MAX_CALLS_PER_MINUTE)


def describe_match(context: MatchContext) -> str:
    lines = [
        f"대회: {context.event_label}",
        f"경기: {context.title}",
        f"형식: {'단일전' if context.match_format == 'singles' else '다인전'}",
        "선택지:",
    ]
    lines += [
        f"- {_OPTION_LABEL_PREFIX}{option.pick} = {option.name}"
        + (" (현 챔피언)" if option.is_champion else "")
        for option in context.options
    ]
    return "\n".join(lines)


def describe_knowledge(chunks: Sequence[KnowledgeChunk]) -> str:
    """지식을 최신 표기와 함께 늘어놓는다. **URL은 넣지 않는다.**

    출처는 우리가 붙인다 — 프롬프트에 URL을 넣으면 모델이 그럴듯한 다른 주소를
    지어내 요약에 섞는다.
    """
    lines = []
    for index, chunk in enumerate(chunks[:MAX_KNOWLEDGE_ITEMS], start=1):
        published = (
            chunk.published_at.date().isoformat() if chunk.published_at else "날짜 미상"
        )
        lines.append(f"[{index}] ({published}) {chunk.text}")
    return "\n".join(lines)


def usable_knowledge(chunks: Sequence[KnowledgeChunk]) -> list[KnowledgeChunk]:
    """출처를 붙일 수 있는 조각만 남긴다(하네스 §3-D6)."""
    return [chunk for chunk in chunks if chunk.source_url]


def json_rule() -> str:
    return _JSON_RULE


#: 지시문과 자료를 잇는 **조립 틀**. 상수로 꺼내 둔 이유는 하나다 — `prompt_version`이
#: 이 문자열까지 해시에 넣어야 "[자료]를 [경기] 앞에 두도록 바꿨다" 같은 변경이
#: 버전에 잡힌다. f-string 안에 흩어 두면 해시가 그 변경을 못 본다.
_PROMPT_LAYOUT = "{persona}\n\n[경기]\n{match}\n\n[자료]\n{knowledge}\n\n{rule}"


def build_prompt(
    persona: str, context: MatchContext, chunks: Sequence[KnowledgeChunk]
) -> str:
    """두 LLM 에이전트가 **같은 틀로** 묻는다. 다른 것은 페르소나뿐이다."""
    return _PROMPT_LAYOUT.format(
        persona=persona,
        match=describe_match(context),
        knowledge=describe_knowledge(chunks),
        rule=_JSON_RULE,
    )


def prompt_version(persona: str) -> str:
    """지시문에서 **파생되는** 판 식별자 (Phase 4). 손으로 올리지 않는다.

    덮는 것은 셋이다: 페르소나 · 조립 틀(`_PROMPT_LAYOUT`) · 출력 규칙(`_JSON_RULE`).
    셋 중 한 글자만 달라도 값이 바뀐다.

    **덮지 못하는 것이 있다.** `describe_match`·`describe_knowledge`가 경기와 자료를
    적는 *방식*은 함수 안에 있어서 이 해시가 보지 못한다. 그 구멍은 조립된 프롬프트
    전문을 고정한 테스트(`test_gemini_agents.py`의 프롬프트 골든)가 막는다 — 형식을
    건드리면 그쪽이 먼저 깨지고, 그때 무엇이 바뀌었는지 사람이 본다.

    앞 16자리만 쓴다. 사람이 눈으로 두 값을 대조하는 용도이고, 서로 다른 지시문이
    16자리까지 같을 일은 실질적으로 없다.
    """
    material = "\x00".join((persona, _PROMPT_LAYOUT, _JSON_RULE))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def silent(
    agent: AgentKind, summary: str, runtime: AgentRuntime | None = None
) -> AgentReport:
    """의견 없음. **실패가 아니라 판단할 근거가 없는 정상 상태다.**"""
    return AgentReport(
        agent=agent, pick=None, weight=0.0, summary=summary, runtime=runtime
    )


async def ask_for_report(
    use_case: GeminiGenerationUseCase,
    *,
    agent: AgentKind,
    agent_version: str,
    prompt_version: str,
    prompt: str,
    context: MatchContext,
    chunks: Sequence[KnowledgeChunk],
    gate: RateGate,
    model: str | None = None,
    fallback_model: str | None = None,
) -> AgentReport:
    """모델에 묻고 리포트로 옮긴다. 엔진이 죽었으면 `AgentUnavailableError`."""
    raw, model_used = await _generate(
        use_case, agent, prompt, gate, model, fallback_model
    )
    runtime = AgentRuntime(
        agent_version=agent_version,
        # **실제로 답한 모델**이다. 예비로 넘어갔으면 예비 쪽 이름이 들어간다.
        model=model_used,
        prompt_version=prompt_version,
    )
    payload = _parse(raw, agent)
    return _to_report(
        payload, agent=agent, context=context, chunks=chunks, runtime=runtime
    )


async def _generate(
    use_case: GeminiGenerationUseCase,
    agent: AgentKind,
    prompt: str,
    gate: RateGate,
    model: str | None,
    fallback_model: str | None = None,
) -> tuple[str, str | None]:
    """일시 장애면 다시 묻고, 그래도 안 되면 예비 모델로 한 번 더 묻는다.

    같은 모델만 두드리면 그 모델이 혼잡한 동안 계속 실패한다. 마지막 시도를 다른
    모델로 돌리는 이유이고, 한도가 모델 단위라 예비 모델은 자기 몫을 따로 갖는다.

    **응답과 함께 그 응답을 낸 모델을 돌려준다** (Phase 4). 호출자가 설정값을 적으면
    예비 모델이 답한 날의 기록이 거짓이 된다 — 주 모델이 혼잡해 예비가 답했는데
    기록에는 주 모델이 남는 상황이고, 그 예측이 왜 달랐는지 영영 설명되지 않는다.
    """
    last: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        is_last = attempt == MAX_ATTEMPTS - 1
        target = fallback_model if (is_last and fallback_model) else model
        try:
            return await _stream_once(use_case, gate, prompt, target), target
        except Exception as exc:  # 네트워크·한도 초과·인증 실패·일시 혼잡
            last = exc
            # 모델 이름과 프롬프트는 로그에도 원문으로 남기지 않는다.
            logger.warning(
                "[kayfabe.agent] 생성 실패 | agent=%s | 시도=%d/%d | %r",
                agent,
                attempt + 1,
                MAX_ATTEMPTS,
                exc,
            )
            if not is_last:
                await asyncio.sleep(
                    RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)]
                )

    raise AgentUnavailableError("AI 분석을 잠시 사용할 수 없습니다.") from last


async def _stream_once(
    use_case: GeminiGenerationUseCase,
    gate: RateGate,
    prompt: str,
    model: str | None,
) -> str:
    await gate.acquire()
    pieces: list[str] = []
    command = GeminiGenerationCommand(prompt=prompt, model=model)
    async for piece in use_case.stream_generate(command):
        pieces.append(piece)
    return "".join(pieces)


def _parse(raw: str, agent: AgentKind) -> dict[str, Any]:
    """코드블록을 두른 응답까지는 받아 준다. 그 이상은 파손으로 본다."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        text = text.removeprefix("json").strip()

    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        logger.warning("[kayfabe.agent] JSON 아님 | agent=%s", agent)
        raise AgentUnavailableError("AI 분석 결과를 읽지 못했습니다.")

    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        logger.warning("[kayfabe.agent] JSON 판독 실패 | agent=%s | %r", agent, exc)
        raise AgentUnavailableError("AI 분석 결과를 읽지 못했습니다.") from exc

    if not isinstance(payload, dict):
        raise AgentUnavailableError("AI 분석 결과를 읽지 못했습니다.")
    return payload


def _to_report(
    payload: dict[str, Any],
    *,
    agent: AgentKind,
    context: MatchContext,
    chunks: Sequence[KnowledgeChunk],
    runtime: AgentRuntime,
) -> AgentReport:
    summary = _summary(payload)
    pick = _pick(payload, context)
    if pick is None:
        # 요약은 살린다 — "왜 못 골랐는지"도 화면에 쓸 근거다.
        # **실행 조건도 살린다** — 모델은 실제로 불렸고, 못 고른 것이 그 판의 결과다.
        return silent(agent, summary, runtime)

    return AgentReport(
        agent=agent,
        pick=pick,
        weight=_weight(payload),
        summary=summary,
        sources=_sources(chunks),
        runtime=runtime,
    )


#: 선택지를 늘어놓을 때 우리가 붙이는 라벨. `describe_match`의 `f"- 코드 {pick} = {name}"`와
#: **같은 문자열이어야 한다** — 한쪽만 바꾸면 이 되돌리기가 조용히 멈춘다.
_OPTION_LABEL_PREFIX = "코드 "


def _strip_label_echo(pick: str) -> str:
    """모델이 **우리 라벨을 통째로 베껴** 보냈을 때 코드만 꺼낸다.

    2026-09-22 운영 실측: `wc26-cruiserweight`에서 `pick='코드 2'`가 왔다. 모델은
    제대로 골랐는데 `describe_match`가 `- 코드 2 = Mini Vikingo`로 적어 준 라벨을
    값으로 되돌려 준 것이고, 대조가 실패해 **그 의견이 통째로 버려졌다.**
    그 경기는 배당도 없어 폴백도 못 해 예측 0건으로 끝났다.

    **관대해지는 것이 아니라 우리가 만든 잡음을 우리가 걷어내는 것이다.** 여기서
    벗겨 내는 것은 우리 프롬프트가 붙인 접두사와 `=` 뒤의 이름뿐이고, 그러고도
    카드에 없는 값이면 그대로 거부된다.
    """
    if pick.startswith(_OPTION_LABEL_PREFIX):
        pick = pick[len(_OPTION_LABEL_PREFIX) :].strip()
    # `코드 2 = Mini Vikingo`처럼 줄 전체를 베낀 경우. 이름 쪽은 아래 이름 대조가
    # 따로 맡으므로 여기서는 코드만 남긴다.
    if "=" in pick:
        pick = pick.split("=", 1)[0].strip()
    return pick


def _pick(payload: dict[str, Any], context: MatchContext) -> str | None:
    raw = payload.get("pick")
    if raw is None:
        return None
    pick = _strip_label_echo(str(raw).strip())
    allowed = {option.pick for option in context.options}
    if pick in allowed:
        return pick

    # 카드에 없는 이름을 고른 것은 의견이 아니다. 이름으로 한 번 더 맞춰 본다.
    for option in context.options:
        if pick and pick.lower() == option.name.lower():
            return option.pick
    logger.warning(
        "[kayfabe.agent] 카드에 없는 pick | match=%s | pick=%r",
        context.match_key,
        pick,
    )
    return None


def _weight(payload: dict[str, Any]) -> float:
    try:
        weight = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, weight))


def _summary(payload: dict[str, Any]) -> str:
    summary = str(payload.get("summary") or "").strip()
    if len(summary) <= MAX_SUMMARY_CHARS:
        return summary
    return summary[: MAX_SUMMARY_CHARS - 1].rstrip() + "…"


def _sources(chunks: Sequence[KnowledgeChunk]) -> tuple[str, ...]:
    """실제로 프롬프트에 넣은 조각의 출처만 붙인다. 순서는 유지하고 중복은 지운다."""
    seen: list[str] = []
    for chunk in chunks[:MAX_KNOWLEDGE_ITEMS]:
        url = chunk.source_url
        if url and url not in seen:
            seen.append(url)
    return tuple(seen[:MAX_SOURCES])
