"""커리어 시뮬레이터 라우터 (하네스 §7·T10).

**예외 → 상태 코드 변환이 여기서만 일어난다**(§8). 도메인과 유스케이스는
`HTTPException`을 만들지 않는다(§4-7) — 전용 `AppError` 계층도 두지 않는다는 저장소
규약(fastapi/CLAUDE.md)과 맞물려, 변환표 하나를 이 파일에 둔다.

`detail`에는 **내부 수치를 담지 않는다**(§8 원칙). 확률·주사위·임계값이 문구로 새면
그것만으로 최적해가 드러난다.
"""

from __future__ import annotations

from collections.abc import Callable

from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from wwe_game.adapter.inbound.api.schemas.career_schema import (
    AdvanceRequest,
    AdvanceResponse,
    CallOutRequest,
    ChoiceRequest,
    FinisherRequest,
    GoalRequest,
    GuestAdvanceRequest,
    GuestAdvanceResponse,
    GuestCallOutRequest,
    GuestChoiceRequest,
    GuestFinisherRequest,
    GuestGoalRequest,
    GuestOfferRequest,
    GuestReportRequest,
    GuestResumeRequest,
    GuestStartRequest,
    LogPageSchema,
    ModeSchema,
    NewsPageSchema,
    OfferRequest,
    PresetSchema,
    ShowReportSchema,
    StartRunRequest,
    title_of_display,
    to_advance,
    to_guest,
    to_log,
    to_mode,
    to_news,
    to_preset,
    to_report,
)
from wwe_game.adapter.inbound.api.schemas.guest_schema import (
    GuestRunState,
    to_domain,
)
from wwe_game.app.dtos.career_dto import (
    AdvanceCommand,
    AnswerOfferCommand,
    CallOutCommand,
    CashInCommand,
    ChangeFinisherCommand,
    ChooseCommand,
    GuestAdvanceCommand,
    GuestAnswerOfferCommand,
    GuestCallOutCommand,
    GuestCashInCommand,
    GuestChangeFinisherCommand,
    GuestChooseCommand,
    GuestReportCommand,
    GuestResumeCommand,
    GuestSetGoalCommand,
    GuestStartCommand,
    SetGoalCommand,
    StartRunCommand,
)
from wwe_game.app.ports.input.career_use_case import (
    CareerUseCase,
    ChoiceRequiredError,
    GuestModeNotAllowedError,
    NoPendingEventError,
    ReportNotFoundError,
    RunAlreadyActiveError,
)
from wwe_game.app.ports.output.career_repository import RunNotFoundError
from wwe_game.dependencies.career_provider import get_career_use_case
from wwe_game.domain.exceptions import (
    CannotCallOutError,
    CannotCashInError,
    CannotChangeFinisherError,
    InvalidCareerRunError,
    InvalidChoiceError,
    InvalidFinisherNameError,
    InvalidRingNameError,
    NoOfferOpenError,
    RunNotActiveError,
    UnknownCountryError,
    UnknownGameModeError,
)
from wwe_game.domain.value_objects.advance_outcome import StepMode
from wwe_game.domain.value_objects.wrestler_identity import Gender, PlayStyle

from fastapi import APIRouter, Depends, HTTPException, Query, status

career_router = APIRouter(prefix="/career", tags=["career"])

