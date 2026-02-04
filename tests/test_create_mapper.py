"""create_mapper ファクトリのテスト."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from sqly.mapper import RowMapper, create_mapper
from sqly.mapper.dataclass import DataclassMapper
from sqly.mapper.manual import ManualMapper


@dataclass
class User:
    """テスト用 dataclass."""

    id: int
    name: str


class TestAutoDetectDataclass:
    """Dataclass の自動検出."""

    def test_dataclass_returns_dataclass_mapper(self) -> None:
        """Dataclass を渡すと DataclassMapper を返す."""
        mapper = create_mapper(User)
        assert isinstance(mapper, DataclassMapper)

    def test_dataclass_mapper_works(self) -> None:
        """自動検出された DataclassMapper が動作する."""
        mapper = create_mapper(User)
        user = mapper.map_row({"id": 1, "name": "Alice"})
        assert user == User(id=1, name="Alice")


class TestAutoDetectPydantic:
    """Pydantic BaseModel の自動検出."""

    def test_pydantic_returns_pydantic_mapper(self) -> None:
        """Pydantic BaseModel を渡すと PydanticMapper を返す."""
        pytest.importorskip("pydantic")
        from pydantic import BaseModel

        from sqly.mapper.pydantic import PydanticMapper

        class Employee(BaseModel):
            id: int
            name: str

        mapper = create_mapper(Employee)
        assert isinstance(mapper, PydanticMapper)

    def test_pydantic_mapper_works(self) -> None:
        """自動検出された PydanticMapper が動作する."""
        pytest.importorskip("pydantic")
        from pydantic import BaseModel

        class Employee(BaseModel):
            id: int
            name: str

        mapper = create_mapper(Employee)
        emp = mapper.map_row({"id": 1, "name": "Alice"})
        assert emp == Employee(id=1, name="Alice")


class TestExplicitCallable:
    """Callable を明示的に渡す場合."""

    def test_callable_returns_manual_mapper(self) -> None:
        """Callable を渡すと ManualMapper を返す."""
        mapper = create_mapper(
            User,
            mapper=lambda row: User(id=row["id"], name=row["name"]),
        )
        assert isinstance(mapper, ManualMapper)

    def test_callable_mapper_works(self) -> None:
        """Callable マッパーが動作する."""
        mapper = create_mapper(
            User,
            mapper=lambda row: User(id=row["uid"], name=row["uname"]),
        )
        user = mapper.map_row({"uid": 1, "uname": "Alice"})
        assert user == User(id=1, name="Alice")

    def test_function_returns_manual_mapper(self) -> None:
        """関数を渡すと ManualMapper を返す."""

        def to_user(row: dict[str, Any]) -> User:
            return User(id=row["id"], name=row["name"])

        mapper = create_mapper(User, mapper=to_user)
        assert isinstance(mapper, ManualMapper)


class TestExplicitRowMapper:
    """RowMapper インスタンスを明示的に渡す場合."""

    def test_row_mapper_returned_as_is(self) -> None:
        """RowMapper インスタンスはそのまま返す."""

        class MyMapper:
            def map_row(self, row: dict[str, Any]) -> User:
                return User(id=row["id"], name=row["name"])

            def map_rows(self, rows: list[dict[str, Any]]) -> list[User]:
                return [self.map_row(r) for r in rows]

        my_mapper = MyMapper()
        result = create_mapper(User, mapper=my_mapper)
        assert result is my_mapper

    def test_row_mapper_works(self) -> None:
        """明示的 RowMapper が動作する."""

        class MyMapper:
            def map_row(self, row: dict[str, Any]) -> User:
                return User(id=row["uid"], name=row["uname"])

            def map_rows(self, rows: list[dict[str, Any]]) -> list[User]:
                return [self.map_row(r) for r in rows]

        mapper = create_mapper(User, mapper=MyMapper())
        user = mapper.map_row({"uid": 1, "uname": "Alice"})
        assert user == User(id=1, name="Alice")


class TestUnsupportedClass:
    """サポートされないクラスの場合."""

    def test_plain_class_raises_type_error(self) -> None:
        """Dataclass でも BaseModel でもないクラスで TypeError."""

        class PlainClass:
            pass

        with pytest.raises(TypeError, match="Cannot create mapper"):
            create_mapper(PlainClass)


class TestSatisfiesProtocol:
    """返されるマッパーが RowMapper プロトコルを満たす."""

    def test_auto_dataclass_satisfies_protocol(self) -> None:
        """自動検出 DataclassMapper は RowMapper."""
        mapper = create_mapper(User)
        assert isinstance(mapper, RowMapper)

    def test_callable_satisfies_protocol(self) -> None:
        """ManualMapper は RowMapper."""
        mapper = create_mapper(
            User,
            mapper=lambda row: User(id=row["id"], name=row["name"]),
        )
        assert isinstance(mapper, RowMapper)
