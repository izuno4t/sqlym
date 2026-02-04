"""TwoWaySQLParser の基本パラメータ置換テスト."""

from sqly.parser.twoway import TwoWaySQLParser


class TestBasicParamSubstitution:
    """基本的なパラメータ置換(? 形式)を検証する."""

    def test_single_removable_param(self) -> None:
        sql = "SELECT * FROM users WHERE name = /* $name */'default'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": "Alice"})
        assert result.sql == "SELECT * FROM users WHERE name = ?"
        assert result.params == ["Alice"]

    def test_single_non_removable_param(self) -> None:
        sql = "SELECT * FROM users WHERE name = /* name */'default'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": "Bob"})
        assert result.sql == "SELECT * FROM users WHERE name = ?"
        assert result.params == ["Bob"]

    def test_number_default(self) -> None:
        sql = "SELECT * FROM users WHERE age = /* $age */25"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"age": 30})
        assert result.sql == "SELECT * FROM users WHERE age = ?"
        assert result.params == [30]

    def test_null_default(self) -> None:
        sql = "SELECT * FROM users WHERE deleted_at = /* deleted_at */NULL"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"deleted_at": None})
        assert result.sql == "SELECT * FROM users WHERE deleted_at = ?"
        assert result.params == [None]


class TestMultipleParams:
    """複数パラメータの置換を検証する."""

    def test_two_params_one_line(self) -> None:
        sql = "WHERE name = /* $name */'test' AND age = /* $age */20"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": "Alice", "age": 30})
        assert result.sql == "WHERE name = ? AND age = ?"
        assert result.params == ["Alice", 30]

    def test_params_across_lines(self) -> None:
        sql = "SELECT * FROM users\nWHERE name = /* $name */'test'\n  AND age = /* $age */20"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": "Alice", "age": 30})
        assert "WHERE name = ?" in result.sql
        assert "AND age = ?" in result.sql
        assert result.params == ["Alice", 30]

    def test_mixed_removable_and_non_removable(self) -> None:
        sql = "WHERE name = /* $name */'test'\n  AND status = /* status */'active'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": "Alice", "status": "inactive"})
        assert result.params == ["Alice", "inactive"]


class TestNoParams:
    """パラメータなしのSQLを検証する."""

    def test_plain_sql(self) -> None:
        sql = "SELECT * FROM users"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({})
        assert result.sql == "SELECT * FROM users"
        assert result.params == []

    def test_multiline_no_params(self) -> None:
        sql = "SELECT *\nFROM users\nWHERE 1 = 1"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({})
        assert result.sql == "SELECT *\nFROM users\nWHERE 1 = 1"
        assert result.params == []


class TestIndentPreservation:
    """インデントが保持されることを検証する."""

    def test_indented_param_line(self) -> None:
        sql = "WHERE\n  AND name = /* $name */'test'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": "Alice"})
        lines = result.sql.split("\n")
        assert lines[0] == "WHERE"
        # WHERE直後の唯一の条件なので先頭ANDは_clean_sqlで除去される
        assert lines[1] == "  name = ?"

    def test_deep_indent_preserved(self) -> None:
        sql = "WHERE\n    AND name = /* $name */'test'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": "Alice"})
        lines = result.sql.split("\n")
        # WHERE直後の唯一の条件なので先頭ANDは_clean_sqlで除去される
        assert lines[1] == "    name = ?"


class TestEmptyLines:
    """空行の扱いを検証する."""

    def test_empty_lines_preserved(self) -> None:
        sql = "SELECT *\n\nFROM users"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({})
        assert result.sql == "SELECT *\n\nFROM users"


class TestParsedSQLNamedParams:
    """ParsedSQL.named_params を検証する."""

    def test_named_params_populated(self) -> None:
        sql = "WHERE name = /* $name */'test'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": "Alice", "extra": 123})
        assert result.named_params == {"name": "Alice", "extra": 123}

    def test_named_params_empty(self) -> None:
        sql = "SELECT 1"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({})
        assert result.named_params == {}
