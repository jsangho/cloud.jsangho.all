"""`CAREER_V3_WRITES_ENABLED` — **닫혀 있으면 세이브가 한 바이트도 안 바뀐다.**

세이브 쓰기는 항상 v3 다(`dump`). 그래서 게이트가 잠긴 동안에는 v1·v2 커리어의 쓰기도
막혀야 하고, 조회는 그대로 돌아야 한다.

가짜 유스케이스를 쓰지 않는다. **실제 라우터 → 실제 배선(`get_career_repository`) →
실제 유스케이스 → 실제 어댑터**를 지나고, 세션만 호출을 기록하는 가짜로 바꾼다. 그래야
"환경변수 → 어댑터 → 503" 이 한 번에 검증되고, DB 없는 CI 에서도 돈다. 진짜 행의
불변(`md5(world::text)`)은 `test_career_v3_write_gate_pg` 가 본다.
"""

from __future__ import annotations

import ast
import copy
import json
import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.sql import Select

from core.matrix.grid_oracle_database_manager import get_db
from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from kayfabe.adapter.inbound.api.v1.career_sandbox_router import career_sandbox_router
from kayfabe.adapter.outbound.orm.career_sandbox_orm import (
    SandboxCareerModel,
    SandboxCareerRequestModel,
)
from kayfabe.adapter.outbound.pg.career_world_codec import SCHEMA_VERSION, dump, load
from kayfabe.adapter.outbound.pg.sandbox_career_pg_repository import (
    SandboxCareerPgRepository,
)
from kayfabe.app.ports.output.sandbox_career_repository import (
    CareerSaveRefusedError,
    CareerSaveRejectedError,
    CareerV3WritesDisabledError,
    CorruptSaveError,
)
from kayfabe.dependencies.career_sandbox_provider import (
    CAREER_V3_WRITES_ENV,
    career_v3_writes_enabled,
)
from kayfabe.dependencies.data_center_provider import get_data_center_repository
from kayfabe.domain.services import career_engine as engine
from kayfabe.domain.services import career_season as season_rules
from kayfabe.domain.services.career_world import Balance, Phase

_BASE = "/api/sandbox/careers"
_TESTS = Path(__file__).resolve().parents[2]
_KAYFABE = _TESTS.parent
_DISABLED = "career_v3_writes_disabled"
_NEW_CAREER = {"name": "Ho", "style": "테크니션", "age": 24}
_ACT = {"action": "휴식"}

#: 잠긴 값들. 앞뒤 공백·대소문자·다른 참 표현도 **닫힘**이다.
_CLOSED = ("", " ", "false", "False", "0", "1", "yes", "on", "TRUE", " true", "true ")


def _fixture(version: int) -> dict[str, Any]:
    """옛 판본 세이브. **시즌 중으로 돌린다** — 골든은 결산 대기로 끝나서 주차 진행이
    저장 전에 409 로 튕기고, 그러면 게이트를 시험하지 못한다."""
    path = _TESTS / "fixtures" / f"career_golden_v{version}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))[f"final_v{version}"]
    return {**raw, "phase": str(Phase.IN_SEASON)}


def _fresh_world():
    return engine.create_world(player="Ho", style="테크니션", seed=7, age=24)


def _fresh() -> dict[str, Any]:
    return dump(_fresh_world())


def _pending() -> dict[str, Any]:
    raw = _fresh()
    raw["pending"] = [
        {
            "id": "evt",
            "kind": "retirement_thought",
            "season": 1,
            "week": 1,
            "subject": "Ho",
            "other": None,
            "headline": "거취를 묻는다",
            "detail": "",
            "choices": [
                {"code": "stay", "label": "계속한다", "enabled": True, "note": ""}
            ],
        }
    ]
    return raw


def _settlement() -> dict[str, Any]:
    return dump(replace(_fresh_world(), phase=Phase.SETTLEMENT))


