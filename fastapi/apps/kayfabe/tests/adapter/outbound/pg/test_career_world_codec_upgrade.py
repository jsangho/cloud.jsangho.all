"""세이브 v1 → v2 업그레이드. **옛 칸은 하나도 움직이지 않고 새 칸만 생긴다.**

v1 픽스처는 손으로 만든 것이 아니다 — `fixtures/career_golden_v1.json` 의 `final_v1`
은 변경 전 코드(v1 코덱)가 52주를 돌고 **실제로 쓴** 세이브다
(`tests/domain/services/test_career_golden.py` 독스트링).
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from kayfabe.adapter.outbound.pg.career_world_codec import (
    SCHEMA_VERSION,
    _upgrade_v1_to_v2,
    dump,
    load,
)
from kayfabe.app.ports.output.sandbox_career_repository import CorruptSaveError
from kayfabe.domain.services import career_tally as tally

_GOLDEN_PATH = (
    Path(__file__).resolve().parents[3]
    / "domain"
    / "services"
    / "test_career_golden.py"
)


def _golden():
    """골든 모듈. 테스트 트리에 `__init__` 이 없어(conftest 독스트링) 경로로 읽는다."""
    spec = importlib.util.spec_from_file_location("_career_golden", _GOLDEN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _v1() -> dict[str, Any]:
    return _golden().load_fixture()["final_v1"]


def _json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _by_name(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {w["name"]: w for w in raw["roster"]}


# ── 보존 ──────────────────────────────────────────────────────────


def test_fixture_is_really_v1() -> None:
    raw = _v1()

    assert raw["version"] == 1
    assert "win_streak" not in raw["roster"][0]
    assert SCHEMA_VERSION == 2


def test_upgrade_keeps_every_v1_field() -> None:
    """**기존 데이터 불변.** v1 이 알던 칸 전부 — 선수 · 전적 · 관계 · 타이틀 · 사건 ·
    로그 · 시즌 · `applied` — 가 읽고 다시 쓴 뒤에도 같다."""
    golden = _golden()
    raw = _v1()

    rewritten = _json(dump(load(raw)))

    assert rewritten["version"] == 2
    assert golden.strip_v2(rewritten) == golden.strip_v2(raw)


def test_upgrade_does_not_mutate_input() -> None:
    """업그레이드는 메모리에서 **새 dict** 를 만든다. 읽은 원본을 고치지 않는다."""
    raw = _v1()
    before = copy.deepcopy(raw)

    load(raw)
    _upgrade_v1_to_v2(raw)

    assert raw == before


def test_v1_to_v2_to_reload_round_trip() -> None:
    """v1 을 읽어 v2 로 쓰고 다시 읽으면 같은 세계다. 두 번째 쓰기도 같은 바이트다."""
    first = load(_v1())
    v2 = dump(first)
    second = load(_json(v2))

    assert second == first
    assert json.dumps(dump(second), ensure_ascii=False) == json.dumps(
        v2, ensure_ascii=False
    )


def test_every_wrestler_gets_the_new_fields() -> None:
    upgraded = _upgrade_v1_to_v2(_v1())

    for w in upgraded["roster"]:
        assert {"win_streak", "best_win_streak", "streaks_since"} <= set(w)
        assert 0 <= w["win_streak"] <= w["best_win_streak"]


# ── 연승 칸의 값 ──────────────────────────────────────────────────


def test_player_with_intact_log_is_counted_exactly() -> None:
    """로그가 온전한 플레이어는 **새 코드로 처음부터 돈 세이브와 같은 값**을 받는다.

    업그레이드는 로그를 다시 세고, 새 엔진은 경기마다 센다. 둘이 같으면 업그레이드가
    추정이 아니라 재계산이라는 증거다.
    """
    golden = _golden()
    raw = _v1()
    _, live = golden.run_trajectory()

    hero = load(raw).hero

    assert hero.streaks_since is None
    assert (hero.win_streak, hero.best_win_streak) == (
        live.hero.win_streak,
        live.hero.best_win_streak,
    )
    assert hero.best_win_streak > 0


def test_npc_with_matches_is_marked_partial() -> None:
    """NPC 는 로그로 정확히 셀 수 없다 — 0에서 세기 시작하고 그 시점을 적는다."""
    raw = _v1()
    world = load(raw)

    played = [w for w in world.roster if not w.is_player and w.match_count > 0]
    assert played, "픽스처에 경기한 NPC 가 있어야 이 테스트가 의미가 있다"
    for w in played:
        assert w.streaks_since == (raw["season"], raw["week"])
        assert (w.win_streak, w.best_win_streak) == (0, 0)


def test_wrestler_without_matches_is_exact_zero() -> None:
    world = load(_v1())

    idle = [w for w in world.roster if w.match_count == 0]
    assert idle
    for w in idle:
        assert w.streaks_since is None
        assert (w.win_streak, w.best_win_streak) == (0, 0)


def test_truncated_log_marks_player_partial() -> None:
    """`MAX_LOG` 로 잘린 세이브 — 첫 줄이 `debut` 가 아니면 다시 세지 않는다."""
    raw = _v1()
    raw["log"] = raw["log"][1:]

    hero = load(raw).hero

    assert hero.streaks_since == (raw["season"], raw["week"])
    assert (hero.win_streak, hero.best_win_streak) == (0, 0)


def test_log_disagreeing_with_record_marks_player_partial() -> None:
    """로그 경기 수가 전적과 안 맞으면 빠진 경기가 있다는 뜻이다 — 다시 세지 않는다."""
    raw = _v1()
    first_match = next(i for i, e in enumerate(raw["log"]) if e["kind"] == "match")
    del raw["log"][first_match]

    hero = load(raw).hero

    assert hero.streaks_since is not None


def test_replay_matches_log_order() -> None:
    """업그레이드가 쓴 값이 로그를 손으로 센 값과 같다."""
    raw = _v1()
    results = [
        e["result"] == "win"
        for e in raw["log"]
        if e["kind"] == "match" and e["subject"] == raw["player"]
    ]

    hero = _by_name(_upgrade_v1_to_v2(raw))[raw["player"]]

    assert (hero["win_streak"], hero["best_win_streak"]) == tally.replay(results)


# ── 거부 정책 ────────────────────────────────────────────────────


@pytest.mark.parametrize("version", [0, 3, 99, "1", "2", True, None, [1], {"v": 1}])
def test_unknown_or_malformed_version_is_refused(version: object) -> None:
    """아는 판본(1·2)이 아니면 **손상 세이브**다 — 해시할 수 없는 값도 500 이 아니다."""
    raw = _v1()
    raw["version"] = version

    with pytest.raises(CorruptSaveError, match="세이브 판본"):
        load(raw)


def test_broken_v1_is_refused_as_corrupt() -> None:
    """업그레이드 도중 칸이 없으면 날것의 `KeyError` 가 아니라 `CorruptSaveError`."""
    raw = _v1()
    del raw["roster"][0]["wins"]

    with pytest.raises(CorruptSaveError):
        load(raw)


@pytest.mark.parametrize("key", ["win_streak", "best_win_streak", "streaks_since"])
def test_v2_without_new_field_is_refused(key: str) -> None:
    """v2 에서 새 칸이 빠졌으면 깨진 세이브다 — 0 · `None`(=정확한 값)으로 메우지 않는다."""
    raw = _json(dump(load(_v1())))
    del raw["roster"][0][key]

    with pytest.raises(CorruptSaveError):
        load(raw)
