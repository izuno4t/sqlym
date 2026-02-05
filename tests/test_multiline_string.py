"""複数行文字列リテラルの解析テスト."""

from sqlym.parser.twoway import TwoWaySQLParser


class TestMultilineStringLiteral:
    """複数行文字列リテラルの解析."""

    def test_multiline_string_basic(self) -> None:
        """複数行文字列リテラルが正しく解析される."""
        sql = """\
INSERT INTO people (id, name, address)
VALUES (
    /* id */'0001',
    /* name */'Yoko',
    /* address */'Ocean-Child''s House
123-4
Tokyo
Japan'
)"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({
            "id": "0002",
            "name": "John",
            "address": "123 Main St\nNew York\nUSA",
        })
        assert "?" in result.sql
        assert result.params == ["0002", "John", "123 Main St\nNew York\nUSA"]

    def test_multiline_string_with_removable(self) -> None:
        """$ 付き複数行文字列が None で行削除される."""
        sql = """\
INSERT INTO people (id, name, address)
VALUES (
    /* id */'0001',
    /* $name */'Yoko',
    /* $address */'Ocean-Child''s House
123-4
Tokyo
Japan'
)"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({
            "id": "0002",
            "name": None,
            "address": None,
        })
        # name と address が削除される
        assert "name" not in result.sql.lower() or "/* $name */" not in result.sql
        assert result.params == ["0002"]

    def test_multiline_string_preserves_content(self) -> None:
        """複数行文字列の内容が保持される."""
        sql = """\
SELECT * FROM logs
WHERE message = /* msg */'Error:
Line 1
Line 2'"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"msg": "Warning:\nFirst\nSecond"})
        assert "message = ?" in result.sql
        assert result.params == ["Warning:\nFirst\nSecond"]

    def test_string_closed_detection(self) -> None:
        """文字列クローズ判定."""
        assert TwoWaySQLParser._is_string_closed("SELECT * FROM t") is True
        assert TwoWaySQLParser._is_string_closed("'hello'") is True
        assert TwoWaySQLParser._is_string_closed("'hello") is False
        assert TwoWaySQLParser._is_string_closed("'hello''world'") is True
        assert TwoWaySQLParser._is_string_closed("'hello''") is False
        assert TwoWaySQLParser._is_string_closed('"hello"') is True
        assert TwoWaySQLParser._is_string_closed('"hello') is False

    def test_multiline_with_escaped_quotes(self) -> None:
        """エスケープされた引用符を含む複数行文字列."""
        sql = """\
INSERT INTO t (msg)
VALUES (/* msg */'It''s a
multi-line
string')"""
        parser = TwoWaySQLParser(sql)
        result = parser.parse({"msg": "Hello\nWorld"})
        assert result.params == ["Hello\nWorld"]
