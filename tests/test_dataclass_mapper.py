"""DataclassMapper のテスト."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import pytest

from sqly.mapper.column import Column, entity
from sqly.mapper.dataclass import DataclassMapper
from sqly.mapper.protocol import RowMapper


@dataclass
class User:
    """テスト用基本エンティティ."""

    id: int
    name: str


class TestDataclassMapperBasic:
    """DataclassMapper の基本動作."""

    def test_map_row(self) -> None:
        """行辞書から dataclass インスタンスを生成する."""
        mapper = DataclassMapper(User)
        user = mapper.map_row({"id": 1, "name": "Alice"})
        assert user == User(id=1, name="Alice")

    def test_map_rows(self) -> None:
        """複数行を変換する."""
        mapper = DataclassMapper(User)
        users = mapper.map_rows(
            [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ]
        )
        assert users == [User(id=1, name="Alice"), User(id=2, name="Bob")]

    def test_map_rows_empty(self) -> None:
        """空リストを渡すと空リストを返す."""
        mapper = DataclassMapper(User)
        assert mapper.map_rows([]) == []

    def test_satisfies_row_mapper_protocol(self) -> None:
        """RowMapper プロトコルを満たす."""
        mapper = DataclassMapper(User)
        assert isinstance(mapper, RowMapper)

    def test_non_dataclass_raises_type_error(self) -> None:
        """Dataclass でないクラスを渡すと TypeError."""

        class NotDataclass:
            pass

        with pytest.raises(TypeError):
            DataclassMapper(NotDataclass)


class TestAnnotatedColumn:
    """Annotated[T, Column('X')] によるマッピング."""

    def test_annotated_column_mapping(self) -> None:
        """Annotated で指定したカラム名でマッピングする."""

        @dataclass
        class Employee:
            id: Annotated[int, Column("EMP_ID")]
            name: Annotated[str, Column("EMP_NAME")]

        mapper = DataclassMapper(Employee)
        emp = mapper.map_row({"EMP_ID": 1, "EMP_NAME": "Alice"})
        assert emp == Employee(id=1, name="Alice")

    def test_mixed_annotated_and_plain(self) -> None:
        """Annotated と通常フィールドの混在."""

        @dataclass
        class Employee:
            id: Annotated[int, Column("EMP_ID")]
            name: str

        mapper = DataclassMapper(Employee)
        emp = mapper.map_row({"EMP_ID": 1, "name": "Alice"})
        assert emp == Employee(id=1, name="Alice")


class TestColumnMap:
    """@entity(column_map={...}) によるマッピング."""

    def test_column_map(self) -> None:
        """Column_map でフィールド名→カラム名を指定."""

        @entity(column_map={"id": "EMP_ID", "name": "EMP_NAME"})
        @dataclass
        class Employee:
            id: int
            name: str

        mapper = DataclassMapper(Employee)
        emp = mapper.map_row({"EMP_ID": 1, "EMP_NAME": "Alice"})
        assert emp == Employee(id=1, name="Alice")

    def test_partial_column_map(self) -> None:
        """Column_map で一部のフィールドのみ指定."""

        @entity(column_map={"id": "EMP_ID"})
        @dataclass
        class Employee:
            id: int
            name: str

        mapper = DataclassMapper(Employee)
        emp = mapper.map_row({"EMP_ID": 1, "name": "Alice"})
        assert emp == Employee(id=1, name="Alice")


class TestNaming:
    """@entity(naming=...) による命名規則変換."""

    def test_snake_to_camel(self) -> None:
        """Snake_case → camelCase 変換."""

        @entity(naming="snake_to_camel")
        @dataclass
        class Employee:
            dept_id: int
            user_name: str

        mapper = DataclassMapper(Employee)
        emp = mapper.map_row({"deptId": 10, "userName": "Alice"})
        assert emp == Employee(dept_id=10, user_name="Alice")

    def test_camel_to_snake(self) -> None:
        """CamelCase → snake_case 変換."""

        @entity(naming="camel_to_snake")
        @dataclass
        class Employee:
            deptId: int
            userName: str

        mapper = DataclassMapper(Employee)
        emp = mapper.map_row({"dept_id": 10, "user_name": "Alice"})
        assert emp == Employee(deptId=10, userName="Alice")

    def test_as_is(self) -> None:
        """As_is（デフォルト）はそのまま."""

        @entity(naming="as_is")
        @dataclass
        class Employee:
            dept_id: int

        mapper = DataclassMapper(Employee)
        emp = mapper.map_row({"dept_id": 10})
        assert emp == Employee(dept_id=10)


class TestNamingConversions:
    """命名規則変換関数の個別テスト."""

    def test_to_camel_basic(self) -> None:
        """基本の snake_to_camel."""
        assert DataclassMapper._to_camel("dept_id") == "deptId"

    def test_to_camel_multiple_underscores(self) -> None:
        """複数アンダースコアの snake_to_camel."""
        assert DataclassMapper._to_camel("first_name_last") == "firstNameLast"

    def test_to_camel_no_underscore(self) -> None:
        """アンダースコアなしの snake_to_camel."""
        assert DataclassMapper._to_camel("name") == "name"

    def test_to_snake_basic(self) -> None:
        """基本の camel_to_snake."""
        assert DataclassMapper._to_snake("deptId") == "dept_id"

    def test_to_snake_multiple_capitals(self) -> None:
        """複数大文字の camel_to_snake."""
        assert DataclassMapper._to_snake("firstNameLast") == "first_name_last"

    def test_to_snake_no_capitals(self) -> None:
        """大文字なしの camel_to_snake."""
        assert DataclassMapper._to_snake("name") == "name"


class TestMappingPriority:
    """マッピング優先順位の検証."""

    def test_annotated_overrides_column_map(self) -> None:
        """Annotated が column_map より優先される."""

        @entity(column_map={"id": "SHOULD_NOT_USE"})
        @dataclass
        class Employee:
            id: Annotated[int, Column("EMP_ID")]

        mapper = DataclassMapper(Employee)
        emp = mapper.map_row({"EMP_ID": 1})
        assert emp == Employee(id=1)

    def test_column_map_overrides_naming(self) -> None:
        """Column_map が naming より優先される."""

        @entity(column_map={"dept_id": "DEPT_CODE"}, naming="snake_to_camel")
        @dataclass
        class Employee:
            dept_id: int
            user_name: str

        mapper = DataclassMapper(Employee)
        emp = mapper.map_row({"DEPT_CODE": 10, "userName": "Alice"})
        assert emp == Employee(dept_id=10, user_name="Alice")


class TestFieldNameFallback:
    """カラム名が見つからない場合のフィールド名フォールバック."""

    def test_fallback_to_field_name(self) -> None:
        """マッピング先カラム名が行に無い場合、フィールド名で探す."""

        @entity(column_map={"id": "EMP_ID"})
        @dataclass
        class Employee:
            id: int
            name: str

        mapper = DataclassMapper(Employee)
        # id は EMP_ID にマッピングされているが、行には "id" しかない
        emp = mapper.map_row({"id": 1, "name": "Alice"})
        assert emp == Employee(id=1, name="Alice")


class TestMappingCache:
    """_mapping_cache のキャッシュ動作."""

    def test_cache_populated(self) -> None:
        """マッピング構築後にキャッシュに格納される."""
        DataclassMapper._mapping_cache.clear()

        @dataclass
        class CachedUser:
            id: int
            name: str

        DataclassMapper(CachedUser)
        assert CachedUser in DataclassMapper._mapping_cache

    def test_cache_reused(self) -> None:
        """同じクラスの2回目はキャッシュを使う."""
        DataclassMapper._mapping_cache.clear()

        @dataclass
        class CachedUser2:
            id: int
            name: str

        mapper1 = DataclassMapper(CachedUser2)
        mapper2 = DataclassMapper(CachedUser2)
        # 同じマッピング辞書オブジェクトを共有する
        assert mapper1._mapping is mapper2._mapping


class TestOptionalFields:
    """オプショナルフィールド（デフォルト値あり）の扱い."""

    def test_optional_field_present(self) -> None:
        """デフォルト値付きフィールドが行にある場合."""

        @dataclass
        class Employee:
            id: int
            name: str
            dept_id: int | None = None

        mapper = DataclassMapper(Employee)
        emp = mapper.map_row({"id": 1, "name": "Alice", "dept_id": 10})
        assert emp == Employee(id=1, name="Alice", dept_id=10)

    def test_optional_field_missing(self) -> None:
        """デフォルト値付きフィールドが行にない場合、デフォルトが使われる."""

        @dataclass
        class Employee:
            id: int
            name: str
            dept_id: int | None = None

        mapper = DataclassMapper(Employee)
        emp = mapper.map_row({"id": 1, "name": "Alice"})
        assert emp == Employee(id=1, name="Alice", dept_id=None)
