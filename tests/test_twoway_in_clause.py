"""TwoWaySQLParser の IN句自動展開テスト."""

import pytest

from sqlym.dialect import Dialect
from sqlym.exceptions import SqlParseError
from sqlym.parser.twoway import TwoWaySQLParser


class TestInClauseBasic:
    """IN句の基本的なリスト展開."""

    def test_list_expanded_to_placeholders(self) -> None:
        """リストパラメータが複数プレースホルダに展開される."""
        sql = "SELECT * FROM users WHERE id IN /* $ids */(1, 2, 3)"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"ids": [10, 20, 30]})
        assert result.sql == "SELECT * FROM users WHERE id IN (?, ?, ?)"
        assert result.params == [10, 20, 30]

    def test_single_element_list(self) -> None:
        """単一要素リストは IN (?) に展開される."""
        sql = "SELECT * FROM users WHERE id IN /* $ids */(1)"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"ids": [42]})
        assert result.sql == "SELECT * FROM users WHERE id IN (?)"
        assert result.params == [42]

    def test_empty_list_becomes_null(self) -> None:
        """非 removable IN句の空リストは IN (NULL) に展開される."""
        sql = "SELECT * FROM users WHERE id IN /* ids */(1, 2, 3)"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"ids": []})
        assert result.sql == "SELECT * FROM users WHERE id IN (NULL)"
        assert result.params == []

    def test_removable_empty_list_removes_line(self) -> None:
        """$付き IN句の空リストは行削除される（negative 拡張）."""
        sql = "SELECT * FROM users WHERE id IN /* $ids */(1, 2, 3)"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"ids": []})
        assert result.sql == ""
        assert result.params == []


class TestInClauseRemoval:
    """IN句と行削除の組み合わせ."""

    def test_removable_in_none_removes_line(self) -> None:
        """$付き IN句パラメータが None → 行削除."""
        sql = "SELECT * FROM users\nWHERE\n  AND id IN /* $ids */(1, 2, 3)"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"ids": None})
        assert "IN" not in result.sql
        assert result.params == []

    def test_non_removable_in_none_keeps_line(self) -> None:
        """非 removable IN句パラメータが None → 行は残る（NULL バインド）."""
        sql = "SELECT * FROM users WHERE id IN /* ids */(1, 2, 3)"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"ids": None})
        # 非 removable で None → リストではないので単一プレースホルダ
        assert "IN" in result.sql
        assert result.params == [None]


class TestInClauseMixed:
    """IN句と通常パラメータの混在."""

    def test_in_clause_with_regular_param(self) -> None:
        """IN句と通常パラメータが同じ SQL に存在."""
        sql = (
            "SELECT * FROM users\n"
            "WHERE name = /* $name */'default'\n"
            "  AND id IN /* $ids */(1, 2, 3)"
        )
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": "Alice", "ids": [10, 20]})
        assert "name = ?" in result.sql
        assert "IN (?, ?)" in result.sql
        assert result.params == ["Alice", 10, 20]

    def test_in_clause_on_same_line_as_regular_param(self) -> None:
        """同一行に通常パラメータと IN句が混在（稀だが対応確認）."""
        sql = "WHERE status = /* $status */'active' AND id IN /* $ids */(1, 2)"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"status": "active", "ids": [5, 6, 7]})
        assert "status = ?" in result.sql
        assert "IN (?, ?, ?)" in result.sql
        assert result.params == ["active", 5, 6, 7]


class TestInClauseMultipleValues:
    """IN句の様々な値パターン."""

    def test_string_list(self) -> None:
        """文字列リストの展開."""
        sql = "SELECT * FROM users WHERE name IN /* $names */('a', 'b')"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"names": ["Alice", "Bob", "Charlie"]})
        assert "IN (?, ?, ?)" in result.sql
        assert result.params == ["Alice", "Bob", "Charlie"]

    def test_large_list(self) -> None:
        """多数要素の展開."""
        sql = "SELECT * FROM users WHERE id IN /* $ids */(1)"
        ids = list(range(1, 11))
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"ids": ids})
        expected_placeholders = ", ".join(["?"] * 10)
        assert f"IN ({expected_placeholders})" in result.sql
        assert result.params == ids


