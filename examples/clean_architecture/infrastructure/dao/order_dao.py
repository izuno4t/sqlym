"""Order DAO - SQL access via sqlym."""

from __future__ import annotations

from datetime import datetime

from infrastructure.dao.entities import OrderEntity
from sqlym import Sqlym


class OrderDAO:
    """Handles SQL operations for Order. Returns Entity."""

    def __init__(self, db: Sqlym) -> None:
        self._db = db

    def find_by_user_id(self, user_id: int) -> list[OrderEntity]:
        return self._db.query(OrderEntity, "orders/find_by_user_id.sql", {"user_id": user_id})

    def insert(self, entity: OrderEntity) -> None:
        params = {
            "user_id": entity.user_id,
            "product_name": entity.product_name,
            "quantity": entity.quantity,
            "total_price": entity.total_price,
            "ordered_at": datetime.now().isoformat(),
        }
        self._db.execute("orders/insert.sql", params)
