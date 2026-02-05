"""Dialect enum のテスト."""

from __future__ import annotations

from sqly import Dialect, escape_like


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

    def test_fullwidth_not_included(self) -> None:
        """全角 ％ ＿ はエスケープ対象外.

        Note:
            Oracle の LIKE ESCAPE 構文では、エスケープ文字の後には
            ``%`` または ``_`` のみ指定可能（ORA-01424）。
            全角文字は LIKE ワイルドカードではないためエスケープ不要。
        """
        for dialect in Dialect:
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


class TestLikeEscapeChar:
    """like_escape_char プロパティのテスト."""

    def test_default_escape_char(self) -> None:
        """全 Dialect でデフォルトエスケープ文字は '#'."""
        for dialect in Dialect:
            assert dialect.like_escape_char == "#"


class TestEscapeLike:
    """escape_like 関数のテスト."""

    def test_escape_percent(self) -> None:
        """% をエスケープする."""
        assert escape_like("10%off", Dialect.SQLITE) == "10#%off"

    def test_escape_underscore(self) -> None:
        """_ をエスケープする."""
        assert escape_like("file_name", Dialect.SQLITE) == "file#_name"

    def test_escape_hash(self) -> None:
        """# (エスケープ文字自体) をエスケープする."""
        assert escape_like("C#", Dialect.SQLITE) == "C##"

    def test_escape_multiple(self) -> None:
        """複数の特殊文字をエスケープする."""
        assert escape_like("10%_#", Dialect.SQLITE) == "10#%#_##"

    def test_no_escape_needed(self) -> None:
        """エスケープ不要な文字列はそのまま."""
        assert escape_like("hello", Dialect.SQLITE) == "hello"

    def test_empty_string(self) -> None:
        """空文字列はそのまま."""
        assert escape_like("", Dialect.SQLITE) == ""

    def test_fullwidth_no_escape(self) -> None:
        """全角 ％ ＿ はエスケープしない.

        Note:
            全角文字は SQL の LIKE ワイルドカードではないため、
            エスケープ不要。Oracle の LIKE ESCAPE 構文では
            エスケープ文字の後に全角文字を指定すると ORA-01424 エラー。
        """
        for dialect in Dialect:
            assert escape_like("100％達成", dialect) == "100％達成"
            assert escape_like("名前＿太郎", dialect) == "名前＿太郎"

    def test_custom_escape_char(self) -> None:
        """カスタムエスケープ文字を指定できる."""
        assert escape_like("10%off", Dialect.SQLITE, escape_char="\\") == "10\\%off"

    def test_custom_escape_char_itself(self) -> None:
        """カスタムエスケープ文字自体もエスケープ対象."""
        # # はデフォルトでエスケープ対象、\ でエスケープ
        assert escape_like("C#", Dialect.SQLITE, escape_char="\\") == "C\\#"

    def test_all_dialects_basic(self) -> None:
        """全 Dialect で基本動作を確認."""
        for dialect in Dialect:
            result = escape_like("test%value_name", dialect)
            assert "#%" in result
            assert "#_" in result
