"""User repository implementation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from domain.models import User
from domain.repositories import UserRepositoryInterface

from infrastructure.dao.entities import UserEntity

if TYPE_CHECKING:
    from infrastructure.dao import UserDAO


class UserRepository(UserRepositoryInterface):
    """User repository - converts Entity to Model."""

    def __init__(self, dao: UserDAO) -> None:
        self._dao = dao

    def find_by_id(self, user_id: int) -> User | None:
        entity = self._dao.find_by_id(user_id)
        return self._to_model(entity) if entity else None

    def find_all(self, department: str | None = None) -> list[User]:
        entities = self._dao.find_all(department)
        return [self._to_model(e) for e in entities]

    def save(self, model: User) -> User:
        entity = self._to_entity(model)
        self._dao.insert(entity)
        saved = self._dao.find_by_email(model.email)
        return self._to_model(saved)  # type: ignore[arg-type]

    @staticmethod
    def _to_model(entity: UserEntity) -> User:
        """Entity → Model."""
        return User(
            id=entity.id,
            name=entity.name,
            email=entity.email,
            department=entity.department,
            created_at=datetime.fromisoformat(entity.created_at) if entity.created_at else None,
        )

    @staticmethod
    def _to_entity(model: User) -> UserEntity:
        """Model → Entity."""
        return UserEntity(
            id=model.id,
            name=model.name,
            email=model.email,
            department=model.department,
        )
