"""インクルードディレクティブ（%include）のテスト."""

import tempfile
from pathlib import Path

import pytest

from sqlym.exceptions import SqlFileNotFoundError, SqlParseError
from sqlym.parser.tokenizer import parse_includes
from sqlym.parser.twoway import TwoWaySQLParser


class TestParseIncludes:
    """インクルードディレクティブパースのテスト."""

    def test_comment_style_include(self) -> None:
        """/* %include "path" */ 形式."""
        line = '/* %include "common/where.sql" */'
        includes = parse_includes(line)
        assert len(includes) == 1
        assert includes[0].path == "common/where.sql"

    def test_line_comment_style_include(self) -> None:
        """-- %include "path" 形式."""
        line = '-- %include "common/where.sql"'
        includes = parse_includes(line)
        assert len(includes) == 1
        assert includes[0].path == "common/where.sql"

    def test_single_quote_path(self) -> None:
        """シングルクォートのパス."""
        line = "/* %include 'common/where.sql' */"
        includes = parse_includes(line)
        assert len(includes) == 1
        assert includes[0].path == "common/where.sql"

    def test_multiple_includes(self) -> None:
        """複数のインクルード."""
        line = '/* %include "a.sql" */ AND /* %include "b.sql" */'
        includes = parse_includes(line)
        assert len(includes) == 2
        assert includes[0].path == "a.sql"
        assert includes[1].path == "b.sql"

    def test_no_includes(self) -> None:
        """インクルードなし."""
        line = "SELECT * FROM users"
        includes = parse_includes(line)
        assert len(includes) == 0


class TestIncludeExpansion:
    """インクルード展開のテスト."""

    def test_simple_include(self) -> None:
        """単純なインクルード."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            # インクルードファイルを作成
            (base_path / "fragment.sql").write_text("id = /* id */1")

            sql = 'SELECT * FROM users WHERE /* %include "fragment.sql" */'
            parser = TwoWaySQLParser(sql, base_path=base_path)
            result = parser.parse({"id": 42})

            assert "id = ?" in result.sql
            assert result.params == [42]

    def test_nested_include(self) -> None:
        """ネストされたインクルード."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            # ネストされたインクルードファイルを作成
            (base_path / "inner.sql").write_text("name = /* name */'default'")
            (base_path / "outer.sql").write_text(
                'id = /* id */1 AND /* %include "inner.sql" */'
            )

            sql = 'SELECT * FROM users WHERE /* %include "outer.sql" */'
            parser = TwoWaySQLParser(sql, base_path=base_path)
            result = parser.parse({"id": 10, "name": "John"})

            assert "id = ?" in result.sql
            assert "name = ?" in result.sql
            assert result.params == [10, "John"]

    def test_include_in_subdirectory(self) -> None:
        """サブディレクトリからのインクルード."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            subdir = base_path / "fragments"
            subdir.mkdir()
            (subdir / "condition.sql").write_text("active = 1")

            sql = 'SELECT * FROM users WHERE /* %include "fragments/condition.sql" */'
            parser = TwoWaySQLParser(sql, base_path=base_path)
            result = parser.parse({})

            assert "active = 1" in result.sql

    def test_include_without_base_path(self) -> None:
        """base_path なしではインクルードが無効."""
        sql = 'SELECT * FROM users WHERE /* %include "fragment.sql" */'
        parser = TwoWaySQLParser(sql)  # base_path なし
        result = parser.parse({})

        # インクルードディレクティブがそのまま残る
        assert '%include "fragment.sql"' in result.sql

    def test_multiline_include(self) -> None:
        """複数行のインクルード."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "multiline.sql").write_text(
                "id = /* id */1\n    AND name = /* name */'default'"
            )

            sql = 'SELECT * FROM users WHERE /* %include "multiline.sql" */'
            parser = TwoWaySQLParser(sql, base_path=base_path)
            result = parser.parse({"id": 1, "name": "Test"})

            assert "id = ?" in result.sql
            assert "name = ?" in result.sql


class TestIncludeErrors:
    """インクルードエラーのテスト."""

    def test_file_not_found(self) -> None:
        """インクルードファイルが見つからない."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            sql = '/* %include "nonexistent.sql" */'
            parser = TwoWaySQLParser(sql, base_path=base_path)

            with pytest.raises(SqlFileNotFoundError):
                parser.parse({})

    def test_circular_include_direct(self) -> None:
        """直接的な循環インクルード."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            # a.sql が自分自身をインクルード
            (base_path / "a.sql").write_text('/* %include "a.sql" */')

            sql = '/* %include "a.sql" */'
            parser = TwoWaySQLParser(sql, base_path=base_path)

            with pytest.raises(SqlParseError):
                parser.parse({})

    def test_circular_include_indirect(self) -> None:
        """間接的な循環インクルード."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            # a.sql → b.sql → a.sql
            (base_path / "a.sql").write_text('/* %include "b.sql" */')
            (base_path / "b.sql").write_text('/* %include "a.sql" */')

            sql = '/* %include "a.sql" */'
            parser = TwoWaySQLParser(sql, base_path=base_path)

            with pytest.raises(SqlParseError):
                parser.parse({})


class TestIncludeWithDirectives:
    """インクルードと他のディレクティブの組み合わせテスト."""

    def test_include_with_block_directive(self) -> None:
        """インクルードとブロックディレクティブ."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "condition.sql").write_text("status = /* status */'active'")

            sql = """\
SELECT *
FROM users
-- %IF include_condition
WHERE /* %include "condition.sql" */
-- %END"""
            parser = TwoWaySQLParser(sql, base_path=base_path)

            result = parser.parse({"include_condition": True, "status": "pending"})
            assert "status = ?" in result.sql

            result2 = parser.parse({"include_condition": False, "status": "pending"})
            assert "WHERE" not in result2.sql
