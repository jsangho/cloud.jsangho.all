from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

from fastapi import HTTPException

logger = logging.getLogger("uvicorn.error")

_TEXT_PLAIN = "text/plain; charset=utf-8"

# 업스트림(LLM)이 과부하·레이트리밋이면 503 을 그대로 되돌려 "잠시 후 재시도"임을
# 클라이언트가 구분할 수 있게 한다. 나머지 실패는 게이트웨이 오류(502)로 묶는다.
_RETRYABLE_UPSTREAM_STATUS = frozenset({408, 429, 500, 502, 503, 504})

EMPTY_UPSTREAM_DETAIL = "모델이 빈 응답을 반환했습니다. 잠시 후 다시 시도해 주세요."
UPSTREAM_FAILED_DETAIL = "모델 응답 생성에 실패했습니다. 잠시 후 다시 시도해 주세요."
MID_STREAM_NOTICE = "\n\n⚠️ 답변 생성이 도중에 끊겼습니다. 다시 시도해 주세요."


def _upstream_status(exc: BaseException) -> int | None:
    """예외에서 업스트림 HTTP 상태 코드를 꺼낸다.

    google-genai(`APIError.code`)와 httpx(`HTTPStatusError.response.status_code`)를
    덕 타이핑으로 함께 다룬다 — 공유 커널이 특정 SDK에 의존하지 않기 위해서다.
    """
    code = getattr(exc, "code", None)
    if not isinstance(code, int):
        code = getattr(getattr(exc, "response", None), "status_code", None)
    return code if isinstance(code, int) else None


async def open_guarded_text_stream(
    source: AsyncIterator[str], *, label: str
) -> StreamingResponse:
    """첫 청크를 확인한 뒤에 `StreamingResponse` 를 만든다.

    `StreamingResponse` 는 헤더를 먼저 내보내므로 생성기 안에서 터진 예외는 상태
    코드로 바꿀 수 없고, 결과적으로 HTTP 200 + 빈 본문이 조용히 나간다. 첫 청크까지를
    라우터 안에서 끌어와 그 구간의 실패는 502/503 으로 올리고, 스트림이 시작된 뒤의
    실패는 본문에 안내 문구로 흘려보낸다.

    호출 측은 `await` 로 받는다 — 첫 청크를 받기 전에는 응답이 시작되지 않는다.
    """
    try:
        first = await anext(source)
    except StopAsyncIteration:
        logger.error("[%s] 업스트림이 아무 청크도 내보내지 않았다", label)
        raise HTTPException(status_code=502, detail=EMPTY_UPSTREAM_DETAIL) from None
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        status = _upstream_status(exc)
        logger.exception("[%s] 스트림 시작 실패 | upstream_status=%s", label, status)
        raise HTTPException(
            status_code=503 if status in _RETRYABLE_UPSTREAM_STATUS else 502,
            detail=UPSTREAM_FAILED_DETAIL,
        ) from exc

    return StreamingResponse(_relay(first, source, label), media_type=_TEXT_PLAIN)


async def _relay(
    first: str, source: AsyncIterator[str], label: str
) -> AsyncIterator[str]:
    yield first
    try:
        async for chunk in source:
            yield chunk
    except asyncio.CancelledError:
        # 클라이언트가 연결을 끊은 경우 — 오류가 아니므로 그대로 전파한다.
        raise
    except Exception:
        logger.exception("[%s] 스트림 도중 실패 — 본문에 안내 문구를 덧붙인다", label)
        yield MID_STREAM_NOTICE
