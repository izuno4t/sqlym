"""User repository interface (port)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain.models import User


class UserRepositoryInterface(ABC):
    """User repository interface - defined in domain layer."""

    @abstractmethod
    def find_by_id(self, user_id: int) -> User | None: ...

    @abstractmethod
    def find_all(self, department: str | None = None) -> list[User]: ...

    @abstractmethod
    def save(self, user: User) -> User: ...
