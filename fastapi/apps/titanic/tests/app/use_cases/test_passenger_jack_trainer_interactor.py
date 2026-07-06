import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from titanic.app.dtos.passenger_jack_trainer_dto import (
    JackTrainerQuery,
    JackTrainerResponse,
)
from titanic.app.use_cases.passenger_jack_trainer_interactor import (
    JackTrainerInteractor,
)

_MODULE = "titanic.app.use_cases.passenger_jack_trainer_interactor"


@pytest.fixture
def mock_kiwi():
    with patch(f"{_MODULE}.Kiwi") as mock_kiwi_cls:
        instance = MagicMock()
        instance.space.return_value = "cleaned text"
        instance.tokenize.return_value = [
            SimpleNamespace(form="타이타닉", tag="NNG"),
            SimpleNamespace(form="생존자", tag="NNG"),
            SimpleNamespace(form="몇", tag="MM"),
        ]
        mock_kiwi_cls.return_value = instance
        yield instance


@pytest.fixture
def mock_repository():
    repo = MagicMock()
    repo.introduce_myself = AsyncMock(
        return_value=JackTrainerResponse(id=9, name="Jack Dawson")
    )
    return repo


@pytest.fixture
def interactor(mock_repository, mock_kiwi):
    return JackTrainerInteractor(repository=mock_repository)


class TestIntroduceMyself:
    def test_calls_repository_with_correct_query(self, interactor, mock_repository):
        query = JackTrainerQuery(id=9, name="Jack Dawson")

        asyncio.run(interactor.introduce_myself(query))

        mock_repository.introduce_myself.assert_called_once_with(query)

    def test_returns_repository_response(self, interactor):
        query = JackTrainerQuery(id=9, name="Jack Dawson")

        response = asyncio.run(interactor.introduce_myself(query))

        assert response == JackTrainerResponse(id=9, name="Jack Dawson")


class TestAnalayzeMessageIntent:
    def test_returns_cleaned_text(self, interactor, mock_kiwi):
        result = asyncio.run(
            interactor.analayze_message_intent("타이타닉의  생존자는 몇명이야.")
        )

        assert result["cleaned_text"] == "cleaned text"

    def test_extracts_nouns_as_keywords(self, interactor, mock_kiwi):
        result = asyncio.run(
            interactor.analayze_message_intent("타이타닉의  생존자는 몇명이야.")
        )

        assert result["keywords"] == ["타이타닉", "생존자"]

    def test_calls_kiwi_space_with_reset_whitespace(self, interactor, mock_kiwi):
        user_message = "타이타닉의  생존자는 몇명이야."

        asyncio.run(interactor.analayze_message_intent(user_message))

        mock_kiwi.space.assert_called_once_with(user_message, reset_whitespace=True)

    def test_sets_space_tolerance(self, interactor, mock_kiwi):
        asyncio.run(interactor.analayze_message_intent("test"))

        assert mock_kiwi.global_config.space_tolerance == 2