_STATUS: tuple[tuple[type[Exception], int, str | None], ...] = (
    (RunNotFoundError, status.HTTP_404_NOT_FOUND, "커리어를 찾을 수 없습니다."),
    (ReportNotFoundError, status.HTTP_404_NOT_FOUND, "그 주차의 리포트가 없습니다."),
    (
        RunAlreadyActiveError,
        status.HTTP_409_CONFLICT,
        "이미 진행 중인 커리어가 있습니다.",
    ),
    (ChoiceRequiredError, status.HTTP_409_CONFLICT, "먼저 선택을 마쳐야 합니다."),
    (NoPendingEventError, status.HTTP_409_CONFLICT, "선택할 이벤트가 없습니다."),
    (NoOfferOpenError, status.HTTP_409_CONFLICT, "지금은 협상 중이 아닙니다."),
    (CannotCashInError, status.HTTP_409_CONFLICT, "지금은 가방을 쓸 수 없습니다."),
    (CannotCallOutError, status.HTTP_409_CONFLICT, "지금은 시비를 걸 수 없습니다."),
    (
        CannotChangeFinisherError,
        status.HTTP_409_CONFLICT,
        "지금은 피니셔를 바꿀 수 없습니다.",
    ),
    # **문구를 덮지 않는다.** 길이·제어문자 중 무엇이 걸렸는지를 도메인이 짚는다.
    (InvalidFinisherNameError, status.HTTP_400_BAD_REQUEST, None),
    (RunNotActiveError, status.HTTP_409_CONFLICT, "이미 끝난 커리어입니다."),
    (InvalidChoiceError, status.HTTP_400_BAD_REQUEST, "선택할 수 없는 항목입니다."),
    (
        InvalidRingNameError,
        status.HTTP_400_BAD_REQUEST,
        "이름은 2~20자로 입력해 주세요.",
    ),
    (UnknownGameModeError, status.HTTP_400_BAD_REQUEST, "선택할 수 없는 항목입니다."),
    (UnknownCountryError, status.HTTP_400_BAD_REQUEST, "선택할 수 없는 항목입니다."),
    (
        GuestModeNotAllowedError,
        status.HTTP_400_BAD_REQUEST,
        "이 모드는 로그인 후 플레이할 수 있습니다.",
    ),
    # **문구를 덮지 않는다.** 이 예외는 "무엇이 빠졌는지 짚어서 거절한다"는
    # §3-D10-1의 구현이라, 도메인이 만든 문장이 곧 사용자가 읽어야 할 문장이다.
    # 뭉개 놓았더니 생성 실패가 "저장된 진행 상황을 읽을 수 없습니다"로 나와
    # 무엇을 고쳐야 할지 알 수 없었다 (2026-08-10).
    (InvalidCareerRunError, status.HTTP_400_BAD_REQUEST, None),
    (ValueError, status.HTTP_400_BAD_REQUEST, "저장된 진행 상황을 읽을 수 없습니다."),
)
"""§8 매핑표. **위에서부터 먼저 걸리는 것이 이긴다** — 하위 클래스를 앞에 둔다.

`RunNotFoundError`가 404인 것이 §11-12다: 남의 세이브에 접근해도 403이 아니라 404다.
403은 "있지만 네 것이 아니다"를 알려 주므로 존재 여부가 새어 나간다.
"""


async def _guard[T](call: Callable[[], object]) -> T:
    """유스케이스 호출 하나를 감싸 예외를 상태 코드로 옮긴다."""
    try:
        result = call()
        return await result if hasattr(result, "__await__") else result  # type: ignore[return-value,misc]
    except Exception as exc:  # noqa: BLE001 - 아래 표에 없으면 그대로 올린다
        for kind, code, detail in _STATUS:
            if isinstance(exc, kind):
                raise HTTPException(
                    status_code=code, detail=detail or str(exc)
                ) from exc
        raise


def _sync[T](call: Callable[[], T]) -> T:
    """동기 유스케이스용 `_guard`. 체험판은 읽고 쓸 저장소가 없어 `await`할 것이 없다."""
    try:
        return call()
    except Exception as exc:  # noqa: BLE001 - 표에 없으면 그대로 올린다
        for kind, code, detail in _STATUS:
            if isinstance(exc, kind):
                raise HTTPException(
                    status_code=code, detail=detail or str(exc)
                ) from exc
        raise


def _enum[T](kind: type[T], raw: str | None, field: str) -> T | None:
    if raw is None:
        return None
    try:
        return kind(raw)  # type: ignore[call-arg]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="선택할 수 없는 항목입니다.",
        ) from exc


def _user_id(claims: TokenPayload) -> int:
    return int(claims.sub)


# ── 메타 (인증 불필요) ───────────────────────────────────────


