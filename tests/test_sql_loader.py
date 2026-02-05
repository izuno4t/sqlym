"""SqlLoader のテスト."""

from __future__ import annotations

from pathlib import Path

import pytest

from sqly import Dialect
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

    def test_path_traversal_rejected(self, tmp_path: Path) -> None:
        """base_path 外へのパスは拒否する."""
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        (tmp_path / "outside.sql").write_text("SELECT 1", encoding="utf-8")
        loader = SqlLoader(base_dir)
        with pytest.raises(SqlFileNotFoundError):
            loader.load("../outside.sql")


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


@pytest.fixture
def dialect_sql_dir(tmp_path: Path) -> Path:
    """Dialect 別 SQL ファイルを含むディレクトリを作成する."""
    # 汎用ファイル
    (tmp_path / "find.sql").write_text("SELECT * FROM t", encoding="utf-8")
    # Oracle 固有
    (tmp_path / "find.oracle.sql").write_text(
        "SELECT * FROM t WHERE ROWNUM <= 10", encoding="utf-8"
    )
    # PostgreSQL 固有
    (tmp_path / "find.postgresql.sql").write_text(
        "SELECT * FROM t LIMIT 10", encoding="utf-8"
    )
    # 汎用のみ（dialect固有なし）
    (tmp_path / "common.sql").write_text("SELECT 1", encoding="utf-8")
    # サブディレクトリ
    sub_dir = tmp_path / "employee"
    sub_dir.mkdir()
    (sub_dir / "find.sql").write_text("SELECT * FROM employees", encoding="utf-8")
    (sub_dir / "find.mysql.sql").write_text(
        "SELECT * FROM employees LIMIT 10", encoding="utf-8"
    )
    return tmp_path


class TestSqlLoaderDialect:
    """Dialect 別 SQL ファイルロード."""

    def test_dialect_specific_file_loaded(self, dialect_sql_dir: Path) -> None:
        """Dialect 固有ファイルが存在すれば優先."""
        loader = SqlLoader(dialect_sql_dir)
        sql = loader.load("find.sql", dialect=Dialect.ORACLE)
        assert "ROWNUM" in sql

    def test_dialect_postgresql(self, dialect_sql_dir: Path) -> None:
        """PostgreSQL 固有ファイルがロードされる."""
        loader = SqlLoader(dialect_sql_dir)
        sql = loader.load("find.sql", dialect=Dialect.POSTGRESQL)
        assert "LIMIT 10" in sql

    def test_dialect_fallback_to_generic(self, dialect_sql_dir: Path) -> None:
        """Dialect 固有ファイルがなければ汎用ファイルにフォールバック."""
        loader = SqlLoader(dialect_sql_dir)
        # MySQL 固有の find.sql-mysql は存在しないのでフォールバック
        sql = loader.load("find.sql", dialect=Dialect.MYSQL)
        assert sql == "SELECT * FROM t"

    def test_dialect_none_loads_generic(self, dialect_sql_dir: Path) -> None:
        """dialect=None では汎用ファイルをロード."""
        loader = SqlLoader(dialect_sql_dir)
        sql = loader.load("find.sql")
        assert sql == "SELECT * FROM t"

    def test_dialect_with_common_file(self, dialect_sql_dir: Path) -> None:
        """Dialect 固有ファイルがないファイルでもフォールバック動作."""
        loader = SqlLoader(dialect_sql_dir)
        sql = loader.load("common.sql", dialect=Dialect.ORACLE)
        assert sql == "SELECT 1"

    def test_dialect_in_subdirectory(self, dialect_sql_dir: Path) -> None:
        """サブディレクトリ内の Dialect 固有ファイル."""
        loader = SqlLoader(dialect_sql_dir)
        sql = loader.load("employee/find.sql", dialect=Dialect.MYSQL)
        assert "LIMIT 10" in sql

    def test_dialect_fallback_in_subdirectory(self, dialect_sql_dir: Path) -> None:
        """サブディレクトリ内で Dialect 固有がなければフォールバック."""
        loader = SqlLoader(dialect_sql_dir)
        sql = loader.load("employee/find.sql", dialect=Dialect.ORACLE)
        assert sql == "SELECT * FROM employees"

    def test_all_dialects_suffix(self, tmp_path: Path) -> None:
        """全 Dialect のサフィックス形式を検証."""
        (tmp_path / "test.sql").write_text("generic", encoding="utf-8")
        (tmp_path / "test.sqlite.sql").write_text("sqlite", encoding="utf-8")
        (tmp_path / "test.postgresql.sql").write_text("postgresql", encoding="utf-8")
        (tmp_path / "test.mysql.sql").write_text("mysql", encoding="utf-8")
        (tmp_path / "test.oracle.sql").write_text("oracle", encoding="utf-8")
        loader = SqlLoader(tmp_path)
        assert loader.load("test.sql", dialect=Dialect.SQLITE) == "sqlite"
        assert loader.load("test.sql", dialect=Dialect.POSTGRESQL) == "postgresql"
        assert loader.load("test.sql", dialect=Dialect.MYSQL) == "mysql"
        assert loader.load("test.sql", dialect=Dialect.ORACLE) == "oracle"
        assert loader.load("test.sql") == "generic"

    def test_file_not_found_with_dialect(self, dialect_sql_dir: Path) -> None:
        """存在しないファイルは dialect 指定時もエラー."""
        loader = SqlLoader(dialect_sql_dir)
        with pytest.raises(SqlFileNotFoundError):
            loader.load("nonexistent.sql", dialect=Dialect.ORACLE)

    def test_path_traversal_rejected_with_dialect(self, tmp_path: Path) -> None:
        """Dialect 指定時もパストラバーサルを拒否."""
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        (tmp_path / "outside.oracle.sql").write_text("SELECT 1", encoding="utf-8")
        loader = SqlLoader(base_dir)
        with pytest.raises(SqlFileNotFoundError):
            loader.load("../outside.sql", dialect=Dialect.ORACLE)
