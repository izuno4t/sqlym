"""Sqlym クラスのテスト."""

from __future__ import annotations

import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sqlym import Dialect, Sqlym


@dataclass
class User:
    """テスト用ユーザーエンティティ."""

    id: int
    name: str
    status: str | None = None


class TestSqlymInit:
    """Sqlym.__init__ のテスト."""

    def test_init_with_defaults(self) -> None:
        """デフォルト値で初期化できる."""
        conn = MagicMock()
        db = Sqlym(conn)
        assert db._connection is conn
        assert db._auto_commit is False

    def test_init_with_sql_dir(self) -> None:
        """sql_dir を指定できる."""
        conn = MagicMock()
        db = Sqlym(conn, sql_dir="custom/sql")
        assert db._loader.base_path == Path("custom/sql")

    def test_init_with_dialect(self) -> None:
        """Dialect を指定できる."""
        conn = MagicMock()
        db = Sqlym(conn, dialect=Dialect.POSTGRESQL)
        assert db._dialect == Dialect.POSTGRESQL

    def test_init_with_auto_commit(self) -> None:
        """auto_commit を指定できる."""
        conn = MagicMock()
        db = Sqlym(conn, auto_commit=True)
        assert db._auto_commit is True


class TestSqlymDialectDetection:
    """Dialect 自動検出のテスト."""

    def test_detect_sqlite(self) -> None:
        """sqlite3 connection から SQLITE を検出."""
        with sqlite3.connect(":memory:") as conn:
            db = Sqlym(conn)
            assert db._dialect == Dialect.SQLITE

    def test_detect_postgresql(self) -> None:
        """Psycopg connection から POSTGRESQL を検出."""
        conn = MagicMock()
        conn.__class__.__module__ = "psycopg.connection"
        db = Sqlym(conn)
        assert db._dialect == Dialect.POSTGRESQL

    def test_detect_mysql(self) -> None:
        """Pymysql connection から MYSQL を検出."""
        conn = MagicMock()
        conn.__class__.__module__ = "pymysql.connections"
        db = Sqlym(conn)
        assert db._dialect == Dialect.MYSQL

    def test_detect_oracle(self) -> None:
        """Oracledb connection から ORACLE を検出."""
        conn = MagicMock()
        conn.__class__.__module__ = "oracledb.connection"
        db = Sqlym(conn)
        assert db._dialect == Dialect.ORACLE

    def test_detect_unknown(self) -> None:
        """不明な connection の場合は None."""
        conn = MagicMock()
        conn.__class__.__module__ = "unknown.driver"
        db = Sqlym(conn)
        assert db._dialect is None


class TestSqlymCommitRollback:
    """commit/rollback のテスト."""

    def test_commit_delegates_to_connection(self) -> None:
        """commit() は connection.commit() を呼ぶ."""
        conn = MagicMock()
        db = Sqlym(conn)
        db.commit()
        conn.commit.assert_called_once()

    def test_rollback_delegates_to_connection(self) -> None:
        """rollback() は connection.rollback() を呼ぶ."""
        conn = MagicMock()
        db = Sqlym(conn)
        db.rollback()
        conn.rollback.assert_called_once()


class TestSqlymContextManager:
    """コンテキストマネージャのテスト."""

    def test_enter_delegates_to_connection(self) -> None:
        """__enter__ は connection.__enter__ を呼ぶ."""
        conn = MagicMock()
        db = Sqlym(conn)
        result = db.__enter__()
        conn.__enter__.assert_called_once()
        assert result is db

    def test_exit_delegates_to_connection(self) -> None:
        """__exit__ は connection.__exit__ を呼ぶ."""
        conn = MagicMock()
        conn.__exit__.return_value = None
        db = Sqlym(conn)
        db.__exit__(None, None, None)
        conn.__exit__.assert_called_once_with(None, None, None)

    def test_with_statement(self) -> None:
        """With 文で使用できる."""
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.__exit__.return_value = None
        with Sqlym(conn) as db:
            assert isinstance(db, Sqlym)
        conn.__enter__.assert_called_once()
        conn.__exit__.assert_called_once()


