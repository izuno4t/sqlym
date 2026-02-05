"""SqlLoader: SQL ファイルの読み込み."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sqly.exceptions import SqlFileNotFoundError

if TYPE_CHECKING:
    from sqly.dialect import Dialect


class SqlLoader:
    """SQL ファイルの読み込み."""

    def __init__(self, base_path: str | Path = "sql") -> None:
        self.base_path = Path(base_path)

    def load(self, path: str, *, dialect: Dialect | None = None) -> str:
        """SQL ファイルを読み込む.

        dialect が指定された場合、まず RDBMS 固有ファイル（例: ``find.sql-oracle``）を
        探し、存在しなければ汎用ファイル（例: ``find.sql``）にフォールバックする。

        Args:
            path: base_path からの相対パス
            dialect: RDBMS 方言。指定時は方言固有ファイルを優先

        Returns:
            SQL テンプレート文字列

        Raises:
            SqlFileNotFoundError: ファイルが存在しない場合

        Examples:
            >>> loader = SqlLoader("sql")
            >>> # sql/find.sql-oracle があれば優先、なければ sql/find.sql
            >>> sql = loader.load("find.sql", dialect=Dialect.ORACLE)

        """
        base_path = self.base_path.resolve()

        if dialect is not None:
            dialect_path = f"{path}-{dialect._dialect_id}"
            dialect_file_path = (base_path / dialect_path).resolve()
            if self._is_valid_path(base_path, dialect_file_path):
                return dialect_file_path.read_text(encoding="utf-8")

        file_path = (base_path / path).resolve()
        if not self._is_valid_path(base_path, file_path):
            msg = f"SQL file not found: {file_path}"
            raise SqlFileNotFoundError(msg)
        return file_path.read_text(encoding="utf-8")

    @staticmethod
    def _is_valid_path(base_path: Path, file_path: Path) -> bool:
        """ファイルパスが有効か（base_path 配下に存在するか）を判定する."""
        if file_path != base_path and base_path not in file_path.parents:
            return False
        return file_path.is_file()
