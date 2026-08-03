from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PhotoResponse(BaseModel):
    """업로드 결과. 필드 별칭은 저장소 관례대로 camelCase다 (Flutter가 이 이름을 읽는다)."""

    model_config = ConfigDict(populate_by_name=True)

    photo_id: str = Field(alias="photoId")
    # 버킷 이름은 담지 않는다 — 클라이언트가 알 필요가 없고, 알면 노출면만 넓어진다.
    key: str
    size_bytes: int = Field(alias="sizeBytes")
    content_type: str = Field(alias="contentType")
