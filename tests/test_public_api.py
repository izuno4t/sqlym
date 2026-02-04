"""公開 API と parse_sql 便利関数のテスト."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from sqly.mapper.column import Column  # get_type_hints がアノテーション文字列を解決するために必要


class TestPublicImports:
    """sqly パッケージからの公開インポート."""

    def test_import_parse_sql(self) -> None:
        """parse_sql をインポートできる."""
        from sqly import parse_sql

        assert callable(parse_sql)

    def test_import_twoway_sql_parser(self) -> None:
        """TwoWaySQLParser をインポートできる."""
        from sqly import TwoWaySQLParser

        assert TwoWaySQLParser is not None

    def test_import_parsed_sql(self) -> None:
        """ParsedSQL をインポートできる."""
        from sqly import ParsedSQL

        assert ParsedSQL is not None

    def test_import_create_mapper(self) -> None:
        """create_mapper をインポートできる."""
        from sqly import create_mapper

        assert callable(create_mapper)

    def test_import_row_mapper(self) -> None:
        """RowMapper をインポートできる."""
        from sqly import RowMapper

        assert RowMapper is not None

    def test_import_manual_mapper(self) -> None:
        """ManualMapper をインポートできる."""
        from sqly import ManualMapper

        assert ManualMapper is not None

    def test_import_column(self) -> None:
        """Column をインポートできる."""
        from sqly import Column

        assert Column is not None

    def test_import_entity(self) -> None:
        """Entity をインポートできる."""
        from sqly import entity

        assert callable(entity)

    def test_import_sql_loader(self) -> None:
        """SqlLoader をインポートできる."""
        from sqly import SqlLoader

        assert SqlLoader is not None

    def test_import_exceptions(self) -> None:
        """例外クラスをインポートできる."""
        from sqly import MappingError, SqlFileNotFoundError, SqlParseError, SqlyError

        assert issubclass(SqlParseError, SqlyError)
        assert issubclass(MappingError, SqlyError)
        assert issubclass(SqlFileNotFoundError, SqlyError)

    def test_all_exports(self) -> None:
        """__all__ に必要な名前が含まれる."""
        import sqly

        expected = {
            "TwoWaySQLParser",
            "ParsedSQL",
            "parse_sql",
            "create_mapper",
            "RowMapper",
            "ManualMapper",
            "Column",
            "entity",
            "SqlLoader",
            "SqlyError",
            "SqlParseError",
            "MappingError",
            "SqlFileNotFoundError",
        }
        assert expected <= set(sqly.__all__)


class TestParseSqlFunction:
    """parse_sql 便利関数の検証."""

    def test_basic_parse(self) -> None:
        """基本のパース."""
        from sqly import parse_sql

        result = parse_sql(
            "SELECT * FROM users WHERE name = /* $name */'default'",
            {"name": "Alice"},
        )
        assert result.sql == "SELECT * FROM users WHERE name = ?"
        assert result.params == ["Alice"]

    def test_placeholder_percent_s(self) -> None:
        """Placeholder に %s を指定."""
        from sqly import parse_sql

        result = parse_sql(
            "SELECT * FROM users WHERE name = /* $name */'default'",
            {"name": "Alice"},
            placeholder="%s",
        )
        assert result.sql == "SELECT * FROM users WHERE name = %s"
        assert result.params == ["Alice"]

    def test_placeholder_named(self) -> None:
        """Placeholder に :name を指定."""
        from sqly import parse_sql

        result = parse_sql(
            "SELECT * FROM users WHERE name = /* $name */'default'",
            {"name": "Alice"},
            placeholder=":name",
        )
        assert result.sql == "SELECT * FROM users WHERE name = :name"
        assert result.named_params == {"name": "Alice"}
        assert result.params == []

    def test_returns_parsed_sql(self) -> None:
        """戻り値が ParsedSQL インスタンス."""
        from sqly import ParsedSQL, parse_sql

        result = parse_sql("SELECT 1", {})
        assert isinstance(result, ParsedSQL)

    def test_line_removal(self) -> None:
        """行削除が動作する."""
        from sqly import parse_sql

        sql = "SELECT * FROM users\nWHERE\n    name = /* $name */'default'"
        result = parse_sql(sql, {"name": None})
        assert result.sql == "SELECT * FROM users"
        assert result.params == []


class TestEndToEndImport:
    """エンドツーエンドのインポートと使用."""

    def test_full_workflow_imports(self) -> None:
        """設計ドキュメントのインポートパターンが動作する."""
        from sqly import create_mapper, parse_sql

        @dataclass
        class Employee:
            id: int
            name: Annotated[str, Column("EMP_NAME")]

        result = parse_sql(
            "SELECT * FROM employees WHERE id = /* $id */1",
            {"id": 100},
        )
        assert result.sql == "SELECT * FROM employees WHERE id = ?"
        assert result.params == [100]

        mapper = create_mapper(Employee)
        emp = mapper.map_row({"id": 100, "EMP_NAME": "Alice"})
        assert emp == Employee(id=100, name="Alice")
