"""`status` 점검 엔드포인트의 권한과 응답 모양을 고정한다.

**조회도 관리자 전용이다.** 이 응답은 운영 DB의 행 상태를 그대로 비추는 점검용
화면이고, 사용자에게 보여줄 값이 아니다 (예측 조회가 공개인 것과 다르다).
"""

from __future__ import annotations

from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from kayfabe.adapter.inbound.api.v1.event_status_router import event_status_router
from kayfabe.adapter.inbound.api.v1.ple_events_router import ple_events_router
from kayfabe.app.dtos.event_status_dto import (
    EventStatusDriftItem,
    EventStatusDriftReport,
)
from kayfabe.dependencies.event_status_provider import get_event_status_use_case
from kayfabe.dependencies.ple_events_provider import get_ple_events

_PREVIEW_URL = "/api/ple_events/maintenance/status-drift"
_CLOSE_URL = "/api/ple_events/maintenance/status-drift/close"

_ITEM = EventStatusDriftItem(
    slug="clash-in-italy",
    status="upcoming",
    start_date=date(2026, 5, 31),
    end_date=None,
    verdict="needs_close",
)


class FakeUseCase:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[str] = []

    async def preview(self, *, today: date | None = None) -> EventStatusDriftReport:
        self.calls.append("preview")
        return EventStatusDriftReport(today=date(2026, 10, 1), items=[_ITEM], pending=1)

    async def close_past(self, *, today: date | None = None) -> EventStatusDriftReport:
        if self.error is not None:
            raise self.error
        self.calls.append("close")
        return EventStatusDriftReport(
            today=date(2026, 10, 1), items=[_ITEM], pending=1, written=1
        )


def _claims(roles: list[str]) -> TokenPayload:
    return TokenPayload(
        sub="1",
        aud="jsangho-api",
        exp=9999999999,
        iat=0,
        jti="jti",
        roles=roles,
        platform="web",
        device_id="d1",
    )


def _client(use_case: FakeUseCase, *, roles: list[str] | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(event_status_router, prefix="/api")
    app.dependency_overrides[get_event_status_use_case] = lambda: use_case
    if roles is not None:
        app.dependency_overrides[get_current_user] = lambda: _claims(roles)
    return TestClient(app)


def test_preview_rejects_anonymous_callers() -> None:
    use_case = FakeUseCase()

    assert _client(use_case).get(_PREVIEW_URL).status_code == 401
    assert use_case.calls == []


def test_preview_rejects_non_admin_users() -> None:
    use_case = FakeUseCase()

    assert _client(use_case, roles=["user"]).get(_PREVIEW_URL).status_code == 403
    assert use_case.calls == []


def test_close_rejects_anonymous_callers() -> None:
    use_case = FakeUseCase()

    assert _client(use_case).post(_CLOSE_URL).status_code == 401
    assert use_case.calls == []


def test_close_rejects_non_admin_users() -> None:
    use_case = FakeUseCase()

    assert _client(use_case, roles=["user"]).post(_CLOSE_URL).status_code == 403
    assert use_case.calls == []


def test_preview_returns_camel_case_dates_and_no_written() -> None:
    response = _client(FakeUseCase(), roles=["admin"]).get(_PREVIEW_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["today"] == "2026-10-01"
    assert body["pending"] == 1
    # 보기만 한 응답에 0이 박히면 "쓸 게 없었다"로 읽힌다.
    assert body["written"] is None
    assert body["items"][0] == {
        "slug": "clash-in-italy",
        "status": "upcoming",
        "startDate": "2026-05-31",
        "endDate": None,
        "verdict": "needs_close",
    }


def test_admin_can_close() -> None:
    use_case = FakeUseCase()

    response = _client(use_case, roles=["admin"]).post(_CLOSE_URL)

    assert response.status_code == 200
    assert response.json()["written"] == 1
    assert use_case.calls == ["close"]


def test_vanished_row_becomes_conflict() -> None:
    """목록이 그 사이에 바뀐 것은 서버 오류가 아니라 충돌이다."""
    use_case = FakeUseCase(error=LookupError("대상 행이 사라졌습니다"))

    response = _client(use_case, roles=["admin"]).post(_CLOSE_URL)

    assert response.status_code == 409
    # 내부 사정(슬러그 원문)이 그대로 새지 않는다
    assert "다시 시도" in response.json()["detail"]


def test_path_is_not_eaten_by_the_slug_route() -> None:
    """같은 prefix의 `GET /ple_events/{slug}`가 이 경로를 삼키지 않는다.

    한 칸짜리(`/status-drift`)로 뒀다면 slug="status-drift"로 먹혀 **권한 검사 없이**
    보드 조회가 돌았을 것이다. 그래서 실제 등록 순서(보드 먼저)로 둘을 함께 올리고
    401이 나오는지 본다 — 보드 쪽으로 샜다면 404가 나온다.
    """
    app = FastAPI()
    app.include_router(ple_events_router, prefix="/api")
    app.include_router(event_status_router, prefix="/api")
    app.dependency_overrides[get_ple_events] = lambda: _BoardNotFound()

    response = TestClient(app).get(_PREVIEW_URL)

    assert response.status_code == 401


class _BoardNotFound:
    """보드 조회로 샜는지 구분하기 위한 대역 — 새면 404가 된다."""

    async def get_board(self, **_: object):
        raise LookupError("없는 대회")
