"""パラメータ修飾記号のテスト."""

from __future__ import annotations

import pytest

from sqlym.exceptions import SqlParseError
from sqlym.parser.tokenizer import tokenize
from sqlym.parser.twoway import TwoWaySQLParser


class TestTokenizerModifiers:
    """Tokenizer の修飾記号パースのテスト."""

    def test_dollar_modifier(self) -> None:
        """$ 修飾子が認識される."""
        tokens = tokenize("/* $name */'default'")
        assert len(tokens) == 1
        assert tokens[0].removable is True
        assert tokens[0].bindless is False

    def test_ampersand_modifier(self) -> None:
        """& 修飾子が認識される."""
        tokens = tokenize("/* &flag */'value'")
        assert len(tokens) == 1
        assert tokens[0].bindless is True
        assert tokens[0].removable is False

    def test_at_modifier(self) -> None:
        """@ 修飾子が認識される."""
        tokens = tokenize("/* @id */'1'")
        assert len(tokens) == 1
        assert tokens[0].required is True

    def test_question_modifier(self) -> None:
        """? 修飾子が認識される."""
        tokens = tokenize("/* ?fallback */'default'")
        assert len(tokens) == 1
        assert tokens[0].fallback is True

    def test_exclamation_modifier(self) -> None:
        """! 修飾子が認識される."""
        tokens = tokenize("/* $!name */'default'")
        assert len(tokens) == 1
        assert tokens[0].negated is True
        assert tokens[0].removable is True

    def test_combined_modifiers(self) -> None:
        """複数の修飾子を組み合わせられる."""
        tokens = tokenize("/* $!name */'default'")
        assert tokens[0].removable is True
        assert tokens[0].negated is True

    def test_no_modifier(self) -> None:
        """修飾子なしのパラメータ."""
        tokens = tokenize("/* name */'default'")
        assert len(tokens) == 1
        assert tokens[0].removable is False
        assert tokens[0].bindless is False
        assert tokens[0].negated is False
        assert tokens[0].required is False
        assert tokens[0].fallback is False


class TestBindlessModifier:
    """& 修飾記号（バインドなし行削除）のテスト."""

    def test_bindless_negative_removes_line(self) -> None:
        """& パラメータが negative なら行削除."""
        sql = """\
SELECT * FROM users
WHERE
    name = /* name */'test'
    AND is_active /* &is_active */"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": "Alice", "is_active": None})
        assert "is_active" not in result.sql
        assert "name = ?" in result.sql
        assert result.params == ["Alice"]

    def test_bindless_positive_no_placeholder(self) -> None:
        """& パラメータが positive ならプレースホルダなしでコメント除去."""
        sql = "SELECT * FROM users WHERE is_active /* &is_active */"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"is_active": True})
        assert result.sql == "SELECT * FROM users WHERE is_active "
        assert result.params == []

    def test_bindless_with_false_removes_line(self) -> None:
        """& パラメータが False なら行削除."""
        sql = """\
SELECT * FROM users
WHERE
    name = /* name */'test'
    AND is_admin /* &is_admin */"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": "Alice", "is_admin": False})
        assert "is_admin" not in result.sql


class TestNegationModifier:
    """! 否定修飾子のテスト."""

    def test_negated_positive_removes_line(self) -> None:
        """$! パラメータが positive なら行削除（反転）."""
        sql = """\
SELECT * FROM users
WHERE
    name = /* name */'test'
    AND age = /* $!age */25"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": "Alice", "age": 30})
        assert "age" not in result.sql
        assert "name = ?" in result.sql

    def test_negated_negative_keeps_line(self) -> None:
        """$! パラメータが negative なら行を残す（反転）."""
        sql = """\
SELECT * FROM users
WHERE
    name = /* name */'test'
    AND age = /* $!age */25"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": "Alice", "age": None})
        assert "age = ?" in result.sql
        assert result.params == ["Alice", None]

    def test_bindless_negated(self) -> None:
        """&! 組み合わせ: positive なら行削除、negative なら残る."""
        sql = """\
SELECT * FROM users
WHERE
    name = /* name */'test'
    AND is_guest /* &!is_member */"""
        parser = TwoWaySQLParser(sql)

        # is_member=True → WHERE の is_guest 行が削除
        result = parser.parse({"name": "Alice", "is_member": True})
        assert "is_guest" not in result.sql
        assert "name = ?" in result.sql

        # is_member=None → 行を残す
        result = parser.parse({"name": "Alice", "is_member": None})
        assert "is_guest" in result.sql


