"""ManualMapper: ユーザー提供の関数をラップするマッパー."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class ManualMapper:
    """ユーザー提供の関数をラップするマッパー."""

    def __init__(self, func: Callable[[dict[str, Any]], Any]) -> None:
        self._func = func

    def map_row(self, row: dict[str, Any]) -> Any:
        """1行をエンティティに変換."""
        return self._func(row)

    def map_rows(self, rows: list[dict[str, Any]]) -> list[Any]:
        """複数行をエンティティのリストに変換."""
        return [self._func(row) for row in rows]
