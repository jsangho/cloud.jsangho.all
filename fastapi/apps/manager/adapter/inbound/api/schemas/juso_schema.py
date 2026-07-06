from __future__ import annotations

import csv
import io

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fastapi import HTTPException

CONTACTS_REQUIRED_COLUMNS = ("Name", "First Name")  # 둘 중 하나면 통과


def _normalize_new_format(row: dict) -> dict:
    """구글 연락처 신규 포맷(First Name/Last Name)을 구버전 alias로 변환."""
    first = row.get("First Name", "")
    last = row.get("Last Name", "")
    row["Name"] = f"{first} {last}".strip() or first or last
    row["Given Name"] = first
    row["Family Name"] = last
    row["Organization 1 - Name"] = row.get("Organization Name", "")
    row["Organization 1 - Title"] = row.get("Organization Title", "")
    row["Organization 1 - Department"] = row.get("Organization Department", "")
    row["E-mail 1 - Type"] = row.get("E-mail 1 - Label", "")
    row["E-mail 2 - Type"] = row.get("E-mail 2 - Label", "")
    row["Phone 1 - Type"] = row.get("Phone 1 - Label", "")
    row["Phone 2 - Type"] = row.get("Phone 2 - Label", "")
    row["Group Membership"] = row.get("Labels", "")
    return row


class ContactRecordSchema(BaseModel):
    """Google Contacts CSV 1행."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(alias="Name")
    given_name: str = Field(default="", alias="Given Name")
    family_name: str = Field(default="", alias="Family Name")
    nickname: str = Field(default="", alias="Nickname")
    birthday: str = Field(default="", alias="Birthday")
    gender: str = Field(default="", alias="Gender")
    occupation: str = Field(default="", alias="Occupation")
    notes: str = Field(default="", alias="Notes")
    group_membership: str = Field(default="", alias="Group Membership")
    email_1_type: str = Field(default="", alias="E-mail 1 - Type")
    email_1_value: str = Field(default="", alias="E-mail 1 - Value")
    email_2_type: str = Field(default="", alias="E-mail 2 - Type")
    email_2_value: str = Field(default="", alias="E-mail 2 - Value")
    phone_1_type: str = Field(default="", alias="Phone 1 - Type")
    phone_1_value: str = Field(default="", alias="Phone 1 - Value")
    phone_2_type: str = Field(default="", alias="Phone 2 - Type")
    phone_2_value: str = Field(default="", alias="Phone 2 - Value")
    address_1_formatted: str = Field(default="", alias="Address 1 - Formatted")
    address_1_street: str = Field(default="", alias="Address 1 - Street")
    address_1_city: str = Field(default="", alias="Address 1 - City")
    address_1_region: str = Field(default="", alias="Address 1 - Region")
    address_1_postal_code: str = Field(default="", alias="Address 1 - Postal Code")
    address_1_country: str = Field(default="", alias="Address 1 - Country")
    org_name: str = Field(default="", alias="Organization 1 - Name")
    org_title: str = Field(default="", alias="Organization 1 - Title")
    org_department: str = Field(default="", alias="Organization 1 - Department")
    website_1_value: str = Field(default="", alias="Website 1 - Value")


class JusoMyselfSchema(BaseModel):
    id: int = 2
    name: str = "Juso Manager"


class JusoSchema(BaseModel):
    """CSV 업로드 본문을 `ContactRecordSchema` 목록으로 담는 스키마."""

    records: list[ContactRecordSchema] = Field(default_factory=list)

    @staticmethod
    def _decode_csv_bytes(raw: bytes) -> str:
        for enc in ("utf-8-sig", "utf-8", "cp949"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        raise HTTPException(
            status_code=400,
            detail="CSV 인코딩을 해석할 수 없습니다. UTF-8로 저장해 주세요.",
        )

    @classmethod
    def from_csv_bytes(cls, raw: bytes) -> JusoSchema:
        return cls.from_csv_text(cls._decode_csv_bytes(raw))

    @classmethod
    def from_csv_text(cls, text: str) -> JusoSchema:
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise HTTPException(status_code=400, detail="CSV 헤더를 찾을 수 없습니다.")

        has_name = any(c in reader.fieldnames for c in CONTACTS_REQUIRED_COLUMNS)
        if not has_name:
            raise HTTPException(
                status_code=400,
                detail="CSV 컬럼 누락: Name 또는 First Name 이 필요합니다.",
            )

        is_new_format = (
            "First Name" in reader.fieldnames and "Name" not in reader.fieldnames
        )

        records: list[ContactRecordSchema] = []
        for row in reader:
            if row is None:
                continue
            if is_new_format:
                row = _normalize_new_format(row)
            try:
                records.append(ContactRecordSchema.model_validate(row))
            except ValidationError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"CSV 행 형식이 올바르지 않습니다: {exc.errors()}",
                ) from exc

        return cls(records=records)


class JusoFileuploadResponse(BaseModel):
    count: int
    inserted: int
