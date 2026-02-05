"""Order entity for persistence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OrderEntity:
    """Maps directly to orders table."""

    id: int | None = None
    user_id: int = 0
    product_name: str = ""
    quantity: int = 0
    total_price: int = 0
    ordered_at: str | None = None
