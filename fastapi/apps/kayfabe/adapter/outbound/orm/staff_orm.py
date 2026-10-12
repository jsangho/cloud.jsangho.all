"""비선수 인원 — 경영진·해설·링아나운서·심판·프로듀서 (`wwe_staff`).

**선수와 같은 표에 넣지 않는다.** `wrestlers`는 예측·전적·임베딩이 매달린 표다.
해설자를 거기 넣으면 선수 수가 늘고, 전적 집계가 경기에 나오지 않는 사람을 세기
시작하며, 벡터 검색에도 섞인다. 역할이 다르면 표도 다르다.

원본은 `_docs/wwe_non_wrestler.csv`이고 `scripts/load_staff_csv.py`가 넣는다.
**67행 중 생년월일이 완전한 행이 64개, `1974-??-??`처럼 월·일을 모르는 행이 3개다**
(2026-10-12 실측). 읽는 쪽이 그 차이를 알아야 하므로 `birth_date`는 선수 표와 같이
**`String`이고 날짜로 파싱하지 않는다** — 모르는 날짜를 1월 1일로 접으면 생일이
아닌 사람이 생일로 뜬다.
"""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.matrix.grid_oracle_database_manager import Base


class StaffOrm(Base):
    __tablename__ = "wwe_staff"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    #: 업무상 식별자. CSV가 이 이름으로 upsert하므로 유일해야 한다.
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    real_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ring_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    korean_ring_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    #: "Commentator" · "Ring Announcer" · "Producer" 등. CSV에 빈 값이 18행 있다.
    role: Mapped[str | None] = mapped_column(String(200), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    #: `YYYY-MM-DD` 또는 `1974-??-??` 또는 빈 값. **파싱은 읽는 쪽이 한다.**
    birth_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    birth_place: Mapped[str | None] = mapped_column(String(150), nullable=True)
    #: 선수 경력이 있는가 — CSV의 `wrestling_experience`("Yes"/"No"/선수명).
    wrestling_experience: Mapped[str | None] = mapped_column(String(100), nullable=True)
    #: CSV의 `Wrestler&Team&Stable` — 담당 선수·팀.
    wrestler_team_stable: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: CSV의 `#` 구역. 브랜드일 수도("RAW") 직군일 수도("Executives") 있다 —
    #: 그래서 `brand`가 아니라 `group_label`이다.
    group_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
