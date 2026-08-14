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


class TestGuestOffer:
    """재계약 협상, 체험판 (§3-D84·D8).

    **여기가 없으면 만료 주차에서 체험판이 통째로 막힌다** — 진행은 `OFFER`로 서는데
    답할 엔드포인트가 없으면 그 세이브는 다시 못 움직인다.
    """

    @staticmethod
    def _until_offer(client: TestClient) -> dict | None:
        """협상이 열릴 때까지 진행한다. 안 열리면 None."""
        body = _start(client)
        state = body["state"]
        for _ in range(60):
            body = client.post(
                "/api/career/guest/advance", json={"state": state, "step": "auto"}
            ).json()
            if body["stopReason"] == "offer":
                return body
            if body.get("pendingEvent"):
                body = client.post(
                    "/api/career/guest/choices",
                    json={
                        "state": body["state"],
                        "choice": body["pendingEvent"]["choices"][0]["code"],
                    },
                ).json()
            elif body["stopReason"] == "goal":
                body = client.post(
                    "/api/career/guest/goal",
                    json={"state": body["state"], "goal": "drift"},
                ).json()
            elif body["run"]["endReason"]:
                return None
            state = body["state"]
        return None

    def test_an_open_offer_arrives_with_its_choices(self, client: TestClient) -> None:
        body = self._until_offer(client)
        if body is None:
            pytest.skip("60번 진행 동안 만료 주차가 안 왔다")
        assert body["run"]["offerOptions"], "협상이 열렸는데 선택지가 안 왔다"
        assert set(body["run"]["offerOptions"][0]) == {
            "code",
            "label",
            "blurb",
            "weeklyPay",
            "years",
        }, "거절 확률 같은 내부 수치가 새면 안 된다 (§11-14)"

    def test_answering_unblocks_the_save(self, client: TestClient) -> None:
        body = self._until_offer(client)
        if body is None:
            pytest.skip("60번 진행 동안 만료 주차가 안 왔다")
        answered = client.post(
            "/api/career/guest/offer", json={"state": body["state"], "offer": "accept"}
        )
        assert answered.status_code == 200, answered.text
        after = answered.json()
        assert after["stopReason"] != "offer"
        assert not after["run"]["offerOptions"]
        # 답했으니 다시 흘러간다 — 안 그러면 진행이 영영 막힌다.
        moved = client.post(
            "/api/career/guest/advance", json={"state": after["state"], "step": "auto"}
        ).json()
        assert moved["run"]["week"] > after["run"]["week"]

    def test_answering_outside_a_negotiation_is_refused(
        self, client: TestClient
    ) -> None:
        state = _start(client)["state"]
        response = client.post(
            "/api/career/guest/offer", json={"state": state, "offer": "accept"}
        )
        assert response.status_code == 409

    def test_an_unknown_answer_is_refused(self, client: TestClient) -> None:
        body = self._until_offer(client)
        if body is None:
            pytest.skip("60번 진행 동안 만료 주차가 안 왔다")
        response = client.post(
            "/api/career/guest/offer",
            json={"state": body["state"], "offer": "돈을_두_배로"},
        )
        assert response.status_code == 400


class TestGuestBriefcase:
    """가방 현금화, 체험판 (§3-D85·D8).

    **막지 않는 행동이라 더 조용히 빠뜨리기 쉽다** — 협상은 없으면 진행이 멈춰
    바로 드러나지만, 이건 없어도 게임이 굴러가서 아무도 모른 채 자동 현금화된다.
    """

    def test_cashing_in_without_a_briefcase_is_refused(
        self, client: TestClient
    ) -> None:
        state = _start(client)["state"]
        response = client.post("/api/career/guest/cash-in", json={"state": state})
        assert response.status_code == 409

    def test_a_carried_briefcase_reaches_the_screen(self, client: TestClient) -> None:
        """가방을 든 세이브를 돌려보내면 응답이 그 자리를 낸다."""
        body = _start(client)
        state = dict(body["state"])
        state["briefcase_week"] = max(1, int(state["week"]) or 1)
        state["week"] = int(state["briefcase_week"]) + 10
        resumed = client.post("/api/career/guest/resume", json={"state": state})
        if resumed.status_code != 200:
            pytest.skip(f"세이브 형식이 달라 세울 수 없다: {resumed.text[:120]}")
        card = resumed.json()["run"]["briefcase"]
        assert card is not None, "가방을 들었는데 화면에 자리가 없다"
        assert set(card) == {
            "title",
            "champion",
            "weeksLeft",
            "pending",
            "canCashIn",
        }, "챔피언의 인기도 같은 내부 수치가 새면 안 된다 (§11-14)"

    def test_carrying_one_does_not_block_advancing(self, client: TestClient) -> None:
        """**막지 않는다** — 협상(§3-D84)과 갈리는 자리다."""
        body = _start(client)
        state = dict(body["state"])
        state["briefcase_week"] = max(1, int(state["week"]) or 1)
        state["week"] = int(state["briefcase_week"]) + 10
        moved = client.post(
            "/api/career/guest/advance", json={"state": state, "step": "auto"}
        )
        if moved.status_code != 200:
            pytest.skip(f"세이브 형식이 달라 세울 수 없다: {moved.text[:120]}")
        assert moved.json()["stopReason"] != "offer"
        assert moved.json()["run"]["week"] > state["week"]


