"""LineUnitクラスのテスト."""

from sqly.parser.line_unit import LineUnit


class TestLineUnitCreation:
    """LineUnitの生成と基本属性を検証する."""

    def test_basic_creation(self) -> None:
        unit = LineUnit(line_number=1, original="SELECT *", indent=0, content="SELECT *")
        assert unit.line_number == 1
        assert unit.original == "SELECT *"
        assert unit.indent == 0
        assert unit.content == "SELECT *"

    def test_default_values(self) -> None:
        unit = LineUnit(line_number=1, original="", indent=0, content="")
        assert unit.children == []
        assert unit.parent is None
        assert unit.removed is False

    def test_indented_line(self) -> None:
        unit = LineUnit(
            line_number=3,
            original="    AND name = 'test'",
            indent=4,
            content="AND name = 'test'",
        )
        assert unit.indent == 4
        assert unit.content == "AND name = 'test'"


class TestLineUnitIsEmpty:
    """is_emptyプロパティを検証する."""

    def test_empty_content(self) -> None:
        unit = LineUnit(line_number=1, original="", indent=0, content="")
        assert unit.is_empty is True

    def test_whitespace_only_content(self) -> None:
        unit = LineUnit(line_number=1, original="   ", indent=0, content="   ")
        assert unit.is_empty is True

    def test_negative_indent(self) -> None:
        unit = LineUnit(line_number=1, original="", indent=-1, content="some content")
        assert unit.is_empty is True

    def test_non_empty_content(self) -> None:
        unit = LineUnit(line_number=1, original="SELECT *", indent=0, content="SELECT *")
        assert unit.is_empty is False

    def test_zero_indent_with_content(self) -> None:
        unit = LineUnit(line_number=1, original="WHERE 1=1", indent=0, content="WHERE 1=1")
        assert unit.is_empty is False


class TestLineUnitParentChild:
    """親子関係の設定を検証する."""

    def test_set_parent(self) -> None:
        parent = LineUnit(line_number=1, original="WHERE", indent=0, content="WHERE")
        child = LineUnit(line_number=2, original="  AND a = 1", indent=2, content="AND a = 1")
        child.parent = parent
        assert child.parent is parent

    def test_add_children(self) -> None:
        parent = LineUnit(line_number=1, original="WHERE", indent=0, content="WHERE")
        child1 = LineUnit(line_number=2, original="  AND a = 1", indent=2, content="AND a = 1")
        child2 = LineUnit(line_number=3, original="  AND b = 2", indent=2, content="AND b = 2")
        parent.children.append(child1)
        parent.children.append(child2)
        assert len(parent.children) == 2
        assert parent.children[0] is child1
        assert parent.children[1] is child2

    def test_parent_child_bidirectional(self) -> None:
        parent = LineUnit(line_number=1, original="WHERE", indent=0, content="WHERE")
        child = LineUnit(line_number=2, original="  AND a = 1", indent=2, content="AND a = 1")
        parent.children.append(child)
        child.parent = parent
        assert child.parent is parent
        assert child in parent.children


class TestLineUnitRemoved:
    """削除フラグを検証する."""

    def test_removed_default_false(self) -> None:
        unit = LineUnit(line_number=1, original="SELECT *", indent=0, content="SELECT *")
        assert unit.removed is False

    def test_set_removed(self) -> None:
        unit = LineUnit(line_number=1, original="SELECT *", indent=0, content="SELECT *")
        unit.removed = True
        assert unit.removed is True
