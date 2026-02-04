"""RowMapper Protocol と ManualMapper のテスト."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqly.mapper.protocol import RowMapper


@dataclass
class User:
    """テスト用エンティティ."""

    id: int
    name: str


class TestRowMapperProtocol:
    """RowMapper Protocol の検証."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """RowMapper は runtime_checkable である."""

        class MyMapper:
            def map_row(self, row: dict[str, Any]) -> User:
                return User(id=row["id"], name=row["name"])

            def map_rows(self, rows: list[dict[str, Any]]) -> list[User]:
                return [self.map_row(r) for r in rows]

        assert isinstance(MyMapper(), RowMapper)

    def test_missing_map_row_not_instance(self) -> None:
        """map_row がないクラスは RowMapper ではない."""

        class NotMapper:
            def map_rows(self, rows: list[dict[str, Any]]) -> list[User]:
                return []

        assert not isinstance(NotMapper(), RowMapper)

    def test_missing_map_rows_not_instance(self) -> None:
        """map_rows がないクラスは RowMapper ではない."""

        class NotMapper:
            def map_row(self, row: dict[str, Any]) -> User:
                return User(id=0, name="")

        assert not isinstance(NotMapper(), RowMapper)

    def test_custom_mapper_map_row(self) -> None:
        """カスタムマッパーの map_row が正しく動作する."""

        class MyMapper:
            def map_row(self, row: dict[str, Any]) -> User:
                return User(id=row["id"], name=row["name"])

            def map_rows(self, rows: list[dict[str, Any]]) -> list[User]:
                return [self.map_row(r) for r in rows]

        mapper: RowMapper[User] = MyMapper()
        user = mapper.map_row({"id": 1, "name": "Alice"})
        assert user == User(id=1, name="Alice")

    def test_custom_mapper_map_rows(self) -> None:
        """カスタムマッパーの map_rows が正しく動作する."""

        class MyMapper:
            def map_row(self, row: dict[str, Any]) -> User:
                return User(id=row["id"], name=row["name"])

            def map_rows(self, rows: list[dict[str, Any]]) -> list[User]:
                return [self.map_row(r) for r in rows]

        mapper: RowMapper[User] = MyMapper()
        users = mapper.map_rows(
            [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ]
        )
        assert users == [User(id=1, name="Alice"), User(id=2, name="Bob")]


class TestManualMapper:
    """ManualMapper の検証."""

    def test_map_row_with_function(self) -> None:
        """関数を渡して map_row が動作する."""
        from sqly.mapper import ManualMapper

        def to_user(row: dict[str, Any]) -> User:
            return User(id=row["id"], name=row["name"])

        mapper = ManualMapper(to_user)
        user = mapper.map_row({"id": 1, "name": "Alice"})
        assert user == User(id=1, name="Alice")

    def test_map_row_with_lambda(self) -> None:
        """Lambda を渡して map_row が動作する."""
        from sqly.mapper import ManualMapper

        mapper = ManualMapper(lambda row: User(id=row["id"], name=row["name"]))
        user = mapper.map_row({"id": 1, "name": "Alice"})
        assert user == User(id=1, name="Alice")

    def test_map_rows(self) -> None:
        """map_rows で複数行を変換する."""
        from sqly.mapper import ManualMapper

        mapper = ManualMapper(lambda row: User(id=row["id"], name=row["name"]))
        users = mapper.map_rows(
            [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ]
        )
        assert users == [User(id=1, name="Alice"), User(id=2, name="Bob")]

    def test_map_rows_empty(self) -> None:
        """map_rows に空リストを渡すと空リストを返す."""
        from sqly.mapper import ManualMapper

        mapper = ManualMapper(lambda row: User(id=row["id"], name=row["name"]))
        assert mapper.map_rows([]) == []

    def test_satisfies_row_mapper_protocol(self) -> None:
        """ManualMapper は RowMapper プロトコルを満たす."""
        from sqly.mapper import ManualMapper

        mapper = ManualMapper(lambda row: row)
        assert isinstance(mapper, RowMapper)

    def test_complex_mapping_logic(self) -> None:
        """複雑な変換ロジックを持つ関数で動作する."""
        from sqly.mapper import ManualMapper

        def complex_mapper(row: dict[str, Any]) -> User:
            return User(
                id=row["EMP_ID"],
                name=f"{row['LAST_NAME']} {row['FIRST_NAME']}",
            )

        mapper = ManualMapper(complex_mapper)
        user = mapper.map_row(
            {
                "EMP_ID": 42,
                "LAST_NAME": "田中",
                "FIRST_NAME": "太郎",
            }
        )
        assert user == User(id=42, name="田中 太郎")
