"""커리어 샌드박스 세이브 — **세이브는 표 하나, JSON 한 칸.**

## 표가 둘인데 규칙은 깨지지 않았다

아래 "표가 하나" 는 **세이브**에 대한 규칙이다 — 세계를 여러 표에 쪼개면
마이그레이션이 규칙 수만큼 늘어난다는 이야기고, `sandbox_careers` 는 그대로 한
칸이다.

`sandbox_career_requests` 는 세이브의 일부가 아니다. **요청 처리 이력**이고,
게임 규칙이 늘어도 칸이 늘지 않는다(요청 id·지문·응답 셋이 전부다). 세이브 안에
넣지 않은 이유는 셋이다 — (1) 보존 기간이 세이브와 다르다(영수증은 버려도 되고
세이브는 못 버린다), (2) 고유 제약으로 중복을 DB 가 막아 줘야 한다, (3) 응답
본문이 통째로 들어가서 세이브 JSON 을 수십 배로 부풀린다.

## 왜 표가 하나인가

이전 커리어 시뮬레이터는 세이브 하나를 다섯 표에 나눠 넣었고(`career_runs` ·
`career_rivalries` · `career_log_entries` · `career_seen_events` ·
`career_trophies`) 마이그레이션이 **열두 개**로 불어났다 — 게임에 칸을 하나 더할
때마다 ALTER 가 하나씩 붙었기 때문이다. 그 표들은 지금도 DB 에 남아 있고(약 62행)
**이 작업은 건드리지 않는다.**

진행 한 번이 세이브를 통째로 다시 쓰므로 쪼갤 이유가 없다. 세계는 JSON 한 칸이고
(`world`), **게임 규칙이 늘어도 스키마가 그대로**다.

## 칼럼으로 뺀 셋

`season`·`week`·`phase` 는 JSON 안에도 있지만 밖으로 복사해 둔다. 목록 화면이
"시즌 3 · 12주차" 를 보여 주려고 세이브를 전부 역직렬화하지 않게 하려는 것이다.
**정본은 JSON 쪽이고 이 셋은 거울이다** — 쓰는 곳이 한 곳이라
(`SandboxCareerPgRepository.save`) 갈라질 자리가 없다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.matrix.grid_oracle_database_manager import Base


class SandboxCareerModel(Base):
    """커리어 하나 = 세계 하나. **사용자 소유다.**

    `user_id` 로 FK 를 걸고 인덱스를 둔다. 조회·수정은 반드시 `user_id` 와 함께
    건다 — 남의 커리어를 열지 못하게 하는 것은 쿼리의 책임이다
    (`shop_pg_repository.set_equipped` 가 같은 규칙을 쓴다).
    """

    __tablename__ = "sandbox_careers"

    #: 목록 질의(`내 커리어를 최근 것부터`)가 쓰는 복합 인덱스.
    #:
    #: **마이그레이션에만 있고 모델에 없었다**(2026-10-21 실측). 이 저장소는 표를
    #: 기동 시 `create_all` 로도 만들므로(`init_db`), 모델에 없으면 그렇게 만들어진
    #: DB 에는 인덱스가 **생기지 않는다.** 게다가 다음 `--autogenerate` 가
    #: "모델에 없는 인덱스" 로 보고 `drop_index` 를 제안한다 — 실제로 제안했다.
    __table_args__ = (
        Index(
            "ix_sandbox_careers_user_updated",
            "user_id",
            text("updated_at DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: 플레이어 선수의 링네임. 목록에 보여 준다.
    player_name: Mapped[str] = mapped_column(String(40), nullable=False)
    #: 결정론의 뿌리. 같은 시드·같은 입력이면 같은 결과다.
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    #: `server_default` 를 함께 두는 것은 **두 경로가 같은 표를 만들게** 하려는
    #: 것이다 — 마이그레이션은 이 기본값을 넣고 모델은 파이썬 쪽 `default` 만
    #: 갖고 있어서, 어느 쪽이 만들었느냐에 따라 DDL 이 갈렸다(실측).
    season: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    week: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    #: `career_world.Phase` 값. 목록이 "진행 중/결산 대기/종료" 를 가른다.
    phase: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="in_season",
        server_default=text("'in_season'"),
    )
    #: 세계 전체. 모양은 `career_world_codec` 이 정한다.
    world: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SandboxCareerRequestModel(Base):
    """처리가 끝난 쓰기 요청 하나. **중복 재적용을 막는 자리다.**

    행 잠금(`load_for_update`)은 **잃어버린 갱신**만 막는다 — 두 요청이 같은
    연산인지 아닌지를 모르므로 순서만 주고 둘 다 적용한다(2026-10-21 실측: 프로모
    두 번이 인기도를 두 번 올리고, 주차 진행 두 번이 두 주를 넘긴다). 도메인의
    `WorldState.applied` 도 못 막는다: 행동 키의 순번이 **남은 포인트**에서 나와
    재시도가 다음 순번을 쓴다.

    요청을 요청으로 식별하려면 **클라이언트가 만든 키**가 필요하고, 그 키를 적어
    두는 곳이 이 표다.

    ## 고유 제약이 계약이다

    `(user_id, career_id, request_id)` 하나. 이것이 B절의 격리 둘을 동시에
    만족시킨다 — 같은 사용자의 서로 다른 커리어, 서로 다른 사용자가 같은 키를
    써도 섞이지 않는다. `career_id` 만으로도 사용자가 정해지지만 `user_id` 를
    함께 두는 것은 조회가 늘 사용자와 함께 걸리기 때문이다(이 저장소 관례).
    """

    __tablename__ = "sandbox_career_requests"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "career_id",
            "request_id",
            name="uq_sandbox_career_requests_scope",
        ),
        #: 보존 상한을 적용할 때 쓰는 인덱스 — "이 커리어의 최신 N 개" 질의.
        Index("ix_sandbox_career_requests_career_id", "career_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    #: 세이브가 지워지면 영수증도 같이 간다. 남겨 둘 이유가 없다.
    career_id: Mapped[int] = mapped_column(
        ForeignKey("sandbox_careers.id", ondelete="CASCADE"), nullable=False
    )
    #: 클라이언트가 만든 키. **서버가 만들면 재시도를 식별할 수 없다.**
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    #: payload 의 sha256 hex(64자). 같은 키에 다른 payload 면 409 로 거부한다.
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    #: 최초 요청의 응답 본문. 재시도가 **같은 답**을 받게 하는 칸이다.
    response: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
