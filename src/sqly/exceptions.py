"""sqly例外クラス."""


class SqlyError(Exception):
    """sqlyの基底例外."""


class SqlParseError(SqlyError):
    """SQLパースエラー."""


class MappingError(SqlyError):
    """マッピングエラー."""


class SqlFileNotFoundError(SqlyError):
    """SQLファイルが見つからない."""
