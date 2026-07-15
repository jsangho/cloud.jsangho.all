from __future__ import annotations

import csv
import io
from dataclasses import asdict

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fastapi import HTTPException
from titanic.app.dtos.crew_james_director_dto import BookingCommand, PersonCommand

JAMES_DIRECTOR_REQUIRED_COLUMNS = (
    "PassengerId",
    "Pclass",
    "Name",
    "Sex",
    "Age",
    "SibSp",
    "Parch",
    "Ticket",
    "Fare",
    "Cabin",
    "Embarked",
)


class TitanicRecordSchema(BaseModel):
    """CSV 1행. `Sex` 컬럼은 `gender` 필드로 매핑합니다."""

    model_config = ConfigDict(populate_by_name=True)

    passenger_id: str = Field(
        alias="PassengerId", description="타이타닉 승객 고유 번호"
    )
    survived: str = Field(
        default="",
        alias="Survived",
        description="생존 여부 (test.csv 등 미제공 시 빈 값)",
    )
    pclass: str = Field(alias="Pclass", description="티켓 등급")
    name: str = Field(alias="Name", description="이름")
    gender: str | None = Field(default=None, alias="Sex", description="성별")
    age: str = Field(alias="Age", description="나이")
    sib_sp: str = Field(alias="SibSp", description="형제자매 수")
    parch: str = Field(alias="Parch", description="부모자식 수")
    ticket: str = Field(alias="Ticket", description="티켓 번호")
    fare: str = Field(alias="Fare", description="티켓 요금")
    cabin: str = Field(alias="Cabin", description="객실 번호")
    embarked: str = Field(alias="Embarked", description="탑승 항구")

    def to_upload_row(self) -> dict[str, str | None]:
        return {
            "PassengerId": self.passenger_id,
            "Survived": self.survived,
            "Pclass": self.pclass,
            "Name": self.name,
            "gender": self.gender,
            "Age": self.age,
            "SibSp": self.sib_sp,
            "Parch": self.parch,
            "Ticket": self.ticket,
            "Fare": self.fare,
            "Cabin": self.cabin,
            "Embarked": self.embarked,
        }


PREVIEW_FIELDS: tuple[tuple[str, str], ...] = (
    ("passenger_id", "PassengerId"),
    ("survived", "Survived"),
    ("pclass", "Pclass"),
    ("name", "Name"),
    ("gender", "gender"),
    ("age", "Age"),
    ("sib_sp", "SibSp"),
    ("parch", "Parch"),
    ("ticket", "Ticket"),
    ("fare", "Fare"),
    ("cabin", "Cabin"),
    ("embarked", "Embarked"),
)


def format_preview_record(index: int, record: TitanicRecordSchema) -> str:
    data = record.model_dump()
    label_width = max(len(label) for _, label in PREVIEW_FIELDS)
    lines = [f"── row {index} " + "─" * 40]
    for field, label in PREVIEW_FIELDS:
        value = data.get(field, "")
        lines.append(f"  {label:<{label_width}} : {value}")
    return "\n".join(lines)


PERSON_COMMAND_PREVIEW_FIELDS: tuple[tuple[str, str], ...] = (
    ("passenger_id", "PassengerId"),
    ("survived", "Survived"),
    ("pclass", "Pclass"),
    ("name", "Name"),
    ("gender", "gender"),
    ("age", "Age"),
    ("sib_sp", "SibSp"),
    ("parch", "Parch"),
)

BOOKING_COMMAND_PREVIEW_FIELDS: tuple[tuple[str, str], ...] = (
    ("pclass", "Pclass"),
    ("ticket", "Ticket"),
    ("fare", "Fare"),
    ("cabin", "Cabin"),
    ("embarked", "Embarked"),
)


def _format_preview_command(
    *, index: int, data: dict[str, object], fields: tuple[tuple[str, str], ...]
) -> str:
    label_width = max(len(label) for _, label in fields)
    lines = [f"── row {index} " + "─" * 40]
    for field, label in fields:
        value = data.get(field, "")
        lines.append(f"  {label:<{label_width}} : {value}")
    return "\n".join(lines)


def format_preview_person_command(index: int, command: PersonCommand) -> str:
    return _format_preview_command(
        index=index,
        data=asdict(command),
        fields=PERSON_COMMAND_PREVIEW_FIELDS,
    )


def format_preview_booking_command(index: int, command: BookingCommand) -> str:
    return _format_preview_command(
        index=index,
        data=asdict(command),
        fields=BOOKING_COMMAND_PREVIEW_FIELDS,
    )


class JamesDirectorMyselfSchema(BaseModel):
    id: int = 1
    name: str = "James Cameron"


class JamesDirectorSchema(BaseModel):
    """CSV 업로드 본문을 `TitanicRecordSchema` 목록으로 담는 스키마."""

    records: list[TitanicRecordSchema] = Field(default_factory=list)

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
    def from_csv_bytes(cls, raw: bytes) -> JamesDirectorSchema:
        return cls.from_csv_text(cls._decode_csv_bytes(raw))

    @classmethod
    def from_csv_text(cls, text: str) -> JamesDirectorSchema:
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise HTTPException(status_code=400, detail="CSV 헤더를 찾을 수 없습니다.")

        missing = [
            c for c in JAMES_DIRECTOR_REQUIRED_COLUMNS if c not in reader.fieldnames
        ]
        if missing:
            raise HTTPException(
                status_code=400, detail=f"CSV 컬럼 누락: {', '.join(missing)}"
            )

        records: list[TitanicRecordSchema] = []
        for row in reader:
            if row is None:
                continue
            try:
                records.append(TitanicRecordSchema.model_validate(row))
            except ValidationError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"CSV 행 형식이 올바르지 않습니다: {exc.errors()}",
                ) from exc

        return cls(records=records)

    def to_upload_rows(self) -> list[dict[str, str | None]]:
        return [record.to_upload_row() for record in self.records]


class JamesDirectorFileuploadResponse(BaseModel):
    count: int
    inserted: int