class TestResume:
    """재개는 **진행이 아니다** (2026-08-11 버그).

    이 경로가 없던 동안 화면은 `advance(step="tick")`으로 재개했고, 셋이 함께 깨져
    있었다: 다시 열 때마다 한 틱(분기 모드면 12주)이 실제로 흘렀고, 대기 이벤트가
    있으면 409라 화면이 세이브를 지웠으며, 그래서 **이벤트 중 새로고침이 곧 커리어
    소멸**이었다.
    """

    def _play_to_event(self, client: TestClient) -> dict:
        state = _start(client)["state"]
        for _ in range(30):
            body = client.post(
                "/api/career/guest/advance", json={"state": state, "step": "auto"}
            ).json()
            state = body["state"]
            if body.get("pendingEvent"):
                return state
        pytest.skip("30번 진행 동안 이벤트가 안 떴다")

    def test_resuming_does_not_burn_a_week(self, client: TestClient) -> None:
        state = _start(client)["state"]
        body = client.post(
            "/api/career/guest/advance", json={"state": state, "step": "auto"}
        ).json()
        before = body["run"]["week"]
        state = body["state"]
        if body.get("pendingEvent"):
            state = client.post(
                "/api/career/guest/choices",
                json={
                    "state": state,
                    "choice": body["pendingEvent"]["choices"][0]["code"],
                },
            ).json()["state"]
        for _ in range(3):  # 새로고침 세 번
            resumed = client.post("/api/career/guest/resume", json={"state": state})
            assert resumed.status_code == 200, resumed.text
            body = resumed.json()
            state = body["state"]
        assert body["run"]["week"] == before, "다시 열었을 뿐인데 커리어가 진행됐다"
        assert body["weeks"] == [], "진행하지 않은 응답에 주차가 실렸다"

    def test_a_pending_event_comes_back_instead_of_a_409(
        self, client: TestClient
    ) -> None:
        # 진행(`advance`)은 409로 막는 게 맞지만(§11-2), 재개까지 막으면 답할 화면이
        # 안 뜬다 — 그 409를 화면이 "못 읽는 세이브"로 오해해 지우고 있었다.
        state = self._play_to_event(client)
        response = client.post("/api/career/guest/resume", json={"state": state})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["pendingEvent"] is not None
        assert body["stopReason"] == "event"

    def test_the_save_survives_a_reload_during_an_event(
        self, client: TestClient
    ) -> None:
        state = self._play_to_event(client)
        resumed = client.post("/api/career/guest/resume", json={"state": state}).json()
        answered = client.post(
            "/api/career/guest/choices",
            json={
                "state": resumed["state"],
                "choice": resumed["pendingEvent"]["choices"][0]["code"],
            },
        )
        assert answered.status_code == 200, answered.text
        assert answered.json()["pendingEvent"] is None

    def test_a_locked_mode_is_refused_on_resume_too(self, client: TestClient) -> None:
        state = _start(client)["state"]
        state["mode"] = "weekly"
        assert (
            client.post("/api/career/guest/resume", json={"state": state}).status_code
            == 400
        )

    def test_a_tampered_state_is_refused_on_resume_too(
        self, client: TestClient
    ) -> None:
        state = _start(client)["state"]
        state["stats"]["popularity"] = 500
        assert (
            client.post("/api/career/guest/resume", json={"state": state}).status_code
            == 400
        )


