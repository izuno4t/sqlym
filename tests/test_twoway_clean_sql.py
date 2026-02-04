"""TwoWaySQLParser._clean_sql() のテスト（WHERE/AND/OR/空括弧除去）."""

from sqly.parser.twoway import TwoWaySQLParser


def _clean(sql: str) -> str:
    """ヘルパー: _clean_sql を直接呼び出す."""
    parser = TwoWaySQLParser("dummy")
    return parser._clean_sql(sql)


class TestCleanSqlLeadingAndOr:
    """WHERE/HAVING 直後の先頭 AND/OR を除去する."""

    def test_strip_leading_and_after_where(self) -> None:
        """WHERE 直後の先頭 AND を除去."""
        sql = "WHERE\n    AND name = ?"
        assert _clean(sql) == "WHERE\n    name = ?"

    def test_strip_leading_or_after_where(self) -> None:
        """WHERE 直後の先頭 OR を除去."""
        sql = "WHERE\n    OR name = ?"
        assert _clean(sql) == "WHERE\n    name = ?"

    def test_only_first_conjunction_stripped(self) -> None:
        """最初の AND/OR のみ除去、後続の AND/OR は保持."""
        sql = "WHERE\n    AND name = ?\n    AND age = ?"
        assert _clean(sql) == "WHERE\n    name = ?\n    AND age = ?"

    def test_strip_leading_and_after_having(self) -> None:
        """HAVING 直後の先頭 AND を除去."""
        sql = "HAVING\n    AND count > 0"
        assert _clean(sql) == "HAVING\n    count > 0"

    def test_case_insensitive(self) -> None:
        """WHERE/AND は大文字小文字を区別しない."""
        sql = "where\n    and name = ?"
        assert _clean(sql) == "where\n    name = ?"

    def test_blank_lines_between_where_and_condition(self) -> None:
        """WHERE と条件行の間に空行があっても AND を除去."""
        sql = "WHERE\n\n    AND name = ?"
        assert _clean(sql) == "WHERE\n\n    name = ?"


class TestCleanSqlUnmatchedParens:
    """対応する開き括弧のない閉じ括弧行を除去する."""

    def test_unmatched_close_paren_removed(self) -> None:
        """対応なし ) 行を除去."""
        sql = "WHERE\n    )\n    AND name = ?"
        assert _clean(sql) == "WHERE\n    name = ?"

    def test_matched_close_paren_preserved(self) -> None:
        """対応あり ) 行は保持."""
        sql = "WHERE\n    (\n        name = ?\n    )"
        assert _clean(sql) == "WHERE\n    (\n        name = ?\n    )"

    def test_multiple_unmatched_close_parens(self) -> None:
        """複数の対応なし ) を除去."""
        sql = "WHERE\n    )\n    )\n    name = ?"
        assert _clean(sql) == "WHERE\n    name = ?"

    def test_inline_parens_not_affected(self) -> None:
        """行内の括弧（IN句等）は影響を受けない."""
        sql = "WHERE id IN (?, ?, ?)"
        assert _clean(sql) == "WHERE id IN (?, ?, ?)"


class TestCleanSqlDanglingWhere:
    """条件のない孤立 WHERE/HAVING を除去する."""

    def test_trailing_where_removed(self) -> None:
        """SQL末尾の条件なし WHERE を除去."""
        sql = "SELECT * FROM users\nWHERE"
        assert _clean(sql) == "SELECT * FROM users"

    def test_trailing_where_with_whitespace_removed(self) -> None:
        """末尾空白付き WHERE を除去."""
        sql = "SELECT * FROM users\nWHERE   \n  "
        assert _clean(sql) == "SELECT * FROM users"

    def test_where_before_order_by_removed(self) -> None:
        """WHERE の後に ORDER BY が続く場合、WHERE を除去."""
        sql = "SELECT * FROM users\nWHERE\nORDER BY id"
        assert _clean(sql) == "SELECT * FROM users\nORDER BY id"


class TestCleanSqlNoOp:
    """クリーンアップ不要の SQL はそのまま返す."""

    def test_plain_sql_unchanged(self) -> None:
        """通常 SQL は変更なし."""
        sql = "SELECT * FROM users"
        assert _clean(sql) == "SELECT * FROM users"

    def test_where_with_condition_unchanged(self) -> None:
        """条件付き WHERE は変更なし."""
        sql = "SELECT * FROM users\nWHERE\n    name = ?"
        assert _clean(sql) == "SELECT * FROM users\nWHERE\n    name = ?"


class TestCleanSqlIntegration:
    """parse() 経由での整形統合テスト."""

    def test_spec_2_4_2_leading_and_removed(self) -> None:
        """SPEC 2.4.2: 先頭 AND 除去."""
        sql = "WHERE\n    id = /* $id */1\n    AND name = /* $name */'太郎'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"id": None, "name": "花子"})
        assert result.sql == "WHERE\n    name = ?"
        assert result.params == ["花子"]

    def test_spec_2_4_3_empty_parens_with_surviving_sibling(self) -> None:
        """SPEC 2.4.3 応用: 空括弧グループ削除後、残った兄弟行を整形."""
        sql = (
            "WHERE\n"
            "    AND (\n"
            "        status = /* $status1 */'active'\n"
            "        OR status = /* $status2 */'pending'\n"
            "    )\n"
            "    AND name = /* $name */'test'"
        )
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"status1": None, "status2": None, "name": "Alice"})
        assert result.sql == "WHERE\n    name = ?"
        assert result.params == ["Alice"]

    def test_all_conditions_none_where_removed(self) -> None:
        """全条件 None → WHERE ごと除去（Rule 3 伝播 + clean_sql）."""
        sql = "SELECT * FROM users\nWHERE\n    AND name = /* $name */'default'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": None})
        assert result.sql == "SELECT * FROM users"
        assert result.params == []

    def test_multiline_partial_removal(self) -> None:
        """複数条件で先頭が削除、中間が残る."""
        sql = (
            "SELECT * FROM users\n"
            "WHERE\n"
            "    id = /* $id */1\n"
            "    AND name = /* $name */'test'\n"
            "    AND age = /* $age */20"
        )
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"id": None, "name": "Alice", "age": 30})
        assert result.sql == "SELECT * FROM users\nWHERE\n    name = ?\n    AND age = ?"
        assert result.params == ["Alice", 30]
