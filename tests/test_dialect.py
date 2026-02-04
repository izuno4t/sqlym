"""Dialect enum のテスト."""

from __future__ import annotations

from sqly import Dialect


class TestDialect:
    """Dialect enum の基本動作."""

    def test_sqlite_placeholder(self) -> None:
        """SQLITE のプレースホルダは '?'."""
        assert Dialect.SQLITE.placeholder == "?"

    def test_postgresql_placeholder(self) -> None:
        """POSTGRESQL のプレースホルダは '%s'."""
        assert Dialect.POSTGRESQL.placeholder == "%s"

    def test_mysql_placeholder(self) -> None:
        """MYSQL のプレースホルダは '%s'."""
        assert Dialect.MYSQL.placeholder == "%s"

    def test_oracle_placeholder(self) -> None:
        """ORACLE のプレースホルダは ':name'."""
        assert Dialect.ORACLE.placeholder == ":name"

    def test_all_have_placeholder(self) -> None:
        """全メンバーが placeholder プロパティを持つ."""
        for dialect in Dialect:
            assert isinstance(dialect.placeholder, str)
            assert len(dialect.placeholder) > 0

    def test_postgresql_and_mysql_same_placeholder(self) -> None:
        """POSTGRESQL と MYSQL は同じプレースホルダだが別メンバー."""
        assert Dialect.POSTGRESQL.placeholder == Dialect.MYSQL.placeholder
        assert Dialect.POSTGRESQL is not Dialect.MYSQL

    def test_all_members(self) -> None:
        """全メンバーが定義されている."""
        members = {d.name for d in Dialect}
        assert members == {"SQLITE", "POSTGRESQL", "MYSQL", "ORACLE"}
