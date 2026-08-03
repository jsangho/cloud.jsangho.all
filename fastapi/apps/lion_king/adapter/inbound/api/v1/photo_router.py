"""사진 보관 엔드포인트.

`/api/vision/*`과 분리한 이유: 저쪽은 얼굴 인식·비전 분석에 넣는 입구라 목적이
다르고, 섞으면 보관 정책·수명·권한이 함께 엉킨다.

⚠️ **인증 필수다.** 무인증 업로드 엔드포인트는 누구나 우리 S3에 파일을 넣을 수
있다는 뜻이고, 비용과 악용이 그대로 따라온다.
"""

from __future__ import annotations

from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from lion_king.adapter.inbound.api.schemas.photo_schema import PhotoResponse
from lion_king.app.dtos.photo_dto import UploadPhotoCommand
from lion_king.app.ports.input.photo_use_case import PhotoUseCase
from lion_king.app.ports.output.photo_repository import PhotoStorageUnavailableError
from lion_king.dependencies.photo_provider import get_photo_use_case
from lion_king.domain.value_objects.photo_content import (
    MAX_PHOTO_BYTES,
    PhotoTooLargeError,
    UnsupportedPhotoFormatError,
)

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

photo_router = APIRouter(prefix="/photos", tags=["photos"])


@photo_router.post("", response_model=PhotoResponse, response_model_by_alias=True)
async def upload_photo(
    file: UploadFile = File(...),
    claims: TokenPayload = Depends(get_current_user),
    use_case: PhotoUseCase = Depends(get_photo_use_case),
):
    """카메라로 찍은 사진 한 장을 보관한다.

    저장 경로의 유저 구분은 **JWT의 `sub`**로 정한다. 클라이언트가 보낸 값을 쓰면
    남의 폴더에 넣을 수 있다.
    """
    # 헤더의 크기를 먼저 본다 — 상한을 넘는 파일을 끝까지 읽고 나서 거절하면
    # 그 시간만큼 메모리를 점유한다. 헤더는 위조될 수 있으므로 아래에서 실제
    # 바이트 수로 다시 판단한다.
    if file.size is not None and file.size > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="사진 용량이 너무 큽니다.")

    content = await file.read()
    try:
        photo = await use_case.upload(
            UploadPhotoCommand(
                user_id=claims.sub,
                data=content,
                content_type=file.content_type or "",
            )
        )
    except UnsupportedPhotoFormatError as exc:
        raise HTTPException(
            status_code=400, detail="jpg 또는 png 사진만 올릴 수 있습니다."
        ) from exc
    except PhotoTooLargeError as exc:
        raise HTTPException(status_code=413, detail="사진 용량이 너무 큽니다.") from exc
    except PhotoStorageUnavailableError as exc:
        # 설정 문제라 사용자가 재시도해도 소용없지만, 내부 사정을 노출하지 않는다.
        raise HTTPException(
            status_code=503, detail="사진 보관소를 사용할 수 없습니다."
        ) from exc

    return PhotoResponse(
        photo_id=photo.photo_id,
        key=photo.key,
        size_bytes=photo.size_bytes,
        content_type=photo.content_type,
    )
