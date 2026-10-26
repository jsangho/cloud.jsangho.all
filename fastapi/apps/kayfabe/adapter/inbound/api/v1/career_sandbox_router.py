"""커리어 샌드박스 API. **로그인이 필요하다 — 세이브가 사용자 소유다.**

## 무상태 장난감과 갈라 둔다

`/sandbox/career/step` 은 그대로 남는다 — 로그인 없이 상태를 들고 와서 한 주를
돌려보는 장난감이고, 서버가 아무것도 저장하지 않는다. 이쪽(`/sandbox/careers`)은
세이브가 있고 소유자가 있다. 경로가 그 구별의 절반이다.

## 사용자 식별은 토큰에서만 얻는다

본문·쿼리의 `userId` 를 신뢰하면 남의 커리어를 연다. `shop_router` 가 같은 규칙을
적어 뒀다.

## 상태 코드가 실패 사유를 가른다

    404  없는 커리어 **또는 남의 커리어** — 구별해 주지 않는다(id 존재 누출)
    409  단계가 맞지 않다 (52주를 다 썼는데 주차 진행, 결산 전에 다음 시즌 등)
         **또는** 요청 키를 다른 요청에 다시 썼다
    422  입력이 틀리다 (없는 행동·선택지, 포인트 소진, 요청 키 형식 오류)

409 와 422 를 가르는 것은 화면이 "결산 버튼을 보여라" 와 "입력을 고쳐라" 를
구별해야 하기 때문이다.

**요청 키 충돌을 문구로 가르지 않는다.** 단계 오류는 도메인의 `ValueError` 문구를
훑어 409 로 가르는데(`_PHASE_HINTS`), 키 충돌은 전용 예외(`RequestKeyConflictError`)로
올라와 문구를 보지 않고 갈린다 — 문구 대조에 항목을 더하면 도메인 문장을 고칠 때
조용히 분기가 바뀐다.

## 쓰기에는 `Idempotency-Key` 헤더가 **필요하다**

헤더를 고른 이유는 둘이다.

1. **쓰기 다섯 중 셋은 본문이 없다**(`/advance` · `/settle` · `/next-season`).
   본문 칸으로 하면 그 셋에 요청 스키마를 새로 만들어야 하고, 계약이 그만큼 더
   움직인다.
2. **키는 게임 입력이 아니다.** 본문에 섞으면 payload 지문을 계산할 때 키 자신을
   빼야 하는데(키가 자기 지문에 들어가면 늘 달라진다) 조용히 틀리기 쉽다. 헤더는
   그 둘을 구조적으로 갈라 둔다.

CORS 는 이미 `allow_headers=["*"]` 라 새 헤더로 막히지 않는다(`main.py`).

**필수로 둔다.** 기본값을 주면 키를 안 보내는 클라이언트가 **보호 없이 조용히**
돌아가고, 그게 지금 고치는 결함이다. 키를 빼먹은 요청은 422 로 막힌다.

## 중복 판정의 유효 범위는 커리어당 최근 8건이다

영수증 보존 상한이 `RECEIPT_KEEP`(=8)이므로(`sandbox_career_repository`), 같은
커리어에 쓰기가 **여덟 번 더 성공한 뒤** 도착한 재시도는 영수증이 이미 잘려 나가
새 요청으로 적용된다. 재시도 창은 요청 하나(타임아웃 수십 초)이고 그 사이 같은
커리어로 여덟 번 더 쓰는 경로가 없어 감수한 트레이드오프다 — **계약의 일부이므로**
헤더 설명에도 적어 OpenAPI 로 내보낸다. 적용 절차·실측 크기는
`fastapi/_docs/sandbox-career-migration.md` §7.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from kayfabe.adapter.inbound.api.schemas.career_sandbox_schema import (
    REQUEST_KEY_MAX,
    REQUEST_KEY_MIN,
    REQUEST_KEY_PATTERN,
    ActionRequest,
    CareerSummarySchema,
    CareerViewSchema,
    CreateCareerRequest,
    LogSchema,
    ResolveRequest,
)
from kayfabe.app.ports.input.career_sandbox_use_case import (
    CareerSandboxUseCase,
    RequestKeyConflictError,
)
from kayfabe.app.ports.output.sandbox_career_repository import CorruptSaveError
from kayfabe.dependencies.career_sandbox_provider import get_career_use_case
from kayfabe.domain.services.career_events import EventNotFoundError

logger = logging.getLogger("uvicorn.error")

career_sandbox_router = APIRouter(prefix="/sandbox/careers", tags=["sandbox-career"])

#: 단계가 맞지 않을 때 도메인이 내는 말머리. 409 로 가른다.
_PHASE_HINTS = ("단계가 아닙니다", "결산이 먼저", "다음 시즌을 시작할 수 없습니다")

#: 쓰기 요청의 멱등 키. **클라이언트가 만든다** — 한 번의 사용자 의도에 하나이고,
#: 응답을 못 받아 다시 보낼 때는 **같은 값**을 쓴다. 새 행동에는 새 값을 쓴다.
RequestKey = Header(
    alias="Idempotency-Key",
    min_length=REQUEST_KEY_MIN,
    max_length=REQUEST_KEY_MAX,
    pattern=REQUEST_KEY_PATTERN,
    description=(
        "한 번의 사용자 의도에 하나. 재전송은 같은 값, 새 행동은 새 값. "
        "같은 값에 다른 내용이면 409. "
        "중복 판정은 커리어당 최근 8건까지만 보장된다 — 같은 커리어에 쓰기가 "
        "8번 더 성공한 뒤 도착한 재시도는 새 요청으로 적용된다."
    ),
)


def _user_id(claims: TokenPayload) -> int:
    try:
        return int(claims.sub)
    except (TypeError, ValueError) as e:
        raise HTTPException(
            status_code=401, detail="토큰의 회원 정보가 올바르지 않습니다."
        ) from e


def _error(exc: Exception) -> HTTPException:
    """도메인 예외를 상태 코드로. **모르는 예외는 다시 던진다.**

    전부 400 으로 뭉개면 화면이 사유를 구별할 수 없고, 전부 삼키면 버그가
    "잘못된 요청" 으로 보고된다.

    **순서가 규칙이다.** `CorruptSaveError` 는 `ValueError` 의 하위라서 아래
    422 분기보다 먼저 와야 한다 — 뒤에 두면 저장된 세이브를 못 읽는 것이
    "입력을 고쳐라" 로 나간다(2026-10-26 실측: 422).
    """
    if isinstance(exc, CorruptSaveError):
        # 서버가 들고 있는 데이터를 못 읽는다. 클라이언트가 할 수 있는 일이
        # 없으므로 4xx 가 아니다. **사유는 로그에만 남긴다** — 판본 번호도
        # 빠진 칸 이름도 내부 사정이다.
        logger.error("[CareerRouter] 세이브를 되살릴 수 없다: %s", exc)
        return HTTPException(status_code=500, detail="세이브를 읽을 수 없습니다")
    if isinstance(exc, RequestKeyConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, KeyError):
        # **`KeyError` 는 "커리어가 없다" 가 아니다.** `LookupError` 의 하위라서
        # 아래 404 분기에 걸리는데, 이 유스케이스에서 `KeyError` 를 내는 곳은
        # 저장된 세계가 자기모순일 때(`WorldState.require` — 로스터에 없는 이름을
        # 가리킨다)뿐이다. 2026-10-26 실측으로 `/advance` 가
        # `404 detail="'로스터에 없는 선수: Nobody'"` 를 냈다 — 상태 코드가 틀렸고
        # 세이브 내용이 함께 새어 나갔다.
        #
        # 정상적인 "없는 사건" 은 `EventNotFoundError` 라는 전용 타입으로 오고
        # `resolve_event` 가 **이 함수를 부르기 전에** 가로챈다. 그쪽 404 는
        # 영향받지 않는다 — 그 타입이 `KeyError` 의 하위이므로 순서가 아니라
        # **타입**이 둘을 가른다.
        raise exc
    if isinstance(exc, LookupError):
        return HTTPException(
            status_code=404, detail=str(exc) or "커리어를 찾을 수 없습니다"
        )
    if isinstance(exc, ValueError):
        message = str(exc)
        if any(hint in message for hint in _PHASE_HINTS):
            return HTTPException(status_code=409, detail=message)
        return HTTPException(status_code=422, detail=message)
    raise exc


@career_sandbox_router.post(
    "", response_model=CareerViewSchema, response_model_by_alias=True
)
async def create_career(
    body: CreateCareerRequest,
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerSandboxUseCase = Depends(get_career_use_case),
):
    """새 커리어. 52주 시즌 1 의 1주차에서 시작한다."""
    user_id = _user_id(claims)
    logger.info("[CareerRouter] create user=%d name=%s", user_id, body.name)
    try:
        return await use_case.create(
            user_id=user_id,
            name=body.name,
            style=body.style,
            age=body.age,
            seed=body.seed,
        )
    except (LookupError, ValueError) as e:
        raise _error(e) from e


@career_sandbox_router.get(
    "", response_model=list[CareerSummarySchema], response_model_by_alias=True
)
async def list_careers(
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerSandboxUseCase = Depends(get_career_use_case),
):
    """내 커리어 목록. **남의 것은 들어오지 않는다.**"""
    return await use_case.list_careers(_user_id(claims))


@career_sandbox_router.get(
    "/{career_id}", response_model=CareerViewSchema, response_model_by_alias=True
)
async def get_career(
    career_id: int,
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerSandboxUseCase = Depends(get_career_use_case),
):
    """현재 상태. **재접속 복구가 이 호출 하나다.**

    **세이브를 못 읽는 경우를 잡는다.** 전에는 `try` 가 없어 `CorruptSaveError`
    가 그대로 올라가 500 `"Internal Server Error"` 로 나갔고, 같은 원인에 대해
    `/log` 와 쓰기 경로는 다른 코드를 냈다 — 한 가지 사실에 상태 코드가 셋이었다.
    """
    try:
        view = await use_case.view(user_id=_user_id(claims), career_id=career_id)
    except CorruptSaveError as e:
        raise _error(e) from e
    if view is None:
        raise HTTPException(status_code=404, detail="커리어를 찾을 수 없습니다")
    return view


@career_sandbox_router.post(
    "/{career_id}/actions",
    response_model=CareerViewSchema,
    response_model_by_alias=True,
)
async def perform_action(
    career_id: int,
    body: ActionRequest,
    request_key: str = RequestKey,
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerSandboxUseCase = Depends(get_career_use_case),
):
    """주간 행동 하나. **효과는 서버가 정한다** — 프론트가 능력치를 보내지 않는다.

    같은 `Idempotency-Key` 로 다시 오면 **한 번만 적용되고** 최초 응답이 그대로
    돌아온다. 같은 키에 다른 행동이면 409.
    """
    try:
        outcome = await use_case.act(
            user_id=_user_id(claims),
            career_id=career_id,
            action=body.action,
            target=body.target,
            request_id=request_key,
        )
    except (RequestKeyConflictError, LookupError, ValueError) as e:
        raise _error(e) from e
    return outcome.body


@career_sandbox_router.post(
    "/{career_id}/advance",
    response_model=CareerViewSchema,
    response_model_by_alias=True,
)
async def advance_week(
    career_id: int,
    request_key: str = RequestKey,
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerSandboxUseCase = Depends(get_career_use_case),
):
    """한 주 진행.

    **같은 `Idempotency-Key` 는 한 주만 진행한다.** 전에는 저장이 끝난 뒤의
    재시도가 **다음 주**를 진행했다 — 도메인의 주차 키는 이미 넘어간 주차를
    가리키므로 재시도를 막지 못한다. 요청 키가 그 빈칸을 메우고, 재시도는 최초
    응답(그 주의 보고 포함)을 그대로 받는다.
    """
    try:
        outcome = await use_case.advance(
            user_id=_user_id(claims), career_id=career_id, request_id=request_key
        )
    except (RequestKeyConflictError, LookupError, ValueError) as e:
        raise _error(e) from e
    return outcome.body


@career_sandbox_router.post(
    "/{career_id}/events/{event_id}",
    response_model=CareerViewSchema,
    response_model_by_alias=True,
)
async def resolve_event(
    career_id: int,
    event_id: str,
    body: ResolveRequest,
    request_key: str = RequestKey,
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerSandboxUseCase = Depends(get_career_use_case),
):
    """사건 해결. **같은 사건의 보상이 두 번 적용되지 않는다.**

    **`EventNotFoundError` 만 404 다.** 전에는 `except KeyError` 로 받았는데,
    도메인은 세이브가 자기모순일 때도 평범한 `KeyError` 를 낸다
    (`_apply_choice` → `WorldState.require`). 그래서 `subject` 가 로스터에 없는
    보류 사건이 **"없는 사건입니다"** 로 보고됐다(2026-10-26 실측). 전용 타입만
    잡으면 그 고장은 아래 절을 거쳐 `_error` 의 `KeyError` 가드로 가고 일반
    500 이 된다.
    """
    try:
        outcome = await use_case.resolve(
            user_id=_user_id(claims),
            career_id=career_id,
            event_id=event_id,
            choice=body.choice,
            request_id=request_key,
        )
    # **순서가 계약이다.** `EventNotFoundError` 는 `KeyError` 를 거쳐
    # `LookupError` 의 하위 타입이다. 그래서 이 전용 404 절은 아래 광범위한
    # `LookupError` 절보다 **반드시 먼저** 있어야 한다 — 순서를 바꾸면 정상적인
    # "없는 사건" 요청이 일반 오류 처리로 흘러 기존 404 계약이 깨진다.
    except EventNotFoundError as e:
        raise HTTPException(
            status_code=404, detail=f"없는 사건입니다: {event_id}"
        ) from e
    except (RequestKeyConflictError, LookupError, ValueError) as e:
        raise _error(e) from e
    return outcome.body


@career_sandbox_router.post(
    "/{career_id}/settle", response_model=CareerViewSchema, response_model_by_alias=True
)
async def settle_season(
    career_id: int,
    request_key: str = RequestKey,
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerSandboxUseCase = Depends(get_career_use_case),
):
    """시즌 결산. **나이가 여기서만 오르고 한 번만 오른다.**"""
    try:
        outcome = await use_case.settle(
            user_id=_user_id(claims), career_id=career_id, request_id=request_key
        )
    except (RequestKeyConflictError, LookupError, ValueError) as e:
        raise _error(e) from e
    return outcome.body


@career_sandbox_router.post(
    "/{career_id}/next-season",
    response_model=CareerViewSchema,
    response_model_by_alias=True,
)
async def start_next_season(
    career_id: int,
    request_key: str = RequestKey,
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerSandboxUseCase = Depends(get_career_use_case),
):
    """다음 시즌 시작. 주차만 1로 돌아가고 나머지는 전부 보존된다."""
    try:
        outcome = await use_case.next_season(
            user_id=_user_id(claims), career_id=career_id, request_id=request_key
        )
    except (RequestKeyConflictError, LookupError, ValueError) as e:
        raise _error(e) from e
    return outcome.body


@career_sandbox_router.get(
    "/{career_id}/log", response_model=list[LogSchema], response_model_by_alias=True
)
async def read_log(
    career_id: int,
    season: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerSandboxUseCase = Depends(get_career_use_case),
):
    """커리어 기록. 최근 것부터, 페이지로 끊어서."""
    try:
        return await use_case.log(
            user_id=_user_id(claims),
            career_id=career_id,
            season=season,
            limit=limit,
            offset=offset,
        )
    except (LookupError, ValueError) as e:
        raise _error(e) from e
