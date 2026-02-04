"""parse_sql 便利関数."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqly.parser.twoway import ParsedSQL, TwoWaySQLParser

if TYPE_CHECKING:
    from sqly.dialect import Dialect


def parse_sql(
    sql: str,
    params: dict[str, Any],
    *,
    placeholder: str = "?",
    dialect: Dialect | None = None,
) -> ParsedSQL:
    """SQL をパースする便利関数.

    Args:
        sql: SQL テンプレート
        params: パラメータ辞書
        placeholder: プレースホルダ形式 ("?", "%s", ":name")
        dialect: RDBMS 方言。指定時は dialect.placeholder を使用する。

    Returns:
        パース結果

    Raises:
        ValueError: dialect と placeholder (デフォルト以外) を同時に指定した場合

    """
    parser = TwoWaySQLParser(sql, placeholder=placeholder, dialect=dialect)
    return parser.parse(params)
