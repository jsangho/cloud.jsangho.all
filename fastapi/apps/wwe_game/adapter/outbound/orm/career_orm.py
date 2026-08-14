"""커리어 세이브 테이블 (하네스 §6 DB 엔티티 · `_docs/ENTITY_RULE.md` · T9).

접두사는 `career_`로 통일한다 — kayfabe가 `ple_*`를 쓰는 것과 같은 이유다.

## 무엇을 표로 빼고 무엇을 칸에 두었나

하네스가 표 다섯 개를 정했다. 그 기준을 그대로 따르되, **목록 중 일부는 칼럼에 둔다.**

| 자료 | 자리 | 이유 |
|---|---|---|
| 대립 · 주차 로그 · 1회성 이벤트 · 트로피 | **표** | 하네스 §6이 정한 것 |
| `titles_held` · `titles_won` · `flags` · `recent_events` | **칼럼(JSON)** | 아래 |

**진행 한 번 = 저장 한 번**(§3-D6)이라, 세이브는 매번 통째로 다시 쓰인다. 순서 있는
512칸짜리 `recent_events`를 표로 빼면 그때마다 512행을 지웠다 다시 넣어야 한다. 조회
단위도 아니다 — 항상 세이브와 함께 읽고 함께 쓴다. 그래서 칼럼이다.

반대로 로그·1회성 이벤트·트로피는 **쌓이기만 하고**, 로그는 페이지 단위로 따로 읽는다
(30년이면 1560줄이다). 그건 표가 맞다.

## 값 객체를 칼럼으로 펴는 이유

`stats`·`condition`·`pending_event`를 JSON 한 덩어리로 넣으면 마이그레이션 없이 필드를
늘릴 수 있어 편하지만, **DB가 그 안을 못 본다** — "인기도 90 이상인 세이브"를 물어볼 수
없고, 잘못된 값이 들어가도 제약이 못 잡는다. 자주 바뀌지 않는 구조라 펴 두는 쪽이 낫다.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

RUN_FK = "career_runs.id"


class CareerRunModel(Base):
    """진행 중이거나 끝난 커리어 하나. **사용자당 진행 중인 것은 하나뿐이다**(§3-D8)."""

    __tablename__ = "career_runs"
    __table_args__ = (
        Index("ix_career_runs_user_status", "user_id", "status"),
        # 진행 중 세이브가 하나뿐이라는 규칙은 유스케이스가 지킨다(§13-Q4). DB 제약으로
        # 걸면 끝난 세이브까지 한 줄로 묶여 이력을 못 남긴다.
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # ── 정체성 (§3-D10) ──
    name: Mapped[str] = mapped_column(String(20))
    gender: Mapped[str] = mapped_column(String(10))
    country: Mapped[str] = mapped_column(String(10))
    play_style: Mapped[str] = mapped_column(String(20))

    # ── 시계 ──
    mode_code: Mapped[str] = mapped_column(String(20))
    seed: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer, default=0)

    # ── 스탯 여섯 (§3-D18) ──
    popularity: Mapped[int] = mapped_column(Integer, default=0)
    in_ring: Mapped[int] = mapped_column(Integer, default=0)
    mic_work: Mapped[int] = mapped_column(Integer, default=0)
    backstage: Mapped[int] = mapped_column(Integer, default=0)
    alignment: Mapped[int] = mapped_column(Integer, default=0)

    # ── 컨디션 (§3-D16) ──
    condition_grade: Mapped[str] = mapped_column(String(20))
    condition_weeks_left: Mapped[int] = mapped_column(Integer, default=0)
    condition_part: Mapped[str | None] = mapped_column(String(20), nullable=True)
    """다친 곳 (§3-D43). 건강하면 None."""
    wear: Mapped[int] = mapped_column(Integer, default=0)

    # ── 대기 이벤트 — 있으면 진행이 막힌다 (§3-D2) ──
    pending_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    pending_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pending_body_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pending_rival: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # ── 소속·벨트 (§3-D20) ──
    brand: Mapped[str] = mapped_column(String(20))
    titles_held: Mapped[list[str]] = mapped_column(JSON, default=list)
    titles_won: Mapped[list[str]] = mapped_column(JSON, default=list)
    """**순서를 지킨다** — 더블 그랜드슬램은 그룹별 획득 횟수로 판정한다(§3-D20)."""

    # ── 누적·상태 ──
    team: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    """지금 속한 팀 (§3-D30). `{"name", "members", "formed_week"}` 또는 None.

    표로 빼지 않는 이유는 `titles_held`와 같다 — 진행 한 번이 세이브를 통째로 다시
    쓰므로(§3-D6) 조회 단위가 아닌 값을 표로 빼면 저장마다 행을 지웠다 다시 넣게 된다.
    """
    flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    recent_events: Mapped[list[str]] = mapped_column(JSON, default=list)
    """쿨다운과 본문 변주 순환이 함께 읽는 최근 이력. 최대 512칸(§event_draw)."""
    injured_parts: Mapped[list[str]] = mapped_column(JSON, default=list)
    """지금까지 다친 적 있는 부위 (§3-D43). **몸이 기억한다** — 재발이 여기서 나온다."""
    events_fired: Mapped[int] = mapped_column(Integer, default=0)
    release_weeks: Mapped[int] = mapped_column(Integer, default=0)
    decline_weeks: Mapped[int] = mapped_column(Integer, default=0)
    tournament_round: Mapped[int] = mapped_column(Integer, default=0)
    """킹 앤 퀸 오브 더 링에서 이긴 라운드 수 (§3-D33). 한 주에 안 끝나는 유일한 형식이다."""
    title_shot: Mapped[bool] = mapped_column(Boolean, default=False)
    """레슬매니아 1선 도전권 (§3-D36). 럼블·챔버 우승이 준다."""
    briefcase_week: Mapped[int] = mapped_column(Integer, default=0)
    """MITB 가방을 딴 주차. 0이면 없다 — **기한이 있어 불리언이 아니다** (§3-D36)."""
    status: Mapped[str] = mapped_column(String(20), index=True)
    end_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ── 계약·돈 (§3-D47) ──
    money: Mapped[int] = mapped_column(BigInteger, default=0)
    """잔액(달러). **`BigInteger`인 이유**: 30년 정상급이면 주 $9만 × 1560주라
    `Integer`(21억)에 닿지는 않지만, 여유를 두지 않을 이유도 없다."""
    contract_pay: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contract_signed_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contract_ends_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unsigned_weeks: Mapped[int] = mapped_column(Integer, default=0)
    goal: Mapped[str | None] = mapped_column(String(16), nullable=True, default=None)
    """이번 분기에 건 것 (§3-D80). 옛 세이브는 `NULL`이라 처음 이어 갈 때 묻는다."""
    goal_quarter: Mapped[int] = mapped_column(Integer, default=-1)
    finisher: Mapped[str] = mapped_column(String(30), default="")
    """지금 쓰는 피니셔 (§3-D88). **빈 문자열이 곧 기본값이다** — 옛 행이 그 상태다."""
    finisher_name: Mapped[str] = mapped_column(String(40), default="")
    """직접 지은 기술 이름 (§3-D88). 코드 칸과 나눠 둔다."""
    finisher_week: Mapped[int] = mapped_column(Integer, default=0)
    """마지막으로 바꾼 주차. 쿨다운 전용이다."""
    offer_week: Mapped[int] = mapped_column(Integer, default=0)
    """재계약 협상이 열린 주차 (§3-D84). 0이면 열려 있지 않다.

    **저장해야 한다.** 협상은 답할 때까지 진행을 막으므로(§11-1), 이 칸이 안 남으면
    새로고침 한 번에 협상이 사라지고 계약 없이 뛰게 된다."""
    """계약 없이 보낸 연속 주차 (§3-D50). 여기가 차면 `EndReason.FADED`다."""
    """계약 한 장을 세 칼럼으로 편다. **셋은 함께 있거나 함께 없다** — 무소속이 None이다.

    JSON 한 칸으로 두지 않은 이유: 만료 주차는 "곧 만료되는 세이브"를 묻는 조회의
    조건이 될 수 있는 값이라, 컬럼으로 두면 나중에 인덱스를 걸 수 있다.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class CareerRivalryModel(Base):
    """대립 상태. 한 세이브에 동시에 두 개까지다(`rivalry_engine.MAX_ACTIVE`)."""

    __tablename__ = "career_rivalries"
    __table_args__ = (
        UniqueConstraint("run_id", "rival_name", name="uq_career_rivalry"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey(RUN_FK, ondelete="CASCADE"), index=True
    )
    rival_name: Mapped[str] = mapped_column(String(60))
    stage: Mapped[str] = mapped_column(String(20))
    heat: Mapped[int] = mapped_column(Integer, default=0)
    started_week: Mapped[int] = mapped_column(Integer, default=0)
    opened_by: Mapped[str] = mapped_column(String(10), default="rival")
    """누가 먼저 걸었는가 (§3-D86). **옛 행은 전부 `rival`이다** — §3-D86 이전의
    대립은 규칙이 열었고, 그건 상대가 지목해 온 것이다."""


class CareerLogEntryModel(Base):
    """자동 진행 한 줄 = 한 행 (§6).

    **리포트 전체를 저장하지 않는다.** 화면과 재조회에 필요한 것은 주차·종류·결과와
    문장뿐이고, 스탯 델타 같은 판정 중간값은 세이브에 이미 반영돼 있다.
    """

    __tablename__ = "career_log_entries"
    __table_args__ = (
        UniqueConstraint("run_id", "week", name="uq_career_log_week"),
        Index("ix_career_log_run_week", "run_id", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey(RUN_FK, ondelete="CASCADE"), index=True
    )
    week: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    result: Mapped[str | None] = mapped_column(String(10), nullable=True)
    show_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    title_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    narration: Mapped[str] = mapped_column(String(400))
    opponent: Mapped[str | None] = mapped_column(String(60), nullable=True)
    match_kind: Mapped[str | None] = mapped_column(String(30), nullable=True)
    """경기 형식 (§3-D32). 이게 없으면 다시 연 로그에서 럼블이 싱글로 읽힌다."""
    match_summary: Mapped[str | None] = mapped_column(String(120), nullable=True)
    """탈락 경기의 한 줄 요약 (§3-D34). **비트 전체는 저장하지 않는다** — 럼블 하나가
    59줄이라 커리어당 2천 줄이 된다 (2026-08-11 사용자 결정).
    """
    popularity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alignment: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """그 주차 **끝의** 인기도와 성향 (§3-D39).

    뉴스의 군중 반응과 턴 판정이 이 둘만 읽는다. 저장하지 않던 시절에는 30년치 반응을
    **마지막 스탯 하나로** 계산해서, 힐턴 이전의 대관에도 야유가 붙었다 —
    `compile_feed`의 설명이 경고하던 바로 그 상황이 실제로 벌어지고 있었다.

    **스탯 전체를 담지 않는다.** 읽는 것이 둘뿐인데 여섯을 저장하면 로그가 커진다.
    옛 행은 None이고, 그때는 최종 스탯으로 되돌아간다.
    """


class CareerSeenEventModel(Base):
    """1회성 이벤트 기록. `(run_id, code)`가 유니크다 — 같은 카드는 한 판에 한 번."""

    __tablename__ = "career_seen_events"
    __table_args__ = (UniqueConstraint("run_id", "code", name="uq_career_seen_event"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey(RUN_FK, ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(60))


class CareerTrophyModel(Base):
    """획득 트로피. 게임 안에서 완결되고 플랫폼 순위표와 엮지 않는다(§3-D7)."""

    __tablename__ = "career_trophies"
    __table_args__ = (UniqueConstraint("run_id", "code", name="uq_career_trophy"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey(RUN_FK, ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(60))
    week: Mapped[int] = mapped_column(Integer, default=0)
