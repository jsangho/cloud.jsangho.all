"""커리어 샌드박스 라우터. **상태 코드와 응답 모양을 고정한다.**

여기서 보는 것은 셋이다.

1. **로그인 없이는 아무것도 안 된다** — 세이브가 사용자 소유다. 본문·쿼리의
   사용자 식별을 믿지 않고 토큰에서만 얻는다.
2. **실패 사유가 상태 코드로 갈린다** — 404(없음·남의 것) · 409(단계) ·
   422(입력). 전부 400으로 뭉개면 화면이 "결산 버튼을 보여라" 와 "입력을 고쳐라"
   를 구별할 수 없다.
3. **DTO 가 camelCase 로 나간다** — 데이터클래스 DTO 를 Pydantic 스키마가 받는
   경로는 조용히 깨질 수 있다(필드 이름이 안 맞으면 500 이다). 그래서 진짜
   유스케이스를 통과시켜 본문을 읽는다.
4. **쓰기는 `Idempotency-Key` 를 요구한다** — 헤더가 없거나 형식이 틀리면 422,
   같은 키에 다른 내용이면 409. 그리고 **재시도는 최초 응답의 본문을 그대로**
   받는다(저장된 dict 가 응답 스키마를 다시 통과한다 — camelCase 가 유지되는지가
   이 경로에서만 드러난다).
"""

from __future__ import annotations

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
from kayfabe.domain.services import career_engine as engine
from kayfabe.domain.services.career_world import Balance, WorldState

_BASE = "/api/sandbox/careers"

#: 짧은 시즌. 52주를 돌리지 않고 단계 오류(409)를 만든다.
_BALANCE = Balance(season_weeks=2)

#: 요청 키 하나. 형식은 `REQUEST_KEY_PATTERN`(영숫자·`_`·`-`, 8~64자)이다.
_KEY = "11111111-2222-3333-4444-555555555555"


def _key(suffix: str) -> dict[str, str]:
    """서로 다른 의도에는 서로 다른 키를 준다."""
    return {"Idempotency-Key": f"{_KEY}-{suffix}"}


class FakeRepository:
    def __init__(self) -> None:
        self.saves: dict[int, WorldState] = {}
        self.owner: dict[int, int] = {}
        self.receipts: dict[tuple[int, int, str], RequestReceipt] = {}

    async def create(
        self, *, user_id: int, player_name: str, seed: int, state: WorldState
    ) -> int:
        self.saves[1] = state
        self.owner[1] = user_id
        return 1

    async def list_for_user(self, user_id: int) -> list:
        return []

    async def load(self, *, user_id: int, career_id: int) -> WorldState | None:
        if self.owner.get(career_id) != user_id:
            return None
        return self.saves.get(career_id)

    async def load_for_update(
        self, *, user_id: int, career_id: int
    ) -> WorldState | None:
        return await self.load(user_id=user_id, career_id=career_id)

    async def find_receipt(
        self, *, user_id: int, career_id: int, request_id: str
    ) -> RequestReceipt | None:
        return self.receipts.get((user_id, career_id, request_id))

    async def save(
        self,
        *,
        user_id: int,
        career_id: int,
        state: WorldState,
        receipt: RequestReceipt | None = None,
    ) -> None:
        if self.owner.get(career_id) != user_id:
            raise LookupError("커리어를 찾을 수 없습니다")
        self.saves[career_id] = state
        if receipt is not None:
            self.receipts[(user_id, career_id, receipt.request_id)] = receipt


class ExplodingUseCase:
    """모르는 예외를 내는 가짜. **라우터가 삼키지 않아야 한다.**"""

    async def advance(self, *, user_id: int, career_id: int, request_id: str) -> Any:
        raise RuntimeError("설계에 없는 고장")


def _claims(sub: str = "1") -> TokenPayload:
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


def _client(use_case, *, sub: str | None = "1") -> TestClient:
    app = FastAPI()
    app.include_router(career_sandbox_router, prefix="/api")
    app.dependency_overrides[get_career_use_case] = lambda: use_case
    if sub is not None:
        app.dependency_overrides[get_current_user] = lambda: _claims(sub)
    return TestClient(app)


