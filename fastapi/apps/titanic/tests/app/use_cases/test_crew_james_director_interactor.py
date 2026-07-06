import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from titanic.app.dtos.crew_james_director_dto import (
    JamesDirectorQuery,
    JamesDirectorResponse,
    TitanicRecordCommand,
)
from titanic.app.use_cases.crew_james_director_interactor import JamesDirectorInteractor


@pytest.fixture
def mock_repository():
    repo = MagicMock()
    repo.introduce_myself = AsyncMock(
        return_value=JamesDirectorResponse(
            id=40000, name="James Cameron이 레포지토리에 다녀옴"
        )
    )
    repo.upload_titanic_file = AsyncMock(return_value=3)
    return repo


@pytest.fixture
def interactor(mock_repository):
    return JamesDirectorInteractor(repository=mock_repository)


def _record(**overrides) -> TitanicRecordCommand:
    defaults = {
        "passenger_id": "1",
        "survived": "0",
        "pclass": "3",
        "name": "Braund, Mr. Owen",
        "gender": "male",
        "age": "22",
        "sib_sp": "1",
        "parch": "0",
        "ticket": "A/5 21171",
        "fare": "7.25",
        "cabin": "",
        "embarked": "S",
    }
    defaults.update(overrides)
    return TitanicRecordCommand(**defaults)


class TestIntroduceMyself:
    def test_calls_repository_with_correct_query(self, interactor, mock_repository):
        query = JamesDirectorQuery(id=4, name="James Cameron")

        asyncio.run(interactor.introduce_myself(query))

        mock_repository.introduce_myself.assert_called_once_with(query)

    def test_returns_repository_response(self, interactor):
        response = asyncio.run(
            interactor.introduce_myself(JamesDirectorQuery(id=4, name="James Cameron"))
        )

        assert response.id == 40000
        assert response.name == "James Cameron이 레포지토리에 다녀옴"


class TestUploadTitanicFile:
    def test_creates_one_passenger_command_per_record(
        self, interactor, mock_repository
    ):
        asyncio.run(
            interactor.upload_titanic_file(
                [_record(passenger_id="1"), _record(passenger_id="2")]
            )
        )

        person_commands = mock_repository.upload_titanic_file.call_args.kwargs[
            "person_commands"
        ]
        assert len(person_commands) == 2

    def test_passenger_command_contains_correct_fields(
        self, interactor, mock_repository
    ):
        asyncio.run(
            interactor.upload_titanic_file(
                [_record(passenger_id="7", gender="female", age="28")]
            )
        )

        person_commands = mock_repository.upload_titanic_file.call_args.kwargs[
            "person_commands"
        ]
        cmd = person_commands[0]
        assert cmd.passenger_id == "7"
        assert cmd.gender == "female"
        assert cmd.age == "28"

    def test_booking_command_contains_correct_fields(self, interactor, mock_repository):
        asyncio.run(
            interactor.upload_titanic_file(
                [_record(pclass="1", fare="100.0", embarked="C")]
            )
        )

        booking_commands = mock_repository.upload_titanic_file.call_args.kwargs[
            "booking_commands"
        ]
        cmd = booking_commands[0]
        assert cmd.pclass == "1"
        assert cmd.fare == "100.0"
        assert cmd.embarked == "C"

    def test_none_fields_become_empty_string(self, interactor, mock_repository):
        asyncio.run(interactor.upload_titanic_file([_record(survived="", cabin="")]))

        person_commands = mock_repository.upload_titanic_file.call_args.kwargs[
            "person_commands"
        ]
        booking_commands = mock_repository.upload_titanic_file.call_args.kwargs[
            "booking_commands"
        ]
        assert person_commands[0].survived == ""
        assert booking_commands[0].cabin == ""

    def test_returns_count_from_repository(self, interactor):
        result = asyncio.run(interactor.upload_titanic_file([_record()]))

        assert result == {"count": 3}
