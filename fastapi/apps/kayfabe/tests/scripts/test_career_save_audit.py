"""오프라인 감사 + 손상 세이브의 API 동작.

두 가지를 함께 고정한다.

1. **감사기가 손상을 잡고 정상을 건드리지 않는다.** 엔진이 만든 골든 궤적이 오탐
   기준이다 — 기록을 손으로 지으면 엔진과 어긋난 규칙을 시험하게 된다.
2. **API 가 손상을 어떻게 보여 주는가.** 런북 §2 R2 의 표가 이 테스트다. 구조·타입
   손상은 모든 경로가 500 이고 다시 저장되지 않는다. 논리 손상은 API 가 못 본다.
"""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from kayfabe.adapter.inbound.api.v1.career_sandbox_router import career_sandbox_router
from kayfabe.adapter.outbound.pg.career_world_codec import dump, load
from kayfabe.app.ports.output.sandbox_career_repository import RequestReceipt
from kayfabe.app.use_cases.career_sandbox_interactor import CareerSandboxInteractor
from kayfabe.dependencies.career_sandbox_provider import get_career_use_case
from kayfabe.domain.services.career_world import Balance, WorldState

_HERE = Path(__file__).resolve()
_TESTS = _HERE.parents[1]
_AUDIT = _HERE.parent / "career_save_audit.py"
_GOLDEN = _TESTS / "domain" / "services" / "test_career_golden.py"
_BASE = "/api/sandbox/careers"


def _module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _module(_AUDIT, "_career_save_audit")


@pytest.fixture(scope="module")
def good() -> dict[str, Any]:
    """엔진이 실제로 만든 기록 40건짜리 세이브. 테스트마다 복사해 쓴다."""
    _, world = _module(_GOLDEN, "_career_golden_audit").run_trajectory()
    assert len(world.matches) == 40
    return dump(world)


def _row(raw: dict[str, Any], career_id: int = 1) -> dict[str, Any]:
    return {
        "id": career_id,
        "season": raw["season"],
        "week": raw["week"],
        "phase": raw["phase"],
        "world": raw,
    }


def _fixture(version: int) -> dict[str, Any]:
    path = _TESTS / "fixtures" / f"career_golden_v{version}.json"
    return json.loads(path.read_text(encoding="utf-8"))[f"final_v{version}"]


def _first(field: str, value: Any) -> Callable[[dict[str, Any]], None]:
    def change(raw: dict[str, Any]) -> None:
        raw["matches"][0][field] = value

    return change


def _drop_field(raw: dict[str, Any]) -> None:
    del raw["matches"][0]["finish"]


def _short_state(raw: dict[str, Any]) -> None:
    raw["matches"][0]["participants"][0]["before"].pop()


def _matches_object(raw: dict[str, Any]) -> None:
    raw["matches"] = {"a": 1}


def _since_text(raw: dict[str, Any]) -> None:
    raw["match_records_since"] = "x"


def _null_record(raw: dict[str, Any]) -> None:
    raw["matches"][0] = None


def _no_v3_keys(raw: dict[str, Any]) -> None:
    del raw["matches"]
    del raw["match_records_since"]


def _version_4(raw: dict[str, Any]) -> None:
    raw["version"] = 4


def _flip_winner(raw: dict[str, Any]) -> None:
    record = raw["matches"][0]
    record["winner_side"] = 1 - record["winner_side"]


def _duplicate(raw: dict[str, Any]) -> None:
    raw["matches"].append(copy.deepcopy(raw["matches"][0]))


def _over_cap(raw: dict[str, Any]) -> None:
    raw["matches"] = raw["matches"] * 3


def _reversed(raw: dict[str, Any]) -> None:
    raw["matches"].reverse()


def _lost_record(raw: dict[str, Any]) -> None:
    del raw["matches"][20]


def _nested_state_text(raw: dict[str, Any]) -> None:
    raw["matches"][0]["participants"][0]["after"][0] = "x"


def _bool_week(raw: dict[str, Any]) -> None:
    raw["matches"][0]["week"] = True


def _heat_text(raw: dict[str, Any]) -> None:
    record = next(m for m in raw["matches"] if m["heat"])
    record["heat"][0]["after"] = "x"


def _injury_text(raw: dict[str, Any]) -> None:
    record = next(m for m in raw["matches"] if m["injury"])
    record["injury"]["weeks_out"] = "x"


