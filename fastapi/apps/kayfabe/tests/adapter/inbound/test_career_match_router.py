"""경기 기록 조회 API(Phase 1 P1). **저장된 기록을 그대로 읽기만 하는지** 고정한다.

여기서 보는 것은 넷이다.

1. **목록·상세의 모양** — camelCase, 최신 경기 우선, 시즌 필터, 페이지네이션,
   참가자 순서 보존, 핀폴이 아닌 경기의 `scorer`·`pinned` = `null`.
2. **기록이 없는 경기의 사유** — `before_records` · `trimmed` · `unexplained`,
   그리고 **경기가 있었다는 증거(로그의 `match` 줄)가 없으면 `null`.** 쉰 주차를
   물었을 때 사유를 지어내지 않는다.
3. **소유권** — 남의 커리어와 없는 커리어는 같은 404 이고, 경기 쪽 사유 칸이 없다.
4. **조회가 아무것도 쓰지 않는다** — 저장·잠금 호출 0회, 세계 지문 불변. 옛 판본
   (v1·v2) 세이브는 메모리에서만 v3 로 올라가고 원본 dict 는 그대로다.

**골든 궤적(`test_career_golden.run_trajectory`)을 입력으로 쓴다** — 엔진이 실제로
만든 기록 40건(태그 18 · 타이틀 17 · 싱글 5, 부상 3건)이다. 기록을 손으로 지으면
엔진과 어긋난 모양을 테스트하게 된다.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from kayfabe.adapter.inbound.api.v1.career_sandbox_router import career_sandbox_router
from kayfabe.adapter.outbound.pg.career_world_codec import dump, load
from kayfabe.app.use_cases.career_sandbox_interactor import CareerSandboxInteractor
from kayfabe.dependencies.career_sandbox_provider import get_career_use_case
from kayfabe.domain.services import career_engine as engine
from kayfabe.domain.services import career_match_record as records
from kayfabe.domain.services.career_world import STATE_FIELDS, Balance, WorldState

_BASE = "/api/sandbox/careers"
_OWNER = "1"
_STRANGER = "2"

_TESTS = Path(__file__).resolve().parents[2]
_GOLDEN_PATH = _TESTS / "domain" / "services" / "test_career_golden.py"
_V1_FIXTURE = _TESTS / "fixtures" / "career_golden_v1.json"
_V2_FIXTURE = _TESTS / "fixtures" / "career_golden_v2.json"


def _golden_module():
    spec = importlib.util.spec_from_file_location("_career_golden_p1", _GOLDEN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def golden() -> WorldState:
    _, world = _golden_module().run_trajectory()
    assert len(world.matches) == 40
    return world


# ── 하네스 ────────────────────────────────────────────────────────


class SpyRepository:
    """커리어 1 하나를 든다. **쓰기·잠금 호출을 센다** — 조회 경로에서 0이어야 한다."""

    def __init__(self, world: WorldState, *, owner: int = 1) -> None:
        self.world = world
        self.owner = owner
        self.saves = 0
        self.locks = 0

    async def create(self, **_: Any) -> int:  # pragma: no cover - 안 쓴다
        raise AssertionError("조회 테스트에서 생성하지 않는다")

    async def list_for_user(self, user_id: int) -> list:
        return []

    async def load(self, *, user_id: int, career_id: int) -> WorldState | None:
        if career_id != 1 or user_id != self.owner:
            return None
        return self.world

    async def load_for_update(self, **_: Any) -> WorldState | None:
        self.locks += 1
        raise AssertionError("조회가 행을 잠갔다")

    async def find_receipt(self, **_: Any):
        raise AssertionError("조회가 영수증을 찾았다")

    async def save(self, **_: Any) -> None:
        self.saves += 1
        raise AssertionError("조회가 세이브를 썼다")


class RawSpyRepository(SpyRepository):
    """세이브를 **dict 로** 들고 매번 진짜 코덱으로 되살린다 — PG 어댑터와 같은 경로.

    옛 판본 업그레이드가 원본을 건드리는지 보려고 쓴다.
    """

    def __init__(self, raw: dict[str, Any]) -> None:
        # 세계를 미리 되살리지 않는다 — 깨진 세이브도 들 수 있어야 한다.
        self.raw = raw
        self.owner = 1
        self.saves = 0
        self.locks = 0

    async def load(self, *, user_id: int, career_id: int) -> WorldState | None:
        if career_id != 1 or user_id != self.owner:
            return None
        return load(self.raw)


def _claims(sub: str) -> TokenPayload:
    return TokenPayload(
        sub=sub,
        aud="jsangho-api",
        exp=9999999999,
        iat=0,
        jti="jti",
        roles=["user"],
        platform="web",
        device_id="d1",
    )


def _client(repo: SpyRepository, *, sub: str | None = _OWNER) -> TestClient:
    app = FastAPI()
    app.include_router(career_sandbox_router, prefix="/api")
    app.dependency_overrides[get_career_use_case] = lambda: CareerSandboxInteractor(
        repository=repo, balance=Balance()
    )
    if sub is not None:
        app.dependency_overrides[get_current_user] = lambda: _claims(sub)
    return TestClient(app)


def _list(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    response = client.get(f"{_BASE}/1/matches", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _detail(client: TestClient, match_id: str) -> dict[str, Any]:
    response = client.get(f"{_BASE}/1/matches/{match_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _first(world: WorldState, predicate) -> records.MatchRecord:
    return next(m for m in world.matches if predicate(m))


def _two_seasons(world: WorldState) -> WorldState:
    """앞 20건을 시즌 1, 뒤 20건을 시즌 2 로 다시 붙인다(내용은 그대로)."""
    relabeled = tuple(
        replace(
            m,
            season=1 + i // 20,
            week=1 + i % 20,
            id=records.match_id(season=1 + i // 20, week=1 + i % 20),
        )
        for i, m in enumerate(world.matches)
    )
    return replace(world, matches=relabeled)


# ── 인증 ──────────────────────────────────────────────────────────


def test_anonymous_callers_are_rejected(golden: WorldState) -> None:
    client = _client(SpyRepository(golden), sub=None)

    assert client.get(f"{_BASE}/1/matches").status_code == 401
    assert client.get(f"{_BASE}/1/matches/s1w1:p").status_code == 401


# ── 1. 목록 ───────────────────────────────────────────────────────


def test_list_returns_every_stored_record_as_camel_case(golden: WorldState) -> None:
    items = _list(_client(SpyRepository(golden)), limit=200)

    assert len(items) == len(golden.matches) == 40
    first = items[0]
    assert set(first) == {
        "id",
        "season",
        "week",
        "brand",
        "kind",
        "reason",
        "teams",
        "winnerSide",
        "title",
        "titleChanged",
        "finish",
        "rating",
        "hasDetail",
    }
    assert all(item["hasDetail"] is True for item in items)


def test_list_copies_stored_values_without_recomputing(golden: WorldState) -> None:
    items = {i["id"]: i for i in _list(_client(SpyRepository(golden)), limit=200)}

    for m in golden.matches:
        item = items[m.id]
        assert (item["season"], item["week"]) == (m.season, m.week)
        assert item["brand"] == m.brand
        assert (item["kind"], item["reason"]) == (m.kind, m.reason)
        assert item["teams"] == [list(m.teams[0]), list(m.teams[1])]
        assert item["winnerSide"] == m.winner_side
        assert (item["title"], item["titleChanged"]) == (m.title, m.title_changed)
        assert (item["finish"], item["rating"]) == (m.finish, m.rating)


def test_list_is_newest_first(golden: WorldState) -> None:
    items = _list(_client(SpyRepository(_two_seasons(golden))), limit=200)

    keys = [(i["season"], i["week"]) for i in items]
    assert keys == sorted(keys, reverse=True)
    assert len(set(keys)) == len(keys)
    assert items[0]["season"] == 2


def test_season_filter(golden: WorldState) -> None:
    client = _client(SpyRepository(_two_seasons(golden)))

    season_2 = _list(client, season=2, limit=200)
    season_1 = _list(client, season=1, limit=200)

    assert len(season_2) == len(season_1) == 20
    assert {i["season"] for i in season_2} == {2}
    assert {i["season"] for i in season_1} == {1}
    assert _list(client, season=3) == []


def test_limit_and_offset_page_through_the_same_order(golden: WorldState) -> None:
    client = _client(SpyRepository(golden))
    everything = [i["id"] for i in _list(client, limit=200)]

    page_1 = [i["id"] for i in _list(client, limit=7, offset=0)]
    page_2 = [i["id"] for i in _list(client, limit=7, offset=7)]
    tail = [i["id"] for i in _list(client, limit=7, offset=35)]

    assert page_1 == everything[:7]
    assert page_2 == everything[7:14]
    assert tail == everything[35:]
    assert len(tail) == 5
    assert _list(client, limit=7, offset=40) == []


def test_paging_applies_after_the_season_filter(golden: WorldState) -> None:
    client = _client(SpyRepository(_two_seasons(golden)))

    page = _list(client, season=1, limit=5, offset=5)

    assert [(i["season"], i["week"]) for i in page] == [
        (1, w) for w in range(15, 10, -1)
    ]


@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 201}, {"offset": -1}, {"season": 0}]
)
def test_out_of_range_query_is_422(golden: WorldState, params: dict) -> None:
    response = _client(SpyRepository(golden)).get(f"{_BASE}/1/matches", params=params)

    assert response.status_code == 422


def test_a_career_without_records_lists_nothing() -> None:
    world = engine.create_world(player="Ho", style="테크니션", seed=7, age=24)

    response = _client(SpyRepository(world)).get(f"{_BASE}/1/matches")

    assert response.status_code == 200
    assert response.json() == []


# ── 2. 상세 ───────────────────────────────────────────────────────


def _state(values: tuple[int, ...]) -> dict[str, int]:
    camel = {"win_streak": "winStreak", "losing_streak": "losingStreak"}
    return {camel.get(f, f): v for f, v in zip(STATE_FIELDS, values, strict=True)}


def _assert_participants(body: dict[str, Any], m: records.MatchRecord) -> None:
    assert [p["name"] for p in body["participants"]] == [p.name for p in m.participants]
    for got, want in zip(body["participants"], m.participants, strict=True):
        assert got["side"] == want.side
        assert got["power"] == {
            "skill": want.power[0],
            "draw": want.power[1],
            "body": want.power[2],
        }
        assert got["before"] == _state(want.before)
        assert got["after"] == _state(want.after)


def test_detail_returns_the_stored_record(golden: WorldState) -> None:
    m = golden.matches[-1]

    body = _detail(_client(SpyRepository(golden)), m.id)

    assert body["id"] == m.id
    assert (body["season"], body["week"], body["brand"]) == (m.season, m.week, m.brand)
    assert (body["kind"], body["reason"]) == (m.kind, m.reason)
    assert (body["title"], body["titleChanged"]) == (m.title, m.title_changed)
    assert body["teams"] == [list(m.teams[0]), list(m.teams[1])]
    assert body["winnerSide"] == m.winner_side
    assert body["probability"] == m.probability
    assert (body["finish"], body["rating"]) == (m.finish, m.rating)
    assert (body["finisher"], body["scorer"], body["pinned"]) == (
        m.finisher,
        m.scorer,
        m.pinned,
    )
    assert body["popularityDelta"] == m.popularity_delta
    _assert_participants(body, m)


def test_single_match_has_two_participants_in_order(golden: WorldState) -> None:
    m = _first(golden, lambda r: r.kind == "single")

    body = _detail(_client(SpyRepository(golden)), m.id)

    assert len(body["participants"]) == 2
    assert [p["side"] for p in body["participants"]] == [0, 1]
    _assert_participants(body, m)


def test_tag_match_has_four_participants_in_order(golden: WorldState) -> None:
    m = _first(golden, lambda r: r.kind == "tag")

    body = _detail(_client(SpyRepository(golden)), m.id)

    assert len(body["participants"]) == 4
    assert [p["side"] for p in body["participants"]] == [0, 0, 1, 1]
    assert body["teams"] == [list(m.teams[0]), list(m.teams[1])]
    # 엔진이 적용한 값 그대로다.
    _assert_participants(body, m)


def test_participants_with_the_same_name_are_not_merged(golden: WorldState) -> None:
    """이름으로 dict 를 만들면 한 칸이 사라진다. 응답은 목록이라 둘 다 남는다."""
    m = _first(golden, lambda r: r.kind == "tag")
    clash = replace(
        m,
        participants=(
            m.participants[0],
            replace(m.participants[1], name=m.participants[0].name),
            *m.participants[2:],
        ),
    )
    world = replace(golden, matches=(clash,))

    body = _detail(_client(SpyRepository(world)), m.id)

    assert len(body["participants"]) == 4
    assert body["participants"][0]["after"] == _state(m.participants[0].after)
    assert body["participants"][1]["after"] == _state(m.participants[1].after)


def test_non_pinfall_has_null_scorer_and_pinned(golden: WorldState) -> None:
    client = _client(SpyRepository(golden))
    non_pin = _first(golden, lambda r: r.finish != records.PINFALL)
    pin = _first(golden, lambda r: r.finish == records.PINFALL)

    body = _detail(client, non_pin.id)
    pin_body = _detail(client, pin.id)

    assert body["scorer"] is None and body["pinned"] is None
    assert "scorer" in body and "pinned" in body
    assert body["finisher"] == non_pin.finisher
    assert (pin_body["scorer"], pin_body["pinned"]) == (pin.scorer, pin.pinned)
    assert pin_body["scorer"] is not None


def test_injury_and_heat_are_returned(golden: WorldState) -> None:
    hurt = _first(golden, lambda r: r.injury is not None)
    heated = _first(golden, lambda r: len(r.heat) > 0)
    client = _client(SpyRepository(golden))

    hurt_body = _detail(client, hurt.id)
    heat_body = _detail(client, heated.id)

    assert hurt.injury is not None
    assert hurt_body["injury"] == {
        "kind": hurt.injury.kind,
        "severity": str(hurt.injury.severity),
        "season": hurt.injury.season,
        "week": hurt.injury.week,
        "weeksOut": hurt.injury.weeks_out,
        "recovered": hurt.injury.recovered,
        "recurrence": hurt.injury.recurrence,
        "permanent": hurt.injury.permanent,
    }
    assert heat_body["heat"] == [
        {"a": h.a, "b": h.b, "before": h.before, "after": h.after} for h in heated.heat
    ]
    healthy = _first(golden, lambda r: r.injury is None)
    assert _detail(client, healthy.id)["injury"] is None


# ── 3. 기록이 없는 경기 ───────────────────────────────────────────


def _missing(client: TestClient, match_id: str) -> dict[str, Any]:
    response = client.get(f"{_BASE}/1/matches/{match_id}")
    assert response.status_code == 404, response.text
    body = response.json()
    assert isinstance(body["detail"], str)
    return body


def test_a_match_before_records_began_is_before_records(golden: WorldState) -> None:
    """업그레이드한 커리어 — `since` 이전 경기는 로그에만 있다."""
    since = golden.matches[10]
    world = replace(
        golden,
        matches=golden.matches[10:],
        match_records_since=(since.season, since.week),
    )

    body = _missing(_client(SpyRepository(world)), golden.matches[0].id)

    assert body["missingReason"] == records.BEFORE_RECORDS


def test_a_match_older_than_the_cap_is_trimmed(golden: WorldState) -> None:
    world = replace(golden, matches=golden.matches[5:])

    body = _missing(_client(SpyRepository(world)), golden.matches[0].id)

    assert body["missingReason"] == records.TRIMMED


def test_a_match_the_log_knows_but_records_lack_is_unexplained(
    golden: WorldState,
) -> None:
    gone = golden.matches[20]
    world = replace(golden, matches=golden.matches[:20] + golden.matches[21:])

    body = _missing(_client(SpyRepository(world)), gone.id)

    assert body["missingReason"] == records.UNEXPLAINED


def test_a_rest_week_has_no_reason_even_when_older_than_records(
    golden: WorldState,
) -> None:
    """**지어내지 않는다.** `missing_reason` 에 쉰 주차를 그대로 물으면 `trimmed`
    가 나오지만, 로그에 그 주차 경기가 없으므로 사유는 `null` 이다."""
    played = {(e.season, e.week) for e in golden.log if e.kind == "match"}
    rest_week = next(w for w in range(1, 53) if (1, w) not in played)
    world = replace(golden, matches=tuple(m for m in golden.matches if m.week > 40))
    assert records.missing_reason(world, season=1, week=rest_week) == records.TRIMMED

    body = _missing(_client(SpyRepository(world)), f"s1w{rest_week}:p")

    assert body["missingReason"] is None


def test_a_match_whose_log_line_is_gone_has_no_reason(golden: WorldState) -> None:
    """로그도 잘린다(`MAX_LOG`). 경기가 있었다는 증거가 없으면 사유를 모른다."""
    first = golden.matches[0]
    world = replace(
        golden,
        matches=golden.matches[5:],
        log=tuple(
            e
            for e in golden.log
            if not (e.season, e.week) == (first.season, first.week)
        ),
    )

    body = _missing(_client(SpyRepository(world)), first.id)

    assert body["missingReason"] is None


@pytest.mark.parametrize("match_id", ["nope", "s9w9:p", "s1w1:x"])
def test_an_unknown_match_id_is_404_without_a_reason(
    golden: WorldState, match_id: str
) -> None:
    body = _missing(_client(SpyRepository(golden)), match_id)

    assert body["missingReason"] is None


def test_an_overlong_match_id_is_422(golden: WorldState) -> None:
    response = _client(SpyRepository(golden)).get(f"{_BASE}/1/matches/{'x' * 33}")

    assert response.status_code == 422


# ── 4. 소유권 ─────────────────────────────────────────────────────


_CAREER_404 = {"detail": "커리어를 찾을 수 없습니다"}


def test_a_missing_career_is_404_on_both_paths(golden: WorldState) -> None:
    client = _client(SpyRepository(golden))

    listed = client.get(f"{_BASE}/999/matches")
    detail = client.get(f"{_BASE}/999/matches/{golden.matches[0].id}")

    assert (listed.status_code, listed.json()) == (404, _CAREER_404)
    assert (detail.status_code, detail.json()) == (404, _CAREER_404)


def test_someone_elses_career_looks_exactly_like_a_missing_one(
    golden: WorldState,
) -> None:
    """같은 본문이어야 한다 — 다르면 "그 id 는 있다" 가 샌다. 경기 사유 칸도 없다."""
    client = _client(SpyRepository(golden), sub=_STRANGER)
    match_id = golden.matches[0].id

    listed = client.get(f"{_BASE}/1/matches")
    detail = client.get(f"{_BASE}/1/matches/{match_id}")
    missing = client.get(f"{_BASE}/999/matches/{match_id}")

    assert (listed.status_code, listed.json()) == (404, _CAREER_404)
    assert (detail.status_code, detail.json()) == (404, _CAREER_404)
    assert detail.json() == missing.json()


def test_a_corrupt_save_is_500_not_404() -> None:
    """못 읽는 세이브는 "없는 커리어" 가 아니다. 판본 번호도 새지 않는다."""
    raw = dump(engine.create_world(player="Ho", style="테크니션", seed=7, age=24))
    raw["version"] = 99
    app = FastAPI()
    app.include_router(career_sandbox_router, prefix="/api")
    app.dependency_overrides[get_career_use_case] = lambda: CareerSandboxInteractor(
        repository=RawSpyRepository(raw)
    )
    app.dependency_overrides[get_current_user] = lambda: _claims(_OWNER)
    client = TestClient(app, raise_server_exceptions=False)

    listed = client.get(f"{_BASE}/1/matches")
    detail = client.get(f"{_BASE}/1/matches/s1w1:p")

    assert listed.status_code == detail.status_code == 500
    assert "99" not in listed.text and "99" not in detail.text


# ── 5. 조회는 아무것도 쓰지 않는다 ────────────────────────────────


def _fingerprint(world: WorldState) -> str:
    return json.dumps(dump(world), sort_keys=True, ensure_ascii=False)


def _hit_every_read(client: TestClient, world: WorldState) -> None:
    _list(client)
    _list(client, season=1, limit=3, offset=2)
    for m in world.matches:
        _detail(client, m.id)
    client.get(f"{_BASE}/1/matches/s1w15:p")


def test_reads_leave_the_world_untouched(golden: WorldState) -> None:
    repo = SpyRepository(golden)
    before = _fingerprint(repo.world)

    _hit_every_read(_client(repo), golden)

    assert repo.saves == 0 and repo.locks == 0
    assert repo.world is golden
    assert _fingerprint(repo.world) == before
    # 세계가 움직이면 바뀌었을 칸들 — 주차·포인트·적용 키·인기도.
    assert (repo.world.season, repo.world.week) == (golden.season, golden.week)
    assert repo.world.applied == golden.applied


def _old_raw(path: Path, key: str) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))[key]


@pytest.mark.parametrize(
    ("path", "key", "version"),
    [(_V1_FIXTURE, "final_v1", 1), (_V2_FIXTURE, "final_v2", 2)],
)
def test_old_saves_are_read_without_saving_or_upgrading(
    path: Path, key: str, version: int
) -> None:
    raw = _old_raw(path, key)
    assert raw["version"] == version
    pristine = copy.deepcopy(raw)
    repo = RawSpyRepository(raw)
    client = _client(repo)
    world = load(raw)
    played = [e for e in world.log if e.kind == "match"]
    assert played

    listed = _list(client)
    body = _missing(
        client, records.match_id(season=played[0].season, week=played[0].week)
    )

    # 기록 도입 전 커리어 — 목록은 비고, 지난 경기는 "도입 전" 이다.
    assert listed == []
    assert body["missingReason"] == records.BEFORE_RECORDS
    # 원본 dict 는 판본까지 그대로, 저장·잠금 0회.
    assert raw == pristine
    assert raw["version"] == version
    assert repo.saves == 0 and repo.locks == 0
