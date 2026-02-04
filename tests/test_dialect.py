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


class TestLikeEscapeChars:
    """like_escape_chars プロパティのテスト."""

    def test_base_chars_common(self) -> None:
        """全 Dialect で #, %, _ がエスケープ対象."""
        base = {"#", "%", "_"}
        for dialect in Dialect:
            assert base <= dialect.like_escape_chars

    def test_oracle_includes_fullwidth(self) -> None:
        """Oracle は全角 ％ ＿ もエスケープ対象."""
        chars = Dialect.ORACLE.like_escape_chars
        assert "％" in chars
        assert "＿" in chars

    def test_non_oracle_excludes_fullwidth(self) -> None:
        """Oracle 以外は全角文字を含まない."""
        for dialect in (Dialect.SQLITE, Dialect.POSTGRESQL, Dialect.MYSQL):
            assert "％" not in dialect.like_escape_chars
            assert "＿" not in dialect.like_escape_chars

    def test_returns_frozenset(self) -> None:
        """戻り値は frozenset."""
        for dialect in Dialect:
            assert isinstance(dialect.like_escape_chars, frozenset)


class TestInClauseLimit:
    """in_clause_limit プロパティのテスト."""

    def test_oracle_limit_1000(self) -> None:
        """Oracle の IN 句上限は 1000."""
        assert Dialect.ORACLE.in_clause_limit == 1000

    def test_others_no_limit(self) -> None:
        """Oracle 以外は上限なし (None)."""
        assert Dialect.SQLITE.in_clause_limit is None
        assert Dialect.POSTGRESQL.in_clause_limit is None
        assert Dialect.MYSQL.in_clause_limit is None


class TestBackslashIsEscape:
    """backslash_is_escape プロパティのテスト."""

    def test_mysql_true(self) -> None:
        """MySQL はバックスラッシュがエスケープ文字."""
        assert Dialect.MYSQL.backslash_is_escape is True

    def test_postgresql_true(self) -> None:
        """PostgreSQL はバックスラッシュがエスケープ文字."""
        assert Dialect.POSTGRESQL.backslash_is_escape is True

    def test_sqlite_false(self) -> None:
        """SQLite はバックスラッシュがエスケープ文字ではない."""
        assert Dialect.SQLITE.backslash_is_escape is False

    def test_oracle_false(self) -> None:
        """Oracle はバックスラッシュがエスケープ文字ではない."""
        assert Dialect.ORACLE.backslash_is_escape is False
