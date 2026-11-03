"""**결정론 골든.** 고정 시드로 한 시즌(52주)을 돌린 궤적이 기준값과 같은가.

## 왜 필요한가

확장(경기 상세 · 쇼 · 스토리라인)은 엔진 한가운데를 고친다. 그때 "기존 세이브의
다음 주차가 예전과 같은 결과를 내는가" 를 지키는 것이 이 파일 하나다. 기존 테스트는
규칙 하나씩을 보고, 이 파일은 **규칙 전부가 맞물린 결과**를 본다.

## 기준값은 어디서 왔나

`fixtures/career_golden_v1.json` 은 Phase 0 변경 **전** 코드(ho=ca13b58)로 이
파일의 `run_trajectory()` 를 돌려 뽑은 것이다. 그래서 같은 파일의 `final_v1` 은
**v1 코덱이 실제로 쓴 세이브**이기도 하다 — 코덱 업그레이드 테스트가 그것을 v1
픽스처로 쓴다(손으로 만든 v1 이 아니다).

**기대값을 갱신하지 않는다.** 이 테스트가 깨지면 바뀐 것은 기준값이 아니라 게임
결과다. 규칙을 일부러 바꾼 경우에만, 무엇이 왜 바뀌는지 적고 다시 뽑는다.

## 뒤 판본에서 더해진 칸은 비교에서 뺀다

`V2_WRESTLER_KEYS`(v2 · 선수 칸)와 `V3_WORLD_KEYS`(v3 · 세계 칸)는 v1 세이브에 없던
칸이다. 비교는 **v1 이 알던 칸 전부**가 같은지를 본다 — 새 칸이 생겼다고 옛 칸이
하나라도 움직이면 실패한다. 새 칸 자체의 정확성은 그 칸의 테스트가 본다
(경기 기록은 `test_career_match_record`).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from kayfabe.adapter.outbound.pg.career_world_codec import dump
from kayfabe.domain.services import career_actions as actions
from kayfabe.domain.services import career_engine as engine
from kayfabe.domain.services import career_events as events
from kayfabe.domain.services import career_season as season_rules
from kayfabe.domain.services.career_world import Balance, Phase, WorldState

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "career_golden_v1.json"

#: 이 시드는 **태그 · 결장 · 복귀 · 방어전 · 타이틀 이동**이 한 시즌에 모두 나오는
#: 것을 골라 정했다(1~400 을 훑어 처음 맞은 값). 아래 `test_trajectory_is_not_trivial`
#: 이 그 조건을 지킨다.
SEED = 11
PLAYER = "Golden Ho"
ALLY = "Rio Castellan"

#: v1 세이브에 없던 선수 칸. 골든 비교에서만 뺀다.
V2_WRESTLER_KEYS = ("win_streak", "best_win_streak", "streaks_since")
#: v2 세이브에 없던 세계 칸(v3 · 경기 기록).
V3_WORLD_KEYS = ("matches", "match_records_since")

#: 주마다 하나씩 돌아가며 쓰는 행동. 행동 다섯 종류를 전부 지나가게 한다.
_ACTION_CYCLE = ("훈련", "프로모", "관계", "휴식", "협상")


def _choice_for(event) -> str | None:
    """사건마다 고를 선택지. **은퇴는 고르지 않는다** — 한 시즌을 끝까지 돌리려고."""
    for c in event.choices:
        if c.enabled and c.code != "retire":
            return c.code
    return None


def run_trajectory() -> tuple[list[dict[str, Any]], WorldState]:
    """고정 시드 한 시즌. 주마다 행동 하나 · 열린 사건 해결 · 주차 진행, 끝에 결산."""
    bal = Balance()
    world = engine.create_world(player=PLAYER, style="테크니션", seed=SEED, age=26)
    weeks: list[dict[str, Any]] = []

    for i in range(bal.season_weeks):
        action = _ACTION_CYCLE[i % len(_ACTION_CYCLE)]
        target = None
        if action == "훈련":
            target = actions.TRAINABLE[(i // len(_ACTION_CYCLE)) % 4]
        elif action == "관계":
            # **대상을 한 명으로 고정한다.** 돌려 가며 고르면 동맹 heat 가 태그 기준
            # (`TEAM_HEAT`)에 닿지 않아 태그 경기가 궤적에 한 번도 나오지 않는다.
            target = ALLY
        try:
            world = actions.perform(world, action=action, balance=bal, target=target)
            acted = action
        except ValueError:
            acted = f"{action}:rejected"

        resolved = []
        for event in list(world.pending):
            code = _choice_for(event)
            if code is None:
                continue
            world = events.resolve(
                world, event_id_=event.id, choice_code=code, balance=bal
            )
            resolved.append(f"{event.id}={code}")

        result = engine.advance_week(world, balance=bal)
        world = result.state
        weeks.append(
            {"action": acted, "resolved": resolved, "report": asdict(result.report)}
        )
        if world.phase != Phase.IN_SEASON:
            break

    if world.phase == Phase.SETTLEMENT:
        world = season_rules.settle(world, balance=bal)
    return weeks, world


def strip_v2(raw: dict[str, Any]) -> dict[str, Any]:
    """뒤 판본 세이브에서 **v1 이 알던 칸만** 남긴다. 판본 칸도 뺀다.

    이름은 v2 때 지었고 그대로 둔다(테스트 여러 곳이 부른다). v3 칸도 함께 뺀다.
    """
    out = {k: v for k, v in raw.items() if k != "version" and k not in V3_WORLD_KEYS}
    out["roster"] = [
        {k: v for k, v in w.items() if k not in V2_WRESTLER_KEYS} for w in raw["roster"]
    ]
    return out


def _json(value: Any) -> Any:
    """튜플·부동소수를 저장된 JSON 과 같은 모양으로 맞춘다."""
    return json.loads(json.dumps(value, ensure_ascii=False))


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_weekly_reports_match_golden() -> None:
    """주차별 보고 — 상대 · 승패 · **승률** · 평가 · 인기도 변화 · 부상 · 사건."""
    weeks, _ = run_trajectory()
    golden = load_fixture()

    assert len(weeks) == len(golden["weeks"])
    for i, (got, want) in enumerate(zip(_json(weeks), golden["weeks"], strict=True)):
        assert got == want, f"{i + 1}주차가 기준값과 다르다"


def test_final_world_matches_golden() -> None:
    """시즌 끝 세계 — 로스터 · 관계 · 타이틀 · 사건 · 로그 · 결산 · `applied`."""
    _, world = run_trajectory()
    golden = load_fixture()

    assert strip_v2(_json(dump(world))) == strip_v2(golden["final_v1"])


def test_trajectory_is_not_trivial() -> None:
    """기준값이 **실제로 무언가를 덮는가.** 경기 없이 쉬기만 한 궤적이면 골든이 빈말이다."""
    golden = load_fixture()
    kinds = {w["report"]["kind"] for w in golden["weeks"]}
    final = golden["final_v1"]

    assert len(golden["weeks"]) == 52
    assert final["phase"] == "offseason"
    assert {"경기", "타이틀전", "방어전", "태그", "결장", "복귀"} <= kinds
    assert any(w["report"]["title_changed"] for w in golden["weeks"])
    assert any(w["resolved"] for w in golden["weeks"])
    assert final["relationships"]
    assert any(t["holder"] for t in final["titles"])
