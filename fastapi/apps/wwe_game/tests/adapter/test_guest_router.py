"""T11 체험판 — 잠긴 모드 400 · 조작된 상태 400 · 로그인과 같은 유스케이스 (§3-D8).

**인증을 끼우지 않는다.** `/guest/*`는 비로그인 경로라, `get_current_user`를 덮어쓰지
않은 채로도 돌아야 한다 — 그게 안 되면 체험판이 아니다.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from test_career_router import (
    MemoryRepository,  # noqa: I001  (tests에 __init__.py가 없다)
)
from wwe_game.adapter.inbound.api.v1.career_router import career_router
from wwe_game.adapter.outbound.narration.rule_narrator import RuleNarrator
from wwe_game.app.use_cases.career_interactor import CareerInteractor
from wwe_game.dependencies.career_provider import get_career_use_case

from fastapi import FastAPI


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(career_router, prefix="/api")
    interactor = CareerInteractor(
        repository=MemoryRepository(), narrator=RuleNarrator()
    )
    app.dependency_overrides[get_career_use_case] = lambda: interactor
    return TestClient(app)


def _start(client: TestClient, mode: str = "quarterly") -> dict:
    response = client.post(
        "/api/career/guest/runs",
        json={"name": "장상호", "mode": mode, "basedOn": "로만 레인즈", "seed": 42},
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestLockedModes:
    @pytest.mark.parametrize("mode", ["monthly", "weekly"])
    def test_the_deep_modes_need_a_login(self, client: TestClient, mode: str) -> None:
        # 틱이 390·1560개라 상태가 브라우저에 안 들어간다 (§11-24).
        response = client.post(
            "/api/career/guest/runs",
            json={"name": "장상호", "mode": mode, "basedOn": "로만 레인즈"},
        )
        assert response.status_code == 400
        assert "로그인" in response.json()["detail"]

    @pytest.mark.parametrize("mode", ["yearly", "quarterly"])
    def test_the_shallow_modes_are_open(self, client: TestClient, mode: str) -> None:
        assert _start(client, mode)["run"]["week"] == 0

    def test_a_locked_mode_is_refused_on_advance_too(self, client: TestClient) -> None:
        # 시작만 막고 진행을 열어 두면 모드를 바꿔 보내는 것으로 뚫린다.
        state = _start(client)["state"]
        state["mode"] = "weekly"
        response = client.post(
            "/api/career/guest/advance", json={"state": state, "step": "auto"}
        )
        assert response.status_code == 400


class TestStatelessPlay:
    def test_the_server_stores_nothing(self, client: TestClient) -> None:
        body = _start(client)
        assert body["run"]["id"] is None, "체험판 세이브에 id가 붙었다"
        # 서버가 아무것도 안 들고 있으므로 로그인 경로에는 진행 중인 커리어가 없다.
        assert body["state"]["seed"] == 42

    def test_advancing_returns_the_whole_save(self, client: TestClient) -> None:
        state = _start(client)["state"]
        body = client.post(
            "/api/career/guest/advance", json={"state": state, "step": "auto"}
        ).json()
        assert body["run"]["week"] > 0
        assert body["state"]["week"] == body["run"]["week"]

    def test_the_save_round_trips(self, client: TestClient) -> None:
        # 브라우저가 보관했다 그대로 보내는 값이라, 왕복해도 진행이 이어져야 한다.
        state = _start(client)["state"]
        weeks = []
        for _ in range(5):
            body = client.post(
                "/api/career/guest/advance", json={"state": state, "step": "auto"}
            ).json()
            if body.get("pendingEvent"):
                body = client.post(
                    "/api/career/guest/choices",
                    json={
                        "state": body["state"],
                        "choice": body["pendingEvent"]["choices"][0]["code"],
                    },
                ).json()
            state = body["state"]
            weeks.append(body["run"]["week"])
        assert weeks == sorted(weeks), "왕복하는 사이에 주차가 되감겼다"

    def test_the_same_seed_replays_the_same_career(self, client: TestClient) -> None:
        def play() -> list[int]:
            state = _start(client)["state"]
            out = []
            for _ in range(3):
                body = client.post(
                    "/api/career/guest/advance", json={"state": state, "step": "auto"}
                ).json()
                if body.get("pendingEvent"):
                    # 대기 이벤트가 서면 진행이 막히므로(§11-2) 먼저 답한다.
                    body = client.post(
                        "/api/career/guest/choices",
                        json={
                            "state": body["state"],
                            "choice": body["pendingEvent"]["choices"][0]["code"],
                        },
                    ).json()
                state = body["state"]
                out.append(body["run"]["stats"]["popularity"])
            return out

        assert play() == play(), "같은 시드가 다른 결과를 냈다 (§3-D4)"


class TestTamperedState:
    def test_an_out_of_range_stat_is_refused(self, client: TestClient) -> None:
        state = _start(client)["state"]
        state["stats"]["popularity"] = 500
        response = client.post(
            "/api/career/guest/advance", json={"state": state, "step": "auto"}
        )
        assert response.status_code == 400

    def test_a_week_past_the_career_is_refused(self, client: TestClient) -> None:
        state = _start(client)["state"]
        state["week"] = 9999
        assert (
            client.post(
                "/api/career/guest/advance", json={"state": state, "step": "auto"}
            ).status_code
            == 400
        )

    def test_an_unknown_code_is_refused(self, client: TestClient) -> None:
        state = _start(client)["state"]
        state["play_style"] = "있을 리 없는 스타일"
        assert (
            client.post(
                "/api/career/guest/advance", json={"state": state, "step": "auto"}
            ).status_code
            == 400
        )

    def test_an_unknown_field_is_refused(self, client: TestClient) -> None:
        # `extra="forbid"` — 모르는 칸이 조용히 무시되면 포맷이 바뀐 걸 아무도 모른다.
        state = _start(client)["state"]
        state["cheat"] = True
        assert (
            client.post(
                "/api/career/guest/advance", json={"state": state, "step": "auto"}
            ).status_code
            == 422
        )

    def test_a_legal_but_lucky_state_is_accepted(self, client: TestClient) -> None:
        # **신뢰하지 않되 막지도 않는다** — 규칙에 맞으면 그대로 받는다 (§3-D8).
        state = _start(client)["state"]
        state["stats"]["popularity"] = 99
        response = client.post(
            "/api/career/guest/advance", json={"state": state, "step": "auto"}
        )
        assert response.status_code == 200


class TestSameRulesAsLogin:
    def test_a_pending_event_blocks_advancing(self, client: TestClient) -> None:
        state = _start(client)["state"]
        for _ in range(30):
            body = client.post(
                "/api/career/guest/advance", json={"state": state, "step": "auto"}
            ).json()
            state = body["state"]
            if body.get("pendingEvent"):
                break
        else:
            pytest.skip("30번 진행 동안 이벤트가 안 떴다")
        blocked = client.post(
            "/api/career/guest/advance", json={"state": state, "step": "auto"}
        )
        assert blocked.status_code == 409, "체험판에서 대기 이벤트가 진행을 안 막는다"

    def test_choosing_without_an_event_is_refused(self, client: TestClient) -> None:
        state = _start(client)["state"]
        response = client.post(
            "/api/career/guest/choices", json={"state": state, "choice": "무엇이든"}
        )
        assert response.status_code == 409

    def test_the_response_hides_internal_numbers(self, client: TestClient) -> None:
        state = _start(client)["state"]
        for _ in range(30):
            body = client.post(
                "/api/career/guest/advance", json={"state": state, "step": "auto"}
            ).json()
            state = body["state"]
            if body.get("pendingEvent"):
                assert set(body["pendingEvent"]["choices"][0]) == {"code", "label"}
                return
        pytest.skip("30번 진행 동안 이벤트가 안 떴다")
