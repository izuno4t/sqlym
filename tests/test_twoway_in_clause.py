"""TwoWaySQLParser の IN句自動展開テスト."""

from sqly.parser.twoway import TwoWaySQLParser


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
        """空リストは IN (NULL) に展開される."""
        sql = "SELECT * FROM users WHERE id IN /* $ids */(1, 2, 3)"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"ids": []})
        assert result.sql == "SELECT * FROM users WHERE id IN (NULL)"
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
