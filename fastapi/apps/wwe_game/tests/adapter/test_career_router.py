"""T10 라우터 — 예외가 상태 코드로 옮겨지는 자리 (하네스 §7·§8).

**DB를 켜지 않는다.** 이 단위가 지키는 계약은 "어느 예외가 어느 상태 코드가 되는가"이지
SQL이 아니다 — 리포지토리는 인터랙터 테스트가 쓰는 것과 같은 메모리 대역으로 갈아 끼운다.
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001  (tests 트리에 __init__.py가 없다)
from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from fastapi.testclient import TestClient
from wwe_game.adapter.inbound.api.v1.career_router import career_router
from wwe_game.adapter.outbound.narration.rule_narrator import RuleNarrator
from wwe_game.app.dtos.career_dto import WeekReportView
from wwe_game.app.ports.output.career_repository import (
    CareerRepository,
    RunNotFoundError,
)
from wwe_game.app.use_cases.career_interactor import CareerInteractor
from wwe_game.dependencies.career_provider import get_career_use_case
from wwe_game.domain.entities.career_run import CareerRun

from fastapi import FastAPI

USER = 7
OTHER = 8


class MemoryRepository(CareerRepository):
    """세이브 하나와 로그만 드는 대역."""

    def __init__(self) -> None:
        self.runs: dict[int, CareerRun] = {}
        self.log: dict[int, list[WeekReportView]] = {}
        self._next = 1

    async def find_active(self, user_id: int) -> CareerRun | None:
        return next(
            (r for r in self.runs.values() if r.user_id == user_id and r.is_active),
            None,
        )

    async def get(self, run_id: int, user_id: int) -> CareerRun:
        run = self.runs.get(run_id)
        if run is None or run.user_id != user_id:
            # **남의 세이브도 "없음"이다** — 403은 존재 여부를 알려 준다(§11-12).
            raise RunNotFoundError("커리어를 찾을 수 없습니다.")
        return run

    async def save(
        self, run: CareerRun, entries: tuple[WeekReportView, ...] = ()
    ) -> CareerRun:
        if run.id is None:
            run = run.evolve(id=self._next)
            self._next += 1
        self.runs[run.id] = run
        self.log.setdefault(run.id, []).extend(entries)
        return run

    async def read_log(
        self, run_id: int, user_id: int, *, offset: int = 0, limit: int = 50
    ) -> tuple[tuple[WeekReportView, ...], int]:
        await self.get(run_id, user_id)
        rows = self.log.get(run_id, [])
        return tuple(rows[offset : offset + limit]), len(rows)


@pytest.fixture
def repository() -> MemoryRepository:
    return MemoryRepository()


@pytest.fixture
def client(repository: MemoryRepository) -> TestClient:
    app = FastAPI()
    app.include_router(career_router, prefix="/api")
    interactor = CareerInteractor(repository=repository, narrator=RuleNarrator())
    app.dependency_overrides[get_career_use_case] = lambda: interactor
    app.dependency_overrides[get_current_user] = lambda: TokenPayload(
        sub=str(USER), aud="web", exp=0, iat=0, jti="test"
    )
    return TestClient(app)


def _start(client: TestClient, **overrides: object) -> dict:
    body = {"name": "장상호", "mode": "yearly", "basedOn": "로만 레인즈"}
    body.update(overrides)  # type: ignore[arg-type]
    return client.post("/api/career/runs", json=body).json()


class TestMeta:
    def test_modes_need_no_login(self, client: TestClient) -> None:
        rows = client.get("/api/career/modes").json()
        assert {r["code"] for r in rows} == {
            "yearly",
            "quarterly",
            "monthly",
            "weekly",
        }
        allowed = {r["code"] for r in rows if r["guestAllowed"]}
        assert allowed == {"yearly", "quarterly"}, "체험판 허용 모드가 스펙과 다르다"

    def test_presets_carry_a_korean_style_label(self, client: TestClient) -> None:
        rows = client.get("/api/career/presets").json()
        assert len(rows) >= 150
        assert all(row["playStyleLabel"] for row in rows)
        assert any(row["playStyleLabel"] == "올라운더" for row in rows)


class TestStart:
    def test_a_new_career_is_created(self, client: TestClient) -> None:
        response = client.post(
            "/api/career/runs",
            json={"name": "장상호", "mode": "yearly", "basedOn": "로만 레인즈"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["run"]["week"] == 0
        assert body["run"]["age"] == 20, "시작 나이는 20세 고정이다 (§3-D10)"
        assert body["run"]["disclaimer"], "고지가 응답에 없다 (§3-D13)"

    def test_a_second_career_is_refused(self, client: TestClient) -> None:
        _start(client)
        assert (
            client.post(
                "/api/career/runs",
                json={"name": "장상호", "mode": "yearly", "basedOn": "로만 레인즈"},
            ).status_code
            == 409
        )

    def test_a_bad_name_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/career/runs",
            json={"name": "가", "mode": "yearly", "basedOn": "로만 레인즈"},
        )
        assert response.status_code == 400
        assert "2~20자" in response.json()["detail"]

    def test_an_unknown_style_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/career/runs",
            json={
                "name": "장상호",
                "mode": "yearly",
                "gender": "male",
                "country": "KR",
                "playStyle": "있을 리 없는 스타일",
            },
        )
        assert response.status_code == 400

    def test_an_unknown_mode_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/career/runs",
            json={"name": "장상호", "mode": "hourly", "basedOn": "로만 레인즈"},
        )
        assert response.status_code == 400


class TestPlay:
    def test_current_is_null_before_starting(self, client: TestClient) -> None:
        # 아직 안 만든 상태는 정상이다 — 404가 아니다.
        assert client.get("/api/career/runs/current").json() is None

    def test_advance_moves_the_career(self, client: TestClient) -> None:
        run_id = _start(client)["run"]["id"]
        body = client.post(
            f"/api/career/runs/{run_id}/advance", json={"step": "auto"}
        ).json()
        assert body["run"]["week"] > 0
        assert body["weeks"], "진행했는데 주차 로그가 비었다"

    def test_a_pending_event_blocks_advancing(self, client: TestClient) -> None:
        run_id = _start(client, mode="weekly")["run"]["id"]
        for _ in range(40):
            body = client.post(
                f"/api/career/runs/{run_id}/advance", json={"step": "auto"}
            ).json()
            if body.get("pendingEvent"):
                break
        else:
            pytest.skip("40번 진행 동안 이벤트가 안 떴다")
        blocked = client.post(
            f"/api/career/runs/{run_id}/advance", json={"step": "auto"}
        )
        assert blocked.status_code == 409, "대기 이벤트가 진행을 막지 않는다 (§11-2)"
        assert "선택" in blocked.json()["detail"]

    def test_choosing_without_an_event_is_refused(self, client: TestClient) -> None:
        run_id = _start(client)["run"]["id"]
        response = client.post(
            f"/api/career/runs/{run_id}/choices", json={"choice": "무엇이든"}
        )
        assert response.status_code == 409

    def test_the_response_hides_internal_numbers(self, client: TestClient) -> None:
        # 확률·위험도가 새면 그것만으로 최적해가 드러난다 (§11-14).
        run_id = _start(client, mode="weekly")["run"]["id"]
        for _ in range(40):
            body = client.post(
                f"/api/career/runs/{run_id}/advance", json={"step": "auto"}
            ).json()
            if body.get("pendingEvent"):
                choice = body["pendingEvent"]["choices"][0]
                assert set(choice) == {"code", "label"}
                return
        pytest.skip("40번 진행 동안 이벤트가 안 떴다")


class TestOwnership:
    def test_someone_elses_run_is_404(
        self, client: TestClient, repository: MemoryRepository
    ) -> None:
        stranger = make_run(seed=3).evolve(id=99, user_id=OTHER)
        repository.runs[99] = stranger
        for call in (
            lambda: client.post("/api/career/runs/99/advance", json={"step": "auto"}),
            lambda: client.get("/api/career/runs/99/log"),
            lambda: client.get("/api/career/runs/99/news"),
            lambda: client.delete("/api/career/runs/99"),
        ):
            assert call().status_code == 404


class TestLogAndNews:
    def test_the_log_paginates(self, client: TestClient) -> None:
        run_id = _start(client, mode="weekly")["run"]["id"]
        for _ in range(5):
            client.post(f"/api/career/runs/{run_id}/advance", json={"step": "auto"})
        page = client.get(f"/api/career/runs/{run_id}/log?limit=3").json()
        assert len(page["entries"]) <= 3
        assert page["total"] >= len(page["entries"])

    def test_news_carries_a_crowd_reaction(self, client: TestClient) -> None:
        run_id = _start(client, mode="weekly")["run"]["id"]
        for _ in range(30):
            body = client.post(
                f"/api/career/runs/{run_id}/advance", json={"step": "auto"}
            ).json()
            if body.get("pendingEvent"):
                client.post(
                    f"/api/career/runs/{run_id}/choices",
                    json={"choice": body["pendingEvent"]["choices"][0]["code"]},
                )
        page = client.get(f"/api/career/runs/{run_id}/news").json()
        if not page["items"]:
            pytest.skip("아직 남을 만한 사건이 없었다")
        item = page["items"][0]
        assert item["headline"] and item["crowdLine"]
        assert item["mood"] in {"roar", "jeer", "split", "hush", "chant"}


class TestRetire:
    def test_retiring_closes_the_career(self, client: TestClient) -> None:
        run_id = _start(client)["run"]["id"]
        body = client.delete(f"/api/career/runs/{run_id}").json()
        assert body["run"]["endReason"] == "player"
        assert client.get("/api/career/runs/current").json() is None