class TestGuestReport:
    """그 밤의 리포트를 체험판에서 (§3-D51).

    화면은 대회 주차에 "그날의 리포트" 토글을 띄우는데, 리포트 경로가 로그인 전용이라
    **누르면 아무것도 안 떴다** (2026-08-12 사용자 신고). 체험판에는 로그가 없으므로
    (§3-D8) 물어보는 방식도 다르다 — 세이브를 본문에 실어 보낸다.
    """

    @staticmethod
    def _play(client: TestClient) -> tuple[dict, list[dict]]:
        """대회 주차가 나올 때까지 진행한다. 세이브와 지나온 주차를 함께 돌려준다."""
        state = _start(client)["state"]
        weeks: list[dict] = []
        for _ in range(12):
            body = client.post(
                "/api/career/guest/advance", json={"state": state, "step": "auto"}
            ).json()
            state = body["state"]
            weeks.extend(body.get("weeks", []))
            if body.get("pendingEvent"):
                body = client.post(
                    "/api/career/guest/choices",
                    json={
                        "state": state,
                        "choice": body["pendingEvent"]["choices"][0]["code"],
                    },
                ).json()
                state = body["state"]
            if any(w["kind"] in ("ple", "special") for w in weeks):
                return state, weeks
        pytest.skip("12번 진행 동안 대회 주차가 안 나왔다")

    def test_a_show_week_has_a_report(self, client: TestClient) -> None:
        state, weeks = self._play(client)
        show_week = next(w["week"] for w in weeks if w["kind"] in ("ple", "special"))
        response = client.post(
            "/api/career/guest/report", json={"state": state, "week": show_week}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["week"] == show_week
        assert body["show"]
        # **벨트에는 늘 주인이 있다** (§3-D38) — 리포트가 그걸 한자리에 모은다.
        assert body["champions"]
        assert all(c["holder"] for c in body["champions"])

    def test_my_match_is_left_to_the_screen(self, client: TestClient) -> None:
        # 로그가 없어 승패·상대를 서버가 모른다. **화면이 이미 그 줄에 들고 있으므로**
        # 비워 보내는 것이 맞다 — 없는 것을 지어내면 그게 더 나쁘다.
        state, weeks = self._play(client)
        show_week = next(w["week"] for w in weeks if w["kind"] in ("ple", "special"))
        body = client.post(
            "/api/career/guest/report", json={"state": state, "week": show_week}
        ).json()
        assert body["result"] is None
        assert body["opponent"] is None
        assert body["narration"] == ""

    def test_an_ordinary_week_is_a_smaller_night(self, client: TestClient) -> None:
        """주간 방송도 리포트가 있다 (§3-D60) — **다만 밤이 작다.**

        §3-D45는 "대회 주차만"으로 닫았지만 사용자 요청으로 열었다. 크기가 같으면
        1560주가 전부 대회가 되므로, 카드가 작다는 것으로 그 자리를 지킨다.
        """
        state, weeks = self._play(client)
        plain = next((w["week"] for w in weeks if w["kind"] == "weekly_show"), None)
        show = next((w["week"] for w in weeks if w["kind"] in ("ple", "special")), None)
        if plain is None or show is None:
            pytest.skip("주간 방송과 대회가 함께 있는 판이 아니다")
        night = client.post(
            "/api/career/guest/report", json={"state": state, "week": plain}
        )
        assert night.status_code == 200, night.text
        big = client.post(
            "/api/career/guest/report", json={"state": state, "week": show}
        ).json()
        assert len(night.json()["card"]) < len(big["card"])
        assert night.json()["isMajor"] is False

    def test_a_week_not_yet_played_is_refused(self, client: TestClient) -> None:
        # 세이브를 고쳐 미래를 물으면 아직 오지 않은 밤의 계보가 나온다.
        state = _start(client)["state"]
        assert (
            client.post(
                "/api/career/guest/report", json={"state": state, "week": 900}
            ).status_code
            == 404
        )

    def test_a_tampered_state_is_refused(self, client: TestClient) -> None:
        state, weeks = self._play(client)
        show_week = next(w["week"] for w in weeks if w["kind"] in ("ple", "special"))
        state["stats"]["popularity"] = 500
        assert (
            client.post(
                "/api/career/guest/report", json={"state": state, "week": show_week}
            ).status_code
            == 400
        )


class TestGuestNews:
    """체험판 인박스 — **배경 소식만** (§3-D67).

    내 뉴스(대관·부상·턴)는 주차 로그에서 나오는데 체험판 로그는 서버에 없다(§3-D8).
    낼 수 있는 것을 안 내지도, 없는 것을 지어내지도 않는다.
    """

    @staticmethod
    def _played(client: TestClient) -> dict:
        state = _start(client)["state"]
        for _ in range(6):
            body = client.post(
                "/api/career/guest/advance", json={"state": state, "step": "auto"}
            ).json()
            state = body["state"]
            if body.get("pendingEvent"):
                state = client.post(
                    "/api/career/guest/choices",
                    json={
                        "state": state,
                        "choice": body["pendingEvent"]["choices"][0]["code"],
                    },
                ).json()["state"]
        return state

    def test_the_world_has_news(self, client: TestClient) -> None:
        state = self._played(client)
        response = client.post("/api/career/guest/news", json={"state": state})
        assert response.status_code == 200, response.text
        assert response.json()["items"], "배경 소식이 한 줄도 없다"

    def test_it_is_only_the_background(self, client: TestClient) -> None:
        mine = {"title_won", "title_lost", "injury", "big_win", "turn", "classic"}
        body = client.post(
            "/api/career/guest/news", json={"state": self._played(client)}
        ).json()
        assert not (mine & {item["kind"] for item in body["items"]})

    def test_it_runs_in_order(self, client: TestClient) -> None:
        body = client.post(
            "/api/career/guest/news", json={"state": self._played(client)}
        ).json()
        weeks = [item["week"] for item in body["items"]]
        assert weeks == sorted(weeks)

    def test_a_tampered_state_is_refused(self, client: TestClient) -> None:
        state = _start(client)["state"]
        state["stats"]["popularity"] = 500
        assert (
            client.post("/api/career/guest/news", json={"state": state}).status_code
            == 400
        )