#: 구조 손상 — 코덱이 거부한다.
_STRUCTURAL = {
    "field-missing": _drop_field,
    "state-width": _short_state,
    "matches-object": _matches_object,
    "since-text": _since_text,
    "null-record": _null_record,
    "v3-keys-absent": _no_v3_keys,
    "unknown-version": _version_4,
}
#: 타입 손상 — 예전에는 코덱을 통과해 상세 200 · 쓰기 저장이 됐다. 지금은 거부된다.
_TYPED = {
    "season-text": _first("season", "x"),
    "id-null": _first("id", None),
    "rating-text": _first("rating", "high"),
    "finish-null": _first("finish", None),
    "title-changed-int": _first("title_changed", 1),
    "probability-text": _first("probability", "0.5"),
    "participant-state-text": _nested_state_text,
    "week-bool": _bool_week,
    "heat-text": _heat_text,
    "injury-text": _injury_text,
}
#: 논리 손상 — 모든 API 가 200 이다.
_LOGICAL = {
    "winner-flipped": (_flip_winner, "RECORD_WINNER"),
    "duplicate-id": (_duplicate, "RECORD_DUPLICATE"),
    "over-cap": (_over_cap, "RECORD_OVER_CAP"),
    "out-of-order": (_reversed, "RECORD_ORDER"),
    "record-lost": (_lost_record, "LOG_WITHOUT_RECORD"),
}


def _damaged(good: dict[str, Any], change: Callable[..., None]) -> dict[str, Any]:
    raw = copy.deepcopy(good)
    change(raw)
    return raw


# ── 오탐 기준 ────────────────────────────────────────────────────


def test_an_engine_made_save_is_clean(good: dict[str, Any]) -> None:
    result = audit.audit_rows([_row(good)])
    assert result["damaged"] == 0, result["reports"]
    assert result["match_records"] == 40


@pytest.mark.parametrize("version", (1, 2))
def test_old_saves_are_clean_and_have_no_records(version: int) -> None:
    result = audit.audit_rows([_row(_fixture(version))])
    assert result["damaged"] == 0, result["reports"]
    assert result["versions"] == {str(version): 1}
    assert result["match_records"] == 0


# ── 탐지 ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("change", _STRUCTURAL.values(), ids=_STRUCTURAL.keys())
def test_structural_damage_is_detected(good: dict[str, Any], change: Any) -> None:
    report = audit.audit_row(_row(_damaged(good, change)))
    assert [i["code"] for i in report["issues"]] == ["DECODE_FAILED"]


@pytest.mark.parametrize("change", _TYPED.values(), ids=_TYPED.keys())
def test_typed_damage_is_detected(good: dict[str, Any], change: Any) -> None:
    report = audit.audit_row(_row(_damaged(good, change)))
    assert [i["code"] for i in report["issues"]] == ["DECODE_FAILED"]


@pytest.mark.parametrize(("change", "code"), _LOGICAL.values(), ids=_LOGICAL.keys())
def test_logical_damage_is_detected(
    good: dict[str, Any], change: Any, code: str
) -> None:
    report = audit.audit_row(_row(_damaged(good, change)))
    assert code in {i["code"] for i in report["issues"]}, report


def test_a_mirror_column_mismatch_is_detected(good: dict[str, Any]) -> None:
    row = {**_row(good), "week": good["week"] + 1}
    assert audit.audit_row(row)["issues"] == [
        {"code": "MIRROR_MISMATCH", "column": "week"}
    ]


def test_only_damaged_careers_are_reported(good: dict[str, Any]) -> None:
    rows = [
        _row(_fixture(1), 1),
        _row(good, 2),
        _row(_damaged(good, _flip_winner), 3),
    ]
    result = audit.audit_rows(rows)
    assert result["careers"] == 3 and result["damaged"] == 1
    assert [r["id"] for r in result["reports"]] == [3]


# ── 파일 입출력 ──────────────────────────────────────────────────


@pytest.mark.parametrize("wrap", ("backup", "envelope"))
def test_both_backup_shapes_are_read(
    tmp_path: Path, good: dict[str, Any], wrap: str
) -> None:
    rows = {"rows": [_row(good)]}
    path = tmp_path / "b.json"
    doc = rows if wrap == "backup" else {"careers": rows}
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    assert audit.main([str(path)]) == audit.EXIT_CLEAN