def _next_season() -> dict[str, Any]:
    return dump(season_rules.settle(load(_settlement()), balance=Balance()))


#: 쓰기 라우트 전부. **각 세계는 그 라우트가 저장 직전까지 가는 상태다** — 입력·단계
#: 오류로 먼저 튕기면 게이트를 시험한 것이 아니다.
_WRITES: dict[tuple[str, str], tuple[Any, dict[str, Any] | None]] = {
    ("POST", ""): (None, _NEW_CAREER),
    ("POST", "/1/actions"): (_fresh, _ACT),
    ("POST", "/1/advance"): (_fresh, None),
    ("POST", "/1/events/evt"): (_pending, {"choice": "stay"}),
    ("POST", "/1/settle"): (_settlement, None),
    ("POST", "/1/next-season"): (_next_season, None),
}


#: 파라미터 ID. **값에서 만들지 않는다** — 함수가 든 값을 `str()` 하면 메모리 주소가 ID에
#: 들어가 실행마다 달라지고, 실행 간 결과를 테스트 단위로 대조할 수 없다.
_WRITE_IDS = tuple(
    f"{method}-{path.removeprefix('/1/').replace('/', '-') or 'create'}"
    for method, path in _WRITES
)


def _row(raw: dict[str, Any]) -> SandboxCareerModel:
    return SandboxCareerModel(
        id=1,
        user_id=1,
        player_name=raw["player"],
        seed=raw["seed"],
        season=raw["season"],
        week=raw["week"],
        phase=raw["phase"],
        world=raw,
    )


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalar_one_or_none(self) -> Any:
        return self._rows[0] if self._rows else None

    def scalars(self) -> _Result:
        return self

    def all(self) -> list[Any]:
        return self._rows


class RecordingSession:
    """어댑터가 세션에 한 일을 적어 둔다. **`writes` 가 비어 있으면 안 쓴 것이다.**"""

    def __init__(self, *rows: SandboxCareerModel) -> None:
        self.rows = list(rows)
        self.receipts: list[SandboxCareerRequestModel] = []
        self.writes: list[str] = []

    async def execute(self, stmt: Any) -> _Result:
        if not isinstance(stmt, Select):
            self.writes.append("execute")
            return _Result([])
        if stmt.column_descriptions[0]["entity"] is SandboxCareerModel:
            return _Result(self.rows)
        # 어댑터의 WHERE 를 따른다 — 다른 요청의 영수증을 돌려주면 재전송처럼 보인다.
        params = stmt.compile().params
        wanted = next(v for k, v in params.items() if k.startswith("request_id"))
        return _Result([r for r in self.receipts if r.request_id == wanted])

    def add(self, obj: Any) -> None:
        self.writes.append("add")
        if isinstance(obj, SandboxCareerRequestModel):
            self.receipts.append(obj)
        else:
            obj.id = len(self.rows) + 1
            self.rows.append(obj)

    async def flush(self) -> None:
        self.writes.append("flush")

    async def commit(self) -> None:
        self.writes.append("commit")


class _NoRoster:
    """명부가 비면 유스케이스가 기본 로스터로 돌아간다 — 생성이 저장까지 간다."""

    async def list_wrestlers(self) -> list:
        return []

    async def list_title_acquisitions(self) -> list:
        return []


def _claims() -> TokenPayload:
    return TokenPayload(
        sub="1",
        aud="jsangho-api",
        exp=9999999999,
        iat=0,
        jti="jti",
    )


def _client(session: RecordingSession) -> TestClient:
    """`get_career_use_case`·`get_career_repository` 는 오버라이드하지 않는다."""
    app = FastAPI()
    app.include_router(career_sandbox_router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_data_center_repository] = _NoRoster
    app.dependency_overrides[get_current_user] = _claims
    return TestClient(app)


def _key(suffix: str = "a") -> dict[str, str]:
    return {"Idempotency-Key": f"gate-request-{suffix}"}


