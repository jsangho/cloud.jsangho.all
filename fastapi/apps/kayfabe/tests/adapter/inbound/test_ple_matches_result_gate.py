"""경기 결과 쓰기 경로의 권한 가드를 고정한다.

이 두 엔드포인트는 한동안 **아무 인증도 없이** 열려 있었다. 화면에서는 프론트 코드에
박힌 비밀번호 하나(`lib/ple-results-admin.ts`)로 가려져 있었지만 서버는 토큰을 보지
않았으므로, 주소만 알면 누구나 운영 대회의 승자를 바꿀 수 있었다. 결과는 사용자 픽
채점과 랭킹의 입력이라 한 번 뒤집히면 그 뒤 숫자가 전부 따라 틀린다.

조회(보드 GET)는 공개로 남는다 — 잠긴 것은 쓰기뿐이다.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from kayfabe.adapter.inbound.api.v1.ple_matches_router import ple_matches_router
from kayfabe.app.dtos.ple_events_dto import PleBoardResponse
from kayfabe.dependencies.ple_events_provider import get_ple_events

_BOARD = PleBoardResponse(
    slug="summerslam",
    label="SummerSlam",
    month=8,
    year=2026,
    status="finished",
    finished_at=datetime(2026, 8, 4, 12, 0, tzinfo=UTC),
    matches=[],
    updated_at=datetime(2026, 8, 4, 12, 0, tzinfo=UTC),
)

_BATCH_URL = "/api/ple-matches/summerslam/results/batch"
_SINGLE_URL = "/api/ple-matches/summerslam/matches/ss26-n2-whc/result"
_BATCH_BODY = {"results": [{"matchKey": "ss26-n2-whc", "winnerSide": "left"}]}
_SINGLE_BODY = {"winnerSide": "left", "status": "finished"}


class SpyUseCase:
    """결과를 쓰는 두 메소드만 가진 대역. 호출 여부가 이 테스트의 관심사다."""

    def __init__(self) -> None:
        self.writes: list[str] = []

    async def set_match_results_batch(
        self, *, slug: str, body: object
    ) -> PleBoardResponse:
        self.writes.append(f"batch:{slug}")
        return _BOARD

    async def set_match_result(
        self, *, slug: str, match_key: str, body: object
    ) -> PleBoardResponse:
        self.writes.append(f"single:{slug}/{match_key}")
        return _BOARD


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


def _client(use_case: SpyUseCase, *, roles: list[str] | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(ple_matches_router, prefix="/api")
    app.dependency_overrides[get_ple_events] = lambda: use_case
    if roles is not None:
        app.dependency_overrides[get_current_user] = lambda: _claims(roles)
    return TestClient(app)


def test_batch_rejects_anonymous_callers() -> None:
    use_case = SpyUseCase()

    response = _client(use_case).post(_BATCH_URL, json=_BATCH_BODY)

    assert response.status_code == 401
    assert use_case.writes == []


def test_batch_rejects_non_admin_users() -> None:
    """로그인만으로는 열리지 않는다 — 결과는 모든 사용자의 점수를 건드린다."""
    use_case = SpyUseCase()

    response = _client(use_case, roles=["user"]).post(_BATCH_URL, json=_BATCH_BODY)

    assert response.status_code == 403
    assert use_case.writes == []


def test_single_rejects_anonymous_callers() -> None:
    use_case = SpyUseCase()

    response = _client(use_case).post(_SINGLE_URL, json=_SINGLE_BODY)

    assert response.status_code == 401
    assert use_case.writes == []


def test_single_rejects_non_admin_users() -> None:
    use_case = SpyUseCase()

    response = _client(use_case, roles=["user"]).post(_SINGLE_URL, json=_SINGLE_BODY)

    assert response.status_code == 403
    assert use_case.writes == []


def test_admin_can_write_results() -> None:
    use_case = SpyUseCase()
    client = _client(use_case, roles=["admin"])

    assert client.post(_BATCH_URL, json=_BATCH_BODY).status_code == 200
    assert client.post(_SINGLE_URL, json=_SINGLE_BODY).status_code == 200
    assert use_case.writes == ["batch:summerslam", "single:summerslam/ss26-n2-whc"]
