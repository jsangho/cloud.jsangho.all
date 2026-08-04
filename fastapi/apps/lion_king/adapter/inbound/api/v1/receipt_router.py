"""영수증 판독 엔드포인트 (S3 → 서버 역방향 파이프라인).

⚠️ **인증 필수다.** 무인증 엔드포인트는 우리 자격증명으로 S3를 읽고 OCR 비용을
태우는 입구가 된다.

상태 코드에서 403을 쓰지 않는다 — 남의 키를 지정한 요청과 없는 키를 지정한 요청이
같은 404를 받아야 존재 여부를 탐색할 수 없다.
"""

from __future__ import annotations

from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from lion_king.adapter.inbound.api.schemas.receipt_schema import (
    OcrReceiptRequest,
    ReceiptDraftResponse,
    ReceiptLineItemResponse,
    ReceiptListResponse,
    ReceiptSummaryResponse,
)
from lion_king.app.dtos.receipt_dto import OcrReceiptCommand
from lion_king.app.ports.input.receipt_use_case import ReceiptUseCase
from lion_king.app.ports.output.photo_repository import PhotoStorageUnavailableError
from lion_king.app.ports.output.receipt_image_repository import ObjectNotFoundError
from lion_king.app.ports.output.receipt_ocr_port import OcrUnavailableError
from lion_king.dependencies.receipt_provider import get_receipt_use_case
from lion_king.domain.services.receipt_parser import ReceiptNotRecognizedError
from lion_king.domain.value_objects.receipt_key import ReceiptKeyNotOwnedError

from fastapi import APIRouter, Depends, HTTPException

receipt_router = APIRouter(prefix="/receipts", tags=["receipts"])

_NOT_FOUND_DETAIL = "영수증 이미지를 찾을 수 없습니다."
_STORAGE_DETAIL = "사진 보관소를 사용할 수 없습니다."


@receipt_router.get(
    "", response_model=ReceiptListResponse, response_model_by_alias=True
)
async def list_receipts(
    claims: TokenPayload = Depends(get_current_user),
    use_case: ReceiptUseCase = Depends(get_receipt_use_case),
):
    """보관 중인 사진 목록. 판독은 하지 않는다 — 목록 길이만큼 OCR 비용이 곱해진다."""
    try:
        summaries = await use_case.list_receipts(user_id=claims.sub)
    except PhotoStorageUnavailableError as exc:
        raise HTTPException(status_code=503, detail=_STORAGE_DETAIL) from exc

    return ReceiptListResponse(
        items=[
            ReceiptSummaryResponse(
                key=summary.key,
                thumbnail_url=summary.thumbnail_url,
                captured_at=summary.captured_at,
            )
            for summary in summaries
        ]
    )


@receipt_router.post(
    "/ocr", response_model=ReceiptDraftResponse, response_model_by_alias=True
)
async def read_receipt(
    request: OcrReceiptRequest,
    claims: TokenPayload = Depends(get_current_user),
    use_case: ReceiptUseCase = Depends(get_receipt_use_case),
):
    """보관된 영수증 한 장을 판독해 가계부 초안을 돌려준다."""
    try:
        draft = await use_case.read_receipt(
            OcrReceiptCommand(user_id=claims.sub, key=request.key)
        )
    except (ReceiptKeyNotOwnedError, ObjectNotFoundError) as exc:
        # 남의 키와 없는 키를 같은 응답으로 묶는다 (403을 쓰지 않는 이유).
        raise HTTPException(status_code=404, detail=_NOT_FOUND_DETAIL) from exc
    except ReceiptNotRecognizedError as exc:
        raise HTTPException(
            status_code=422,
            detail="영수증을 인식하지 못했습니다. 다시 촬영해 주세요.",
        ) from exc
    except PhotoStorageUnavailableError as exc:
        raise HTTPException(status_code=503, detail=_STORAGE_DETAIL) from exc
    except OcrUnavailableError as exc:
        raise HTTPException(
            status_code=503, detail="영수증 판독을 잠시 사용할 수 없습니다."
        ) from exc

    return ReceiptDraftResponse(
        merchant_name=draft.merchant_name,
        business_no=draft.business_no,
        transacted_at=draft.transacted_at,
        total_amount=draft.total_amount,
        vat_amount=draft.vat_amount,
        currency=draft.currency,
        line_items=[
            ReceiptLineItemResponse(
                name=item.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                amount=item.amount,
            )
            for item in draft.line_items
        ],
        confidence=draft.confidence,
        needs_review=draft.needs_review,
    )
