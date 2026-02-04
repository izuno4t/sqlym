"""create_mapper ファクトリ関数."""

from __future__ import annotations

from dataclasses import is_dataclass
from typing import Any

from sqly.mapper.manual import ManualMapper
from sqly.mapper.protocol import RowMapper


def create_mapper(
    entity_cls: type,
    *,
    mapper: Any = None,
) -> Any:
    """マッパーを生成する.

    Args:
        entity_cls: エンティティクラス
        mapper: RowMapper インスタンス、Callable、または None（自動判定）

    Returns:
        RowMapper プロトコルを満たすマッパー

    Raises:
        TypeError: マッパーを自動判定できない場合

    """
    if mapper is not None:
        if isinstance(mapper, RowMapper):
            return mapper
        if callable(mapper):
            return ManualMapper(mapper)

    if is_dataclass(entity_cls):
        from sqly.mapper.dataclass import DataclassMapper

        return DataclassMapper(entity_cls)

    if hasattr(entity_cls, "model_validate"):
        from sqly.mapper.pydantic import PydanticMapper

        return PydanticMapper(entity_cls)

    msg = (
        f"Cannot create mapper for {entity_cls}. "
        f"Use dataclass, Pydantic, or provide a custom mapper."
    )
    raise TypeError(msg)
