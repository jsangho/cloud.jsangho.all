from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class EventStatusDriftItemSchema(BaseModel):
    """대회 하나의 판정.

    `verdict`는 넷 중 하나다 — `needs_close`(날짜가 지났는데 안 닫혔다) ·
    `already_finished` · `upcoming`(아직 안 지났다) · `unknown_date`(날짜 미상이라
    **보류**. 통과가 아니다).
    """

    model_config = ConfigDict(populate_by_name=True)

    slug: str
    status: str
    start_date: date | None = Field(default=None, alias="startDate")
    end_date: date | None = Field(default=None, alias="endDate")
    verdict: str


class EventStatusDriftSchema(BaseModel):
    """점검 결과.

    `written`이 `null`이면 **쓰지 않았다**는 뜻이다 — 0(쓸 게 없었다)과 다르다.
    """

    model_config = ConfigDict(populate_by_name=True)

    #: 판정 기준일(UTC). 대회 당일은 지난 것으로 보지 않는다.
    today: date
    items: list[EventStatusDriftItemSchema]
    pending: int
    written: int | None = None
