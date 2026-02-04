"""PydanticMapper のテスト."""

from __future__ import annotations

import pytest

from sqly.mapper.protocol import RowMapper

pydantic = pytest.importorskip("pydantic")

from pydantic import BaseModel  # noqa: E402

from sqly.mapper.pydantic import PydanticMapper  # noqa: E402


class User(BaseModel):
    """テスト用基本モデル."""

    id: int
    name: str


class TestPydanticMapperBasic:
    """PydanticMapper の基本動作."""

    def test_map_row(self) -> None:
        """行辞書から Pydantic モデルインスタンスを生成する."""
        mapper = PydanticMapper(User)
        user = mapper.map_row({"id": 1, "name": "Alice"})
        assert user == User(id=1, name="Alice")

    def test_map_rows(self) -> None:
        """複数行を変換する."""
        mapper = PydanticMapper(User)
        users = mapper.map_rows(
            [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ]
        )
        assert users == [User(id=1, name="Alice"), User(id=2, name="Bob")]

    def test_map_rows_empty(self) -> None:
        """空リストを渡すと空リストを返す."""
        mapper = PydanticMapper(User)
        assert mapper.map_rows([]) == []

    def test_satisfies_row_mapper_protocol(self) -> None:
        """RowMapper プロトコルを満たす."""
        mapper = PydanticMapper(User)
        assert isinstance(mapper, RowMapper)


class TestPydanticMapperValidation:
    """Pydantic のバリデーションが動作する."""

    def test_type_coercion(self) -> None:
        """Pydantic の型変換が動作する."""
        mapper = PydanticMapper(User)
        user = mapper.map_row({"id": "42", "name": "Alice"})
        assert user.id == 42
        assert isinstance(user.id, int)

    def test_validation_error(self) -> None:
        """不正な値で ValidationError が発生する."""
        mapper = PydanticMapper(User)
        with pytest.raises(pydantic.ValidationError):
            mapper.map_row({"id": "not_a_number", "name": "Alice"})


class TestPydanticMapperOptionalFields:
    """オプショナルフィールドの扱い."""

    def test_optional_field_present(self) -> None:
        """デフォルト値付きフィールドが行にある場合."""

        class Employee(BaseModel):
            id: int
            name: str
            dept_id: int | None = None

        mapper = PydanticMapper(Employee)
        emp = mapper.map_row({"id": 1, "name": "Alice", "dept_id": 10})
        assert emp == Employee(id=1, name="Alice", dept_id=10)

    def test_optional_field_missing(self) -> None:
        """デフォルト値付きフィールドが行にない場合."""

        class Employee(BaseModel):
            id: int
            name: str
            dept_id: int | None = None

        mapper = PydanticMapper(Employee)
        emp = mapper.map_row({"id": 1, "name": "Alice"})
        assert emp == Employee(id=1, name="Alice", dept_id=None)


class TestPydanticMapperAliasFields:
    """Pydantic の alias フィールド対応."""

    def test_alias_field(self) -> None:
        """Field(alias=...) でカラム名マッピングが動作する."""
        from pydantic import Field

        class Employee(BaseModel):
            id: int = Field(alias="EMP_ID")
            name: str = Field(alias="EMP_NAME")

            model_config = {"populate_by_name": True}

        mapper = PydanticMapper(Employee)
        emp = mapper.map_row({"EMP_ID": 1, "EMP_NAME": "Alice"})
        assert emp.id == 1
        assert emp.name == "Alice"


class TestPydanticMapperNonBaseModel:
    """BaseModel でないクラスを渡した場合."""

    def test_non_base_model_raises_type_error(self) -> None:
        """BaseModel でないクラスを渡すと TypeError."""

        class NotPydantic:
            pass

        with pytest.raises(TypeError):
            PydanticMapper(NotPydantic)
