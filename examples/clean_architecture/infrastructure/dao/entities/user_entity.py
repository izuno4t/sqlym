"""User entity for persistence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UserEntity:
    """Maps directly to users table."""

    id: int | None = None
    name: str = ""
    email: str = ""
    department: str | None = None
    created_at: str | None = None
