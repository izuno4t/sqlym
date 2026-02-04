"""例外クラスのテスト."""

import pytest

from sqly.exceptions import MappingError, SqlFileNotFoundError, SqlParseError, SqlyError


class TestExceptionHierarchy:
    """例外クラスの継承関係を検証する."""

    def test_sqly_error_is_exception(self) -> None:
        assert issubclass(SqlyError, Exception)

    def test_sql_parse_error_is_sqly_error(self) -> None:
        assert issubclass(SqlParseError, SqlyError)

    def test_mapping_error_is_sqly_error(self) -> None:
        assert issubclass(MappingError, SqlyError)

    def test_sql_file_not_found_error_is_sqly_error(self) -> None:
        assert issubclass(SqlFileNotFoundError, SqlyError)


class TestExceptionCatch:
    """基底例外で子例外をキャッチできることを検証する."""

    def test_catch_sql_parse_error_as_sqly_error(self) -> None:
        with pytest.raises(SqlyError):
            raise SqlParseError("parse failed")

    def test_catch_mapping_error_as_sqly_error(self) -> None:
        with pytest.raises(SqlyError):
            raise MappingError("mapping failed")

    def test_catch_sql_file_not_found_error_as_sqly_error(self) -> None:
        with pytest.raises(SqlyError):
            raise SqlFileNotFoundError("file not found")


class TestExceptionMessage:
    """例外メッセージが保持されることを検証する."""

    def test_sqly_error_message(self) -> None:
        err = SqlyError("test message")
        assert str(err) == "test message"

    def test_sql_parse_error_message(self) -> None:
        err = SqlParseError("parse failed")
        assert str(err) == "parse failed"