def test_damage_sets_the_exit_code_and_output_carries_no_save_content(
    tmp_path: Path, good: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    raw = _damaged(good, _flip_winner)
    path = tmp_path / "b.json"
    path.write_text(json.dumps({"rows": [_row(raw)]}), encoding="utf-8")

    assert audit.main([str(path)]) == audit.EXIT_DAMAGED

    out = capsys.readouterr().out
    assert raw["player"] not in out
    assert raw["matches"][0]["brand"] not in out


def test_an_unreadable_file_is_not_called_clean(tmp_path: Path) -> None:
    path = tmp_path / "b.json"
    path.write_text("{}", encoding="utf-8")
    assert audit.main([str(path)]) == audit.EXIT_UNREADABLE
    assert audit.main([str(tmp_path / "없음.json")]) == audit.EXIT_UNREADABLE


def test_the_auditor_cannot_reach_a_database() -> None:
    """운영에 닿을 수 없다는 것을 import 로 고정한다."""
    tree = ast.parse(_AUDIT.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not imported & {"psycopg", "sqlalchemy", "asyncpg", "httpx", "requests"}
    assert not any(name.startswith("core") for name in imported)
    assert not any("repository" in name and "pg" in name for name in imported)


# ── 손상이 API 에서 어떻게 보이는가 ──────────────────────────────


class OneSave:
    """세이브 하나를 dict 그대로 들고 있는 저장소. 저장은 `dump` 로 되돌려 적는다."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw
        self.saves = 0

    async def load(self, *, user_id: int, career_id: int) -> WorldState | None:
        return load(copy.deepcopy(self.raw))

    async def load_for_update(
        self, *, user_id: int, career_id: int
    ) -> WorldState | None:
        return load(copy.deepcopy(self.raw))

    async def find_receipt(self, **_: Any) -> RequestReceipt | None:
        return None

    async def save(self, *, state: WorldState, **_: Any) -> None:
        self.raw = dump(state)
        self.saves += 1


def _client(repository: OneSave) -> TestClient:
    app = FastAPI()
    app.include_router(career_sandbox_router, prefix="/api")
    app.dependency_overrides[get_career_use_case] = lambda: CareerSandboxInteractor(
        repository=repository,  # type: ignore[arg-type]
        balance=Balance(),
    )
    app.dependency_overrides[get_current_user] = lambda: TokenPayload(
        sub="1", aud="jsangho-api", exp=9999999999, iat=0, jti="jti"
    )
    return TestClient(app, raise_server_exceptions=False)


def _act(client: TestClient) -> int:
    response = client.post(
        f"{_BASE}/1/actions",
        json={"action": "휴식"},
        headers={"Idempotency-Key": "audit-request-1"},
    )
    return response.status_code


def _in_season(raw: dict[str, Any]) -> dict[str, Any]:
    return {**raw, "phase": "in_season"}


@pytest.mark.parametrize(
    "change",
    (*_STRUCTURAL.values(), *_TYPED.values()),
    ids=(*_STRUCTURAL.keys(), *_TYPED.keys()),
)
def test_unreadable_damage_fails_loudly_and_is_not_rewritten(
    good: dict[str, Any], change: Any
) -> None:
    raw = _in_season(_damaged(good, change))
    repository = OneSave(copy.deepcopy(raw))
    client = _client(repository)

    for path in ("", "/log", "/matches", "/matches/s1w1:p"):
        response = client.get(f"{_BASE}/1{path}")
        assert response.status_code == 500, path
        assert response.json() == {"detail": "세이브를 읽을 수 없습니다"}, path
    assert _act(client) == 500
    assert repository.saves == 0
    assert repository.raw == raw


@pytest.mark.parametrize(
    "change", [c for c, _ in _LOGICAL.values()], ids=_LOGICAL.keys()
)
def test_logical_damage_is_invisible_to_the_api(
    good: dict[str, Any], change: Any
) -> None:
    client = _client(OneSave(_in_season(_damaged(good, change))))
    assert client.get(f"{_BASE}/1").status_code == 200
    assert client.get(f"{_BASE}/1/matches").status_code == 200
    assert _act(client) == 200


# ── 오탐: 엔진이 만든 세이브를 거부하면 게임이 멈춘다 ────────────


@pytest.mark.parametrize("seed", range(1, 41))
def test_engine_saves_pass_strict_decoding_and_the_audit(seed: int) -> None:
    golden_module = _module(_GOLDEN, f"_career_golden_seed_{seed}")
    golden_module.SEED = seed
    _, world = golden_module.run_trajectory()

    raw = json.loads(json.dumps(dump(world), ensure_ascii=False))

    assert load(raw) == world
    assert audit.audit_row(_row(raw))["issues"] == []