def _interactor() -> CareerSandboxInteractor:
    return CareerSandboxInteractor(repository=FakeRepository(), balance=_BALANCE)


def _create(client: TestClient) -> dict:
    response = client.post(
        _BASE, json={"name": "Ho", "style": "테크니션", "age": 24, "seed": 7}
    )
    assert response.status_code == 200, response.text
    return response.json()


# ── 인증 ──────────────────────────────────────────────────────────


def test_anonymous_callers_are_rejected_everywhere() -> None:
    client = _client(_interactor(), sub=None)

    assert client.get(_BASE).status_code == 401
    assert client.post(_BASE, json={"name": "Ho", "style": "파워"}).status_code == 401
    assert client.get(f"{_BASE}/1").status_code == 401
    assert client.post(f"{_BASE}/1/advance", headers=_key("a")).status_code == 401
    assert client.get(f"{_BASE}/1/log").status_code == 401


def test_a_non_numeric_subject_is_an_auth_error_not_a_crash() -> None:
    assert _client(_interactor(), sub="not-a-number").get(_BASE).status_code == 401


# ── 응답 모양 ─────────────────────────────────────────────────────


def test_create_returns_camel_case_with_server_season_length() -> None:
    body = _create(_client(_interactor()))

    assert body["seasonWeeks"] == _BALANCE.season_weeks
    assert body["maxActionPoints"] == _BALANCE.action_points
    assert body["nextCard"]["kind"]
    assert body["player"]["isPlayer"] is True
    assert body["player"]["debutAge"] == 24
    assert body["lastReport"] is None


def test_risk_is_a_band_with_reasons_and_carries_no_score() -> None:
    """**퍼센트 칸이 없다.** 있으면 화면이 검증되지 않은 확률을 적는다."""
    body = _create(_client(_interactor()))

    risk = body["player"]["risk"]
    assert set(risk) == {"band", "reasons"}
    assert risk["band"]


def test_advance_reports_the_week_that_was_played() -> None:
    client = _client(_interactor())
    _create(client)

    body = client.post(f"{_BASE}/1/advance", headers=_key("w1")).json()

    assert body["week"] == 2
    assert body["lastReport"]["week"] == 1
    assert "riskBand" in body["lastReport"]


def test_log_is_paged_and_camel_cased() -> None:
    client = _client(_interactor())
    _create(client)
    client.post(f"{_BASE}/1/advance", headers=_key("w1"))

    response = client.get(f"{_BASE}/1/log", params={"limit": 1, "offset": 0})

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert {"season", "week", "kind", "subject", "summary"} <= set(rows[0])


def test_log_rejects_an_out_of_range_limit() -> None:
    client = _client(_interactor())
    _create(client)

    assert client.get(f"{_BASE}/1/log", params={"limit": 999}).status_code == 422


# ── 실패 사유가 코드로 갈린다 ─────────────────────────────────────


def test_missing_career_is_404() -> None:
    assert _client(_interactor()).get(f"{_BASE}/999").status_code == 404


def test_someone_elses_career_is_404_not_403() -> None:
    """**있다는 사실조차 알려 주지 않는다** — 403 이면 id 의 존재가 새어 나간다."""
    use_case = _interactor()
    _create(_client(use_case, sub="1"))

    stranger = _client(use_case, sub="2")

    assert stranger.get(f"{_BASE}/1").status_code == 404
    assert stranger.post(f"{_BASE}/1/advance", headers=_key("w1")).status_code == 404


def test_wrong_phase_is_409() -> None:
    client = _client(_interactor())
    _create(client)
    for week in range(_BALANCE.season_weeks):
        assert (
            client.post(f"{_BASE}/1/advance", headers=_key(f"w{week}")).status_code
            == 200
        )

    response = client.post(f"{_BASE}/1/advance", headers=_key("over"))

    assert response.status_code == 409
    assert "단계" in response.json()["detail"]


