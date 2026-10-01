from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PendingMatchSchema(BaseModel):
    """결과가 없는 경기 하나. **모델을 부르지 않고** 읽은 값이다."""

    model_config = ConfigDict(populate_by_name=True)

    event_slug: str = Field(alias="eventSlug")
    event_label: str = Field(alias="eventLabel")
    match_key: str = Field(alias="matchKey")
    title: str
    #: 카드에 실린 이름들. 보류 사유(`name_not_on_card`)를 사람이 읽으려면 필요하다.
    options: list[str] = Field(default_factory=list)


class PendingMatchListSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[PendingMatchSchema]


class VerifyResultsRequest(BaseModel):
    """실행 요청.

    `apply`가 **기본 거짓**이다 — 쓰는 값이 모델이 읽은 문서에서 파생되므로, 쓰기는
    언제나 명시해야 한다(`verify_match_results.py --apply`와 같은 규약).
    """

    model_config = ConfigDict(populate_by_name=True)

    event_slug: str | None = Field(default=None, alias="eventSlug")
    #: 비우면 `limit`이 앞에서부터 자른다. 화면은 사람이 집은 경기를 하나씩 보낸다.
    match_keys: list[str] = Field(default_factory=list, alias="matchKeys")
    #: 비용이 경기 수에 비례하므로 상한을 낮게 둔다.
    limit: int = Field(default=5, ge=1, le=20)
    apply: bool = False


class MatchVerificationSchema(BaseModel):
    """경기 하나의 결과 — 쓴 것과 보류한 것 모두 같은 모양으로 보고된다.

    **모델 이름은 넣지 않는다** (§11 검증 기준 6: 응답 어디에도 모델 이름이 없다).
    비용을 보는 자리는 `toolCalls`다.
    """

    model_config = ConfigDict(populate_by_name=True)

    event_slug: str = Field(alias="eventSlug")
    match_key: str = Field(alias="matchKey")
    title: str
    #: 쓸 수 있다고 판정된 값. 보류면 둘 다 `null`이다.
    pick: str | None = None
    winner_name: str | None = Field(default=None, alias="winnerName")
    #: 보류 사유. `null`이면 보류가 아니다.
    hold: str | None = None
    #: **실제로 DB에 썼는가.** 드라이런에서는 `pick`이 있어도 거짓이다.
    written: bool = False
    #: 모델이 든 근거 구절. `quote_not_found` 를 사람이 판단하는 자리다.
    quote: str = ""
    source_title: str = Field(default="", alias="sourceTitle")
    source_revision_id: str | None = Field(default=None, alias="sourceRevisionId")
    tool_calls: int = Field(default=0, alias="toolCalls")


class VerificationRunSchema(BaseModel):
    """한 실행 전체의 보고."""

    model_config = ConfigDict(populate_by_name=True)

    matches: list[MatchVerificationSchema]
    #: 쓰기 모드로 돌았는가.
    applied: bool
    #: 결과 미기록으로 **찾아낸** 경기 수. 고르기·자르기 이전 총수다 — 이 값이 없으면
    #: 한 건만 돌린 실행이 "하나밖에 없다"로 읽힌다.
    found: int
    written: int
    #: 쓸 수 있다고 판정된 수. 드라이런에서 `written`은 0이고 이 값만 올라간다.
    writable: int
    held: int
    tool_calls: int = Field(alias="toolCalls")
