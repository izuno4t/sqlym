"""Create user use case."""

from __future__ import annotations

from typing import TYPE_CHECKING

from domain.models import User

if TYPE_CHECKING:
    from domain.repositories import UserRepositoryInterface


class CreateUserUseCase:
    def __init__(self, user_repo: UserRepositoryInterface) -> None:
        self._user_repo = user_repo

    def execute(self, name: str, email: str, department: str | None = None) -> User:
        user = User(name=name, email=email, department=department)
        return self._user_repo.save(user)