def test_settle_before_the_season_ends_is_409() -> None:
    client = _client(_interactor())
    _create(client)

    assert client.post(f"{_BASE}/1/settle", headers=_key("s")).status_code == 409


def test_unknown_action_is_422() -> None:
    client = _client(_interactor())
    _create(client)

    response = client.post(
        f"{_BASE}/1/actions", json={"action": "춤"}, headers=_key("dance")
    )

    assert response.status_code == 422


def test_unknown_event_is_404() -> None:
    client = _client(_interactor())
    _create(client)

    response = client.post(
        f"{_BASE}/1/events/evt:missing",
        json={"choice": "retire"},
        headers=_key("evt"),
    )

    assert response.status_code == 404


def test_unknown_errors_are_not_swallowed_as_bad_requests() -> None:
    """**모르는 예외는 다시 던진다.** 400 으로 뭉개면 버그가 사용자 입력 오류로 보고된다."""
    client = _client(ExplodingUseCase())

    with pytest.raises(RuntimeError, match="설계에 없는 고장"):
        client.post(f"{_BASE}/1/advance", headers=_key("boom"))


# ── 요청 키 계약 ──────────────────────────────────────────────────


def test_writes_without_a_request_key_are_rejected() -> None:
    """**필수다.** 선택이면 키를 안 보내는 클라이언트가 보호 없이 조용히 돌아간다."""
    client = _client(_interactor())
    _create(client)

    assert client.post(f"{_BASE}/1/advance").status_code == 422
    assert (
        client.post(f"{_BASE}/1/actions", json={"action": "프로모"}).status_code == 422
    )
    assert client.post(f"{_BASE}/1/settle").status_code == 422
    assert client.post(f"{_BASE}/1/next-season").status_code == 422
    assert (
        client.post(f"{_BASE}/1/events/evt:x", json={"choice": "a"}).status_code == 422
    )


def test_a_too_short_or_malformed_request_key_is_rejected() -> None:
    """짧은 키는 서로 다른 의도가 겹치기 쉽다 — 그러면 멱등성이 오답 전달이 된다."""
    client = _client(_interactor())
    _create(client)

    short = client.post(f"{_BASE}/1/advance", headers={"Idempotency-Key": "abc"})
    spaced = client.post(f"{_BASE}/1/advance", headers={"Idempotency-Key": "a b c d e"})

    assert short.status_code == 422
    assert spaced.status_code == 422


def test_create_still_works_without_a_request_key() -> None:
    """생성에는 키 범위(커리어)가 없다 — 계약을 넓히지 않았다."""
    assert _create(_client(_interactor()))["week"] == 1


def test_repeating_advance_with_the_same_key_replays_the_first_body() -> None:
    """**본문이 바이트 단위로 같아야 한다.** 저장된 dict 가 응답 스키마를 다시 통과한다."""
    client = _client(_interactor())
    _create(client)
    headers = _key("w1")

    first = client.post(f"{_BASE}/1/advance", headers=headers)
    second = client.post(f"{_BASE}/1/advance", headers=headers)

    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json() == first.json()
    # 주차가 한 번만 넘어갔다.
    assert client.get(f"{_BASE}/1").json()["week"] == 2
    # 재시도도 그 주의 보고를 받는다 — 세이브에 없는 값이라 영수증에 담겨 있다.
    assert second.json()["lastReport"]["week"] == 1


def test_repeating_an_action_with_the_same_key_spends_one_point() -> None:
    client = _client(_interactor())
    created = _create(client)
    headers = _key("promo")
    body = {"action": "프로모", "target": None}

    first = client.post(f"{_BASE}/1/actions", json=body, headers=headers)
    second = client.post(f"{_BASE}/1/actions", json=body, headers=headers)

    assert second.json() == first.json()
    assert (
        client.get(f"{_BASE}/1").json()["actionPoints"] == created["actionPoints"] - 1
    )


def test_the_same_key_with_a_different_payload_is_409() -> None:
    client = _client(_interactor())
    _create(client)
    headers = _key("promo")

    client.post(f"{_BASE}/1/actions", json={"action": "프로모"}, headers=headers)
    clash = client.post(f"{_BASE}/1/actions", json={"action": "휴식"}, headers=headers)

    assert clash.status_code == 409
    assert "요청 키" in clash.json()["detail"]


