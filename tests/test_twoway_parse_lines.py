"""TwoWaySQLParser._parse_lines() と _build_tree() のテスト."""

from sqly.parser.twoway import TwoWaySQLParser


class TestParseLines:
    """_parse_lines()のテスト: SQL文字列を行単位のLineUnitリストに変換する."""

    def test_single_line(self) -> None:
        parser = TwoWaySQLParser("SELECT * FROM users")
        units = parser._parse_lines()
        assert len(units) == 1
        assert units[0].line_number == 1
        assert units[0].original == "SELECT * FROM users"
        assert units[0].indent == 0
        assert units[0].content == "SELECT * FROM users"

    def test_multiple_lines(self) -> None:
        sql = "SELECT *\nFROM users\nWHERE id = 1"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines()
        assert len(units) == 3
        assert units[0].content == "SELECT *"
        assert units[1].content == "FROM users"
        assert units[2].content == "WHERE id = 1"

    def test_line_numbers_start_at_1(self) -> None:
        sql = "SELECT *\nFROM users"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines()
        assert units[0].line_number == 1
        assert units[1].line_number == 2

    def test_indented_lines(self) -> None:
        sql = "WHERE\n  AND a = 1\n  AND b = 2"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines()
        assert units[0].indent == 0
        assert units[0].content == "WHERE"
        assert units[1].indent == 2
        assert units[1].content == "AND a = 1"
        assert units[2].indent == 2
        assert units[2].content == "AND b = 2"

    def test_original_preserves_whitespace(self) -> None:
        sql = "  AND a = 1"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines()
        assert units[0].original == "  AND a = 1"
        assert units[0].content == "AND a = 1"

    def test_empty_line(self) -> None:
        sql = "SELECT *\n\nFROM users"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines()
        assert len(units) == 3
        assert units[1].is_empty is True
        assert units[1].indent == -1

    def test_whitespace_only_line(self) -> None:
        sql = "SELECT *\n   \nFROM users"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines()
        assert units[1].is_empty is True
        assert units[1].indent == -1

    def test_deep_indentation(self) -> None:
        sql = "WHERE\n    AND (\n        OR x = 1\n        OR y = 2\n    )"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines()
        assert units[0].indent == 0
        assert units[1].indent == 4
        assert units[2].indent == 8
        assert units[3].indent == 8
        assert units[4].indent == 4

    def test_defaults(self) -> None:
        parser = TwoWaySQLParser("SELECT 1")
        units = parser._parse_lines()
        assert units[0].children == []
        assert units[0].parent is None
        assert units[0].removed is False


class TestBuildTree:
    """_build_tree()のテスト: インデントから親子関係を構築する(Rule 2)."""

    def test_flat_lines_no_parent(self) -> None:
        sql = "SELECT *\nFROM users\nWHERE 1 = 1"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines()
        parser._build_tree(units)
        for unit in units:
            assert unit.parent is None
            assert unit.children == []

    def test_simple_parent_child(self) -> None:
        sql = "WHERE\n  AND a = 1"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines()
        parser._build_tree(units)
        parent, child = units[0], units[1]
        assert child.parent is parent
        assert child in parent.children

    def test_multiple_children(self) -> None:
        sql = "WHERE\n  AND a = 1\n  AND b = 2\n  AND c = 3"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines()
        parser._build_tree(units)
        parent = units[0]
        assert len(parent.children) == 3
        for child in units[1:]:
            assert child.parent is parent

    def test_nested_hierarchy(self) -> None:
        sql = "WHERE\n  AND (\n    OR x = 1\n    OR y = 2\n  )"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines()
        parser._build_tree(units)
        where = units[0]
        and_paren = units[1]
        or_x = units[2]
        or_y = units[3]
        close_paren = units[4]

        # WHERE -> AND (, )
        assert and_paren.parent is where
        assert close_paren.parent is where
        assert and_paren in where.children
        assert close_paren in where.children

        # AND ( -> OR x, OR y
        assert or_x.parent is and_paren
        assert or_y.parent is and_paren
        assert or_x in and_paren.children
        assert or_y in and_paren.children

    def test_empty_lines_skipped(self) -> None:
        sql = "WHERE\n\n  AND a = 1"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines()
        parser._build_tree(units)
        where = units[0]
        empty = units[1]
        child = units[2]
        assert empty.parent is None
        assert empty.children == []
        assert child.parent is where
        assert child in where.children

    def test_indent_decrease_returns_to_parent_level(self) -> None:
        sql = "SELECT *\nFROM users\nWHERE\n  AND a = 1\nORDER BY id"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines()
        parser._build_tree(units)
        _select, _from, where, and_a, order = units
        assert and_a.parent is where
        assert order.parent is None
        assert order.children == []

    def test_sibling_groups_under_different_parents(self) -> None:
        sql = "WHERE\n  AND a = 1\n  AND b = 2\nORDER BY\n  id\n  name"
        parser = TwoWaySQLParser(sql)
        units = parser._parse_lines()
        parser._build_tree(units)
        where, and_a, and_b, order, id_, name = units
        assert len(where.children) == 2
        assert and_a.parent is where
        assert and_b.parent is where
        assert len(order.children) == 2
        assert id_.parent is order
        assert name.parent is order
