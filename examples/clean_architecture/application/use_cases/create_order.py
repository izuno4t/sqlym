"""Create order use case."""

from __future__ import annotations

from typing import TYPE_CHECKING

from domain.models import Order

if TYPE_CHECKING:
    from domain.repositories import OrderRepositoryInterface, UserRepositoryInterface


class CreateOrderUseCase:
    def __init__(
        self,
        user_repo: UserRepositoryInterface,
        order_repo: OrderRepositoryInterface,
    ) -> None:
        self._user_repo = user_repo
        self._order_repo = order_repo

    def execute(self, user_id: int, product_name: str, quantity: int, unit_price: int) -> Order:
        user = self._user_repo.find_by_id(user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")

        order = Order(
            user_id=user_id,
            product_name=product_name,
            quantity=quantity,
            total_price=quantity * unit_price,
        )

        if not order.is_valid:
            raise ValueError("Invalid order")

        return self._order_repo.save(order)
