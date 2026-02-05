"""Order repository implementation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from domain.models import Order
from domain.repositories import OrderRepositoryInterface

from infrastructure.dao.entities import OrderEntity

if TYPE_CHECKING:
    from infrastructure.dao import OrderDAO


class OrderRepository(OrderRepositoryInterface):
    """Order repository - converts Entity to Model."""

    def __init__(self, dao: OrderDAO) -> None:
        self._dao = dao

    def find_by_user_id(self, user_id: int) -> list[Order]:
        entities = self._dao.find_by_user_id(user_id)
        return [self._to_model(e) for e in entities]

    def save(self, model: Order) -> Order:
        entity = self._to_entity(model)
        self._dao.insert(entity)
        entities = self._dao.find_by_user_id(model.user_id)
        return self._to_model(entities[0]) if entities else model

    @staticmethod
    def _to_model(entity: OrderEntity) -> Order:
        """Entity → Model."""
        return Order(
            id=entity.id,
            user_id=entity.user_id,
            product_name=entity.product_name,
            quantity=entity.quantity,
            total_price=entity.total_price,
            ordered_at=datetime.fromisoformat(entity.ordered_at) if entity.ordered_at else None,
        )

    @staticmethod
    def _to_entity(model: Order) -> OrderEntity:
        """Model → Entity."""
        return OrderEntity(
            id=model.id,
            user_id=model.user_id,
            product_name=model.product_name,
            quantity=model.quantity,
            total_price=model.total_price,
        )
