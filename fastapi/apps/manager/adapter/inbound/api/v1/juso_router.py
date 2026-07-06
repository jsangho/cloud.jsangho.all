from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from manager.adapter.inbound.api.schemas.juso_schema import (
    JusoFileuploadResponse,
    JusoMyselfSchema,
    JusoSchema,
)
from manager.app.dtos.juso_dto import (
    ContactListItem,
    ContactRecordCommand,
    JusoQuery,
    JusoResponse,
)
from manager.app.ports.input.juso_use_case import JusoUseCase
from manager.dependencies.juso_provider import get_juso_use_case

juso_router = APIRouter(prefix="/juso", tags=["juso"])


def _parse_uploaded_csv(raw: bytes) -> JusoSchema:
    if not raw.strip():
        raise HTTPException(status_code=400, detail="빈 CSV 파일입니다.")
    schema = JusoSchema.from_csv_bytes(raw)
    if not schema.records:
        raise HTTPException(status_code=400, detail="CSV에 데이터 행이 없습니다.")
    return schema


def _to_fileupload_response(result: dict[str, int]) -> JusoFileuploadResponse:
    count = result["count"]
    return JusoFileuploadResponse(count=count, inserted=count)


def _to_record_commands(records: list) -> list[ContactRecordCommand]:
    return [
        ContactRecordCommand(
            name=record.name,
            given_name=record.given_name,
            family_name=record.family_name,
            nickname=record.nickname,
            birthday=record.birthday,
            gender=record.gender,
            occupation=record.occupation,
            notes=record.notes,
            group_membership=record.group_membership,
            email_1_type=record.email_1_type,
            email_1_value=record.email_1_value,
            email_2_type=record.email_2_type,
            email_2_value=record.email_2_value,
            phone_1_type=record.phone_1_type,
            phone_1_value=record.phone_1_value,
            phone_2_type=record.phone_2_type,
            phone_2_value=record.phone_2_value,
            address_1_formatted=record.address_1_formatted,
            address_1_street=record.address_1_street,
            address_1_city=record.address_1_city,
            address_1_region=record.address_1_region,
            address_1_postal_code=record.address_1_postal_code,
            address_1_country=record.address_1_country,
            org_name=record.org_name,
            org_title=record.org_title,
            org_department=record.org_department,
            website_1_value=record.website_1_value,
        )
        for record in records
    ]


@juso_router.get("/contacts", summary="등록된 연락처 목록 조회")
async def list_contacts(
    use_case: JusoUseCase = Depends(get_juso_use_case),
) -> list[ContactListItem]:
    return await use_case.list_contacts()


@juso_router.delete("/contacts", summary="등록된 연락처 전체 삭제")
async def delete_all_contacts(
    use_case: JusoUseCase = Depends(get_juso_use_case),
) -> dict[str, int]:
    return await use_case.delete_all_contacts()


@juso_router.get("/myself")
async def introduce_myself(
    use_case: JusoUseCase = Depends(get_juso_use_case),
) -> JusoResponse:
    schema = JusoMyselfSchema()
    query = JusoQuery(id=schema.id, name=schema.name)
    return await use_case.introduce_myself(query)


@juso_router.post(
    "/fileupload",
    response_model=JusoFileuploadResponse,
    summary="Google Contacts CSV 파일 업로드",
)
async def upload_contacts(
    file: UploadFile = File(...),
    use_case: JusoUseCase = Depends(get_juso_use_case),
):
    """Google Contacts 형식 CSV 파일 업로드"""
    schema = _parse_uploaded_csv(await file.read())
    result = await use_case.upload_contacts(_to_record_commands(schema.records))
    return _to_fileupload_response(result)