@career_router.get("/modes", response_model=list[ModeSchema])
def read_modes(
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> list[ModeSchema]:
    """모드 4종. **`guestAllowed`가 체험판 허용의 판정 근거다**(§3-D8)."""
    return [to_mode(m) for m in use_case.modes()]


@career_router.get("/presets", response_model=list[PresetSchema])
def read_presets(
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> list[PresetSchema]:
    """ "○○를 바탕으로" 목록 (§3-D10-1). **이름은 물려주지 않는다.**"""
    return [to_preset(p) for p in use_case.presets()]


# ── 로그인 플레이 ────────────────────────────────────────────


@career_router.post(
    "/runs", response_model=AdvanceResponse, status_code=status.HTTP_201_CREATED
)
async def start_run(
    body: StartRunRequest,
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> AdvanceResponse:
    command = StartRunCommand(
        user_id=_user_id(claims),
        name=body.name,
        mode_code=body.mode,
        based_on=body.based_on,
        gender=_enum(Gender, body.gender, "gender"),
        country_code=body.country,
        play_style=_enum(PlayStyle, body.play_style, "playStyle"),
    )
    return to_advance(await _guard(lambda: use_case.start(command)))


@career_router.get("/runs/current", response_model=AdvanceResponse | None)
async def read_current(
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> AdvanceResponse | None:
    """진행 중인 세이브. **없으면 null이지 404가 아니다** — 아직 안 만든 상태는 정상이다."""
    result = await _guard(lambda: use_case.current(_user_id(claims)))
    return to_advance(result) if result is not None else None


@career_router.post("/runs/{run_id}/advance", response_model=AdvanceResponse)
async def advance(
    run_id: int,
    body: AdvanceRequest,
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> AdvanceResponse:
    """'다음'. 대기 이벤트가 있으면 **409로 막힌다**(§11-2)."""
    command = AdvanceCommand(
        run_id=run_id,
        user_id=_user_id(claims),
        step=_enum(StepMode, body.step, "step") or StepMode.AUTO,
    )
    return to_advance(await _guard(lambda: use_case.advance(command)))


@career_router.post("/runs/{run_id}/choices", response_model=AdvanceResponse)
async def choose(
    run_id: int,
    body: ChoiceRequest,
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> AdvanceResponse:
    command = ChooseCommand(
        run_id=run_id, user_id=_user_id(claims), choice_code=body.choice
    )
    return to_advance(await _guard(lambda: use_case.choose(command)))


@career_router.post("/runs/{run_id}/goal", response_model=AdvanceResponse)
async def set_goal(
    run_id: int,
    body: GoalRequest,
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> AdvanceResponse:
    """이번 분기에 걸 것을 정한다 (§3-D80).

    **`choices`와 따로 둔다.** 이벤트 응답과 목표 선언은 성격이 반대라(반응 대 선언)
    한 엔드포인트로 합치면 그 구분이 URL에서 사라진다.
    """
    command = SetGoalCommand(
        run_id=run_id, user_id=_user_id(claims), goal_code=body.goal
    )
    return to_advance(await _guard(lambda: use_case.set_goal(command)))


@career_router.post("/runs/{run_id}/offer", response_model=AdvanceResponse)
async def answer_offer(
    run_id: int,
    body: OfferRequest,
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> AdvanceResponse:
    """재계약 협상에 답한다 (§3-D84).

    `/goal`과 나란한 자리다 — 둘 다 **먼저 정하는 것**이고, 답하기 전에는 진행이
    막힌다. 협상 중이 아닌데 부르면 409다.
    """
    command = AnswerOfferCommand(
        run_id=run_id, user_id=_user_id(claims), offer_code=body.offer
    )
    return to_advance(await _guard(lambda: use_case.answer_offer(command)))


@career_router.post("/runs/{run_id}/cash-in", response_model=AdvanceResponse)
async def cash_in(
    run_id: int,
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> AdvanceResponse:
    """가방을 쓰기로 한다 (§3-D85).

    **본문이 없다.** 고를 선택지가 아니라 "지금 한다"는 사실 하나뿐이라, 목표·협상과
    달리 무엇을 골랐는지 실어 보낼 것이 없다.

    **진행을 막고 있던 것이 아니다** — 안 부르고 '다음'을 눌러도 아무 일도 일어나지
    않는다. 쓸 수 없는 상태(없거나 · 이미 정했거나 · 무소속이거나 · 이미 그 벨트를
    감고 있거나)면 409다.
    """
    command = CashInCommand(run_id=run_id, user_id=_user_id(claims))
    return to_advance(await _guard(lambda: use_case.cash_in(command)))


@career_router.post("/runs/{run_id}/call-out", response_model=AdvanceResponse)
async def call_out(
    run_id: int,
    body: CallOutRequest,
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> AdvanceResponse:
    """그 사람에게 시비를 건다 (§3-D86).

    **후보 목록 밖의 이름은 409다.** 급·브랜드 그림이 요청 한 줄로 무너지지 않게
    도메인이 막는다(§3-D53).
    """
    command = CallOutCommand(
        run_id=run_id, user_id=_user_id(claims), rival_name=body.rival
    )
    return to_advance(await _guard(lambda: use_case.call_out(command)))


@career_router.post("/runs/{run_id}/finisher", response_model=AdvanceResponse)
async def change_finisher(
    run_id: int,
    body: FinisherRequest,
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> AdvanceResponse:
    """피니셔를 바꾼다 (§3-D88).

    **두 갈래를 한 엔드포인트로 받는다** — 목록에서 고르면 `code`, 이름을 직접
    지으면 `name`. 어느 쪽인지는 화면이 먼저 묻고 정한다.

    쿨다운 중이면 409, 이름이 규칙에 안 맞으면 400이다.
    """
    command = ChangeFinisherCommand(
        run_id=run_id,
        user_id=_user_id(claims),
        code=body.code,
        name=body.name,
        hold=body.hold,
    )
    return to_advance(await _guard(lambda: use_case.change_finisher(command)))


@career_router.get("/runs/{run_id}/report", response_model=ShowReportSchema)
async def read_report(
    run_id: int,
    week: int = Query(..., ge=1),
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> ShowReportSchema:
    """그 밤의 리포트 (§3-D45). **대회 주차만** — 주간 방송까지 열면 로그와 같아진다."""
    report = await _guard(lambda: use_case.read_report(run_id, _user_id(claims), week))
    return to_report(report)


@career_router.get("/runs/{run_id}/log", response_model=LogPageSchema)
async def read_log(
    run_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> LogPageSchema:
    """커리어 로그. **30년이면 1560줄이라 전부 내려보내지 않는다.**"""
    page = await _guard(
        lambda: use_case.read_log(run_id, _user_id(claims), offset=offset, limit=limit)
    )
    return to_log(page)


@career_router.get("/runs/{run_id}/news", response_model=NewsPageSchema)
async def read_news(
    run_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> NewsPageSchema:
    """내 세계선의 뉴스 — 사건과 **군중 반응** (§3-D31).

    로그와 다른 엔드포인트인 이유는 담는 것이 달라서다. 로그가 1560줄일 때 뉴스는
    70줄 남짓이고, 팀 세계의 소식이 함께 들어온다(§3-D30).
    """
    page = await _guard(
        lambda: use_case.read_news(run_id, _user_id(claims), offset=offset, limit=limit)
    )
    return to_news(page)


@career_router.delete("/runs/{run_id}", response_model=AdvanceResponse)
async def retire(
    run_id: int,
    claims: TokenPayload = Depends(get_current_user),
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> AdvanceResponse:
    """스스로 커리어를 닫는다 — 은퇴 조건 중 하나다(§3-D16)."""
    return to_advance(await _guard(lambda: use_case.retire(run_id, _user_id(claims))))


# ── 체험판 (§3-D8 · 인증 불필요) ─────────────────────────────


def _restore(state: GuestRunState) -> object:
    """받은 세이브를 도메인으로 되살린다. **어긴 값은 여기서 400이 된다**(§11-26).

    라우터가 직접 감싸는 이유: `_guard`는 유스케이스 호출 하나를 감싸는데, 복원은 그
    앞에서 일어난다. 조작된 상태는 유스케이스에 닿기 전에 걸러야 한다.
    """
    try:
        return to_domain(state)
    except Exception as exc:  # noqa: BLE001 - 값 객체가 던지는 것은 전부 400이다
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="저장된 진행 상황을 읽을 수 없습니다.",
        ) from exc


@career_router.post(
    "/guest/runs",
    response_model=GuestAdvanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_guest(
    body: GuestStartRequest,
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> GuestAdvanceResponse:
    """체험판 시작. **`monthly`·`weekly`는 400이다**(§11-24).

    두 모드는 틱이 390·1560개라 상태가 브라우저에 안 들어간다.
    """
    command = GuestStartCommand(
        name=body.name,
        mode_code=body.mode,
        based_on=body.based_on,
        gender=_enum(Gender, body.gender, "gender"),
        country_code=body.country,
        play_style=_enum(PlayStyle, body.play_style, "playStyle"),
        seed=body.seed,
    )
    return to_guest(_sync(lambda: use_case.start_guest(command)))


@career_router.post("/guest/advance", response_model=GuestAdvanceResponse)
def advance_guest(
    body: GuestAdvanceRequest,
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> GuestAdvanceResponse:
    """받은 세이브를 진행시켜 **다음 상태를 통째로** 돌려준다. 저장하지 않는다."""
    command = GuestAdvanceCommand(
        run=_restore(body.state),  # type: ignore[arg-type]
        step=_enum(StepMode, body.step, "step") or StepMode.AUTO,
    )
    return to_guest(_sync(lambda: use_case.advance_guest(command)))


@career_router.post("/guest/resume", response_model=GuestAdvanceResponse)
def resume_guest(
    body: GuestResumeRequest,
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> GuestAdvanceResponse:
    """다시 열었을 때의 화면 상태. **진행하지 않는다** — 로그인 쪽 `/runs/current`의 짝이다.

    `POST`인 이유는 세이브가 본문에 실려서다. 조회이지만 URL에 담을 크기가 아니다.

    대기 이벤트가 있어도 **409가 아니다.** 여기서 막으면 답할 화면 자체가 안 뜬다.
    """
    command = GuestResumeCommand(run=_restore(body.state))  # type: ignore[arg-type]
    return to_guest(_sync(lambda: use_case.resume_guest(command)))


@career_router.post("/guest/choices", response_model=GuestAdvanceResponse)
def choose_guest(
    body: GuestChoiceRequest,
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> GuestAdvanceResponse:
    command = GuestChooseCommand(
        run=_restore(body.state),  # type: ignore[arg-type]
        choice_code=body.choice,
    )
    return to_guest(_sync(lambda: use_case.choose_guest(command)))


@career_router.post("/guest/goal", response_model=GuestAdvanceResponse)
def set_guest_goal(
    body: GuestGoalRequest,
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> GuestAdvanceResponse:
    """체험판의 분기 목표 (§3-D80). 없으면 콜업 뒤 체험판이 통째로 막힌다."""
    command = GuestSetGoalCommand(
        run=_restore(body.state),  # type: ignore[arg-type]
        goal_code=body.goal,
    )
    return to_guest(_sync(lambda: use_case.set_guest_goal(command)))


@career_router.post("/guest/offer", response_model=GuestAdvanceResponse)
def answer_guest_offer(
    body: GuestOfferRequest,
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> GuestAdvanceResponse:
    """체험판의 재계약 협상 (§3-D84). 없으면 만료 주차에서 체험판이 통째로 막힌다."""
    command = GuestAnswerOfferCommand(
        run=_restore(body.state),  # type: ignore[arg-type]
        offer_code=body.offer,
    )
    return to_guest(_sync(lambda: use_case.answer_guest_offer(command)))


@career_router.post("/guest/cash-in", response_model=GuestAdvanceResponse)
def cash_in_guest(
    body: GuestResumeRequest,
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> GuestAdvanceResponse:
    """체험판의 가방 현금화 (§3-D85). **세이브만 받는다** — 고를 것이 없다."""
    command = GuestCashInCommand(run=_restore(body.state))  # type: ignore[arg-type]
    return to_guest(_sync(lambda: use_case.cash_in_guest(command)))


@career_router.post("/guest/call-out", response_model=GuestAdvanceResponse)
def call_out_guest(
    body: GuestCallOutRequest,
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> GuestAdvanceResponse:
    """체험판의 시비 걸기 (§3-D86)."""
    command = GuestCallOutCommand(
        run=_restore(body.state),  # type: ignore[arg-type]
        rival_name=body.rival,
    )
    return to_guest(_sync(lambda: use_case.call_out_guest(command)))


@career_router.post("/guest/finisher", response_model=GuestAdvanceResponse)
def change_guest_finisher(
    body: GuestFinisherRequest,
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> GuestAdvanceResponse:
    """체험판의 피니셔 교체 (§3-D88)."""
    command = GuestChangeFinisherCommand(
        run=_restore(body.state),  # type: ignore[arg-type]
        code=body.code,
        name=body.name,
        hold=body.hold,
    )
    return to_guest(_sync(lambda: use_case.change_guest_finisher(command)))


@career_router.post("/guest/news", response_model=NewsPageSchema)
def read_guest_news(
    body: GuestResumeRequest,
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> NewsPageSchema:
    """체험판 인박스 (§3-D67). **배경 소식만 실린다** — 내 로그는 서버에 없다(§3-D8).

    `POST`인 이유는 `/guest/resume`과 같다 — 조회이지만 세이브가 본문에 실린다.
    """
    command = GuestResumeCommand(run=_restore(body.state))  # type: ignore[arg-type]
    return to_news(_sync(lambda: use_case.read_guest_news(command)))


@career_router.post("/guest/report", response_model=ShowReportSchema)
def read_guest_report(
    body: GuestReportRequest,
    use_case: CareerUseCase = Depends(get_career_use_case),
) -> ShowReportSchema:
    """그 밤의 리포트, 체험판 (§3-D51). 대회 주차가 아니면 404다.

    `GET /runs/{id}/report`의 짝이지만 **돌려주는 것이 좁다** — 체험판에는 로그가 없어
    내 경기 기록(승패·상대·서술)이 비어 온다. 화면이 그 줄을 이미 들고 있으므로
    리포트가 채울 것은 배경(그날의 벨트·그 무렵)뿐이다.

    `POST`인 이유는 `/guest/resume`과 같다 — 조회이지만 세이브가 본문에 실린다.
    """
    stake = title_of_display(body.title_at_stake) if body.title_at_stake else None
    command = GuestReportCommand(
        run=_restore(body.state),  # type: ignore[arg-type]
        week=body.week,
        busy=(body.opponent,) if body.opponent else (),
        stakes=(stake,) if stake is not None else (),
    )
    return to_report(_sync(lambda: use_case.read_guest_report(command)))
