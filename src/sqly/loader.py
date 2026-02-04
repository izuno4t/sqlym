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
        file_path = self.base_path / path
        if not file_path.exists():
            msg = f"SQL file not found: {file_path}"
            raise SqlFileNotFoundError(msg)
        return file_path.read_text(encoding="utf-8")
