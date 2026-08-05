"""서사·루머 에이전트가 함께 쓰는 프롬프트 조립과 응답 판독.

두 에이전트는 **묻는 것만 다르고 다루는 위험은 같다**: 모델이 카드에 없는 이름을
고르거나, JSON이 아닌 말을 하거나, 근거 없이 확신하는 경우다. 그 처리를 한곳에 둔다.

여기서 정한 원칙 둘.
1. **출처 있는 지식이 없으면 모델을 부르지 않는다.** 근거 없는 예측은 만들지 않는다
   (하네스 §3-D6). 부르지 않으면 비용도 들지 않는다.
2. **모델 이름·프롬프트 원문은 리포트로 나가지 않는다**(§4-10 · §11-6). 나가는 것은
   pick·확신·요약·출처 URL뿐이다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Sequence
from typing import Any

from kayfabe.app.dtos.agent_prediction_dto import KnowledgeChunk, MatchContext
from kayfabe.app.ports.output.agent_errors import AgentUnavailableError
from kayfabe.domain.entities.agent_prediction import AgentKind, AgentReport
from ontology.app.dtos.gemini_generation_dto import GeminiGenerationCommand
from ontology.app.ports.input.gemini_generation_use_case import GeminiGenerationUseCase

logger = logging.getLogger("uvicorn.error")

#: 화면 한 줄에 들어갈 분량. 넘치면 자른다 — 모델이 장문을 쓰는 날이 있다.
MAX_SUMMARY_CHARS = 300

#: 프롬프트에 넣는 지식 조각 수. 검색이 더 많이 줘도 여기서 끊는다.
MAX_KNOWLEDGE_ITEMS = 5

#: 리포트에 붙이는 출처 수.
MAX_SOURCES = 5

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
        f"- 코드 {option.pick} = {option.name}"
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


def silent(agent: AgentKind, summary: str) -> AgentReport:
    """의견 없음. **실패가 아니라 판단할 근거가 없는 정상 상태다.**"""
    return AgentReport(agent=agent, pick=None, weight=0.0, summary=summary)


async def ask_for_report(
    use_case: GeminiGenerationUseCase,
    *,
    agent: AgentKind,
    prompt: str,
    context: MatchContext,
    chunks: Sequence[KnowledgeChunk],
    gate: RateGate,
) -> AgentReport:
    """모델에 묻고 리포트로 옮긴다. 엔진이 죽었으면 `AgentUnavailableError`."""
    raw = await _generate(use_case, agent, prompt, gate)
    payload = _parse(raw, agent)
    return _to_report(payload, agent=agent, context=context, chunks=chunks)


async def _generate(
    use_case: GeminiGenerationUseCase, agent: AgentKind, prompt: str, gate: RateGate
) -> str:
    await gate.acquire()

    pieces: list[str] = []
    try:
        async for piece in use_case.stream_generate(GeminiGenerationCommand(prompt)):
            pieces.append(piece)
    except Exception as exc:  # 네트워크·한도 초과·인증 실패
        # 모델 이름과 프롬프트는 로그에도 원문으로 남기지 않는다.
        logger.warning("[kayfabe.agent] 생성 실패 | agent=%s | %r", agent, exc)
        raise AgentUnavailableError("AI 분석을 잠시 사용할 수 없습니다.") from exc
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
) -> AgentReport:
    summary = _summary(payload)
    pick = _pick(payload, context)
    if pick is None:
        # 요약은 살린다 — "왜 못 골랐는지"도 화면에 쓸 근거다.
        return silent(agent, summary)

    return AgentReport(
        agent=agent,
        pick=pick,
        weight=_weight(payload),
        summary=summary,
        sources=_sources(chunks),
    )


def _pick(payload: dict[str, Any], context: MatchContext) -> str | None:
    raw = payload.get("pick")
    if raw is None:
        return None
    pick = str(raw).strip()
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
