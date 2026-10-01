"""결과 확정 엔드포인트의 권한·응답 모양을 고정한다.

이 문을 열면서 프로바이더 독스트링의 이전 결정("라우터에 열지 않는다")을 뒤집었다.
그 결정이 걱정했던 두 가지를 여기서 막는다:

1. **누가 썼는지** — 관리자 전용이고, 쓰기 요청에는 토큰의 `sub`가 로그에 남는다.
2. **사람의 확인** — 목록 조회는 모델을 부르지 않고, 쓰기는 `apply=true`를 명시한
   별도 요청이다. 기본은 드라이런이다.

§11 검증 기준 6(응답 어디에도 모델 이름이 없다)도 여기서 함께 붙든다.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from kayfabe.adapter.inbound.api.v1.result_verification_router import (
    result_verification_router,
)
from kayfabe.app.dtos.result_verification_dto import (
    MatchVerification,
    VerificationRun,
    VerifyResultsCommand,
)
from kayfabe.dependencies.result_verification_provider import get_result_verification
from kayfabe.domain.entities.result_verification import (
    HoldReason,
    MatchUnderReview,
    ReviewOption,
)

_PENDING_URL = "/api/ple_events/maintenance/result-verification/pending"
_RUN_URL = "/api/ple_events/maintenance/result-verification/run"

_MATCH = MatchUnderReview(
    event_slug="money-in-the-bank",
    event_label="Money in the Bank 2026",
    match_key="mitb26-whc",
    title="World Heavyweight Championship",
    options=(
        ReviewOption(pick="left", name="Roman Reigns"),
        ReviewOption(pick="right", name="Cody Rhodes"),
    ),
)


class FakeUseCase:
    def __init__(self) -> None:
        self.commands: list[VerifyResultsCommand] = []
        self.pending_calls = 0

    async def list_pending(self, *, event_slug: str | None = None):
        self.pending_calls += 1
        return (_MATCH,)

    async def verify(self, command: VerifyResultsCommand) -> VerificationRun:
        self.commands.append(command)
        return VerificationRun(
            matches=(
                MatchVerification(
                    event_slug="money-in-the-bank",
                    match_key="mitb26-whc",
                    title="World Heavyweight Championship",
                    pick="left" if command.apply else "left",
                    winner_name="Roman Reigns",
                    written=command.apply,
                    quote="Reigns defeated Rhodes",
                    source_title="Money in the Bank (2026)",
                    source_revision_id="777",
                    tool_calls=3,
                    model="gemini-secret-name",
                ),
                MatchVerification(
                    event_slug="money-in-the-bank",
                    match_key="mitb26-men",
                    title="Men's Money in the Bank Ladder Match",
                    hold=HoldReason.QUOTE_NOT_FOUND,
                    tool_calls=2,
                ),
            ),
            applied=command.apply,
            found=5,
        )


def _claims(roles: list[str]) -> TokenPayload:
    return TokenPayload(
        sub="7",
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
    app.include_router(result_verification_router, prefix="/api")
    app.dependency_overrides[get_result_verification] = lambda: use_case
    if roles is not None:
        app.dependency_overrides[get_current_user] = lambda: _claims(roles)
    return TestClient(app)


def test_pending_rejects_anonymous_callers() -> None:
    use_case = FakeUseCase()

    assert _client(use_case).get(_PENDING_URL).status_code == 401
    assert use_case.pending_calls == 0


def test_pending_rejects_non_admin_users() -> None:
    use_case = FakeUseCase()

    assert _client(use_case, roles=["user"]).get(_PENDING_URL).status_code == 403
    assert use_case.pending_calls == 0


def test_run_rejects_anonymous_callers() -> None:
    use_case = FakeUseCase()

    assert _client(use_case).post(_RUN_URL, json={}).status_code == 401
    assert use_case.commands == []


def test_run_rejects_non_admin_users() -> None:
    """LLM 비용이 들고 DB를 쓰는 입구라 로그인만으로는 열리지 않는다."""
    use_case = FakeUseCase()

    response = _client(use_case, roles=["user"]).post(_RUN_URL, json={})

    assert response.status_code == 403
    assert use_case.commands == []


def test_pending_lists_options_by_name() -> None:
    response = _client(FakeUseCase(), roles=["admin"]).get(_PENDING_URL)

    assert response.status_code == 200
    assert response.json()["items"][0] == {
        "eventSlug": "money-in-the-bank",
        "eventLabel": "Money in the Bank 2026",
        "matchKey": "mitb26-whc",
        "title": "World Heavyweight Championship",
        "options": ["Roman Reigns", "Cody Rhodes"],
    }


def test_run_defaults_to_dry_run() -> None:
    """**기본이 드라이런이다.** 쓰는 값이 모델이 읽은 문서에서 파생되기 때문이다."""
    use_case = FakeUseCase()

    response = _client(use_case, roles=["admin"]).post(_RUN_URL, json={})

    assert response.status_code == 200
    body = response.json()
    assert use_case.commands[0].apply is False
    assert body["applied"] is False
    assert body["written"] == 0
    # 쓸 수 있다고 판정된 것은 따로 센다 — 드라이런에서 이 값만 올라간다.
    assert body["writable"] == 1
    assert body["held"] == 1


def test_run_passes_selection_through() -> None:
    use_case = FakeUseCase()

    _client(use_case, roles=["admin"]).post(
        _RUN_URL,
        json={
            "eventSlug": "money-in-the-bank",
            "matchKeys": ["mitb26-whc"],
            "limit": 1,
            "apply": True,
        },
    )

    command = use_case.commands[0]
    assert command.event_slug == "money-in-the-bank"
    assert command.match_keys == ("mitb26-whc",)
    assert command.limit == 1
    assert command.apply is True


def test_found_survives_selection() -> None:
    """한 건만 골라 돌려도 **총수**가 응답에 남는다 — 없으면 "하나뿐"으로 읽힌다."""
    response = _client(FakeUseCase(), roles=["admin"]).post(
        _RUN_URL, json={"matchKeys": ["mitb26-whc"]}
    )

    assert response.json()["found"] == 5


def test_hold_reason_is_a_plain_word() -> None:
    body = _client(FakeUseCase(), roles=["admin"]).post(_RUN_URL, json={}).json()

    assert body["matches"][0]["hold"] is None
    assert body["matches"][1]["hold"] == "quote_not_found"


def test_response_never_carries_the_model_name() -> None:
    """§11 검증 기준 6. DTO 에는 `model` 이 있지만 스키마에는 자리가 없다."""
    body = _client(FakeUseCase(), roles=["admin"]).post(_RUN_URL, json={}).text

    assert "gemini-secret-name" not in body
    assert "model" not in body


def test_limit_is_bounded() -> None:
    """비용이 경기 수에 비례하므로 상한을 스키마가 막는다."""
    use_case = FakeUseCase()

    response = _client(use_case, roles=["admin"]).post(_RUN_URL, json={"limit": 999})

    assert response.status_code == 422
    assert use_case.commands == []