class TestInClauseSplit:
    """IN句の上限分割テスト."""

    def test_no_split_without_dialect(self) -> None:
        """Dialect 未指定なら分割しない."""
        sql = "SELECT * FROM t WHERE id IN /* $ids */(1)"
        ids = list(range(1, 1500))
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"ids": ids})
        assert "OR" not in result.sql
        assert result.params == ids

    def test_no_split_within_limit(self) -> None:
        """上限以下なら分割しない."""
        sql = "SELECT * FROM t WHERE id IN /* $ids */(1)"
        ids = list(range(1, 1001))  # ちょうど 1000 件
        parser = TwoWaySQLParser(sql, dialect=Dialect.ORACLE)
        result = parser.parse({"ids": ids})
        assert "OR" not in result.sql

    def test_split_over_limit_positional(self) -> None:
        """上限超過で ? 形式の分割."""
        sql = "SELECT * FROM t WHERE id IN /* $ids */(1)"
        ids = list(range(1, 1004))  # 1003 件 → 1000 + 3
        parser = TwoWaySQLParser(sql, dialect=Dialect.SQLITE)
        # SQLite は in_clause_limit=None なので分割しない
        result = parser.parse({"ids": ids})
        assert "OR" not in result.sql

    def test_split_oracle_positional(self) -> None:
        """Oracle (1000件上限) で ? 形式の分割."""
        sql = "SELECT * FROM t WHERE col IN /* $ids */(1)"
        # placeholder を ? にしてテスト（Oracle は通常 :name だが分割ロジックの検証用）
        ids = list(range(1, 1004))  # 1003 件
        parser = TwoWaySQLParser(sql, placeholder="?")
        parser.dialect = Dialect.ORACLE  # in_clause_limit=1000 を注入
        result = parser.parse({"ids": ids})
        assert result.sql.count("col IN") == 2
        assert "OR" in result.sql
        assert result.sql.startswith("SELECT * FROM t WHERE (col IN")
        assert result.params == ids

    def test_split_oracle_named(self) -> None:
        """Oracle :name 形式での分割."""
        sql = "SELECT * FROM t WHERE id IN /* $ids */(1)"
        ids = list(range(1, 2002))  # 2001 件 → 1000 + 1000 + 1
        parser = TwoWaySQLParser(sql, dialect=Dialect.ORACLE)
        result = parser.parse({"ids": ids})
        assert result.sql.count("id IN") == 3
        assert result.sql.count(" OR ") == 2
        assert result.sql.startswith("SELECT * FROM t WHERE (id IN")
        assert len(result.named_params) == 2001
        # パラメータの順序が正しいか確認
        assert result.named_params["ids_0"] == 1
        assert result.named_params["ids_1000"] == 1001
        assert result.named_params["ids_2000"] == 2001

    def test_split_exact_multiple(self) -> None:
        """上限のちょうど倍数で分割."""
        sql = "SELECT * FROM t WHERE x IN /* $ids */(1)"
        ids = list(range(1, 2001))  # 2000 件 → 1000 + 1000
        parser = TwoWaySQLParser(sql, dialect=Dialect.ORACLE)
        result = parser.parse({"ids": ids})
        assert result.sql.count("x IN") == 2
        assert result.sql.count(" OR ") == 1

    def test_split_with_table_alias(self) -> None:
        """テーブルエイリアス付きカラムの分割."""
        sql = "SELECT * FROM t WHERE e.dept_id IN /* $ids */(1)"
        ids = list(range(1, 1002))  # 1001 件
        parser = TwoWaySQLParser(sql, dialect=Dialect.ORACLE)
        result = parser.parse({"ids": ids})
        assert result.sql.count("e.dept_id IN") == 2
        assert "OR" in result.sql

    def test_split_preserves_surrounding_sql(self) -> None:
        """分割しても前後の SQL が維持される."""
        sql = "SELECT * FROM t WHERE name = /* $name */'x' AND id IN /* $ids */(1) ORDER BY id"
        ids = list(range(1, 1002))
        parser = TwoWaySQLParser(sql, dialect=Dialect.ORACLE)
        result = parser.parse({"name": "Alice", "ids": ids})
        assert "name = :name" in result.sql
        assert "ORDER BY id" in result.sql
        assert result.named_params["name"] == "Alice"
        assert len(result.named_params) == 1002  # name + 1001 ids

    def test_split_with_function_expression(self) -> None:
        """関数式の IN 句を分割できる."""
        sql = "SELECT * FROM t WHERE UPPER(name) IN /* $ids */(1)"
        ids = list(range(1, 1002))
        parser = TwoWaySQLParser(sql, dialect=Dialect.ORACLE)
        result = parser.parse({"ids": ids})
        assert result.sql.count("UPPER(name) IN") == 2
        assert " OR " in result.sql

    def test_split_with_quoted_identifier(self) -> None:
        """引用符付き識別子の IN 句を分割できる."""
        sql = 'SELECT * FROM t WHERE "User".id IN /* $ids */(1)'
        ids = list(range(1, 1002))
        parser = TwoWaySQLParser(sql, dialect=Dialect.ORACLE)
        result = parser.parse({"ids": ids})
        assert result.sql.count('"User".id IN') == 2
        assert " OR " in result.sql

    def test_split_raises_when_column_unresolved(self) -> None:
        """列式が抽出できない場合は例外."""
        sql = "SELECT * FROM t WHERE id + 1 IN /* $ids */(1)"
        ids = list(range(1, 1002))
        parser = TwoWaySQLParser(sql, dialect=Dialect.ORACLE)
        with pytest.raises(SqlParseError):
            parser.parse({"ids": ids})

    def test_split_error_includes_sql_when_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """設定が有効ならSQL断片を含める."""
        from sqlym import config

        monkeypatch.setattr(config, "ERROR_INCLUDE_SQL", True)
        sql = "SELECT * FROM t WHERE id + 1 IN /* $ids */(1)"
        ids = list(range(1, 1002))
        parser = TwoWaySQLParser(sql, dialect=Dialect.ORACLE)
        with pytest.raises(SqlParseError, match=r"line=1 sql='SELECT \* FROM t WHERE id \+ 1 IN"):
            parser.parse({"ids": ids})

    def test_split_error_excludes_sql_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """設定が無効ならSQL断片を含めない."""
        from sqlym import config

        monkeypatch.setattr(config, "ERROR_INCLUDE_SQL", False)
        sql = "SELECT * FROM t WHERE id + 1 IN /* $ids */(1)"
        ids = list(range(1, 1002))
        parser = TwoWaySQLParser(sql, dialect=Dialect.ORACLE)
        with pytest.raises(SqlParseError) as excinfo:
            parser.parse({"ids": ids})
        assert "sql=" not in str(excinfo.value)
        assert "line=1" in str(excinfo.value)

    def test_split_error_language_english(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """英語メッセージに切り替えられる."""
        from sqlym import config

        monkeypatch.setattr(config, "ERROR_MESSAGE_LANGUAGE", "en")
        sql = "SELECT * FROM t WHERE id + 1 IN /* $ids */(1)"
        ids = list(range(1, 1002))
        parser = TwoWaySQLParser(sql, dialect=Dialect.ORACLE)
        with pytest.raises(SqlParseError, match=r"Failed to extract column expression"):
            parser.parse({"ids": ids})
