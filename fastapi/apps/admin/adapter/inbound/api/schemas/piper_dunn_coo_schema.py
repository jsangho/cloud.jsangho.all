from pydantic import BaseModel, Field


class DunnCooSchema(BaseModel):
    id: int = Field(0, description="Employee ID")
    name: str = Field("재러드 던", description="Employee's name")
    # Pied Piper COO. 본명은 도널드 던. Richard의 충직한 조력자. Hooli 출신

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 4,
                "name": "Jared Dunn",
            }
        }
    }
