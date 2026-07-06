from pydantic import BaseModel


class VisionMyselfSchema(BaseModel):
    id: int = 1
    name: str = "Vision Service"