class TestRequiredModifier:
    """@ 必須パラメータ修飾記号のテスト."""

    def test_required_with_value(self) -> None:
        """@ パラメータに値があれば正常に処理."""
        sql = "SELECT * FROM users WHERE id = /* @id */1"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"id": 100})
        assert "id = ?" in result.sql
        assert result.params == [100]

    def test_required_none_raises(self) -> None:
        """@ パラメータが None なら例外."""
        sql = "SELECT * FROM users WHERE id = /* @id */1"
        parser = TwoWaySQLParser(sql)
        with pytest.raises(SqlParseError, match="param='id'"):
            parser.parse({"id": None})

    def test_required_false_raises(self) -> None:
        """@ パラメータが False なら例外（negative 拡張）."""
        sql = "SELECT * FROM users WHERE id = /* @id */1"
        parser = TwoWaySQLParser(sql)
        with pytest.raises(SqlParseError, match="param='id'"):
            parser.parse({"id": False})

    def test_required_empty_list_raises(self) -> None:
        """@ パラメータが空リストなら例外（negative 拡張）."""
        sql = "SELECT * FROM users WHERE id = /* @id */1"
        parser = TwoWaySQLParser(sql)
        with pytest.raises(SqlParseError, match="param='id'"):
            parser.parse({"id": []})

    def test_required_missing_raises(self) -> None:
        """@ パラメータが未指定なら例外."""
        sql = "SELECT * FROM users WHERE id = /* @id */1"
        parser = TwoWaySQLParser(sql)
        with pytest.raises(SqlParseError, match="param='id'"):
            parser.parse({})


class TestTrailingDelimiterRemoval:
    """行末区切り除去のテスト."""

    def test_trailing_and_removed(self) -> None:
        """行末の AND が除去される."""
        sql = """\
SELECT * FROM users
WHERE
    age >= /* $age_from */25 AND
    age <= /* $age_to */50"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"age_from": 20, "age_to": None})
        assert "age >= ?" in result.sql
        assert "AND" not in result.sql.split("\n")[-1]  # 最終行に AND がない
        assert result.params == [20]

    def test_trailing_or_removed(self) -> None:
        """行末の OR が除去される."""
        sql = """\
SELECT * FROM users
WHERE
    status = /* $status1 */'a' OR
    status = /* $status2 */'b'"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"status1": "active", "status2": None})
        assert "status = ?" in result.sql
        assert "OR" not in result.sql.split("\n")[-1]

    def test_trailing_comma_before_paren_removed(self) -> None:
        """閉じ括弧前の行末カンマが除去される."""
        sql = """\
INSERT INTO users (id, name, email)
VALUES (
    /* id */1,
    /* $name */'',
    /* $email */''
)"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"id": 1, "name": "Alice", "email": None})
        # email 行が削除され、name 行末のカンマが除去される
        lines = result.sql.split("\n")
        name_line = [
            line for line in lines if "?" in line and "," not in line.split("?")[-1]
        ]
        assert len(name_line) >= 1  # カンマが除去された行がある

    def test_multiple_trailing_and_removed(self) -> None:
        """複数行の行末 AND が除去される."""
        sql = """\
SELECT * FROM users
WHERE
    a = /* $a */1 AND
    b = /* $b */2 AND
    c = /* $c */3"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"a": 1, "b": None, "c": None})
        assert "a = ?" in result.sql
        assert "b" not in result.sql
        assert "c" not in result.sql
        # 最終的な SQL に余計な AND がないことを確認
        clean_sql = " ".join(result.sql.split())
        assert not clean_sql.rstrip().endswith("AND")


class TestFallbackModifier:
    """? フォールバック修飾記号のテスト."""

    def test_fallback_first_positive(self) -> None:
        """フォールバックチェーンで最初の positive な値を使用."""
        sql = "SELECT * FROM users WHERE name = /* ?a ?b */'default'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"a": "Alice", "b": "Bob"})
        assert "name = ?" in result.sql
        assert result.params == ["Alice"]

    def test_fallback_second_positive(self) -> None:
        """最初が negative なら2番目の値を使用."""
        sql = "SELECT * FROM users WHERE name = /* ?a ?b */'default'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"a": None, "b": "Bob"})
        assert "name = ?" in result.sql
        assert result.params == ["Bob"]

    def test_fallback_third_positive(self) -> None:
        """3つ目のパラメータまでフォールバック."""
        sql = "SELECT * FROM users WHERE name = /* ?a ?b ?c */'default'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"a": None, "b": None, "c": "Charlie"})
        assert "name = ?" in result.sql
        assert result.params == ["Charlie"]

    def test_fallback_all_negative_removes_line(self) -> None:
        """全て negative ならば行削除."""
        sql = """\
SELECT * FROM users
WHERE
    id = /* id */1
    AND name = /* ?a ?b */'default'"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"id": 1, "a": None, "b": None})
        assert "name" not in result.sql
        assert result.params == [1]

    def test_fallback_false_is_negative(self) -> None:
        """False は negative として扱われる."""
        sql = "SELECT * FROM users WHERE flag = /* ?a ?b */'default'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"a": False, "b": True})
        assert "flag = ?" in result.sql
        assert result.params == [True]

    def test_fallback_empty_list_is_negative(self) -> None:
        """空リストは negative として扱われる."""
        sql = "SELECT * FROM users WHERE name = /* ?a ?b */'default'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"a": [], "b": "Bob"})
        assert "name = ?" in result.sql
        assert result.params == ["Bob"]

    def test_fallback_tokenizer_recognizes_pattern(self) -> None:
        """Tokenizer がフォールバックパターンを認識する."""
        tokens = tokenize("/* ?a ?b ?c */'default'")
        assert len(tokens) == 1
        assert tokens[0].fallback is True
        assert tokens[0].fallback_names == ("a", "b", "c")
        assert tokens[0].name == "a"
        assert tokens[0].removable is True

    def test_fallback_with_number_default(self) -> None:
        """数値デフォルト値でのフォールバック."""
        sql = "SELECT * FROM users WHERE age = /* ?min_age ?default_age */25"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"min_age": None, "default_age": 30})
        assert "age = ?" in result.sql
        assert result.params == [30]

    def test_fallback_missing_params_all_negative(self) -> None:
        """未指定パラメータは negative として扱われる."""
        sql = """\
