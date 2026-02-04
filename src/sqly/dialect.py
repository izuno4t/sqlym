"""Dialect enum: RDBMS ごとの SQL 方言定義."""

from __future__ import annotations

from enum import Enum


class Dialect(Enum):
    """RDBMS ごとの SQL 方言.

    POSTGRESQL と MYSQL は同じプレースホルダ ``%s`` を使用するが、
    方言固有プロパティが異なるため別メンバーとして定義する。
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

    @property
    def like_escape_chars(self) -> frozenset[str]:
        """LIKE 句でエスケープが必要な特殊文字を返す.

        Oracle では全角 ``％`` ``＿`` もエスケープ対象となる。

        Returns:
            エスケープ対象文字の frozenset
        """
        base = frozenset({"#", "%", "_"})
        match self:
            case Dialect.ORACLE:
                return base | frozenset({"％", "＿"})
            case _:
                return base

    @property
    def in_clause_limit(self) -> int | None:
        """IN 句に指定できる要素数の上限を返す.

        Oracle は 1000 件の制限がある。他の RDBMS は制限なし。

        Returns:
            上限値。None は無制限を意味する。
        """
        match self:
            case Dialect.ORACLE:
                return 1000
            case _:
                return None

    @property
    def backslash_is_escape(self) -> bool:
        """バックスラッシュが文字列リテラル内でエスケープ文字として機能するか.

        MySQL と PostgreSQL ではデフォルトで True。
        """
        match self:
            case Dialect.MYSQL | Dialect.POSTGRESQL:
                return True
            case _:
                return False
