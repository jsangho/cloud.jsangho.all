from pydantic import BaseModel, Field


class DineshDashSchema(BaseModel):
    id: int = Field(0, description="Employee ID")
    name: str = Field("디네시 추타이", description="Employee's name")
    # Pied Piper 대시보드 엔지니어. 자칭 "웹소켓 전문가". 길포일과 항상 티격태격

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 3,
                "name": "Dinesh Chugtai",
            }
        }
    }
