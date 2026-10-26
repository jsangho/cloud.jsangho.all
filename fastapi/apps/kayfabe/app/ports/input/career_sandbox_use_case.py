"""커리어 샌드박스 입력 포트.

**무상태 장난감(`SandboxUseCase`)과 갈라 둔다.** 그쪽은 상태를 받아 상태를 돌려줄
뿐 저장하지 않고, 이쪽은 사용자 소유의 세이브를 읽고 쓴다. 같은 포트에 두면
호출하는 쪽이 "이건 저장되나" 를 구별할 이유가 사라진다.

무상태 경로는 **그대로 남는다** — 로그인 없이 돌려 보는 장난감이라 회귀 대상이다.

## 쓰기는 `request_id` 를 **요구한다**

쓰기 다섯(`act`·`advance`·`resolve`·`settle`·`next_season`)이 전부 클라이언트가
만든 요청 키를 받는다. 선택 인수가 아니라 필수다 — 기본값을 두면 키를 안 보낸
호출자가 **조용히 보호 없이** 돌아가고, 그게 지금 고치는 결함이다.

**서버가 키를 만들면 안 된다.** 서버가 매번 새로 만들면 모든 요청이 새 요청이라
재시도를 식별할 수 없다. 같은 사용자 의도에 같은 키를 붙이는 것은 클라이언트만
할 수 있는 일이다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.career_sandbox_dto import (
    CareerOutcome,
    CareerSummaryDto,
    CareerViewDto,
    LogDto,
)


class RequestKeyConflictError(Exception):
    """같은 요청 키에 **다른 payload** 가 들어왔다.

    재시도로 볼 수 없다 — 돌려줄 응답은 다른 요청의 것이고, 적용하면 키가
    가리키는 요청이 둘이 된다. 그래서 거부한다(라우터가 409 로 번역한다).

    실수의 방향이 비대칭이라 거부가 맞다: 거부는 화면이 새 키로 다시 보내면
    끝이지만, 통과는 사용자가 하지 않은 행동이 적용되거나 하지 않은 행동의 응답을
    받는 것이다.
    """


class CareerSandboxUseCase(ABC):
    @abstractmethod
    async def create(
        self, *, user_id: int, name: str, style: str, age: int, seed: int | None = None
    ) -> CareerViewDto:
        """새 커리어. `seed` 를 주면 결과가 재현된다(테스트·공유용)."""
        ...

    @abstractmethod
    async def list_careers(self, user_id: int) -> list[CareerSummaryDto]: ...

    @abstractmethod
    async def view(self, *, user_id: int, career_id: int) -> CareerViewDto | None:
        """현재 상태. **재접속 복구가 이 한 번의 호출이다.**"""
        ...

    @abstractmethod
    async def act(
        self,
        *,
        user_id: int,
        career_id: int,
        action: str,
        target: str | None,
        request_id: str,
    ) -> CareerOutcome:
        """주간 행동 하나. 포인트가 없거나 입력이 틀리면 `ValueError`.

        같은 `request_id` 로 다시 오면 **아무것도 바꾸지 않고** 최초 응답을
        돌려준다. 같은 키에 다른 행동이면 `RequestKeyConflictError`.
        """
        ...

    @abstractmethod
    async def advance(
        self, *, user_id: int, career_id: int, request_id: str
    ) -> CareerOutcome:
        """한 주 진행. 같은 `request_id` 의 재시도는 **주차를 넘기지 않는다.**"""
        ...

    @abstractmethod
    async def resolve(
        self,
        *,
        user_id: int,
        career_id: int,
        event_id: str,
        choice: str,
        request_id: str,
    ) -> CareerOutcome:
        """사건 해결. **같은 사건을 두 번 해결할 수 없다**(멱등)."""
        ...

    @abstractmethod
    async def settle(
        self, *, user_id: int, career_id: int, request_id: str
    ) -> CareerOutcome:
        """시즌 결산. **나이가 여기서만 오르고, 한 번만 오른다.**"""
        ...

    @abstractmethod
    async def next_season(
        self, *, user_id: int, career_id: int, request_id: str
    ) -> CareerOutcome:
        """다음 시즌 시작. 주차만 1로 돌아가고 나머지는 보존된다."""
        ...

    @abstractmethod
    async def log(
        self,
        *,
        user_id: int,
        career_id: int,
        season: int | None,
        limit: int,
        offset: int,
    ) -> list[LogDto]:
        """커리어 기록. 긴 목록이므로 페이지로 끊는다."""
        ...
