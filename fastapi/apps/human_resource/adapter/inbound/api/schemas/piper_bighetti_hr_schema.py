from pydantic import BaseModel, Field


class BighettiHrSchema(BaseModel):
    id: int = Field(0, description="Employee ID")
    name: str = Field("넬슨 빅헤드 비게티", description="Employee's name")
    # Pied Piper HR. 빅헤드라는 별명으로 불림. 우연한 행운으로 스탠퍼드 AI Lab 공동소장이 됨

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 2,
                "name": "Nelson Bighetti",
            }
        }
    }
