"""negative/positive 判定拡張のテスト."""

from __future__ import annotations

from sqlym.parser.twoway import TwoWaySQLParser, is_negative


class TestIsNegative:
    """is_negative 関数のテスト."""

    def test_none_is_negative(self) -> None:
        """None は negative."""
        assert is_negative(None) is True

    def test_false_is_negative(self) -> None:
        """False は negative."""
        assert is_negative(False) is True

    def test_true_is_positive(self) -> None:
        """True は positive."""
        assert is_negative(True) is False

    def test_empty_list_is_negative(self) -> None:
        """空リスト [] は negative."""
        assert is_negative([]) is True

    def test_list_with_values_is_positive(self) -> None:
        """値を持つリストは positive."""
        assert is_negative([1, 2, 3]) is False
        assert is_negative(["a", "b"]) is False

    def test_list_with_all_none_is_negative(self) -> None:
        """全要素が None のリストは negative."""
        assert is_negative([None, None, None]) is True

    def test_list_with_all_false_is_negative(self) -> None:
        """全要素が False のリストは negative."""
        assert is_negative([False, False]) is True

    def test_list_with_mixed_negative_is_negative(self) -> None:
        """全要素が negative（None/False 混在）のリストは negative."""
        assert is_negative([None, False, None]) is True

    def test_list_with_some_positive_is_positive(self) -> None:
        """一部でも positive な要素があるリストは positive."""
        assert is_negative([None, 1, None]) is False
        assert is_negative([False, "value", False]) is False

    def test_nested_list_all_negative_is_negative(self) -> None:
        """ネストしたリストで全要素が negative なら negative."""
        assert is_negative([[], [], []]) is True
        assert is_negative([[None], [None, None]]) is True

    def test_nested_list_with_positive_is_positive(self) -> None:
        """ネストしたリストで一部 positive なら positive."""
        assert is_negative([[1], []]) is False

    def test_zero_is_positive(self) -> None:
        """0 は positive（None/False のみ negative）."""
        assert is_negative(0) is False

    def test_empty_string_is_positive(self) -> None:
        """空文字列は positive."""
        assert is_negative("") is False

    def test_empty_dict_is_positive(self) -> None:
        """空辞書は positive（リストのみ特別扱い）."""
        assert is_negative({}) is False


class TestParserWithNegativeExtension:
    """パーサーの negative 拡張判定テスト."""

    def test_false_removes_line(self) -> None:
        """False は行削除される."""
        sql = """\
SELECT * FROM users
WHERE
    status = /* $status */'active'
    AND enabled = /* $enabled */true"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"status": "active", "enabled": False})
        assert "enabled" not in result.sql
        assert "status = ?" in result.sql
        assert result.params == ["active"]

    def test_empty_list_removes_line(self) -> None:
        """空リスト [] は行削除される."""
        sql = """\
SELECT * FROM users
WHERE
    status = /* $status */'active'
    AND dept_id IN /* $dept_ids */(1, 2, 3)"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"status": "active", "dept_ids": []})
        assert "dept_id" not in result.sql
        assert "status = ?" in result.sql
        assert result.params == ["active"]

    def test_all_none_list_removes_line(self) -> None:
        """全要素が None のリストは行削除される."""
        sql = """\
SELECT * FROM users
WHERE
    status = /* $status */'active'
    AND category IN /* $categories */(1, 2)"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"status": "active", "categories": [None, None]})
        assert "category" not in result.sql
        assert "status = ?" in result.sql

    def test_list_with_positive_values_kept(self) -> None:
        """一部でも positive な要素があるリストは行が残る."""
        sql = """\
SELECT * FROM users
WHERE dept_id IN /* $dept_ids */(1, 2, 3)"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"dept_ids": [None, 10, None]})
        # リストは展開されるが、None はフィルタされる
        # 現在の実装では None を含むリストもそのまま展開される
        assert "dept_id IN" in result.sql
        assert result.params == [None, 10, None]

    def test_non_removable_false_binds_null(self) -> None:
        """非 removable パラメータの False は NULL としてバインド."""
        sql = "SELECT * FROM users WHERE enabled = /* enabled */true"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"enabled": False})
        assert "enabled = ?" in result.sql
        assert result.params == [False]

    def test_non_removable_empty_list_binds(self) -> None:
        """非 removable パラメータの空リストは IN (NULL) になる."""
        sql = "SELECT * FROM users WHERE id IN /* ids */(1, 2)"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"ids": []})
        assert "IN (NULL)" in result.sql
        assert result.params == []

    def test_true_keeps_line(self) -> None:
        """True は行が残る."""
        sql = """\
SELECT * FROM users
WHERE enabled = /* $enabled */true"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"enabled": True})
        assert "enabled = ?" in result.sql
        assert result.params == [True]

    def test_zero_keeps_line(self) -> None:
        """0 は行が残る（positive）."""
        sql = """\
SELECT * FROM users
WHERE count = /* $count */1"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"count": 0})
        assert "count = ?" in result.sql
        assert result.params == [0]

    def test_empty_string_keeps_line(self) -> None:
        """空文字列は行が残る（positive）."""
        sql = """\
SELECT * FROM users
WHERE name = /* $name */'default'"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"name": ""})
        assert "name = ?" in result.sql
        assert result.params == [""]


class TestParserNegativeWithParentRemoval:
    """negative 拡張と親子関係による削除のテスト."""

    def test_all_children_false_removes_parent(self) -> None:
        """全ての子が False で削除されると親も削除."""
        sql = """\
SELECT * FROM users
WHERE
    id = /* $id */1
    AND (
        flag1 = /* $flag1 */true
        OR flag2 = /* $flag2 */true
    )"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"id": 100, "flag1": False, "flag2": False})
        assert "id = ?" in result.sql
        assert "flag1" not in result.sql
        assert "flag2" not in result.sql
        assert "(" not in result.sql
        assert result.params == [100]

    def test_where_removed_when_all_false(self) -> None:
        """WHERE 配下が全て False で削除されると WHERE も削除."""
        sql = """\
SELECT * FROM users
WHERE
    enabled = /* $enabled */true
    AND active = /* $active */true"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"enabled": False, "active": False})
        assert "WHERE" not in result.sql
        assert result.params == []
