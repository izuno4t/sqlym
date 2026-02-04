"""pytest 共通設定: DB テスト基盤."""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

import pytest

# --- 接続 URL ---
POSTGRESQL_URL = os.environ.get(
    "SQLY_TEST_POSTGRESQL_URL",
    "host=localhost port=5432 dbname=sqly_test user=sqly password=sqly_test_pass",
)
MYSQL_URL = os.environ.get("SQLY_TEST_MYSQL_URL", "")
ORACLE_DSN = os.environ.get("SQLY_TEST_ORACLE_DSN", "localhost:1521/XEPDB1")

# --- MySQL 接続パラメータのデフォルト ---
MYSQL_DEFAULTS: dict[str, Any] = {
    "host": "localhost",
    "port": 3306,
    "database": "sqly_test",
    "user": "sqly",
    "password": "sqly_test_pass",
}


def _can_connect_postgresql() -> bool:
    """PostgreSQL に接続可能か判定する."""
    try:
        import psycopg

        conn = psycopg.connect(POSTGRESQL_URL, connect_timeout=3)
        conn.close()
    except Exception:
        return False
    return True


def _can_connect_oracle() -> bool:
    """Oracle に接続可能か判定する."""
    try:
        import oracledb

        conn = oracledb.connect(user="sqly", password="sqly_test_pass", dsn=ORACLE_DSN)
        conn.close()
    except Exception:
        return False
    return True


def _can_connect_mysql() -> bool:
    """MySQL に接続可能か判定する."""
    try:
        import pymysql

        params = _parse_mysql_url()
        conn = pymysql.connect(**params, connect_timeout=3)
        conn.close()
    except Exception:
        return False
    return True


def _parse_mysql_url() -> dict[str, Any]:
    """環境変数または既定値から MySQL 接続パラメータを構築する."""
    if MYSQL_URL:
        # 簡易パース: mysql://user:pass@host:port/db
        from urllib.parse import urlparse

        parsed = urlparse(MYSQL_URL)
        return {
            "host": parsed.hostname or MYSQL_DEFAULTS["host"],
            "port": parsed.port or MYSQL_DEFAULTS["port"],
            "database": (parsed.path or "/sqly_test").lstrip("/"),
            "user": parsed.username or MYSQL_DEFAULTS["user"],
            "password": parsed.password or MYSQL_DEFAULTS["password"],
        }
    return dict(MYSQL_DEFAULTS)


# --- DB 接続可否キャッシュ ---
_pg_available: bool | None = None
_mysql_available: bool | None = None
_oracle_available: bool | None = None


def _is_pg_available() -> bool:
    global _pg_available
    if _pg_available is None:
        _pg_available = _can_connect_postgresql()
    return _pg_available


def _is_mysql_available() -> bool:
    global _mysql_available
    if _mysql_available is None:
        _mysql_available = _can_connect_mysql()
    return _mysql_available


def _is_oracle_available() -> bool:
    global _oracle_available
    if _oracle_available is None:
        _oracle_available = _can_connect_oracle()
    return _oracle_available


# --- マーカーによる自動スキップ ---
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """DB マーカー付きテストを接続不可時に自動スキップする."""
    for item in items:
        if "postgresql" in item.keywords and not _is_pg_available():
            item.add_marker(pytest.mark.skip(reason="PostgreSQL is not available"))
        if "mysql" in item.keywords and not _is_mysql_available():
            item.add_marker(pytest.mark.skip(reason="MySQL is not available"))
        if "oracle" in item.keywords and not _is_oracle_available():
            item.add_marker(pytest.mark.skip(reason="Oracle is not available"))


# --- DB fixture ---
@pytest.fixture
def pg_conn() -> Generator[Any, None, None]:
    """PostgreSQL 接続 fixture."""
    import psycopg
    from psycopg.rows import dict_row

    conn = psycopg.connect(POSTGRESQL_URL, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def mysql_conn() -> Generator[Any, None, None]:
    """MySQL 接続 fixture."""
    import pymysql
    import pymysql.cursors

    params = _parse_mysql_url()
    conn = pymysql.connect(**params, cursorclass=pymysql.cursors.DictCursor)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def oracle_conn() -> Generator[Any, None, None]:
    """Oracle 接続 fixture."""
    import oracledb

    conn = oracledb.connect(user="sqly", password="sqly_test_pass", dsn=ORACLE_DSN)
    try:
        yield conn
    finally:
        conn.close()
