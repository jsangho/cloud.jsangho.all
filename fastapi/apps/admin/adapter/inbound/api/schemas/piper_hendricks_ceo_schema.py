from pydantic import BaseModel, Field


class HendricksCeoSchema(BaseModel):
    id: int = Field(0, description="Employee ID")
    name: str = Field("리처드 헨드릭스", description="Employee's name")
    # Pied Piper CEO. 미들아웃 압축 알고리즘 발명자. 세상을 바꿀 압축 기술을 만든 창업자

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 1,
                "name": "Richard Hendricks",
            }
        }
    }
