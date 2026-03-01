"""エスケープ関連ユーティリティ."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlym.dialect import Dialect


def escape_like(value: str, dialect: Dialect, *, escape_char: str | None = None) -> str:
    """LIKE 句で使用する値の特殊文字をエスケープする.

    LIKE 句のワイルドカード文字（``%``, ``_``）およびエスケープ文字自体を
    エスケープ処理する。

    Args:
        value: エスケープ対象の文字列
        dialect: RDBMS 方言
        escape_char: エスケープ文字（省略時は dialect.like_escape_char を使用）

    Returns:
        エスケープ処理された文字列

    Examples:
        >>> from sqlym import Dialect, escape_like
        >>> escape_like("10%off", Dialect.SQLITE)
        '10#%off'
        >>> escape_like("file_name", Dialect.ORACLE)
        'file#_name'
        >>> escape_like("100％達成", Dialect.ORACLE)
        '100％達成'

    Note:
        この関数でエスケープした値を LIKE 句で使用する場合、
        SQL に ``ESCAPE '#'`` 句を追加する必要がある::

            SELECT * FROM t WHERE name LIKE ? ESCAPE '#'

    """
    esc = escape_char if escape_char is not None else dialect.like_escape_char
    escape_chars = dialect.like_escape_chars
    result: list[str] = []
    for ch in value:
        if ch in escape_chars:
            result.append(esc)
        result.append(ch)
    return "".join(result)
