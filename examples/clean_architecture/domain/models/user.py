"""User entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    id: int | None = None
    name: str = ""
    email: str = ""
    department: str | None = None
    created_at: datetime | None = None
