"""Order repository interface (port)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain.models import Order


class OrderRepositoryInterface(ABC):
    """Order repository interface - defined in domain layer."""

    @abstractmethod
    def find_by_user_id(self, user_id: int) -> list[Order]: ...

    @abstractmethod
    def save(self, order: Order) -> Order: ...
