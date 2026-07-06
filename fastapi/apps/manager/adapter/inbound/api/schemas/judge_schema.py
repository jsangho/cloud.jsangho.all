from pydantic import BaseModel


class JudgeMyselfSchema(BaseModel):
    id: int = 1
    name: str = "Judge"