class TestSqlymIntegration:
    """Sqlym 統合テスト（SQLite）."""

    @pytest.fixture
    def sql_dir(self) -> Path:
        """テスト用 SQL ディレクトリを作成."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sql_path = Path(tmpdir)
            users_dir = sql_path / "users"
            users_dir.mkdir()

            # find.sql
            (users_dir / "find.sql").write_text(
                """\
SELECT id, name, status
FROM users
WHERE status = /* $status */'active'
"""
            )

            # find_by_id.sql
            (users_dir / "find_by_id.sql").write_text(
                """\
SELECT id, name, status
FROM users
WHERE id = /* id */0
"""
            )

            # insert.sql
            (users_dir / "insert.sql").write_text(
                """\
INSERT INTO users (id, name, status)
VALUES (/* id */0, /* name */'', /* status */'')
"""
            )

            # update.sql
            (users_dir / "update.sql").write_text(
                """\
UPDATE users
SET name = /* name */''
WHERE id = /* id */0
"""
            )

            # delete.sql
            (users_dir / "delete.sql").write_text(
                """\
DELETE FROM users
WHERE id = /* id */0
"""
            )

            yield sql_path

    @pytest.fixture
    def db(self, sql_dir: Path) -> Sqlym:
        """テスト用 Sqlym インスタンスを作成."""
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT
            )
            """
        )
        conn.execute("INSERT INTO users VALUES (1, 'Alice', 'active')")
        conn.execute("INSERT INTO users VALUES (2, 'Bob', 'inactive')")
        conn.execute("INSERT INTO users VALUES (3, 'Charlie', 'active')")
        conn.commit()
        return Sqlym(conn, sql_dir=sql_dir)

    def test_query(self, db: Sqlym) -> None:
        """query() で複数行を取得できる."""
        users = db.query(User, "users/find.sql", {"status": "active"})
        assert len(users) == 2
        assert all(isinstance(u, User) for u in users)
        assert users[0].name == "Alice"
        assert users[1].name == "Charlie"

    def test_query_no_results(self, db: Sqlym) -> None:
        """query() で結果がない場合は空リストを返す."""
        users = db.query(User, "users/find.sql", {"status": "unknown"})
        assert users == []

    def test_query_with_line_removal(self, db: Sqlym) -> None:
        """query() で $param が None なら行削除される."""
        users = db.query(User, "users/find.sql", {"status": None})
        assert len(users) == 3  # WHERE 条件なし → 全件取得

    def test_query_one(self, db: Sqlym) -> None:
        """query_one() で1行を取得できる."""
        user = db.query_one(User, "users/find_by_id.sql", {"id": 1})
        assert user is not None
        assert user.id == 1
        assert user.name == "Alice"

    def test_query_one_no_result(self, db: Sqlym) -> None:
        """query_one() で結果がない場合は None を返す."""
        user = db.query_one(User, "users/find_by_id.sql", {"id": 999})
        assert user is None

    def test_execute_insert(self, db: Sqlym) -> None:
        """execute() で INSERT できる."""
        affected = db.execute(
            "users/insert.sql",
            {"id": 4, "name": "David", "status": "active"},
        )
        assert affected == 1
        db.commit()
        user = db.query_one(User, "users/find_by_id.sql", {"id": 4})
        assert user is not None
        assert user.name == "David"

    def test_execute_update(self, db: Sqlym) -> None:
        """execute() で UPDATE できる."""
        affected = db.execute("users/update.sql", {"id": 1, "name": "Alice Updated"})
        assert affected == 1
        db.commit()
        user = db.query_one(User, "users/find_by_id.sql", {"id": 1})
        assert user is not None
        assert user.name == "Alice Updated"

    def test_execute_delete(self, db: Sqlym) -> None:
        """execute() で DELETE できる."""
        affected = db.execute("users/delete.sql", {"id": 1})
        assert affected == 1
        db.commit()
        user = db.query_one(User, "users/find_by_id.sql", {"id": 1})
        assert user is None

    def test_insert_returns_lastrowid(self, db: Sqlym) -> None:
        """insert() で自動生成 ID を取得できる."""
        lastrowid = db.insert(
            "users/insert.sql",
            {"id": 4, "name": "David", "status": "active"},
        )
        assert lastrowid is not None
        db.commit()
        user = db.query_one(User, "users/find_by_id.sql", {"id": 4})
        assert user is not None
        assert user.name == "David"

    def test_insert_auto_commit(self, db: Sqlym, sql_dir: Path) -> None:
        """insert() で auto_commit が動作する."""
        db_auto = Sqlym(db._connection, sql_dir=sql_dir, auto_commit=True)
        lastrowid = db_auto.insert(
            "users/insert.sql",
            {"id": 5, "name": "Eve", "status": "active"},
        )
        assert lastrowid is not None
        user = db.query_one(User, "users/find_by_id.sql", {"id": 5})
        assert user is not None


