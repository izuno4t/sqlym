"""補助関数のテスト."""

from sqlym.parser.tokenizer import tokenize
from sqlym.parser.twoway import TwoWaySQLParser


class TestConcatHelper:
    """%concat / %C 補助関数のテスト."""

    def test_concat_basic(self) -> None:
        """基本的な連結."""
        sql = "SELECT * FROM users WHERE name LIKE /* %concat('%', part, '%') */'%test%'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"part": "John"})
        assert "LIKE ?" in result.sql
        assert result.params == ["%John%"]

    def test_concat_short_form(self) -> None:
        """%C 短縮形."""
        sql = "SELECT * FROM users WHERE name LIKE /*%C '%' part '%' */'%test%'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"part": "Jane"})
        assert "LIKE ?" in result.sql
        assert result.params == ["%Jane%"]

    def test_concat_multiple_params(self) -> None:
        """複数パラメータの連結."""
        sql = "SELECT * FROM t WHERE col LIKE /* %concat(prefix, middle, suffix) */'test'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"prefix": "A", "middle": "B", "suffix": "C"})
        assert result.params == ["ABC"]

    def test_concat_with_none(self) -> None:
        """None パラメータは無視される."""
        sql = "SELECT * FROM t WHERE col LIKE /* %concat('%', part, '%') */'test'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"part": None})
        assert result.params == ["%%"]

    def test_concat_tokenizer(self) -> None:
        """Tokenizer が %concat を認識する."""
        tokens = tokenize("/* %concat('%', x, '%') */'test'")
        assert len(tokens) == 1
        assert tokens[0].helper_func == "concat"
        assert tokens[0].helper_args == ("'%'", "x", "'%'")


class TestLikeEscapeHelper:
    """%L 補助関数（LIKE エスケープ）のテスト."""

    def test_like_escape_basic(self) -> None:
        """基本的な LIKE エスケープ."""
        sql = "SELECT * FROM logs WHERE msg LIKE /*%L '%' keyword '%' */'%test%'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"keyword": "100%"})
        assert "LIKE ? escape '#'" in result.sql
        assert result.params == ["%100#%%"]

    def test_like_escape_underscore(self) -> None:
        """アンダースコアのエスケープ."""
        sql = "SELECT * FROM t WHERE name LIKE /*%L keyword */'test'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"keyword": "file_name"})
        assert result.params == ["file#_name"]

    def test_like_escape_both(self) -> None:
        """% と _ 両方のエスケープ."""
        sql = "SELECT * FROM t WHERE val LIKE /*%L '%' search '%' */'%x%'"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"search": "10%_done"})
        assert result.params == ["%10#%#_done%"]

    def test_like_escape_tokenizer(self) -> None:
        """Tokenizer が %L を認識する."""
        tokens = tokenize("/*%L '%' x '%' */'test'")
        assert len(tokens) == 1
        assert tokens[0].helper_func == "L"


class TestStrSqlHelper:
    """%STR / %SQL 補助関数（直接埋め込み）のテスト."""

    def test_str_embed(self) -> None:
        """%STR による直接埋め込み."""
        sql = "SELECT * FROM users ORDER BY /* %STR(order_col) */id"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"order_col": "name"})
        assert "ORDER BY name" in result.sql
        assert result.params == []

    def test_sql_embed(self) -> None:
        """%SQL による直接埋め込み."""
        sql = "SELECT * FROM /* %SQL(table_name) */users"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"table_name": "employees"})
        assert "FROM employees" in result.sql

    def test_str_with_none_uses_default(self) -> None:
        """None の場合はデフォルト値を使用."""
        sql = "SELECT * FROM users ORDER BY /* %STR(order_col) */id"
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"order_col": None})
        assert "ORDER BY id" in result.sql

    def test_str_tokenizer(self) -> None:
        """Tokenizer が %STR を認識する."""
        tokens = tokenize("/* %STR(col) */default")
        assert len(tokens) == 1
        assert tokens[0].helper_func == "STR"
        assert tokens[0].name == "col"

    def test_sql_tokenizer(self) -> None:
        """Tokenizer が %SQL を認識する."""
        tokens = tokenize("/* %SQL(tbl) */default")
        assert len(tokens) == 1
        assert tokens[0].helper_func == "SQL"
        assert tokens[0].name == "tbl"
