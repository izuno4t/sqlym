"""インライン条件分岐（%if/%elseif/%else/%end）のテスト."""

from sqlym.parser.tokenizer import parse_inline_conditions
from sqlym.parser.twoway import TwoWaySQLParser


class TestParseInlineConditions:
    """インライン条件分岐パースのテスト."""

    def test_simple_if_else(self) -> None:
        """単純な %if/%else/%end."""
        line = "SELECT /*%if active */ 'yes' /*%else */ 'no' /*%end*/ as status"
        conditions = parse_inline_conditions(line)
        assert len(conditions) == 1
        cond = conditions[0]
        assert cond.conditions == ("active",)
        assert cond.values == ("'yes'", "'no'")

    def test_if_only(self) -> None:
        """%else なしの %if/%end."""
        line = "SELECT /*%if show */ value /*%end*/ FROM t"
        conditions = parse_inline_conditions(line)
        assert len(conditions) == 1
        cond = conditions[0]
        assert cond.conditions == ("show",)
        assert cond.values == ("value",)

    def test_if_elseif_else(self) -> None:
        """%if/%elseif/%else/%end."""
        line = "SELECT /*%if a */ 1 /*%elseif b */ 2 /*%else */ 3 /*%end*/ as num"
        conditions = parse_inline_conditions(line)
        assert len(conditions) == 1
        cond = conditions[0]
        assert cond.conditions == ("a", "b")
        assert cond.values == ("1", "2", "3")

    def test_multiple_inline_conditions(self) -> None:
        """複数のインライン条件分岐."""
        line = (
            "SELECT /*%if a */ x /*%else */ y /*%end*/, "
            "/*%if b */ m /*%else */ n /*%end*/"
        )
        conditions = parse_inline_conditions(line)
        assert len(conditions) == 2

    def test_no_inline_conditions(self) -> None:
        """インライン条件分岐なし."""
        line = "SELECT * FROM users"
        conditions = parse_inline_conditions(line)
        assert len(conditions) == 0


class TestInlineConditionEvaluation:
    """インライン条件分岐評価のテスト."""

    def test_if_true(self) -> None:
        """%if 条件が true."""
        sql = "SELECT /*%if active */ 'active' /*%else */ 'inactive' /*%end*/ as status FROM users"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"active": True})
        assert "'active'" in result.sql
        assert "'inactive'" not in result.sql

    def test_if_false(self) -> None:
        """%if 条件が false."""
        sql = "SELECT /*%if active */ 'active' /*%else */ 'inactive' /*%end*/ as status FROM users"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"active": False})
        assert "'inactive'" in result.sql
        assert "'active'" not in result.sql

    def test_if_without_else_true(self) -> None:
        """%else なしで条件が true."""
        sql = "SELECT id /*%if show_name */, name /*%end*/ FROM users"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"show_name": True})
        assert ", name" in result.sql

    def test_if_without_else_false(self) -> None:
        """%else なしで条件が false."""
        sql = "SELECT id /*%if show_name */, name /*%end*/ FROM users"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"show_name": False})
        assert ", name" not in result.sql

    def test_elseif_first_true(self) -> None:
        """%elseif: 最初の条件が true."""
        sql = "SELECT /*%if a */ 'A' /*%elseif b */ 'B' /*%else */ 'C' /*%end*/ as val"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"a": True, "b": False})
        assert "'A'" in result.sql
        assert "'B'" not in result.sql
        assert "'C'" not in result.sql

    def test_elseif_second_true(self) -> None:
        """%elseif: 2番目の条件が true."""
        sql = "SELECT /*%if a */ 'A' /*%elseif b */ 'B' /*%else */ 'C' /*%end*/ as val"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"a": False, "b": True})
        assert "'B'" in result.sql
        assert "'A'" not in result.sql
        assert "'C'" not in result.sql

    def test_elseif_all_false(self) -> None:
        """%elseif: 全ての条件が false."""
        sql = "SELECT /*%if a */ 'A' /*%elseif b */ 'B' /*%else */ 'C' /*%end*/ as val"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"a": False, "b": False})
        assert "'C'" in result.sql


class TestInlineConditionWithParams:
    """インライン条件分岐とパラメータの組み合わせテスト."""

    def test_inline_with_parameter_in_branch(self) -> None:
        """ブランチ内のパラメータ."""
        sql = "SELECT /*%if use_name */ /* name */'default' /*%else */ 'unknown' /*%end*/ as val"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"use_name": True, "name": "John"})
        assert "?" in result.sql
        assert result.params == ["John"]

    def test_inline_with_parameter_selected_branch(self) -> None:
        """選択されたブランチのパラメータのみバインド."""
        sql = "SELECT /*%if a */ /* val1 */'x' /*%else */ /* val2 */'y' /*%end*/ as v"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"a": True, "val1": "V1", "val2": "V2"})
        assert result.params == ["V1"]

    def test_complex_condition_in_inline(self) -> None:
        """複合条件式."""
        sql = "SELECT /*%if a AND b */ 'both' /*%else */ 'not both' /*%end*/ as status"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"a": True, "b": True})
        assert "'both'" in result.sql

        result2 = parser.parse({"a": True, "b": False})
        assert "'not both'" in result2.sql


class TestMultipleInlineConditions:
    """複数のインライン条件分岐のテスト."""

    def test_two_inline_conditions(self) -> None:
        """2つのインライン条件分岐."""
        sql = (
            "SELECT /*%if a */ x /*%else */ y /*%end*/ as col1, "
            "/*%if b */ m /*%else */ n /*%end*/ as col2"
        )
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"a": True, "b": False})
        assert "x as col1" in result.sql
        assert "n as col2" in result.sql
