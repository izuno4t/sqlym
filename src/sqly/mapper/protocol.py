"""RowMapper プロトコル定義."""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class RowMapper(Protocol[T]):
    """マッパーのインターフェース."""

    def map_row(self, row: dict[str, Any]) -> T:
        """1行をエンティティに変換."""
        ...

    def map_rows(self, rows: list[dict[str, Any]]) -> list[T]:
        """複数行をエンティティのリストに変換."""
        ...
