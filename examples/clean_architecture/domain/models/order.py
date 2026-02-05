"""Order entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Order:
    id: int | None = None
    user_id: int = 0
    product_name: str = ""
    quantity: int = 0
    total_price: int = 0
    ordered_at: datetime | None = None

    @property
    def is_valid(self) -> bool:
        return self.user_id > 0 and self.quantity > 0 and self.total_price > 0
