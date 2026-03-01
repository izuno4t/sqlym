"""Sqlym: 高レベル API."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any, TypeVar

from sqlym._parse import parse_sql
from sqlym.loader import SqlLoader
from sqlym.mapper.factory import create_mapper

if TYPE_CHECKING:
    from sqlym.dialect import Dialect
    from sqlym.mapper.protocol import RowMapper

T = TypeVar("T")


class Sqlym:
    """sqlym の高レベル API.

    SQL ファイルの読み込み、パース、実行、結果マッピングを統合する。

    Examples:
        >>> db = Sqlym(connection, sql_dir="sql")
        >>> users = db.query(User, "users/find.sql", {"status": "active"})
        >>> user = db.query_one(User, "users/find_by_id.sql", {"id": 1})
        >>> affected = db.execute("users/update.sql", {"id": 1, "name": "new"})

        コンテキストマネージャとして使用:

        >>> with Sqlym(connection) as db:
        ...     db.execute("users/update.sql", {"id": 1})
        ...     db.execute("users/update.sql", {"id": 2})
        # 正常終了 → connection の __exit__ により commit
        # 例外発生 → connection の __exit__ により rollback

        auto_commit モード（ツール向け）:

        >>> db = Sqlym(connection, auto_commit=True)
        >>> db.execute("users/update.sql", {"id": 1})  # 即座に commit

    """

    def __init__(
        self,
        connection: Any,
        *,
        sql_dir: str | Path = "sql",
        dialect: Dialect | None = None,
        auto_commit: bool = False,
    ) -> None:
        """初期化.

        Args:
            connection: DB 接続オブジェクト（PEP 249 DB-API 2.0 準拠）
            sql_dir: SQL ファイルのベースディレクトリ
            dialect: RDBMS 方言（None の場合は自動検出を試みる）
            auto_commit: True の場合、execute() 後に自動で commit する

        """
        self._connection = connection
        self._loader = SqlLoader(sql_dir)
        self._dialect = dialect if dialect is not None else self._detect_dialect()
        self._auto_commit = auto_commit

    def __enter__(self) -> Sqlym:
        """コンテキストマネージャ: connection に委譲."""
        self._connection.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """コンテキストマネージャ: connection に委譲."""
        return self._connection.__exit__(exc_type, exc_val, exc_tb)

    def commit(self) -> None:
        """トランザクションをコミットする（connection.commit() のラッパー）."""
        self._connection.commit()

    def rollback(self) -> None:
        """トランザクションをロールバックする（connection.rollback() のラッパー）."""
        self._connection.rollback()

    def query(
        self,
        entity: type[T],
        sql_path: str,
        params: dict[str, Any] | None = None,
        *,
        mapper: RowMapper[T] | Callable[..., T] | None = None,
    ) -> list[T]:
        """SELECT を実行し、結果をエンティティのリストで返す.

        Args:
            entity: エンティティクラス
            sql_path: SQL ファイルパス（sql_dir からの相対パス）
            params: パラメータ辞書
            mapper: カスタムマッパー（省略時は自動生成）

        Returns:
            エンティティのリスト

        """
        rows = self._execute_query(sql_path, params)
        row_mapper = create_mapper(entity, mapper=mapper)
        return row_mapper.map_rows(rows)

    def query_one(
        self,
        entity: type[T],
        sql_path: str,
        params: dict[str, Any] | None = None,
        *,
        mapper: RowMapper[T] | Callable[..., T] | None = None,
    ) -> T | None:
        """SELECT を実行し、最初の1行をエンティティで返す.

        Args:
            entity: エンティティクラス
            sql_path: SQL ファイルパス（sql_dir からの相対パス）
            params: パラメータ辞書
            mapper: カスタムマッパー（省略時は自動生成）

        Returns:
            エンティティ、または結果がない場合は None

        """
        rows = self._execute_query(sql_path, params)
        if not rows:
            return None
        row_mapper = create_mapper(entity, mapper=mapper)
        return row_mapper.map_row(rows[0])

    def execute(
        self,
        sql_path: str,
        params: dict[str, Any] | None = None,
    ) -> int:
        """INSERT/UPDATE/DELETE を実行し、影響行数を返す.

        Args:
            sql_path: SQL ファイルパス（sql_dir からの相対パス）
            params: パラメータ辞書

        Returns:
            影響を受けた行数

        """
        cursor = self._execute_write(sql_path, params)
        try:
            return cursor.rowcount
        finally:
            cursor.close()

    def insert(
        self,
        sql_path: str,
        params: dict[str, Any] | None = None,
    ) -> int | None:
        """INSERT を実行し、自動生成された ID を返す.

        Args:
            sql_path: SQL ファイルパス（sql_dir からの相対パス）
            params: パラメータ辞書

        Returns:
            自動生成された ID（lastrowid）、または None

        """
        cursor = self._execute_write(sql_path, params)
        try:
            return cursor.lastrowid
        finally:
            cursor.close()

    def _execute_write(
        self,
        sql_path: str,
        params: dict[str, Any] | None,
    ) -> Any:
        """書き込み系 SQL を実行し、カーソルを返す.

        Args:
            sql_path: SQL ファイルパス（sql_dir からの相対パス）
            params: パラメータ辞書

        Returns:
            実行済みカーソル

        """
        sql_template = self._loader.load(sql_path, dialect=self._dialect)
        result = parse_sql(
            sql_template,
            params or {},
            dialect=self._dialect,
        )
        cursor = self._connection.cursor()
        try:
            cursor.execute(result.sql, result.params)
            if self._auto_commit:
                self._connection.commit()
        except Exception:
            cursor.close()
            raise
        return cursor

    def _execute_query(
        self,
        sql_path: str,
        params: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """SELECT を実行し、結果を辞書のリストで返す."""
        sql_template = self._loader.load(sql_path, dialect=self._dialect)
        result = parse_sql(
            sql_template,
            params or {},
            dialect=self._dialect,
        )
        cursor = self._connection.cursor()
        try:
            cursor.execute(result.sql, result.params)
            if cursor.description is None:
                return []
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def _detect_dialect(self) -> Dialect | None:
        """Connection オブジェクトから Dialect を自動検出する."""
        from sqlym.dialect import Dialect

        module = type(self._connection).__module__
        if "sqlite3" in module:
            return Dialect.SQLITE
        if "psycopg" in module:
            return Dialect.POSTGRESQL
        if "pymysql" in module:
            return Dialect.MYSQL
        if "oracledb" in module:
            return Dialect.ORACLE
        return None