def test_the_same_key_on_a_different_endpoint_is_409() -> None:
    """연산 이름이 지문에 들어가지 않으면 여기서 **주차 진행 응답**이 돌아간다."""
    client = _client(_interactor())
    _create(client)
    headers = _key("shared")

    assert client.post(f"{_BASE}/1/advance", headers=headers).status_code == 200
    assert client.post(f"{_BASE}/1/settle", headers=headers).status_code == 409


def test_a_key_conflict_does_not_collide_with_the_phase_409() -> None:
    """둘 다 409 지만 문구로 갈린다 — 화면이 "결산 버튼" 과 "키를 새로" 를 구별한다."""
    client = _client(_interactor())
    _create(client)
    for week in range(_BALANCE.season_weeks):
        client.post(f"{_BASE}/1/advance", headers=_key(f"w{week}"))

    phase = client.post(f"{_BASE}/1/advance", headers=_key("over"))

    assert phase.status_code == 409
    assert "요청 키" not in phase.json()["detail"]


def test_different_keys_advance_two_weeks() -> None:
    """정상적인 연속 행동은 각각 적용된다 — 멱등성이 진행을 막지 않는다."""
    client = _client(_interactor())
    _create(client)

    client.post(f"{_BASE}/1/advance", headers=_key("w1"))
    client.post(f"{_BASE}/1/advance", headers=_key("w2"))

    assert client.get(f"{_BASE}/1").json()["week"] == 3


# ── 읽을 수 없는 세이브 ────────────────────────────────────────────
#
# 저장된 세이브를 되살릴 수 없는 것은 **서버 쪽 사실**이다. 클라이언트가 고칠 수
# 있는 것이 없으므로 4xx 가 아니고, 어느 경로로 물어도 같은 답이어야 한다.
#
# 2026-10-26 실측으로 셋이 어긋나 있었다.
#
#     판본 불일치   GET /{id} → 500(일반 문구) · /log · 쓰기 → 422
#     칸 누락       /log · /advance → 404 detail="'action_points'"
#     세계 자기모순  /advance → 404 detail="'로스터에 없는 선수: Nobody'"
#
# 뒤 둘은 `KeyError` 가 `LookupError` 의 하위라서 "없으면 404" 분기에 걸린 것이고,
# 저장된 내용이 응답에 함께 실렸다.


class RawRepository:
    """세이브를 **dict 로** 들고 진짜 codec 으로 되살린다 — PG 어댑터와 같은 모양.

    `FakeRepository` 는 `WorldState` 를 그대로 들고 있어 **역직렬화 경로가 아예
    없다.** 읽기 실패는 거기서는 재현되지 않는다.

    🔴 **소유권 테스트에 쓰지 말 것.** `load` 가 `user_id` · `career_id` 를
    무시하고 **절대 `None` 을 돌려주지 않는다** — 읽기 실패만 보는 하네스라
    일부러 그렇게 뒀다. 이걸로 "남의 커리어는 404" 를 재면 조용히 통과한다.
    소유권은 `FakeRepository` 쪽 테스트(`test_someone_elses_career_is_404_not_403`)
    가 본다.
    """

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw

    async def create(self, **_: Any) -> int:
        return 1

    async def list_for_user(self, user_id: int) -> list:
        return []

    async def load(self, *, user_id: int, career_id: int) -> WorldState | None:
        return load(self.raw)

    async def load_for_update(
        self, *, user_id: int, career_id: int
    ) -> WorldState | None:
        return load(self.raw)

    async def find_receipt(self, **_: Any) -> RequestReceipt | None:
        return None

    async def save(self, **_: Any) -> None:
        return None


