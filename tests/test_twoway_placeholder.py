"""TwoWaySQLParser の複数プレースホルダ形式テスト（%s, :name, dialect）."""

import pytest

from sqlym import Dialect, parse_sql
from sqlym.parser.twoway import TwoWaySQLParser


class TestPercentSBasic:
    """%s 形式の基本テスト."""

    def test_single_param(self) -> None:
        """%s 形式で単一パラメータ置換."""
        sql = "SELECT * FROM users WHERE name = /* $name */'default'"
        parser = TwoWaySQLParser(sql, placeholder="%s")
        result = parser.parse({"name": "Alice"})
        assert result.sql == "SELECT * FROM users WHERE name = %s"
        assert result.params == ["Alice"]

    def test_multiple_params(self) -> None:
        """%s 形式で複数パラメータ置換."""
        sql = (
            "SELECT * FROM users\n"
            "WHERE\n"
            "    name = /* $name */'default'\n"
            "    AND age = /* $age */20"
        )
        parser = TwoWaySQLParser(sql, placeholder="%s")
        result = parser.parse({"name": "Alice", "age": 30})
        assert "name = %s" in result.sql
        assert "age = %s" in result.sql
        assert result.params == ["Alice", 30]

    def test_in_clause(self) -> None:
        """%s 形式で IN 句展開."""
        sql = "SELECT * FROM users WHERE id IN /* $ids */(1, 2, 3)"
        parser = TwoWaySQLParser(sql, placeholder="%s")
        result = parser.parse({"ids": [10, 20, 30]})
        assert "IN (%s, %s, %s)" in result.sql
        assert result.params == [10, 20, 30]

    def test_line_removal(self) -> None:
        """%s 形式で行削除が動作する."""
        sql = "SELECT * FROM users\nWHERE\n    name = /* $name */'default'"
        parser = TwoWaySQLParser(sql, placeholder="%s")
        result = parser.parse({"name": None})
        assert result.sql == "SELECT * FROM users"
        assert result.params == []

    def test_named_params_is_input_dict(self) -> None:
        """%s 形式では named_params は入力辞書."""
        sql = "SELECT * FROM users WHERE name = /* $name */'default'"
        parser = TwoWaySQLParser(sql, placeholder="%s")
        result = parser.parse({"name": "Alice", "extra": 123})
        assert result.named_params == {"name": "Alice", "extra": 123}


class TestNamedBasic:
    """:name 形式の基本テスト."""

    def test_single_param(self) -> None:
        """:name 形式で単一パラメータ置換."""
        sql = "SELECT * FROM users WHERE name = /* $name */'default'"
        parser = TwoWaySQLParser(sql, placeholder=":name")
        result = parser.parse({"name": "Alice"})
        assert result.sql == "SELECT * FROM users WHERE name = :name"
        assert result.named_params == {"name": "Alice"}

    def test_multiple_params(self) -> None:
        """:name 形式で複数パラメータ置換."""
        sql = (
            "SELECT * FROM users\n"
            "WHERE\n"
            "    name = /* $name */'default'\n"
            "    AND age = /* $age */20"
        )
        parser = TwoWaySQLParser(sql, placeholder=":name")
        result = parser.parse({"name": "Alice", "age": 30})
        assert "name = :name" in result.sql
        assert "age = :age" in result.sql
        assert result.named_params == {"name": "Alice", "age": 30}

    def test_params_list_empty(self) -> None:
        """:name 形式では params リストは空."""
        sql = "SELECT * FROM users WHERE name = /* $name */'default'"
        parser = TwoWaySQLParser(sql, placeholder=":name")
        result = parser.parse({"name": "Alice"})
        assert result.params == []

    def test_non_removable_param(self) -> None:
        """:name 形式で非 removable パラメータ."""
        sql = "SELECT * FROM users WHERE deleted_at = /* deleted_at */NULL"
        parser = TwoWaySQLParser(sql, placeholder=":name")
        result = parser.parse({"deleted_at": None})
        assert result.sql == "SELECT * FROM users WHERE deleted_at = :deleted_at"
        assert result.named_params == {"deleted_at": None}