class TestSqlymAutoCommit:
    """auto_commit モードのテスト."""

    def test_auto_commit_calls_commit(self, tmp_path: Path) -> None:
        """auto_commit=True の場合、execute() 後に commit が呼ばれる."""
        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()
        (sql_dir / "update.sql").write_text("UPDATE users SET name = /* name */''")

        conn = MagicMock()
        cursor = MagicMock()
        cursor.rowcount = 1
        conn.cursor.return_value = cursor

        db = Sqlym(conn, sql_dir=sql_dir, auto_commit=True)
        db.execute("update.sql", {"name": "test"})

        conn.commit.assert_called_once()

    def test_no_auto_commit_by_default(self, tmp_path: Path) -> None:
        """auto_commit=False（デフォルト）の場合、execute() 後に commit は呼ばれない."""
        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()
        (sql_dir / "update.sql").write_text("UPDATE users SET name = /* name */''")

        conn = MagicMock()
        cursor = MagicMock()
        cursor.rowcount = 1
        conn.cursor.return_value = cursor

        db = Sqlym(conn, sql_dir=sql_dir, auto_commit=False)
        db.execute("update.sql", {"name": "test"})

        conn.commit.assert_not_called()


class TestSqlymWithContextManager:
    """コンテキストマネージャを使った統合テスト."""

    def test_context_manager_commit_on_success(self, tmp_path: Path) -> None:
        """正常終了時は commit される."""
        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()
        (sql_dir / "insert.sql").write_text("INSERT INTO users VALUES (/* id */0, /* name */'')")

        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE users (id INTEGER, name TEXT)")

        with Sqlym(conn, sql_dir=sql_dir) as db:
            db.execute("insert.sql", {"id": 1, "name": "Test"})

        # コンテキスト終了後にデータが確定している
        cursor = conn.execute("SELECT * FROM users")
        rows = cursor.fetchall()
        assert len(rows) == 1

    def test_context_manager_rollback_on_exception(self, tmp_path: Path) -> None:
        """例外発生時は rollback される."""
        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()
        (sql_dir / "insert.sql").write_text("INSERT INTO users VALUES (/* id */0, /* name */'')")

        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE users (id INTEGER, name TEXT)")

        with pytest.raises(ValueError, match="Test error"), Sqlym(conn, sql_dir=sql_dir) as db:
            db.execute("insert.sql", {"id": 1, "name": "Test"})
            raise ValueError("Test error")

        # 例外によりロールバックされ、データは存在しない
        cursor = conn.execute("SELECT * FROM users")
        rows = cursor.fetchall()
        assert len(rows) == 0
