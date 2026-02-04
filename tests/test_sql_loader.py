"""SqlLoader のテスト."""

from __future__ import annotations

from pathlib import Path

import pytest

from sqly.exceptions import SqlFileNotFoundError
from sqly.loader import SqlLoader


@pytest.fixture
def sql_dir(tmp_path: Path) -> Path:
    """テスト用 SQL ディレクトリを作成する."""
    # employee/find_all.sql
    emp_dir = tmp_path / "employee"
    emp_dir.mkdir()
    (emp_dir / "find_all.sql").write_text("SELECT * FROM employees", encoding="utf-8")
    # employee/find_by_id.sql
    (emp_dir / "find_by_id.sql").write_text(
        "SELECT * FROM employees\nWHERE id = /* $id */1",
        encoding="utf-8",
    )
    # department/find_all.sql
    dept_dir = tmp_path / "department"
    dept_dir.mkdir()
    (dept_dir / "find_all.sql").write_text("SELECT * FROM departments", encoding="utf-8")
    return tmp_path


class TestSqlLoaderBasic:
    """SqlLoader の基本動作."""

    def test_load_simple_file(self, sql_dir: Path) -> None:
        """SQL ファイルを読み込む."""
        loader = SqlLoader(sql_dir)
        sql = loader.load("employee/find_all.sql")
        assert sql == "SELECT * FROM employees"

    def test_load_multiline_file(self, sql_dir: Path) -> None:
        """複数行の SQL ファイルを読み込む."""
        loader = SqlLoader(sql_dir)
        sql = loader.load("employee/find_by_id.sql")
        assert "SELECT * FROM employees" in sql
        assert "WHERE id = /* $id */1" in sql

    def test_load_different_subdirectory(self, sql_dir: Path) -> None:
        """別のサブディレクトリから読み込む."""
        loader = SqlLoader(sql_dir)
        sql = loader.load("department/find_all.sql")
        assert sql == "SELECT * FROM departments"


class TestSqlLoaderBasePath:
    """Base_path の扱い."""

    def test_string_base_path(self, sql_dir: Path) -> None:
        """文字列で base_path を指定."""
        loader = SqlLoader(str(sql_dir))
        sql = loader.load("employee/find_all.sql")
        assert sql == "SELECT * FROM employees"

    def test_path_base_path(self, sql_dir: Path) -> None:
        """Path オブジェクトで base_path を指定."""
        loader = SqlLoader(sql_dir)
        sql = loader.load("employee/find_all.sql")
        assert sql == "SELECT * FROM employees"

    def test_default_base_path(self) -> None:
        """デフォルト base_path は 'sql'."""
        loader = SqlLoader()
        assert loader.base_path == Path("sql")


class TestSqlLoaderFileNotFound:
    """ファイルが見つからない場合."""

    def test_missing_file_raises_error(self, sql_dir: Path) -> None:
        """存在しないファイルで SqlFileNotFoundError."""
        loader = SqlLoader(sql_dir)
        with pytest.raises(SqlFileNotFoundError):
            loader.load("nonexistent.sql")

    def test_missing_directory_raises_error(self, sql_dir: Path) -> None:
        """存在しないディレクトリで SqlFileNotFoundError."""
        loader = SqlLoader(sql_dir)
        with pytest.raises(SqlFileNotFoundError):
            loader.load("unknown/find_all.sql")

    def test_error_message_contains_path(self, sql_dir: Path) -> None:
        """エラーメッセージにファイルパスが含まれる."""
        loader = SqlLoader(sql_dir)
        with pytest.raises(SqlFileNotFoundError, match=r"nonexistent\.sql"):
            loader.load("nonexistent.sql")


class TestSqlLoaderEncoding:
    """ファイルエンコーディング."""

    def test_utf8_content(self, tmp_path: Path) -> None:
        """UTF-8 の日本語コンテンツを読み込む."""
        sql_file = tmp_path / "test.sql"
        sql_file.write_text(
            "SELECT * FROM users WHERE name = /* $name */'太郎'",
            encoding="utf-8",
        )
        loader = SqlLoader(tmp_path)
        sql = loader.load("test.sql")
        assert "'太郎'" in sql
