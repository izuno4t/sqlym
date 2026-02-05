"""ブロックディレクティブ（%IF/%ELSE/%END）のテスト."""

import pytest

from sqlym.exceptions import SqlParseError
from sqlym.parser.tokenizer import Directive, DirectiveType, parse_directive
from sqlym.parser.twoway import TwoWaySQLParser


class TestParseDirective:
    """ディレクティブパースのテスト."""

    def test_parse_if(self) -> None:
        """-- %IF condition をパースする."""
        d = parse_directive("-- %IF name")
        assert d is not None
        assert d.type == DirectiveType.IF
        assert d.condition == "name"

    def test_parse_if_with_spaces(self) -> None:
        """スペース付き -- %IF をパースする."""
        d = parse_directive("  -- %IF condition  ")
        assert d is not None
        assert d.type == DirectiveType.IF
        assert d.condition == "condition"

    def test_parse_elseif(self) -> None:
        """-- %ELSEIF condition をパースする."""
        d = parse_directive("-- %ELSEIF another")
        assert d is not None
        assert d.type == DirectiveType.ELSEIF
        assert d.condition == "another"

    def test_parse_else(self) -> None:
        """-- %ELSE をパースする."""
        d = parse_directive("-- %ELSE")
        assert d is not None
        assert d.type == DirectiveType.ELSE
        assert d.condition is None

    def test_parse_end(self) -> None:
        """-- %END をパースする."""
        d = parse_directive("-- %END")
        assert d is not None
        assert d.type == DirectiveType.END
        assert d.condition is None

    def test_parse_non_directive(self) -> None:
        """ディレクティブでない行."""
        assert parse_directive("SELECT * FROM users") is None
        assert parse_directive("-- regular comment") is None
        assert parse_directive("/* comment */") is None


class TestIfElseBasic:
    """基本的な %IF/%ELSE のテスト."""

    def test_if_true_branch(self) -> None:
        """%IF 条件が true の場合、IF ブロックが選択される."""
        sql = """\
SELECT *
FROM users
-- %IF active
WHERE active = 1
-- %ELSE
WHERE deleted = 0
-- %END"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"active": True})
        assert "WHERE active = 1" in result.sql
        assert "WHERE deleted" not in result.sql

    def test_if_false_branch(self) -> None:
        """%IF 条件が false の場合、ELSE ブロックが選択される."""
        sql = """\
SELECT *
FROM users
-- %IF active
WHERE active = 1
-- %ELSE
WHERE deleted = 0
-- %END"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"active": None})
        assert "WHERE deleted = 0" in result.sql
        assert "WHERE active" not in result.sql

    def test_if_without_else(self) -> None:
        """%ELSE なしの %IF ブロック."""
        sql = """\
SELECT *
FROM users
-- %IF include_name
WHERE name = /* name */'default'
-- %END"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"include_name": True, "name": "John"})
        assert "WHERE name = ?" in result.sql

        result2 = parser.parse({"include_name": False, "name": "John"})
        assert "WHERE" not in result2.sql

    def test_if_with_parameter_in_block(self) -> None:
        """ブロック内のパラメータが展開される."""
        sql = """\
SELECT *
FROM users
-- %IF filter
WHERE id = /* id */1
-- %END"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"filter": True, "id": 42})
        assert "WHERE id = ?" in result.sql
        assert result.params == [42]


class TestElseIf:
    """%ELSEIF のテスト."""

    def test_elseif_first_true(self) -> None:
        """最初の条件が true."""
        sql = """\
SELECT *
-- %IF type_a
FROM table_a
-- %ELSEIF type_b
FROM table_b
-- %ELSE
FROM table_c
-- %END"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"type_a": True, "type_b": False})
        assert "FROM table_a" in result.sql
        assert "FROM table_b" not in result.sql
        assert "FROM table_c" not in result.sql

    def test_elseif_second_true(self) -> None:
        """2番目の条件が true."""
        sql = """\