def _raw_client(raw: dict[str, Any]) -> TestClient:
    """`raise_server_exceptions=False` 라야 500 을 **응답으로** 받는다."""
    app = FastAPI()
    app.include_router(career_sandbox_router, prefix="/api")
    app.dependency_overrides[get_career_use_case] = lambda: CareerSandboxInteractor(
        repository=RawRepository(raw), balance=_BALANCE
    )
    app.dependency_overrides[get_current_user] = lambda: _claims("1")
    return TestClient(app, raise_server_exceptions=False)


def _healthy_raw() -> dict[str, Any]:
    return dump(
        engine.create_world(
            player="Ho", style="테크니션", seed=7, age=24, balance=_BALANCE
        )
    )


def _read_paths(client: TestClient) -> dict[str, int]:
    """같은 세이브를 네 경로로 물어 본다."""
    return {
        "detail": client.get(f"{_BASE}/1").status_code,
        "log": client.get(f"{_BASE}/1/log").status_code,
        "advance": client.post(f"{_BASE}/1/advance", headers=_key("adv")).status_code,
        "event": client.post(
            f"{_BASE}/1/events/evt", json={"choice": "a"}, headers=_key("evt")
        ).status_code,
    }


def test_an_unsupported_schema_version_is_not_a_client_error() -> None:
    """**판본이 미래면 500 이다.** 422 는 "입력을 고쳐라" 인데 고칠 입력이 없다."""
    raw = _healthy_raw()
    raw["version"] = _healthy_raw()["version"] + 1

    response = _raw_client(raw).get(f"{_BASE}/1")

    assert response.status_code == 500


def test_an_unsupported_schema_version_is_the_same_code_everywhere() -> None:
    """한 가지 사실에 상태 코드가 하나여야 한다 — 전에는 셋이었다."""
    raw = _healthy_raw()
    raw["version"] = _healthy_raw()["version"] + 1

    assert set(_read_paths(_raw_client(raw)).values()) == {500}


def test_an_unsupported_schema_version_does_not_leak_the_version() -> None:
    """판본 번호는 내부 사정이다 — 로그에만 남는다."""
    raw = _healthy_raw()
    raw["version"] = 99

    detail = str(_raw_client(raw).get(f"{_BASE}/1").json()["detail"])

    assert "99" not in detail


def test_a_save_missing_a_field_is_not_an_event_404() -> None:
    """**칸이 빠진 세이브와 "없는 사건" 은 다른 일이다.**

    전에는 둘 다 404 였고, 사건 경로에서는 `없는 사건입니다: evt` 라고 답했다 —
    세이브가 안 읽힌 것을 사건이 없다고 보고하면 진단이 반대로 간다.
    """
    raw = _healthy_raw()
    del raw["action_points"]

    response = _raw_client(raw).post(
        f"{_BASE}/1/events/evt", json={"choice": "a"}, headers=_key("evt")
    )

    assert response.status_code == 500
    assert "없는 사건" not in str(response.json()["detail"])


def test_a_save_missing_a_field_does_not_leak_the_field_name() -> None:
    """빠진 칸 이름은 저장 구조를 그대로 말해 준다 — 응답에 실리면 안 된다."""
    raw = _healthy_raw()
    del raw["action_points"]

    detail = str(_raw_client(raw).post(f"{_BASE}/1/advance", headers=_key("a")).json())

    assert "action_points" not in detail


def test_an_inconsistent_world_is_not_a_career_404() -> None:
    """`WorldState.require` 의 `KeyError` 는 "커리어가 없다" 가 아니다.

    `KeyError` 가 `LookupError` 의 하위라 404 분기에 걸렸고, 로스터에 없는
    **선수 이름이 응답에 실렸다**.
    """
    raw = _healthy_raw()
    raw["player"] = "Nobody"

    response = _raw_client(raw).post(f"{_BASE}/1/advance", headers=_key("adv"))

    assert response.status_code == 500
    # **`.text` 로 본다.** 다시 던진 예외는 FastAPI 가 JSON 이 아닌
    # `Internal Server Error` 본문으로 낸다 — `.json()` 이면 테스트가 파싱에서
    # 죽어 정작 재는 것(이름 누출)을 못 본다.
    assert "Nobody" not in response.text