SELECT * FROM users
WHERE
    id = /* id */1
    AND name = /* ?a ?b */'default'"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"id": 1})  # a, b は未指定
        assert "name" not in result.sql
        assert result.params == [1]


class TestSetOperatorRemoval:
    """区切りのみの行（UNION/UNION ALL 等）の結合処理テスト."""

    def test_union_removed_when_second_query_removed(self) -> None:
        """2番目のクエリが削除されたとき UNION も削除."""
        sql = """\
SELECT * FROM users WHERE name = /* $name1 */'a'
UNION
SELECT * FROM users WHERE name = /* $name2 */'b'"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name1": "Alice", "name2": None})
        assert "UNION" not in result.sql
        assert "Alice" not in result.sql  # バインド
        assert "name = ?" in result.sql

    def test_union_all_removed_when_second_query_removed(self) -> None:
        """2番目のクエリが削除されたとき UNION ALL も削除."""
        sql = """\
SELECT * FROM users WHERE name = /* $name1 */'a'
UNION ALL
SELECT * FROM users WHERE name = /* $name2 */'b'"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name1": "Alice", "name2": None})
        assert "UNION" not in result.sql
        assert "name = ?" in result.sql

    def test_union_removed_when_first_query_removed(self) -> None:
        """1番目のクエリが削除されたとき UNION も削除."""
        sql = """\
SELECT * FROM users WHERE name = /* $name1 */'a'
UNION
SELECT * FROM users WHERE name = /* $name2 */'b'"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name1": None, "name2": "Bob"})
        assert "UNION" not in result.sql
        assert "name = ?" in result.sql
        assert result.params == ["Bob"]

    def test_except_removed_when_query_removed(self) -> None:
        """EXCEPT も同様に処理."""
        sql = """\
SELECT * FROM users WHERE name = /* $name1 */'a'
EXCEPT
SELECT * FROM users WHERE name = /* $name2 */'b'"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name1": "Alice", "name2": None})
        assert "EXCEPT" not in result.sql

    def test_intersect_removed_when_query_removed(self) -> None:
        """INTERSECT も同様に処理."""
        sql = """\
SELECT * FROM users WHERE name = /* $name1 */'a'
INTERSECT
SELECT * FROM users WHERE name = /* $name2 */'b'"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name1": "Alice", "name2": None})
        assert "INTERSECT" not in result.sql

    def test_union_kept_when_both_queries_present(self) -> None:
        """両方のクエリがある場合は UNION を残す."""
        sql = """\
SELECT * FROM users WHERE name = /* $name1 */'a'
UNION
SELECT * FROM users WHERE name = /* $name2 */'b'"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name1": "Alice", "name2": "Bob"})
        assert "UNION" in result.sql
        assert result.params == ["Alice", "Bob"]

    def test_multiple_unions_partial_removal(self) -> None:
        """複数の UNION で部分的な削除."""
        sql = """\
SELECT * FROM users WHERE name = /* $name1 */'a'
UNION
SELECT * FROM users WHERE name = /* $name2 */'b'
UNION
SELECT * FROM users WHERE name = /* $name3 */'c'"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name1": "Alice", "name2": None, "name3": "Charlie"})
        # name2 の行と対応する UNION が削除される
        assert result.sql.count("UNION") == 1
        assert result.params == ["Alice", "Charlie"]

    def test_union_with_indented_queries(self) -> None:
        """インデントされたクエリでも正しく処理."""
        sql = """\
    SELECT * FROM users WHERE name = /* $name1 */'a'
UNION ALL
    SELECT * FROM users WHERE name = /* $name2 */'b'"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name1": "Alice", "name2": None})
        assert "UNION" not in result.sql
