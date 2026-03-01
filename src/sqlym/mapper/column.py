"""Column アノテーションと @entity デコレータ."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_VALID_NAMING = frozenset({"as_is", "snake_to_camel", "camel_to_snake"})


@dataclass(frozen=True)
class Column:
    """カラム名を指定するアノテーション."""

    name: str


def entity(
    cls: type | None = None,
    *,
    column_map: dict[str, str] | None = None,
    naming: str = "as_is",
) -> Any:
    """エンティティデコレータ.

    Args:
        cls: デコレート対象クラス
        column_map: フィールド名→カラム名のマッピング
        naming: 命名規則 ("as_is", "snake_to_camel", "camel_to_snake")

    """
    if naming not in _VALID_NAMING:
        msg = f"Invalid naming: {naming!r}. Must be one of {sorted(_VALID_NAMING)}"
        raise ValueError(msg)

    def decorator(cls: type) -> type:
        cls.__column_map__ = column_map or {}  # type: ignore[attr-defined]
        cls.__column_naming__ = naming  # type: ignore[attr-defined]
        return cls

    if cls is not None:
        return decorator(cls)
    return decorator
