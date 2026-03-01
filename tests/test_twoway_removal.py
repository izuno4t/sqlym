"""TwoWaySQLParser の行削除ロジック（Rule 3, Rule 4）テスト."""

from sqlym.parser.twoway import TwoWaySQLParser


class TestRule4Basic:
    """Rule 4: $付きパラメータが None なら行を削除する."""

    def test_removable_param_none_removes_line(self) -> None:
        """$param が None → 行削除."""
        sql = "SELECT * FROM users\nWHERE\n  AND name = /* $name */'default'"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines(parser.original_sql)
        parser._build_tree(units)
        parser._evaluate_params(units, {"name": None})
        assert units[2].removed is True

    def test_removable_param_with_value_keeps_line(self) -> None:
        """$param が値あり → 行削除しない."""
        sql = "SELECT * FROM users\nWHERE\n  AND name = /* $name */'default'"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines(parser.original_sql)
        parser._build_tree(units)
        parser._evaluate_params(units, {"name": "Alice"})
        assert units[2].removed is False

    def test_non_removable_param_none_keeps_line(self) -> None:
        """非 removable param が None → 行削除しない（NULL バインド）."""
        sql = "SELECT * FROM users\nWHERE\n  AND name = /* name */'default'"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines(parser.original_sql)
        parser._build_tree(units)
        parser._evaluate_params(units, {"name": None})
        assert units[2].removed is False

    def test_removable_param_missing_from_params_removes_line(self) -> None:
        """$param が params に存在しない → 行削除."""
        sql = "SELECT * FROM users\nWHERE\n  AND name = /* $name */'default'"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines(parser.original_sql)
        parser._build_tree(units)
        parser._evaluate_params(units, {})
        assert units[2].removed is True


class TestRule4MultipleLines:
    """Rule 4: 複数行のうち一部が None → 該当行のみ削除."""

    def test_partial_removal(self) -> None:
        """複数条件のうち一部が None → 該当行のみ削除される."""
        sql = (
            "SELECT * FROM users\n"
            "WHERE\n"
            "  AND name = /* $name */'default'\n"
            "  AND age = /* $age */20"
        )
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines(parser.original_sql)
        parser._build_tree(units)
        parser._evaluate_params(units, {"name": None, "age": 30})
        assert units[2].removed is True  # name は None → 削除
        assert units[3].removed is False  # age は値あり → 残る

    def test_all_removable_none(self) -> None:
        """全ての removable パラメータが None → 全行削除."""
        sql = (
            "SELECT * FROM users\n"
            "WHERE\n"
            "  AND name = /* $name */'default'\n"
            "  AND age = /* $age */20"
        )
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines(parser.original_sql)
        parser._build_tree(units)
        parser._evaluate_params(units, {"name": None, "age": None})
        assert units[2].removed is True
        assert units[3].removed is True


class TestRule3Basic:
    """Rule 3: 子が全削除なら親も削除."""

    def test_all_children_removed_removes_parent(self) -> None:
        """子が全削除 → 親も削除."""
        sql = (
            "SELECT * FROM users\n"
            "WHERE\n"
            "  AND name = /* $name */'default'\n"
            "  AND age = /* $age */20"
        )
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines(parser.original_sql)
        parser._build_tree(units)
        parser._evaluate_params(units, {"name": None, "age": None})
        parser._propagate_removal(units)
        assert units[1].removed is True  # WHERE も削除

    def test_partial_children_removed_keeps_parent(self) -> None:
        """子の一部だけ削除 → 親は残る."""
        sql = (
            "SELECT * FROM users\n"
            "WHERE\n"
            "  AND name = /* $name */'default'\n"
            "  AND age = /* $age */20"
        )
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines(parser.original_sql)
        parser._build_tree(units)
        parser._evaluate_params(units, {"name": None, "age": 30})
        parser._propagate_removal(units)
        assert units[1].removed is False  # WHERE は残る


class TestRule3Nested:
    """Rule 3: ネストした親子関係での伝播."""

    def test_grandchildren_all_removed_propagates(self) -> None:
        """孫が全削除 → 子削除 → 親削除（伝播）."""
        sql = (
            "WHERE\n"
            "  AND (\n"
            "    OR status = /* $status1 */'active'\n"
            "    OR status = /* $status2 */'pending'\n"
            "  )"
        )
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines(parser.original_sql)
        parser._build_tree(units)
        parser._evaluate_params(units, {"status1": None, "status2": None})
        parser._propagate_removal(units)
        # 孫 (status1, status2) が削除 → AND ( が削除 → WHERE が削除
        assert units[2].removed is True  # OR status1
        assert units[3].removed is True  # OR status2
        assert units[1].removed is True  # AND (
        assert units[0].removed is True  # WHERE

    def test_closing_paren_also_removed(self) -> None:
        """閉じ括弧も子として伝播で削除される."""
        sql = (
            "WHERE\n"
            "  AND (\n"
            "    OR status = /* $status1 */'active'\n"
            "    OR status = /* $status2 */'pending'\n"
            "  )"
        )
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines(parser.original_sql)
        parser._build_tree(units)
        parser._evaluate_params(units, {"status1": None, "status2": None})
        parser._propagate_removal(units)
        assert units[4].removed is True  # ) も削除


class TestIntegration:
    """parse() 経由での統合テスト."""

    def test_where_removed_when_all_conditions_none(self) -> None:
        """WHERE + 条件行で条件が全 None → WHERE ごと削除."""
        sql = (
            "SELECT * FROM users\n"
            "WHERE\n"
            "  AND name = /* $name */'default'\n"
            "  AND age = /* $age */20"
        )
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": None, "age": None})
        assert "WHERE" not in result.sql
        assert "name" not in result.sql
        assert "age" not in result.sql
        assert result.sql.strip() == "SELECT * FROM users"
        assert result.params == []

    def test_partial_removal_keeps_remaining(self) -> None:
        """一部条件が None → 残った条件で SQL を構築."""
        sql = (
            "SELECT * FROM users\n"
            "WHERE\n"
            "  AND name = /* $name */'default'\n"
            "  AND age = /* $age */20"
        )
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": None, "age": 30})
        assert "WHERE" in result.sql
        assert "name" not in result.sql
        assert "age = ?" in result.sql
        assert result.params == [30]

    def test_non_removable_none_binds_null(self) -> None:
        """非 removable が None → 行を残し NULL バインド."""
        sql = "SELECT * FROM users\nWHERE\n  AND deleted_at = /* deleted_at */NULL"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"deleted_at": None})
        assert "deleted_at = ?" in result.sql
        assert result.params == [None]

    def test_no_params_no_removal(self) -> None:
        """パラメータなし SQL は変更されない."""
        sql = "SELECT * FROM users\nWHERE id = 1"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({})
        assert result.sql == "SELECT * FROM users\nWHERE id = 1"
