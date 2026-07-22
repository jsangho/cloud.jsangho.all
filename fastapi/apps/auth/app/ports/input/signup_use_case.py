from __future__ import annotations

from abc import ABC, abstractmethod


class SignupUseCase(ABC):
    @abstractmethod
    async def signup(
        self,
        *,
        login_id: str,
        nickname: str,
        email: str,
        password: str,
        password_confirm: str,
    ) -> None:
        """회원가입 (`POST /signup`)."""
        ...
