from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from titanic.adapter.inbound.api.schemas.crew_james_director_schema import (
    JamesDirectorFileuploadResponse,
    JamesDirectorMyselfSchema,
    JamesDirectorSchema,
)
from titanic.app.dtos.crew_james_director_dto import (
    JamesDirectorQuery,
    JamesDirectorResponse,
    TitanicRecordCommand,
)
from titanic.app.ports.input.crew_james_director_use_case import JamesDirectorUseCase
from titanic.dependencies.crew_james_director_provider import get_james_director

"""
 감독: 제임스 카메론 (James Cameron)
 전설적인 흥행작 <타이타닉>을 연출하여
 "내가 세상의 왕이다!"를 외친 제임스 카메론 감독의 라우터
 완벽주의 성향으로 타이타닉의 모든 세트와 디테일을
 고증한 아키텍처의 총괄 디렉터 역할 수행
"""

james_director_router = APIRouter(prefix="/james", tags=["james"])


def _parse_uploaded_csv(raw: bytes) -> JamesDirectorSchema:
    if not raw.strip():
        raise HTTPException(status_code=400, detail="빈 CSV 파일입니다.")
    schema = JamesDirectorSchema.from_csv_bytes(raw)
    if not schema.records:
        raise HTTPException(status_code=400, detail="CSV에 데이터 행이 없습니다.")
    return schema


def _to_fileupload_response(result: dict[str, int]) -> JamesDirectorFileuploadResponse:
    count = result["count"]
    return JamesDirectorFileuploadResponse(count=count, inserted=count)


def _to_record_commands(records: list) -> list[TitanicRecordCommand]:
    return [
        TitanicRecordCommand(
            passenger_id=record.passenger_id or "",
            survived=record.survived or "",
            pclass=record.pclass or "",
            name=record.name or "",
            gender=record.gender or "",
            age=record.age or "",
            sib_sp=record.sib_sp or "",
            parch=record.parch or "",
            ticket=record.ticket or "",
            fare=record.fare or "",
            cabin=record.cabin or "",
            embarked=record.embarked or "",
        )
        for record in records
    ]


@james_director_router.get("/myself")
async def introduce_myself(
    james: JamesDirectorUseCase = Depends(get_james_director),
) -> JamesDirectorResponse:
    schema = JamesDirectorMyselfSchema(id=2, name="James Cameron")
    query = JamesDirectorQuery(id=schema.id, name=schema.name)
    return await james.introduce_myself(query)


@james_director_router.post(
    "/fileupload",
    response_model=JamesDirectorFileuploadResponse,
    summary="타이타닉 승객 데이터 CSV 파일 업로드",
)
async def upload_titanic_file(
    file: UploadFile = File(...),
    james: JamesDirectorUseCase = Depends(get_james_director),
):
    """타이타닉 승객 데이터 CSV 파일 업로드"""
    schema = _parse_uploaded_csv(await file.read())
    result = await james.upload_titanic_file(_to_record_commands(schema.records))
    return _to_fileupload_response(result)
