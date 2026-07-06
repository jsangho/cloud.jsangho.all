from pydantic import BaseModel, Field


class GilfoyleSysSchema(BaseModel):
    id: int = Field(0, description="Employee ID")
    name: str = Field("버트램 길포일", description="Employee's name")
    # Pied Piper 시스템 엔지니어. 냉소적 천재. 사탄교 신자. Dinesh와 항상 충돌

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 5,
                "name": "Bertram Gilfoyle",
            }
        }
    }