def _assert_blocked(response: Any) -> None:
    assert response.status_code == 503, response.text
    body = response.json()
    assert body["code"] == _DISABLED
    assert isinstance(body["detail"], str) and body["detail"]
    assert set(body) == {"detail", "code"}


@pytest.fixture(autouse=True)
def _closed_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """개발자 셸이나 `.env` 에 값이 있어도 테스트는 미설정에서 시작한다."""
    monkeypatch.delenv(CAREER_V3_WRITES_ENV, raising=False)


# ── 값 해석 ──────────────────────────────────────────────────────


def test_unset_is_closed() -> None:
    assert career_v3_writes_enabled() is False


@pytest.mark.parametrize("value", _CLOSED)
def test_anything_but_exact_true_is_closed(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(CAREER_V3_WRITES_ENV, value)
    assert career_v3_writes_enabled() is False


def test_exact_true_is_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CAREER_V3_WRITES_ENV, "true")
    assert career_v3_writes_enabled() is True


@pytest.mark.parametrize("value", (None, *_CLOSED))
def test_closed_values_block_a_real_request(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is not None:
        monkeypatch.setenv(CAREER_V3_WRITES_ENV, value)
    session = RecordingSession()
    _assert_blocked(_client(session).post(_BASE, json=_NEW_CAREER))
    assert session.rows == [] and session.writes == []


def test_true_allows_the_same_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CAREER_V3_WRITES_ENV, "true")
    session = RecordingSession()
    response = _client(session).post(_BASE, json=_NEW_CAREER)
    assert response.status_code == 200, response.text
    assert [r.world["version"] for r in session.rows] == [SCHEMA_VERSION]
    assert "commit" in session.writes


# ── 차단: 모든 쓰기 라우트 ───────────────────────────────────────


def test_write_ids_are_stable_and_distinct() -> None:
    assert _WRITE_IDS == (
        "POST-create",
        "POST-actions",
        "POST-advance",
        "POST-events-evt",
        "POST-settle",
        "POST-next-season",
    )


def test_no_collected_test_id_carries_a_memory_address(
    request: pytest.FixtureRequest,
) -> None:
    """실행 간 대조가 깨지지 않게. 메모리 주소가 든 ID 는 돌릴 때마다 다른 테스트가 된다."""
    addressed = [
        item.nodeid
        for item in request.session.items
        if re.search(r" at 0x[0-9a-f]+", item.nodeid)
    ]
    assert addressed == []


def test_the_table_covers_every_write_route() -> None:
    """**쓰기 라우트가 늘면 여기서 터진다** — 새 경로가 이 파일을 비켜 가지 못하게."""
    declared = {
        (method, route.path.removeprefix("/sandbox/careers"))
        for route in career_sandbox_router.routes
        if isinstance(route, APIRoute)
        for method in route.methods - {"GET", "HEAD"}
    }
    assert declared == {
        ("POST", ""),
        ("POST", "/{career_id}/actions"),
        ("POST", "/{career_id}/advance"),
        ("POST", "/{career_id}/events/{event_id}"),
        ("POST", "/{career_id}/settle"),
        ("POST", "/{career_id}/next-season"),
    }


@pytest.mark.parametrize(("route", "spec"), _WRITES.items(), ids=_WRITE_IDS)
def test_every_write_route_is_blocked_without_touching_the_session(
    route: tuple[str, str], spec: tuple[Any, dict[str, Any] | None]
) -> None:
    make, body = spec
    original = make() if make else None
    rows = (_row(copy.deepcopy(original)),) if make else ()
    session = RecordingSession(*rows)

    response = _client(session).post(_BASE + route[1], json=body, headers=_key())

    _assert_blocked(response)
    assert session.writes == [] and session.receipts == []
    if make:
        assert session.rows[0].world == original