class TestNamedInClause:
    """:name 形式の IN 句展開テスト."""

    def test_in_clause_list(self) -> None:
        """:name 形式で IN 句をリスト展開."""
        sql = "SELECT * FROM users WHERE id IN /* $ids */(1, 2, 3)"
        parser = TwoWaySQLParser(sql, placeholder=":name")
        result = parser.parse({"ids": [10, 20, 30]})
        assert "IN (:ids_0, :ids_1, :ids_2)" in result.sql
        assert result.named_params == {"ids_0": 10, "ids_1": 20, "ids_2": 30}

    def test_in_clause_single_element(self) -> None:
        """:name 形式で IN 句の単一要素."""
        sql = "SELECT * FROM users WHERE id IN /* $ids */(1)"
        parser = TwoWaySQLParser(sql, placeholder=":name")
        result = parser.parse({"ids": [42]})
        assert "IN (:ids_0)" in result.sql
        assert result.named_params == {"ids_0": 42}

    def test_in_clause_empty_list(self) -> None:
        """:name 形式で非 removable IN 句の空リスト."""
        sql = "SELECT * FROM users WHERE id IN /* ids */(1, 2, 3)"
        parser = TwoWaySQLParser(sql, placeholder=":name")
        result = parser.parse({"ids": []})
        assert "IN (NULL)" in result.sql
        assert result.named_params == {}

    def test_in_clause_removable_empty_list(self) -> None:
        """:name 形式で $付き IN 句の空リストは IN (NULL) に変換."""
        sql = "SELECT * FROM users WHERE id IN /* $ids */(1, 2, 3)"
        parser = TwoWaySQLParser(sql, placeholder=":name")
        result = parser.parse({"ids": []})
        # IN 句の空リストは IN (NULL) に変換（行削除ではない）
        assert "IN (NULL)" in result.sql
        assert result.named_params == {}

    def test_in_clause_non_list(self) -> None:
        """:name 形式で IN 句に非リスト値（None等）."""
        sql = "SELECT * FROM users WHERE id IN /* ids */(1, 2, 3)"
        parser = TwoWaySQLParser(sql, placeholder=":name")
        result = parser.parse({"ids": None})
        assert "IN (:ids)" in result.sql
        assert result.named_params == {"ids": None}


class TestNamedRemoval:
    """:name 形式での行削除テスト."""

    def test_removable_param_none(self) -> None:
        """:name 形式で $param が None → 行削除."""
        sql = "SELECT * FROM users\nWHERE\n    name = /* $name */'default'"
        parser = TwoWaySQLParser(sql, placeholder=":name")
        result = parser.parse({"name": None})
        assert result.sql == "SELECT * FROM users"
        assert result.named_params == {}
        assert result.params == []

    def test_partial_removal(self) -> None:
        """:name 形式で部分行削除."""
        sql = "SELECT * FROM users\nWHERE\n    id = /* $id */1\n    AND name = /* $name */'test'"
        parser = TwoWaySQLParser(sql, placeholder=":name")
        result = parser.parse({"id": None, "name": "Alice"})
        assert result.sql == "SELECT * FROM users\nWHERE\n    name = :name"
        assert result.named_params == {"name": "Alice"}


class TestNamedMixed:
    """:name 形式で通常パラメータと IN 句の混在."""

    def test_regular_and_in_clause(self) -> None:
        """:name 形式で通常パラメータと IN 句を併用."""
        sql = "SELECT * FROM users\nWHERE name = /* $name */'default'\n  AND id IN /* $ids */(1, 2)"
        parser = TwoWaySQLParser(sql, placeholder=":name")
        result = parser.parse({"name": "Alice", "ids": [10, 20]})
        assert "name = :name" in result.sql
        assert "IN (:ids_0, :ids_1)" in result.sql
        assert result.named_params == {"name": "Alice", "ids_0": 10, "ids_1": 20}
        assert result.params == []


