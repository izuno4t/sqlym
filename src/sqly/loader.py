"""SqlLoader: SQL ファイルの読み込み."""

from __future__ import annotations

from pathlib import Path

from sqly.exceptions import SqlFileNotFoundError


class SqlLoader:
    """SQL ファイルの読み込み."""

    def __init__(self, base_path: str | Path = "sql") -> None:
        self.base_path = Path(base_path)

    def load(self, path: str) -> str:
        """SQL ファイルを読み込む.

        Args:
            path: base_path からの相対パス

        Returns:
            SQL テンプレート文字列

        Raises:
            SqlFileNotFoundError: ファイルが存在しない場合

        """
        base_path = self.base_path.resolve()
        file_path = (base_path / path).resolve()
        if file_path != base_path and base_path not in file_path.parents:
            msg = f"SQL file not found: {file_path}"
            raise SqlFileNotFoundError(msg)
        if not file_path.is_file():
            msg = f"SQL file not found: {file_path}"
            raise SqlFileNotFoundError(msg)
        return file_path.read_text(encoding="utf-8")