@pytest.mark.parametrize(("route", "spec"), _WRITES.items(), ids=_WRITE_IDS)
def test_every_write_route_reaches_storage_when_open(
    monkeypatch: pytest.MonkeyPatch,
    route: tuple[str, str],
    spec: tuple[Any, dict[str, Any] | None],
) -> None:
    """위 차단 테스트가 **입력 오류로 튕긴 것이 아님**을 증명하는 짝이다."""
    monkeypatch.setenv(CAREER_V3_WRITES_ENV, "true")
    make, body = spec
    session = RecordingSession(*((_row(make()),) if make else ()))

    response = _client(session).post(_BASE + route[1], json=body, headers=_key())

    assert response.status_code == 200, response.text
    assert session.rows[0].world["version"] == SCHEMA_VERSION


@pytest.mark.parametrize("version", (1, 2))
@pytest.mark.parametrize(("path", "body"), (("/1/actions", _ACT), ("/1/advance", None)))
def test_old_saves_are_not_converted_while_closed(
    version: int, path: str, body: dict[str, Any] | None
) -> None:
    original = _fixture(version)
    session = RecordingSession(_row(copy.deepcopy(original)))

    _assert_blocked(_client(session).post(_BASE + path, json=body, headers=_key()))

    world = session.rows[0].world
    assert world == original and world["version"] == version
    assert "matches" not in world and "match_records_since" not in world
    assert session.writes == []


@pytest.mark.parametrize("version", (1, 2))
def test_old_saves_convert_only_when_open(
    monkeypatch: pytest.MonkeyPatch, version: int
) -> None:
    """닫힌 동안 막은 것이 실제로 일어날 변환이었음을 보인다."""
    monkeypatch.setenv(CAREER_V3_WRITES_ENV, "true")
    session = RecordingSession(_row(_fixture(version)))

    response = _client(session).post(f"{_BASE}/1/actions", json=_ACT, headers=_key())

    assert response.status_code == 200, response.text
    assert session.rows[0].world["version"] == SCHEMA_VERSION
    assert session.rows[0].world["match_records_since"] is not None


def test_a_match_record_is_never_appended_while_closed() -> None:
    session = RecordingSession(_row(_fresh()))

    _assert_blocked(_client(session).post(f"{_BASE}/1/advance", headers=_key()))

    world = session.rows[0].world
    assert world["matches"] == [] and world["week"] == 1
    assert session.receipts == []


def test_a_match_record_is_appended_when_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(CAREER_V3_WRITES_ENV, "true")
    session = RecordingSession(_row(_fresh()))

    response = _client(session).post(f"{_BASE}/1/advance", headers=_key())

    assert response.status_code == 200, response.text
    assert len(session.rows[0].world["matches"]) == 1


# ── 요청으로는 열 수 없다 ────────────────────────────────────────


def test_the_client_cannot_open_the_gate() -> None:
    session = RecordingSession()
    response = _client(session).post(
        _BASE,
        params={"CAREER_V3_WRITES_ENABLED": "true", "v3_writes_enabled": "true"},
        json={**_NEW_CAREER, "v3WritesEnabled": True, CAREER_V3_WRITES_ENV: "true"},
        headers={CAREER_V3_WRITES_ENV: "true", "X-V3-Writes-Enabled": "true"},
        cookies={CAREER_V3_WRITES_ENV: "true"},
    )
    _assert_blocked(response)
    assert session.rows == [] and session.writes == []


# ── 저장소 직접 호출 ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_adapter_is_closed_unless_told_otherwise() -> None:
    """**기본값이 닫힘이다** — 배선을 거치지 않고 어댑터를 만들어도 쓰지 못한다."""
    session = RecordingSession(_row(_fresh()))
    repository = SandboxCareerPgRepository(session)  # type: ignore[arg-type]
    world = _fresh_world()

    with pytest.raises(CareerV3WritesDisabledError):
        await repository.create(user_id=1, player_name="Ho", seed=7, state=world)
    with pytest.raises(CareerV3WritesDisabledError):
        await repository.save(user_id=1, career_id=1, state=world)

    assert session.writes == [] and len(session.rows) == 1