class TestDialectArg:
    """dialect 引数のテスト."""

    def test_dialect_sqlite(self) -> None:
        """dialect=SQLITE で '?' プレースホルダ."""
        parser = TwoWaySQLParser(
            "SELECT * FROM t WHERE id = /* $id */0",
            dialect=Dialect.SQLITE,
        )
        result = parser.parse({"id": 1})
        assert result.sql == "SELECT * FROM t WHERE id = ?"
        assert result.params == [1]

    def test_dialect_postgresql(self) -> None:
        """dialect=POSTGRESQL で '%s' プレースホルダ."""
        parser = TwoWaySQLParser(
            "SELECT * FROM t WHERE id = /* $id */0",
            dialect=Dialect.POSTGRESQL,
        )
        result = parser.parse({"id": 1})
        assert result.sql == "SELECT * FROM t WHERE id = %s"
        assert result.params == [1]

    def test_dialect_mysql(self) -> None:
        """dialect=MYSQL で '%s' プレースホルダ."""
        parser = TwoWaySQLParser(
            "SELECT * FROM t WHERE id = /* $id */0",
            dialect=Dialect.MYSQL,
        )
        result = parser.parse({"id": 1})
        assert result.sql == "SELECT * FROM t WHERE id = %s"
        assert result.params == [1]

    def test_dialect_oracle(self) -> None:
        """dialect=ORACLE で ':name' プレースホルダ."""
        parser = TwoWaySQLParser(
            "SELECT * FROM t WHERE id = /* $id */0",
            dialect=Dialect.ORACLE,
        )
        result = parser.parse({"id": 1})
        assert result.sql == "SELECT * FROM t WHERE id = :id"
        assert result.named_params == {"id": 1}

    def test_dialect_none_uses_default(self) -> None:
        """dialect=None ではデフォルトの '?' を使用."""
        parser = TwoWaySQLParser(
            "SELECT * FROM t WHERE id = /* $id */0",
            dialect=None,
        )
        result = parser.parse({"id": 1})
        assert result.sql == "SELECT * FROM t WHERE id = ?"

    def test_dialect_and_non_default_placeholder_raises(self) -> None:
        """Dialect と placeholder (デフォルト以外) の同時指定は ValueError."""
        with pytest.raises(ValueError, match="dialect と placeholder は同時に指定できません"):
            TwoWaySQLParser(
                "SELECT * FROM t",
                placeholder="%s",
                dialect=Dialect.POSTGRESQL,
            )

    def test_dialect_with_default_placeholder_ok(self) -> None:
        """Dialect と placeholder='?' (デフォルト) の同時指定は許可."""
        parser = TwoWaySQLParser(
            "SELECT * FROM t WHERE id = /* $id */0",
            placeholder="?",
            dialect=Dialect.POSTGRESQL,
        )
        result = parser.parse({"id": 1})
        assert result.sql == "SELECT * FROM t WHERE id = %s"

    def test_dialect_in_clause(self) -> None:
        """Dialect 指定時の IN 句展開."""
        parser = TwoWaySQLParser(
            "SELECT * FROM t WHERE id IN /* $ids */(0)",
            dialect=Dialect.POSTGRESQL,
        )
        result = parser.parse({"ids": [1, 2, 3]})
        assert result.sql == "SELECT * FROM t WHERE id IN (%s, %s, %s)"
        assert result.params == [1, 2, 3]


class TestParseSqlDialect:
    """parse_sql 便利関数の dialect 引数テスト."""

    def test_dialect_postgresql(self) -> None:
        """parse_sql で dialect=POSTGRESQL."""
        result = parse_sql(
            "SELECT * FROM t WHERE id = /* $id */0",
            {"id": 1},
            dialect=Dialect.POSTGRESQL,
        )
        assert result.sql == "SELECT * FROM t WHERE id = %s"
        assert result.params == [1]

    def test_dialect_and_placeholder_raises(self) -> None:
        """parse_sql で dialect と placeholder 同時指定は ValueError."""
        with pytest.raises(ValueError, match="dialect と placeholder は同時に指定できません"):
            parse_sql(
                "SELECT * FROM t",
                {},
                placeholder="%s",
                dialect=Dialect.POSTGRESQL,
            )

    def test_no_dialect_backward_compatible(self) -> None:
        """Dialect 未指定で既存動作と互換."""
        result = parse_sql(
            "SELECT * FROM t WHERE id = /* $id */0",
            {"id": 1},
        )
        assert result.sql == "SELECT * FROM t WHERE id = ?"
        assert result.params == [1]
