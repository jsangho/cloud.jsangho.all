"""결과 확정 에이전트 — **이 저장소의 첫 진짜 에이전트다.**

승부예측 코디네이터(`ai_prediction_interactor`)와 견주면 차이가 분명하다. 저쪽은
`asyncio.gather`로 정해진 세 호출을 한 번씩 던지고 끝난다 — 워크플로우다. 이쪽은
**몇 걸음이 필요한지 미리 알 수 없다.** 대회 문서 제목이 빗나가면 다른 표기로 다시
찾아야 하고, 목차를 보고 어느 절에 결과가 있는지 골라야 하고, 그 절에 이 경기가
없으면 다른 절을 읽어야 한다. 분기가 데이터에 따라 갈리므로 고정 호출로 못 쓴다.

**아는 것은 미리 알려 준다.** 대회 문서 제목은 사람이 전수 실측한 표
(`app/services/wiki_event_titles`)에 있으므로 모델에게 찾게 하지 않는다 —
`_lookup_hint`가 그 이유와 실측을 적고 있다. 줄어든 것은 이름 맞히기뿐이고,
어느 절을 읽을지·더 읽을지는 여전히 모델이 정한다.

## 모델에게 쓰기 도구를 주지 않는다

`_TOOLS`에 읽기 둘뿐이다. 모델이 할 수 있는 일은 문서를 찾고 읽는 것이고, 마지막에
"승자는 이 사람이고 근거는 이 구절"이라고 **주장**하는 것까지다. 그 주장을 쓸지는
`adjudicate`(순수 함수)가 정하고, 쓰는 것은 이 인터랙터가 `MatchResultWriter`로 한다.
모델이 DB에 닿는 경로가 구조적으로 없다.

## 걸음에는 상한이 있다

§2-D7이 경계한 것("에이전트를 트래픽에 매달면 비용이 트래픽에 비례한다")이 에이전트
에서는 다른 모양으로 온다 — **루프가 끝나지 않으면 비용이 무한이다.** 그래서 경기당
걸음 수와 도구 호출 수 둘 다 상한을 두고, 넘으면 `NO_CLAIM` 보류로 끝낸다. 보류는
정상 종료다.

## 호출 간격을 벌린다

무료 등급 한도는 **모델 단위 분당 5회**다. 이 에이전트는 경기 하나에 여러 번 부르므로
`gemini_agent_support`의 `RateGate`보다 훨씬 쉽게 한도에 닿는다. 그쪽 게이트를 함께
쓰지 못하는 것은 계층 때문이다(app은 adapter를 import할 수 없다). 대신 호출이 전부
순차라 **간격을 벌리는 것으로 충분하다** — 동시성이 없으니 창을 셀 필요가 없다.

운영에서 예측 생성과 겹치지 않게, 이 에이전트는 **다른 모델을 쓰도록** 프로바이더가
모델 이름을 넣어 준다(한도가 모델 단위인 것을 그대로 이용한다).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from kayfabe.app.dtos.result_verification_dto import (
    MatchVerification,
    VerificationRun,
    VerifyResultsCommand,
)
from kayfabe.app.ports.input.result_verification_use_case import (
    ResultVerificationUseCase,
)
from kayfabe.app.ports.output.match_result_writer import MatchResultWriter
from kayfabe.app.ports.output.pending_result_repository import PendingResultRepository
from kayfabe.app.services.wiki_event_titles import article_title_for
from kayfabe.domain.entities.result_verification import (
    Evidence,
    HoldReason,
    MatchUnderReview,
    ResultClaim,
    Verdict,
)
from kayfabe.domain.services.result_adjudication import adjudicate
from ontology.app.dtos.gemini_tool_dto import (
    ToolCall,
    ToolDeclaration,
    ToolExchange,
    ToolStepCommand,
)
from ontology.app.ports.input.gemini_tool_use_case import GeminiToolUseCase
from ontology.app.ports.output.gemini_tool_errors import ToolCallUnavailableError
from ontology.app.ports.output.wiki_article_port import WikiArticlePort, WikiSection
from ontology.app.ports.output.wiki_title_port import WikiTitlePort

logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class ArticleHint:
    """우리가 이미 아는 것 — 어느 문서의 어느 절들인가.

    모델에게 **알려 주는** 값이지 모델이 만든 값이 아니다. 그래서 인용 검증의
    기준이 되지 않는다 — 증거는 여전히 `read_wiki_section`이 실제로 돌려준
    본문뿐이다.
    """

    title: str
    sections: tuple[WikiSection, ...]


#: 경기 하나에 허용하는 모델 왕복 수.
#:
#: 힌트가 있으면 정상 경로는 **2걸음**이다(절 읽기 → 답). 없으면 3걸음이고
#: (문서 찾기 → 절 읽기 → 답), 문서 이름이 빗나가면 더 든다 — 그 초과가
#: `worlds-collide`에서 두 경기를 보류로 만들었고 `_lookup_hint`가 그 대응이다.
#: 여유를 두되 넉넉하게 잡을 값이 아니다: **하루 한도가 천장이라 걸음 수가 곧
#: 그날 볼 수 있는 경기 수다.**
MAX_STEPS_PER_MATCH = 6

#: 경기 하나에 허용하는 도구 호출 수. 한 걸음에 여러 호출을 요청할 수 있어 따로 센다.
MAX_TOOL_CALLS_PER_MATCH = 8

#: 절 본문을 모델에게 건네는 분량의 상한. 넘치면 자르고 잘렸다고 알린다 —
#: 조용히 자르면 모델이 "결과가 없다"고 답하는데 실은 우리가 지운 것이다.
MAX_SECTION_CHARS = 12000

#: 모델 호출 사이 최소 간격(초). 한도가 분당 5회라 15초면 분당 4회로 맞는다 —
#: `gemini_agent_support.MAX_CALLS_PER_MINUTE`가 남겨 둔 몫과 같은 계산이다.
MIN_CALL_INTERVAL_SECONDS = 15.0

_PERSONA = (
    "당신은 이미 끝난 프로레슬링 대회의 공식 결과를 위키피디아에서 확인하는 조사원입니다. "
    "추측하지 않습니다. 문서에 적힌 것만 옮깁니다."
)

#: 답의 형식과 규칙. 힌트가 있든 없든 같다 — 이 부분이 갈리면 검증 기준이 갈린다.
_ANSWER_RULES = (
    "다 찾았으면 **아래 JSON 하나만** 출력하세요. 코드블록·설명·인사말을 붙이지 마세요.\n"
    '{"winner_name": "<선택지에 적힌 이름 또는 null>", '
    '"quote": "<읽은 본문에서 그대로 옮긴 구절>"}\n\n'
    "규칙:\n"
    "- quote는 read_wiki_section이 돌려준 본문에서 **한 글자도 바꾸지 말고** 옮기세요. "
    "요약·번역·맞춤법 교정을 하면 검증에서 떨어집니다.\n"
    "- quote는 **이 경기 한 줄만** 옮기세요. 여러 경기를 한 번에 담으면 어느 승패가 "
    "이 경기의 것인지 알 수 없어 떨어집니다.\n"
    "- quote 안에 승자의 이름이 보여야 하고, **그 문장이 승자로 적은 사람**이어야 "
    "합니다. `A defeated B`에서 이긴 쪽은 A입니다 — 거꾸로 적으면 떨어집니다.\n"
    "- 문서를 못 찾았거나 그 경기의 결과가 적혀 있지 않으면 winner_name을 null로 두세요.\n"
    "- 무승부·노컨테스트처럼 승자가 없으면 winner_name을 null로 두세요.\n"
    "- **모르면 null입니다.** 그럴듯한 쪽을 고르지 마세요."
)

_INSTRUCTIONS = (
    "절차:\n"
    "1. find_wiki_article로 이 대회의 위키피디아 문서를 찾으세요. 대회 문서 제목에는 "
    "규칙이 없습니다(`WrestleMania 42`·`Backlash (2026)`·`Survivor Series: WarGames "
    "(2026)`처럼 갈립니다). 빗나가면 다른 표기로 다시 부르세요.\n"
    "2. 목차에서 결과가 적힌 절을 골라 read_wiki_section으로 읽으세요. 보통 "
    "`Results` 또는 `Event` 절입니다. 그 절에 이 경기가 없으면 다른 절을 읽으세요.\n"
    "3. 아래 [경기]의 승자를 [선택지] 안에서 찾으세요.\n\n"
) + _ANSWER_RULES


#: 힌트가 있을 때의 지시문. **1번(문서 찾기)이 사라진다.**
#:
#: `find_wiki_article`을 목록에서 빼지는 않는다 — 표가 낡아 목차에 결과 절이 없는 날
#: 모델이 스스로 찾을 길을 남겨 둔다. 다만 기본 경로에서는 부를 일이 없다.
_INSTRUCTIONS_WITH_HINT = (
    "절차:\n"
    "1. 위 [목차]에서 결과가 적힌 절을 골라 read_wiki_section으로 읽으세요. "
    "**[문서]의 제목을 그대로 title로 넘기세요.** 보통 `Results` 또는 `Event` 절입니다. "
    "그 절에 이 경기가 없으면 목차의 다른 절을 읽으세요.\n"
    "2. 아래 [경기]의 승자를 [선택지] 안에서 찾으세요.\n"
    "   목차에 결과가 적힌 절이 없어 보이면 그때만 find_wiki_article로 다른 문서를 "
    "찾으세요.\n\n"
) + _ANSWER_RULES

_TOOLS: tuple[ToolDeclaration, ...] = (
    ToolDeclaration(
        name="find_wiki_article",
        description=(
            "이름으로 영어 위키피디아 문서를 찾아 정규 제목과 목차를 돌려줍니다. "
            "리다이렉트를 따라가며, 동음이의 문서와 없는 문서를 구분해 알려 줍니다."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "찾을 문서 이름"},
            },
            "required": ["name"],
        },
    ),
    ToolDeclaration(
        name="read_wiki_section",
        description=(
            "find_wiki_article이 준 목차에서 절 하나의 본문을 읽습니다. "
            "본문은 위키텍스트이며 표가 그대로 들어 있습니다."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "find_wiki_article이 돌려준 정규 제목",
                },
                "index": {"type": "string", "description": "목차에 적힌 절 번호"},
            },
            "required": ["title", "index"],
        },
    ),
)


class ResultVerificationInteractor(ResultVerificationUseCase):
    """`sleep`·`monotonic`은 테스트가 갈아 끼우는 자리다 — 기본값이 실제 동작이다."""

    def __init__(
        self,
        pending: PendingResultRepository,
        writer: MatchResultWriter,
        tools: GeminiToolUseCase,
        titles: WikiTitlePort,
        articles: WikiArticlePort,
        *,
        model: str | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self._pending = pending
        self._writer = writer
        self._tools = tools
        self._titles = titles
        self._articles = articles
        self._model = model
        self._sleep = sleep or asyncio.sleep
        self._monotonic = monotonic or time.monotonic
        self._last_call_at: float | None = None

    async def list_pending(
        self, *, event_slug: str | None = None
    ) -> tuple[MatchUnderReview, ...]:
        """대상 목록만. `verify`와 **같은 호출**이라 둘이 갈릴 수 없다."""
        return await self._pending.list_pending(event_slug=event_slug)

    async def verify(self, command: VerifyResultsCommand) -> VerificationRun:
        found = await self._pending.list_pending(event_slug=command.event_slug)
        # **이름으로 고른 것이 `limit`보다 앞선다.** 고른 쪽은 사람이 목록을 보고 집은
        # 것이므로 앞에서부터 자르는 규칙을 덮어쓴다. `found`는 **자르기 전 총수**
        # 그대로 둔다 — 고른 하나만 돌렸다는 사실이 "하나밖에 없다"로 읽히면 안 된다.
        if command.match_keys:
            wanted = set(command.match_keys)
            targets = tuple(m for m in found if m.match_key in wanted)
        else:
            targets = found[: max(command.limit, 0)]
        logger.info(
            "[kayfabe.result_agent] 대상 %d건 (전체 %d건) | apply=%s",
            len(targets),
            len(found),
            command.apply,
        )

        results: list[MatchVerification] = []
        for match in targets:
            results.append(await self._verify_one(match, apply=command.apply))

        return VerificationRun(
            matches=tuple(results), applied=command.apply, found=len(found)
        )

    async def _verify_one(
        self, match: MatchUnderReview, *, apply: bool
    ) -> MatchVerification:
        try:
            claim, evidence, calls, model = await self._investigate(match)
        except ToolCallUnavailableError as exc:
            # **한 경기의 장애가 실행을 끝내지 않는다.** 2026-09-28 운영 실측: 넷째
            # 경기에서 503이 나 예외가 `verify`를 뚫고 나갔고, **앞선 세 경기의
            # 작업까지 함께 날아갔다**(보고도 남지 않았다). 배치로 도는 에이전트에서
            # 한 대상의 실패는 그 대상의 보류여야 한다.
            logger.warning(
                "[kayfabe.result_agent] 엔진 장애로 보류 | match=%s | %r",
                match.match_key,
                exc,
            )
            return _to_dto(
                match,
                Verdict(match_key=match.match_key, hold=HoldReason.ENGINE_UNAVAILABLE),
                written=False,
                calls=0,
                model=None,
            )

        verdict = adjudicate(match, claim, evidence)

        written = False
        if verdict.writable and apply:
            written = await self._writer.record_winner(
                event_slug=match.event_slug,
                match_key=match.match_key,
                pick=verdict.pick or "",
                winner_name=verdict.winner_name or "",
            )
            if not written:
                # `list_pending`이 본 경기가 쓰기에서 사라진 것이다. 조용히 넘기지 않는다.
                raise RuntimeError(
                    f"대상 경기가 사라졌습니다: {match.event_slug}/{match.match_key}"
                )

        _log_verdict(match, verdict, written=written, calls=calls)
        return _to_dto(match, verdict, written=written, calls=calls, model=model)

    # ────────────────────────────── 루프 ──────────────────────────────

    async def _investigate(
        self, match: MatchUnderReview
    ) -> tuple[ResultClaim | None, tuple[Evidence, ...], int, str | None]:
        """모델이 멈추라고 할 때까지 도구를 물어다 준다.

        돌려주는 것 넷: 주장(없으면 `None`) · **모델에게 실제로 건넨 본문** ·
        도구 호출 수 · 답한 모델. 두 번째가 인용 검증의 기준이고, 그래서 여기서
        모으는 것이 중요하다 — 나중에 위키에 다시 물어 대조하면 그 사이의 편집이
        정직한 인용을 위조로 만든다.
        """
        prompt = _build_prompt(match, await self._lookup_hint(match))
        exchanges: list[ToolExchange] = []
        evidence: list[Evidence] = []
        calls = 0
        model: str | None = None

        for step in range(MAX_STEPS_PER_MATCH):
            await self._pace()
            result = await self._tools.next_step(
                ToolStepCommand(
                    prompt=prompt,
                    tools=_TOOLS,
                    exchanges=tuple(exchanges),
                    model=self._model,
                )
            )
            model = result.model or model

            if not result.wants_tools:
                return _parse_claim(result.text, match), tuple(evidence), calls, model

            for call in result.calls:
                if calls >= MAX_TOOL_CALLS_PER_MATCH:
                    logger.info(
                        "[kayfabe.result_agent] 도구 호출 상한 | match=%s",
                        match.match_key,
                    )
                    return None, tuple(evidence), calls, model
                calls += 1
                payload, found = await self._run_tool(call)
                if found is not None:
                    evidence.append(found)
                exchanges.append(ToolExchange(call=call, result=payload))

            logger.info(
                "[kayfabe.result_agent] 걸음 %d | match=%s | 누적 호출=%d",
                step + 1,
                match.match_key,
                calls,
            )

        logger.info(
            "[kayfabe.result_agent] 걸음 상한 — 보류 | match=%s", match.match_key
        )
        return None, tuple(evidence), calls, model

    async def _lookup_hint(self, match: MatchUnderReview) -> ArticleHint | None:
        """이 대회의 문서 제목과 목차를 **미리** 찾아 둔다. 모르면 `None`.

        ## 왜 모델에게 찾게 하지 않는가

        우리가 **이미 알기 때문이다.** `wiki_event_titles`는 사람이 전수 실측한 표이고,
        모델이 그것을 다시 알아내려고 쓰는 호출은 전부 낭비다. 그 낭비가 실제로
        사고를 냈다 — `worlds-collide`에서 모델이 `Worlds Collide`(동음이의)와
        `WWE Worlds Collide`(결과 없는 총론)를 거치다 걸음 상한에 걸려 두 경기가
        통째로 보류됐다(2026-09-28 실측, 경기당 6호출).

        여기서 얻는 것은 비용만이 아니다. **하루 한도가 천장이라 호출 수가 곧
        처리 가능한 경기 수다** — 경기당 4~6에서 2로 줄면 하루에 보는 경기가 배 이상
        늘어난다.

        ## 그래도 에이전트다

        줄어든 것은 "문서 이름 맞히기"뿐이다. **어느 절에 결과가 있는지는 여전히
        모델이 고른다** — `Results`·`Event`·`Night 1`로 갈리고 문서마다 다르다.
        첫 절에 이 경기가 없으면 다른 절을 읽는 것도 그대로다. 표가 낡았거나
        `None`이면 `find_wiki_article`로 스스로 찾는 경로도 살아 있다.

        **조회가 실패해도 보류하지 않는다.** 힌트가 없으면 모델이 찾으면 된다.
        """
        title = article_title_for(match.event_slug)
        if not title:
            return None
        sections = await self._articles.sections(title)
        if not sections:
            logger.info(
                "[kayfabe.result_agent] 목차를 못 받아 힌트 없이 간다 | title=%s", title
            )
            return None
        return ArticleHint(title=title, sections=sections)

    async def _pace(self) -> None:
        """앞선 호출과 `MIN_CALL_INTERVAL_SECONDS`만큼 벌린다. 첫 호출은 기다리지 않는다."""
        if self._last_call_at is not None:
            elapsed = self._monotonic() - self._last_call_at
            if elapsed < MIN_CALL_INTERVAL_SECONDS:
                await self._sleep(MIN_CALL_INTERVAL_SECONDS - elapsed)
        self._last_call_at = self._monotonic()

    async def _run_tool(self, call: ToolCall) -> tuple[dict[str, Any], Evidence | None]:
        """도구 하나를 실행한다. **실패를 예외로 올리지 않는다.**

        실패를 적어 돌려주면 모델이 그것을 읽고 다른 이름·다른 절로 다시 시도한다.
        예외로 올리면 그 경기가 통째로 끝나 버려, 고칠 수 있는 실수까지 보류가 된다.
        """
        if call.name == "find_wiki_article":
            return await self._find_article(str(call.arguments.get("name") or "")), None
        if call.name == "read_wiki_section":
            return await self._read_section(
                str(call.arguments.get("title") or ""),
                str(call.arguments.get("index") or ""),
            )
        logger.warning("[kayfabe.result_agent] 모르는 도구 | name=%s", call.name)
        return {"error": f"그런 도구는 없습니다: {call.name}"}, None

    async def _find_article(self, name: str) -> dict[str, Any]:
        if not name.strip():
            return {"error": "문서 이름이 비어 있습니다."}

        resolved = await self._titles.resolve([name])
        if resolved is None:
            return {"error": "위키 조회가 실패했습니다. 잠시 뒤 다시 시도하세요."}

        title = resolved.get(name)
        if title is None or title.canonical is None:
            return {"status": "missing", "message": f"`{name}` 문서가 없습니다."}
        if title.is_disambiguation:
            return {
                "status": "disambiguation",
                "message": (
                    f"`{name}`은 동음이의 문서입니다. 더 구체적인 제목으로 부르세요."
                ),
            }

        sections = await self._articles.sections(title.canonical)
        if sections is None:
            return {"error": f"`{title.canonical}`의 목차를 읽지 못했습니다."}

        return {
            "status": "found",
            "title": title.canonical,
            "sections": [
                {"index": section.index, "line": section.line} for section in sections
            ],
        }

    async def _read_section(
        self, title: str, index: str
    ) -> tuple[dict[str, Any], Evidence | None]:
        if not title.strip() or not index.strip():
            return {"error": "title과 index가 모두 필요합니다."}, None

        section = await self._articles.read_section(title, index)
        if section is None:
            return {"error": f"`{title}`의 {index}번 절을 읽지 못했습니다."}, None

        text = section.text
        truncated = len(text) > MAX_SECTION_CHARS
        if truncated:
            text = text[:MAX_SECTION_CHARS]

        # **모델에게 건넨 것과 똑같은 문자열을 증거로 남긴다.** 자른 뒤의 값이어야
        # 한다 — 자르기 전 본문으로 대조하면 우리가 보여 주지도 않은 구절을 인용한
        # 주장이 통과한다.
        evidence = Evidence(
            text=text,
            source_title=section.title,
            revision_id=section.revision_id,
        )
        payload: dict[str, Any] = {
            "title": section.title,
            "section": section.line or index,
            "text": text,
        }
        if truncated:
            payload["truncated"] = f"본문이 길어 앞 {MAX_SECTION_CHARS}자만 보냈습니다."
        return payload, evidence


# ────────────────────────────── 프롬프트·판독 ──────────────────────────────


def _build_prompt(match: MatchUnderReview, hint: ArticleHint | None) -> str:
    options = "\n".join(f"- {option.name}" for option in match.options)
    return (
        f"{_PERSONA}\n\n"
        f"[대회]\n{match.event_label}\n\n"
        f"[경기]\n{match.title}\n\n"
        f"[선택지]\n{options}\n\n"
        f"{_hint_block(hint)}"
        f"{_INSTRUCTIONS if hint is None else _INSTRUCTIONS_WITH_HINT}"
    )


def _hint_block(hint: ArticleHint | None) -> str:
    """알고 있는 문서와 목차를 적어 준다. 모르면 빈 문자열."""
    if hint is None:
        return ""
    lines = "\n".join(f"- {section.index}: {section.line}" for section in hint.sections)
    return f"[문서]\n{hint.title}\n\n[목차]\n{lines}\n\n"


def _parse_claim(text: str, match: MatchUnderReview) -> ResultClaim | None:
    """마지막 글에서 JSON을 꺼낸다. 못 읽으면 `None` — 보류가 된다.

    코드블록을 두른 응답까지는 받아 준다(`gemini_agent_support._parse`와 같은 관용).
    그 이상은 파손으로 보고, **0.5나 빈 이름을 만들어 채우지 않는다.**
    """
    body = text.strip()
    if body.startswith("```"):
        body = body.split("```")[1] if "```" in body[3:] else body[3:]
        body = body.removeprefix("json").strip()

    start, end = body.find("{"), body.rfind("}")
    if start == -1 or end <= start:
        logger.warning("[kayfabe.result_agent] JSON 아님 | match=%s", match.match_key)
        return None

    try:
        payload = json.loads(body[start : end + 1])
    except json.JSONDecodeError as exc:
        logger.warning(
            "[kayfabe.result_agent] JSON 판독 실패 | match=%s | %r",
            match.match_key,
            exc,
        )
        return None

    if not isinstance(payload, dict):
        return None

    raw_name = payload.get("winner_name")
    name = str(raw_name).strip() if raw_name is not None else ""
    return ResultClaim(
        winner_name=name or None,
        quote=str(payload.get("quote") or ""),
    )


def _log_verdict(
    match: MatchUnderReview, verdict: Verdict, *, written: bool, calls: int
) -> None:
    if verdict.writable:
        logger.info(
            "[kayfabe.result_agent] %s | %s -> %s (%s) | 기록=%s | 호출=%d | 출처=%s@%s",
            match.event_slug,
            match.match_key,
            verdict.pick,
            verdict.winner_name,
            "예" if written else "드라이런",
            calls,
            verdict.source_title,
            verdict.source_revision_id or "판본미상",
        )
        return
    logger.info(
        "[kayfabe.result_agent] %s | %s 보류(%s) | 호출=%d",
        match.event_slug,
        match.match_key,
        verdict.hold or HoldReason.NO_CLAIM,
        calls,
    )


def _to_dto(
    match: MatchUnderReview,
    verdict: Verdict,
    *,
    written: bool,
    calls: int,
    model: str | None,
) -> MatchVerification:
    return MatchVerification(
        event_slug=match.event_slug,
        match_key=match.match_key,
        title=match.title,
        pick=verdict.pick,
        winner_name=verdict.winner_name,
        hold=verdict.hold,
        written=written,
        quote=verdict.quote,
        source_title=verdict.source_title,
        source_revision_id=verdict.source_revision_id,
        tool_calls=calls,
        model=model,
    )
