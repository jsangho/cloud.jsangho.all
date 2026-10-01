"""대회 `status` 드리프트 점검 엔드포인트 — **관리자 전용**.

여기서 닫히는 드리프트에는 그동안 **사람이 돌리는 스크립트밖에 없었다**
(`scripts/close_past_events.py`). 결과를 넣지 않는 대회는 날짜가 아무리 지나도
`upcoming`으로 남고, 그 상태를 전제로 도는 뒤 단계(결과 확정 대상 추리기 등)가
조용히 0건을 낸다. 돌리는 것을 잊으면 아무 에러도 나지 않는다는 것이 이 작업의
성질이고, 그래서 화면에 올렸다.

**보기와 쓰기를 다른 메소드로 갈랐다.** 스크립트가 기본 드라이런인 이유와 같다 —
`finished`는 사람이 확인한 사실이 아니라 오늘 날짜로부터 파생된 판정이다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.security.dependencies import RoleChecker
from core.security.role import UserRole
from core.security.token_verifier import TokenPayload
from kayfabe.adapter.inbound.api.schemas.event_status_schema import (
    EventStatusDriftItemSchema,
    EventStatusDriftSchema,
)
from kayfabe.app.dtos.event_status_dto import EventStatusDriftReport
from kayfabe.app.ports.input.event_status_use_case import EventStatusUseCase
from kayfabe.dependencies.event_status_provider import get_event_status_use_case

event_status_router = APIRouter(prefix="/ple_events", tags=["ple-event-status"])

_admin_only = RoleChecker(UserRole.ADMIN)

# 경로가 `/maintenance/...` 두 칸 아래인 것은 **일부러**다. 같은 prefix에 이미
# `GET /ple_events/{slug}`가 있어서, 한 칸짜리 `/status-drift`는 등록 순서에 따라
# slug="status-drift"로 먹힌다. 두 칸이면 어느 순서로 붙여도 섞이지 않는다.


@event_status_router.get(
    "/maintenance/status-drift",
    response_model=EventStatusDriftSchema,
    response_model_by_alias=True,
)
async def preview_status_drift(
    _: TokenPayload = Depends(_admin_only),
    use_case: EventStatusUseCase = Depends(get_event_status_use_case),
):
    """지금 상태를 보여준다. **아무것도 쓰지 않는다.**"""
    return _to_schema(await use_case.preview())


@event_status_router.post(
    "/maintenance/status-drift/close",
    response_model=EventStatusDriftSchema,
    response_model_by_alias=True,
)
async def close_past_events(
    _: TokenPayload = Depends(_admin_only),
    use_case: EventStatusUseCase = Depends(get_event_status_use_case),
):
    """날짜가 지난 대회의 `status`만 `finished`로 넘긴다. 다시 눌러도 안전하다(멱등)."""
    try:
        report = await use_case.close_past()
    except LookupError as exc:
        # 읽은 뒤 쓰기 사이에 행이 사라졌다. 사라진 이유는 여기서 알 수 없다.
        raise HTTPException(
            status_code=409,
            detail="점검 중 대회 목록이 바뀌었습니다. 다시 시도해 주세요.",
        ) from exc
    return _to_schema(report)


def _to_schema(report: EventStatusDriftReport) -> EventStatusDriftSchema:
    return EventStatusDriftSchema(
        today=report.today,
        items=[
            EventStatusDriftItemSchema(
                slug=item.slug,
                status=item.status,
                startDate=item.start_date,
                endDate=item.end_date,
                verdict=item.verdict,
            )
            for item in report.items
        ],
        pending=report.pending,
        written=report.written,
    )
