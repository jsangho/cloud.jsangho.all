from pydantic import BaseModel, ConfigDict, Field


class WalterRoasterSchema(BaseModel):
    id: int = 6
    name: str = "Walter"


class WalterRoasterPassengerItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    passenger_id: int | None = Field(default=None, alias="PassengerId")
    survived: int | None = Field(default=None, alias="Survived")
    pclass: int | None = Field(default=None, alias="Pclass")
    name: str | None = Field(default=None, alias="Name")
    gender: str | None = Field(default=None, alias="gender")
    age: float | None = Field(default=None, alias="Age")
    sib_sp: int | None = Field(default=None, alias="SibSp")
    parch: int | None = Field(default=None, alias="Parch")
    ticket: str | None = Field(default=None, alias="Ticket")
    fare: float | None = Field(default=None, alias="Fare")
    cabin: str | None = Field(default=None, alias="Cabin")
    embarked: str | None = Field(default=None, alias="Embarked")


class WalterRoasterOpenfileResponse(BaseModel):
    id: int
    name: str
    memo: str
    page: int
    pageSize: int
    total: int
    items: list[WalterRoasterPassengerItem]