@pytest.mark.parametrize("error_type", (ValueError, LookupError))
def test_the_error_cannot_fall_into_a_client_error_branch(error_type: type) -> None:
    assert not issubclass(CareerV3WritesDisabledError, error_type)


# ── 조회는 계속 된다 ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "make",
    (lambda: _fixture(1), lambda: _fixture(2), _fresh),
    ids=("v1", "v2", "v3"),
)
@pytest.mark.parametrize("path", ("/1", "/1/log", "/1/matches"))
def test_reads_work_and_write_nothing_while_closed(make: Any, path: str) -> None:
    original = make()
    session = RecordingSession(_row(copy.deepcopy(original)))

    response = _client(session).get(_BASE + path)

    assert response.status_code == 200, response.text
    assert session.rows[0].world == original
    assert session.writes == []


def test_listing_works_while_closed() -> None:
    row = _row(_fixture(1))
    row.created_at = row.updated_at = datetime(2026, 11, 6, tzinfo=UTC)
    session = RecordingSession(row)

    response = _client(session).get(_BASE)

    assert response.status_code == 200, response.text
    assert [c["id"] for c in response.json()] == [1]
    assert session.writes == []


# ── 멱등과의 관계 ────────────────────────────────────────────────


def test_a_blocked_request_leaves_no_receipt_and_can_be_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """실패는 영수증을 남기지 않는다 — 열린 뒤 **같은 키**가 정상 적용된다."""
    session = RecordingSession(_row(_fresh()))
    client = _client(session)

    _assert_blocked(client.post(f"{_BASE}/1/actions", json=_ACT, headers=_key()))
    monkeypatch.setenv(CAREER_V3_WRITES_ENV, "true")
    response = client.post(f"{_BASE}/1/actions", json=_ACT, headers=_key())

    assert response.status_code == 200, response.text
    assert len(session.receipts) == 1


def test_a_finished_request_replays_without_writing_while_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """닫히기 전에 끝난 요청의 재전송은 저장된 응답을 받는다. **쓰기가 없다.**

    차단할 이유가 없다 — 이미 일어난 일의 응답을 다시 읽는 것이고, 여기서 503 을
    주면 응답을 놓친 클라이언트는 성공한 요청을 실패로 알게 된다.
    """
    session = RecordingSession(_row(_fresh()))
    client = _client(session)
    monkeypatch.setenv(CAREER_V3_WRITES_ENV, "true")
    first = client.post(f"{_BASE}/1/actions", json=_ACT, headers=_key("old"))
    assert first.status_code == 200, first.text

    monkeypatch.delenv(CAREER_V3_WRITES_ENV)
    session.writes.clear()
    world = copy.deepcopy(session.rows[0].world)

    replayed = client.post(f"{_BASE}/1/actions", json=_ACT, headers=_key("old"))
    fresh = client.post(f"{_BASE}/1/actions", json=_ACT, headers=_key("new"))

    assert replayed.status_code == 200 and replayed.json() == first.json()
    _assert_blocked(fresh)
    assert session.writes == [] and session.rows[0].world == world


# ── 구조: 게이트를 비켜 가는 저장 경로가 없다 ────────────────────


def _production_modules() -> list[tuple[Path, ast.Module]]:
    found = []
    for path in sorted(_KAYFABE.rglob("*.py")):
        if "tests" in path.relative_to(_KAYFABE).parts:
            continue
        found.append((path, ast.parse(path.read_text(encoding="utf-8"))))
    return found


def _importers(*names: str) -> set[str]:
    """그 이름을 import 하는 운영 모듈의 상대 경로."""
    hits = set()
    for path, tree in _production_modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(
                alias.name in names for alias in node.names
            ):
                hits.add(path.relative_to(_KAYFABE).as_posix())
    return hits


