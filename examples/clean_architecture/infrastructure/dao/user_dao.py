"""User DAO - SQL access via sqlym."""

from __future__ import annotations

from datetime import datetime

from infrastructure.dao.entities import UserEntity
from sqlym import Sqlym


class UserDAO:
    """Handles SQL operations for User. Returns Entity."""

    def __init__(self, db: Sqlym) -> None:
        self._db = db

    def find_by_id(self, user_id: int) -> UserEntity | None:
        return self._db.query_one(UserEntity, "users/find_by_id.sql", {"id": user_id})

    def find_by_email(self, email: str) -> UserEntity | None:
        return self._db.query_one(UserEntity, "users/find_by_email.sql", {"email": email})

    def find_all(self, department: str | None = None) -> list[UserEntity]:
        return self._db.query(UserEntity, "users/find_all.sql", {"department": department})

    def insert(self, entity: UserEntity) -> None:
        params = {
            "name": entity.name,
            "email": entity.email,
            "department": entity.department,
            "created_at": datetime.now().isoformat(),
        }
        self._db.execute("users/insert.sql", params)