SELECT *
-- %IF type_a
FROM table_a
-- %ELSEIF type_b
FROM table_b
-- %ELSE
FROM table_c
-- %END"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"type_a": False, "type_b": True})
        assert "FROM table_b" in result.sql
        assert "FROM table_a" not in result.sql
        assert "FROM table_c" not in result.sql

    def test_elseif_all_false(self) -> None:
        """全ての条件が false で ELSE が選択される."""
        sql = """\
SELECT *
-- %IF type_a
FROM table_a
-- %ELSEIF type_b
FROM table_b
-- %ELSE
FROM table_c
-- %END"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"type_a": False, "type_b": False})
        assert "FROM table_c" in result.sql


class TestConditionExpressions:
    """条件式のテスト."""

    def test_not_condition(self) -> None:
        """NOT 演算子."""
        sql = """\
SELECT *
-- %IF NOT active
FROM inactive_users
-- %ELSE
FROM active_users
-- %END"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"active": False})
        assert "FROM inactive_users" in result.sql

        result2 = parser.parse({"active": True})
        assert "FROM active_users" in result2.sql

    def test_and_condition(self) -> None:
        """AND 演算子."""
        sql = """\
SELECT *
-- %IF a AND b
FROM both_true
-- %ELSE
FROM not_both
-- %END"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"a": True, "b": True})
        assert "FROM both_true" in result.sql

        result2 = parser.parse({"a": True, "b": False})
        assert "FROM not_both" in result2.sql

    def test_or_condition(self) -> None:
        """OR 演算子."""
        sql = """\
SELECT *
-- %IF a OR b
FROM either_true
-- %ELSE
FROM neither
-- %END"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"a": True, "b": False})
        assert "FROM either_true" in result.sql

        result2 = parser.parse({"a": False, "b": False})
        assert "FROM neither" in result2.sql

    def test_complex_condition(self) -> None:
        """複合条件式."""
        sql = """\
SELECT *
-- %IF a AND b OR c
FROM selected
-- %ELSE
FROM fallback
-- %END"""
        parser = TwoWaySQLParser(sql)
        # a AND b = True (both true)
        result = parser.parse({"a": True, "b": True, "c": False})
        assert "FROM selected" in result.sql

        # c = True
        result2 = parser.parse({"a": False, "b": False, "c": True})
        assert "FROM selected" in result2.sql

        # all false
        result3 = parser.parse({"a": False, "b": False, "c": False})
        assert "FROM fallback" in result3.sql


class TestNestedIf:
    """ネストされた %IF のテスト."""

    def test_nested_if(self) -> None:
        """ネストされた %IF ブロック."""
        sql = """\
SELECT *
-- %IF outer
FROM outer_table
-- %IF inner
WHERE inner_cond = 1
-- %END
-- %END"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"outer": True, "inner": True})
        assert "FROM outer_table" in result.sql
        assert "WHERE inner_cond = 1" in result.sql

    def test_nested_if_outer_false(self) -> None:
        """外側の条件が false の場合、内側も含めて除外."""
        sql = """\
SELECT *
-- %IF outer
FROM outer_table
-- %IF inner
WHERE inner_cond = 1
-- %END
-- %ELSE
FROM default_table
-- %END"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"outer": False, "inner": True})
        assert "FROM default_table" in result.sql
        assert "FROM outer_table" not in result.sql


class TestErrorCases:
    """エラーケースのテスト."""

    def test_unclosed_if_block(self) -> None:
        """%END がない %IF ブロック."""
        sql = """\
SELECT *
-- %IF condition
WHERE col = 1"""
        parser = TwoWaySQLParser(sql)
        with pytest.raises(SqlParseError):
            parser.parse({"condition": True})

    def test_else_without_if(self) -> None:
        """対応する %IF がない %ELSE."""
        sql = """\
SELECT *
-- %ELSE
FROM users"""
        parser = TwoWaySQLParser(sql)
        with pytest.raises(SqlParseError):
            parser.parse({})

    def test_end_without_if(self) -> None:
        """対応する %IF がない %END."""
        sql = """\
SELECT *
-- %END"""
        parser = TwoWaySQLParser(sql)
        with pytest.raises(SqlParseError):
            parser.parse({})