_ADAPTER = "adapter/outbound/pg/sandbox_career_pg_repository.py"


def test_only_the_adapter_imports_the_save_encoder() -> None:
    assert _importers("dump", "career_world_codec") == {_ADAPTER}


def test_only_the_adapter_touches_the_save_models() -> None:
    assert _importers("SandboxCareerModel", "SandboxCareerRequestModel") == {_ADAPTER}


def test_the_adapter_encodes_in_one_gated_place() -> None:
    tree = ast.parse((_KAYFABE / _ADAPTER).read_text(encoding="utf-8"))
    encoder = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_encode"
    )

    def calls(root: ast.AST, name: str) -> list[ast.Call]:
        return [
            n
            for n in ast.walk(root)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == name
        ]

    assert len(calls(tree, "dump")) == len(calls(encoder, "dump")) == 1
    # `create`·`save` 둘 다 첫 문장에서 게이트를 지난다.
    for method in ("create", "save"):
        fn = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == method
        )
        first = fn.body[0]
        assert isinstance(first, ast.Assign), method
        assert isinstance(first.value, ast.Call)
        assert isinstance(first.value.func, ast.Attribute)
        assert first.value.func.attr == "_encode", method


# ── 저장 거부: 규칙에 어긋난 경기 기록은 커밋 전에 막는다 ─────────


def _world_with_bad_record() -> Any:
    """도메인 버그를 흉내 낸다. 기록은 있는데 `rating` 이 글자다."""
    world = engine.advance_week(_fresh_world(), balance=Balance()).state
    assert world.matches
    bad = replace(world.matches[0], rating="high")  # type: ignore[arg-type]
    return replace(world, matches=(bad,))


@pytest.mark.asyncio
async def test_the_adapter_rejects_a_bad_record_before_touching_the_session() -> None:
    session = RecordingSession(_row(_fresh()))
    repository = SandboxCareerPgRepository(
        session,  # type: ignore[arg-type]
        v3_writes_enabled=True,
    )
    world = _world_with_bad_record()

    with pytest.raises(CareerSaveRejectedError):
        await repository.save(user_id=1, career_id=1, state=world)
    with pytest.raises(CareerSaveRejectedError):
        await repository.create(user_id=1, player_name="Ho", seed=7, state=world)

    assert session.writes == [] and len(session.rows) == 1


def test_a_rejected_save_is_reported_and_leaves_the_last_good_save(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(CAREER_V3_WRITES_ENV, "true")
    world = _world_with_bad_record()
    monkeypatch.setattr(
        engine,
        "advance_week",
        lambda state, *, balance: SimpleNamespace(state=world, report=None),
    )
    original = _fresh()
    session = RecordingSession(_row(copy.deepcopy(original)))

    response = _client(session).post(f"{_BASE}/1/advance", headers=_key())

    assert response.status_code == 500, response.text
    assert response.json()["code"] == "career_save_rejected"
    assert isinstance(response.json()["detail"], str)
    assert session.rows[0].world == original
    assert session.writes == [] and session.receipts == []


def test_the_closed_gate_answers_before_record_rules() -> None:
    """닫힘이 먼저다 — 쓰기가 닫혔는데 규칙 오류로 보고되면 원인이 흐려진다."""
    session = RecordingSession()
    repository = SandboxCareerPgRepository(session)  # type: ignore[arg-type]

    with pytest.raises(CareerV3WritesDisabledError):
        repository._encode(_world_with_bad_record())


def test_save_errors_are_not_read_errors() -> None:
    assert not issubclass(CareerSaveRejectedError, CorruptSaveError)
    assert not issubclass(CareerV3WritesDisabledError, CorruptSaveError)
    assert issubclass(CareerSaveRejectedError, CareerSaveRefusedError)
    assert issubclass(CareerV3WritesDisabledError, CareerSaveRefusedError)
