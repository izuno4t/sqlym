"""Column クラスと @entity デコレータのテスト."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from sqly.mapper.column import Column, entity


class TestColumn:
    """Column クラスの検証."""

    def test_column_name(self) -> None:
        """Column の name 属性."""
        col = Column("EMP_ID")
        assert col.name == "EMP_ID"

    def test_column_repr(self) -> None:
        """Column の repr."""
        col = Column("EMP_NAME")
        assert repr(col) == "Column('EMP_NAME')"


class TestEntityDecorator:
    """@entity デコレータの検証."""

    def test_entity_no_args(self) -> None:
        """引数なし @entity でデフォルト属性を付与."""

        @entity
        @dataclass
        class User:
            id: int
            name: str

        assert User.__column_map__ == {}
        assert User.__column_naming__ == "as_is"

    def test_entity_with_column_map(self) -> None:
        """Column_map を指定."""

        @entity(column_map={"id": "EMP_ID", "name": "EMP_NAME"})
        @dataclass
        class Employee:
            id: int
            name: str

        assert Employee.__column_map__ == {"id": "EMP_ID", "name": "EMP_NAME"}
        assert Employee.__column_naming__ == "as_is"

    def test_entity_with_naming(self) -> None:
        """Naming を指定."""

        @entity(naming="snake_to_camel")
        @dataclass
        class Employee:
            dept_id: int
            user_name: str

        assert Employee.__column_map__ == {}
        assert Employee.__column_naming__ == "snake_to_camel"

    def test_entity_with_both(self) -> None:
        """Column_map と naming を両方指定."""

        @entity(column_map={"id": "EMP_ID"}, naming="camel_to_snake")
        @dataclass
        class Employee:
            id: int
            name: str

        assert Employee.__column_map__ == {"id": "EMP_ID"}
        assert Employee.__column_naming__ == "camel_to_snake"

    def test_entity_preserves_class(self) -> None:
        """デコレータ適用後もクラスが正常に動作する."""

        @entity(column_map={"id": "USER_ID"})
        @dataclass
        class User:
            id: int
            name: str

        user = User(id=1, name="Alice")
        assert user.id == 1
        assert user.name == "Alice"

    def test_entity_class_identity(self) -> None:
        """デコレータは元のクラスを返す（ラッパーではない）."""

        @dataclass
        class Original:
            id: int

        decorated = entity(Original)
        assert decorated is Original


class TestColumnWithAnnotated:
    """Annotated[T, Column('X')] の使用検証."""

    def test_annotated_column_accessible(self) -> None:
        """Annotated メタデータから Column を取得できる."""
        from typing import get_args, get_origin

        @dataclass
        class Employee:
            id: Annotated[int, Column("EMP_ID")]
            name: Annotated[str, Column("EMP_NAME")]
            email: str

        # Annotated の型ヒントから Column を抽出できることを検証
        import typing

        type_hints = typing.get_type_hints(Employee, include_extras=True)

        # id フィールド
        id_hint = type_hints["id"]
        assert get_origin(id_hint) is Annotated
        id_args = get_args(id_hint)
        assert isinstance(id_args[1], Column)
        assert id_args[1].name == "EMP_ID"

        # name フィールド
        name_hint = type_hints["name"]
        name_args = get_args(name_hint)
        assert isinstance(name_args[1], Column)
        assert name_args[1].name == "EMP_NAME"

        # email フィールドには Column なし
        email_hint = type_hints["email"]
        assert get_origin(email_hint) is not Annotated
