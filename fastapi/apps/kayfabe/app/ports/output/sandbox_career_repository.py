"""커리어 세이브 출력 포트.

**세계를 통째로 읽고 통째로 쓴다.** 포트가 `WorldState` 하나만 다루므로 게임
규칙이 늘어도 이 인터페이스가 넓어지지 않는다 — 지난번에 저장 계층이 규칙을 따라
불어난 경로를 막는 자리다.

## 잠금을 포트에 적어 둔다

`load_for_update` 가 따로 있는 것은 의도다. 멱등 키는 **같은** 연산의 재시도를
막지만, 서로 **다른** 두 요청이 같은 세이브를 동시에 읽으면 둘 다 "이 주차는 아직
처리 안 됐다" 를 보고 둘 다 쓴다(나중 쓰기가 이긴다 — 잃어버린 갱신).

그래서 쓰기 경로는 행을 잠그고 읽는다. 잠금이 구현 세부가 아니라 **계약**이라서
포트에 적는다 — 어댑터를 갈아도 이 성질은 유지돼야 한다.

## 요청 영수증은 세이브와 **한 트랜잭션**이다

`save` 가 `receipt` 를 함께 받는 것도 계약이다. 영수증을 따로 커밋하면 둘 사이에
프로세스가 죽는 창이 생긴다 — 세이브는 바뀌었는데 영수증이 없으면 재시도가 **또
적용**되고, 영수증만 있으면 하지 않은 일을 했다고 답한다. 포트를 둘로 쪼개지 않고
`save` 를 넓힌 이유가 이것이다(메서드 두 개면 트랜잭션 경계를 호출자가 지켜야
한다).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from kayfabe.domain.services.career_world import WorldState

#: 커리어 하나가 들고 있는 영수증 상한. **이 수가 보존 정책의 전부다.**
#:
#: 영수증에는 응답 본문이 통째로 들어간다(수십 KB). 무제한이면 52주 × 시즌 × 주당
#: 행동 수만큼 쌓여 세이브보다 커진다. 그래서 쓰기마다 **같은 트랜잭션에서** 오래된
#: 것을 떨어뜨린다 — 정리 배치도 크론도 없고, 상한이 구조로 보장된다.
#:
#: 감수한 트레이드오프: 같은 커리어에 쓰기가 여덟 번 더 성공한 **뒤에** 도착한
#: 재시도는 중복으로 식별되지 않는다. 재시도 창은 요청 하나(타임아웃 수십 초)이고
#: 그 사이에 같은 커리어로 여덟 번 더 쓰는 경로는 없다.
RECEIPT_KEEP = 8


class CorruptSaveError(ValueError):
    """저장된 세이브를 되살릴 수 없다. **클라이언트가 고칠 수 있는 것이 아니다.**

    판본이 맞지 않거나 칸이 빠진 경우다. 원인은 둘이지만 호출자에게는 같은
    사실이라 이름을 하나로 둔다 — 서버가 들고 있는 데이터를 읽을 수 없다.

    **이 이름이 필요한 이유는 `KeyError` 가 `LookupError` 의 하위라서다.** 칸이
    빠진 세이브를 되살리다 나는 `KeyError` 가 그대로 올라가면 라우터의 "없으면
    404" 분기(`LookupError`)가 그것을 **"커리어가 없다"** 로 번역한다. 실제로
    그랬다 — 2026-10-26 실측으로 `/log` 와 `/advance` 가
    `404 detail="'action_points'"` 를 냈다. 저장된 JSON 의 칸 이름이 응답에
    그대로 실리는 누출도 같은 경로였다.

    `ValueError` 를 물려받는 것은 이 예외가 이미 `ValueError` 로 올라오던 자리를
    대체하기 때문이다(판본 불일치). `ValueError` 로 잡던 호출자는 그대로
    돌아가고, 구별이 필요한 쪽만 이 이름을 본다. **그래서 라우터의 422 분기보다
    먼저 검사해야 한다.**

    ## 왜 포트에 있나

    내는 쪽은 아웃바운드 어댑터(`career_world_codec`)고 받는 쪽은 인바운드
    라우터다. 어댑터끼리 import 하면 방향이 어긋나므로, 포트 경계에 두고 양쪽이
    그것을 본다 — 같은 파일의 `DuplicateRequestError` 와 같은 자리다.
    """


class DuplicateRequestError(Exception):
    """같은 (user, career, request) 영수증이 이미 있다.

    **고유 제약이 마지막 방어선이다.** 정상 경로에서는 행 잠금이 먼저 막으므로 이
    예외가 나오지 않는다. 그래도 두는 이유는 잠금이 없는 경로(고립 수준을 올렸다,
    어댑터를 갈았다, 연결이 끊겨 잠금이 풀렸다)에서 중복이 조용히 통과하지 않게
    하려는 것이다 — DB 가 거부하면 호출자가 되돌리고 저장된 응답을 읽는다.
    """


@dataclass(frozen=True)
class CareerRow:
    """목록 한 줄. **세이브를 열지 않고** 읽을 수 있는 것만 담는다."""

    id: int
    player_name: str
    season: int
    week: int
    phase: str
    seed: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RequestReceipt:
    """처리가 끝난 쓰기 요청 하나.

    **지문과 응답을 함께 든다.** 요청 id 만 적어 두면 같은 id 로 다른 payload 가
    들어왔을 때 그걸 재시도로 착각해 엉뚱한 응답을 돌려준다 — 지문이 그 경로를
    막고, 응답이 "최초 요청의 본문을 그대로" 재사용하게 한다.

    `response` 는 `CareerViewDto` 를 `dataclasses.asdict` 로 눕힌 **snake_case**
    dict 다. 스키마가 `populate_by_name=True` 라 그대로 응답 모델에 먹고, 나올 때
    camelCase 로 다시 붙는다 — 그래서 손으로 쓴 역직렬화기가 필요 없다.
    """

    request_id: str
    #: payload 의 sha256. 연산 이름이 지문에 들어간다 — 같은 키로 `/actions` 와
    #: `/advance` 를 때리면 충돌로 잡혀야 한다.
    fingerprint: str
    response: dict[str, Any] = field(default_factory=dict)


class SandboxCareerRepository(ABC):
    @abstractmethod
    async def create(
        self, *, user_id: int, player_name: str, seed: int, state: WorldState
    ) -> int:
        """새 커리어를 만들고 id 를 돌려준다."""
        ...

    @abstractmethod
    async def list_for_user(self, user_id: int) -> list[CareerRow]:
        """그 사용자의 커리어 목록. 최근 것부터."""
        ...

    @abstractmethod
    async def load(self, *, user_id: int, career_id: int) -> WorldState | None:
        """읽기 전용 조회. 남의 것이면 `None` — **없는 것과 같이 취급한다.**

        403 과 404 를 가르면 "그 id 는 존재한다" 가 새어 나간다.

        **행은 있는데 되살릴 수 없으면 `CorruptSaveError`** 다 — `None` 이
        아니다. 둘을 섞으면 깨진 세이브가 "없는 커리어" 로 보고되고, 사용자는
        자기 세이브가 사라졌다고 읽는다. 없음은 `None`, 고장은 예외다.
        """
        ...

    @abstractmethod
    async def load_for_update(
        self, *, user_id: int, career_id: int
    ) -> WorldState | None:
        """쓰기 전 조회. **행을 잠근다**(`FOR UPDATE`).

        같은 트랜잭션 안에서 `save` 까지 끝내야 잠금이 의미를 갖는다.

        없음·고장의 구별은 `load` 와 같다 — 남의 것·없는 것은 `None`, 되살릴 수
        없는 세이브는 `CorruptSaveError`.
        """
        ...

    @abstractmethod
    async def find_receipt(
        self, *, user_id: int, career_id: int, request_id: str
    ) -> RequestReceipt | None:
        """이 요청이 이미 처리됐나. **잠금을 잡은 뒤에 불러야 한다.**

        잠금 전에 읽으면 동시 요청 둘이 모두 `None` 을 보고 둘 다 적용한다. 순서가
        규칙이다 — `load_for_update` → `find_receipt` → (없으면) 적용.
        """
        ...

    @abstractmethod
    async def save(
        self,
        *,
        user_id: int,
        career_id: int,
        state: WorldState,
        receipt: RequestReceipt | None = None,
    ) -> None:
        """세계를 통째로 덮어쓴다. 남의 것이면 `LookupError`.

        `receipt` 를 주면 **같은 트랜잭션에서** 함께 쓰고, 그 커리어의 영수증을
        최신 `RECEIPT_KEEP` 개로 자른다. 같은 (user, career, request) 가 이미
        있으면 `DuplicateRequestError` — 호출자는 되돌리고 저장된 응답을 읽어야 한다.
        """
        ...