def test_a_genuinely_missing_event_is_still_404() -> None:
    """**대조군.** 세이브가 멀쩡하면 없는 사건은 그대로 404 다 — 고친 것이 이
    의미를 건드리지 않았다는 확인이다.
    """
    response = _raw_client(_healthy_raw()).post(
        f"{_BASE}/1/events/does-not-exist", json={"choice": "a"}, headers=_key("evt")
    )

    assert response.status_code == 404
    assert "없는 사건" in response.json()["detail"]


def test_a_healthy_save_still_reads_on_every_path() -> None:
    """읽기 경로 넷이 멀쩡한 세이브에 대해 그대로 돌아간다."""
    paths = _read_paths(_raw_client(_healthy_raw()))

    assert paths["detail"] == 200
    assert paths["log"] == 200
    assert paths["advance"] == 200


# ── 사건 해결: "없는 사건" 과 "깨진 세이브" 를 가른다 ──────────────
#
# `resolve` 안에서 `KeyError` 가 나는 자리가 둘이고 뜻이 반대다.
#
#     EventNotFoundError                  없는 사건 id 를 보냈다      → 404
#     WorldState.require 의 KeyError      세이브가 자기모순이다        → 500
#
# 2026-10-26 실측으로 `except KeyError` 가 둘을 같이 잡아, `subject` 가 로스터에
# 없는 보류 사건이 `404 "없는 사건입니다: evt"` 로 보고됐다. 깨진 세이브를 "그
# 사건은 없다" 고 답한 것이다.
#
# **문구로 가르지 않는다.** 아래 테스트도 상태 코드와 비노출만 본다.


def _with_pending(subject: str) -> dict[str, Any]:
    """보류 사건 하나를 심은 세이브. `subject` 가 로스터에 있는지가 변수다.

    `stay` 를 고르는 것은 **효과가 자기완결적**이라서다 — `event.other` 를 요구
    하지 않고 은퇴 의사만 거둔다. 효과가 정의되지 않은 코드를 주면 도메인이
    `ValueError` 를 내어 재려는 경로에 닿지 못한다.
    """
    raw = _healthy_raw()
    raw["pending"] = [
        {
            "id": "evt",
            "kind": "retirement_thought",
            "season": 1,
            "week": 1,
            "subject": subject,
            "other": None,
            "headline": "거취를 묻는다",
            "detail": "",
            "choices": [
                {"code": "stay", "label": "계속한다", "enabled": True, "note": ""}
            ],
        }
    ]
    return raw


def _resolve(raw: dict[str, Any], event_id: str = "evt"):
    return _raw_client(raw).post(
        f"{_BASE}/1/events/{event_id}",
        json={"choice": "stay"},
        headers=_key("resolve"),
    )


def test_a_missing_event_id_is_404_even_with_a_pending_event() -> None:
    """**정상 404 보존.** 보류 사건이 있어도 다른 id 를 물으면 없는 사건이다."""
    response = _resolve(_with_pending("Ho"), event_id="not-this-one")

    assert response.status_code == 404


def test_an_event_whose_subject_left_the_roster_is_not_a_404() -> None:
    """`require` 의 `KeyError` 가 "없는 사건" 으로 보고되지 않는다."""
    response = _resolve(_with_pending("Nobody"))

    assert response.status_code == 500


def test_an_event_with_a_broken_subject_does_not_leak_the_name() -> None:
    """저장된 세계의 선수 이름이 응답에 실리지 않는다.

    `.text` 로 보는 것은 다시 던진 예외의 본문이 JSON 이 아니기 때문이다.
    """
    assert "Nobody" not in _resolve(_with_pending("Nobody")).text


def test_resolving_a_healthy_event_still_succeeds() -> None:
    """**대조군.** 멀쩡한 사건·선택지는 그대로 처리된다 — 고친 것이 성공 경로를
    건드리지 않았다는 확인이다.
    """
    response = _resolve(_with_pending("Ho"))

    assert response.status_code == 200, response.text
    # 해결된 사건은 보류 목록에서 빠진다.
    assert response.json()["pending"] == []
