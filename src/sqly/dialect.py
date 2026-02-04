"""Dialect enum: RDBMS ごとのプレースホルダ形式."""

from __future__ import annotations

from enum import Enum


class Dialect(Enum):
    """RDBMS ごとの SQL 方言.

    POSTGRESQL と MYSQL は同じプレースホルダ ``%s`` を使用するが、
    将来の方言固有拡張に備えて別メンバーとして定義する。
    """

    SQLITE = ("sqlite", "?")
    POSTGRESQL = ("postgresql", "%s")
    MYSQL = ("mysql", "%s")
    ORACLE = ("oracle", ":name")

    def __init__(self, dialect_id: str, placeholder_fmt: str) -> None:
        self._dialect_id = dialect_id
        self._placeholder_fmt = placeholder_fmt

    @property
    def placeholder(self) -> str:
        """プレースホルダ文字列を返す."""
        return self._placeholder_fmt
