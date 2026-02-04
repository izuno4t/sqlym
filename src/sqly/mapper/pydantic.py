"""PydanticMapper: Pydantic BaseModel 用のマッパー."""

from __future__ import annotations

from typing import Any


class PydanticMapper:
    """Pydantic BaseModel 用のマッパー."""

    def __init__(self, entity_cls: type) -> None:
        if not hasattr(entity_cls, "model_validate"):
            msg = f"{entity_cls} is not a Pydantic BaseModel"
            raise TypeError(msg)
        self.entity_cls = entity_cls

    def map_row(self, row: dict[str, Any]) -> Any:
        """1行をエンティティに変換."""
        return self.entity_cls.model_validate(row)

    def map_rows(self, rows: list[dict[str, Any]]) -> list[Any]:
        """複数行をエンティティのリストに変換."""
        return [self.map_row(row) for row in rows]
