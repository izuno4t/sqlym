"""PostgreSQL 統合テスト: パース → DB実行 → マッピングの一連フロー検証."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import pytest

from sqly import Column, Dialect, ParsedSQL, SqlLoader, create_mapper, parse_sql
from sqly.mapper.column import entity

pytestmark = pytest.mark.postgresql


@dataclass
class Employee:
    """テスト用エンティティ."""

    id: int
    name: str
    dept_id: int | None = None


@dataclass
class AnnotatedEmployee:
    """Annotated カラムマッピング付きエンティティ."""

    id: Annotated[int, Column("emp_id")]
    name: Annotated[str, Column("emp_name")]
    dept_id: Annotated[int | None, Column("department_id")] = None


@entity(naming="snake_to_camel")
@dataclass
class CamelEmployee:
    """CamelCase カラム名のエンティティ."""

    emp_id: int
    emp_name: str


@pytest.fixture
def db(pg_conn: Any) -> Any:
    """テスト用テーブルを作成し、テストデータを投入する."""
    cur = pg_conn.cursor()
    cur.execute("DROP TABLE IF EXISTS employees")
    cur.execute("""
        CREATE TABLE employees (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            dept_id INTEGER
        )
    """)
    cur.executemany(
        "INSERT INTO employees (id, name, dept_id) VALUES (%s, %s, %s)",
        [
            (1, "Alice", 10),
            (2, "Bob", 20),
            (3, "Charlie", 10),
            (4, "Diana", None),
        ],
    )
    pg_conn.commit()
    yield pg_conn
    cur.execute("DROP TABLE IF EXISTS employees")
    pg_conn.commit()


@pytest.fixture
def db_aliased(pg_conn: Any) -> Any:
    """エイリアス付きカラム名の DB を作成する."""
    cur = pg_conn.cursor()
    cur.execute("DROP TABLE IF EXISTS employees_aliased")
    cur.execute("""
        CREATE TABLE employees_aliased (
            emp_id SERIAL PRIMARY KEY,
            emp_name TEXT NOT NULL,
            department_id INTEGER
        )
    """)
    cur.executemany(
        "INSERT INTO employees_aliased (emp_id, emp_name, department_id) VALUES (%s, %s, %s)",
        [
            (1, "Alice", 10),
            (2, "Bob", 20),
        ],
    )
    pg_conn.commit()
    yield pg_conn
    cur.execute("DROP TABLE IF EXISTS employees_aliased")
    pg_conn.commit()


def _fetch_all(conn: Any, result: ParsedSQL) -> list[dict]:
    """ParsedSQL を実行し、行辞書のリストを返すヘルパー."""
    cur = conn.cursor()
    cur.execute(result.sql, result.params)
    return [dict(row) for row in cur.fetchall()]


class TestBasicFlow:
    """基本フロー: パース → 実行 → マッピング."""

    def test_select_all(self, db: Any) -> None:
        """全件取得."""
        sql = "SELECT * FROM employees"
        result = parse_sql(sql, {}, dialect=Dialect.POSTGRESQL)
        rows = _fetch_all(db, result)
        mapper = create_mapper(Employee)
        employees = mapper.map_rows(rows)
        assert len(employees) == 4
        assert employees[0] == Employee(id=1, name="Alice", dept_id=10)

    def test_select_with_param(self, db: Any) -> None:
        """パラメータ付き検索."""
        sql = "SELECT * FROM employees WHERE id = /* $id */999"
        result = parse_sql(sql, {"id": 2}, dialect=Dialect.POSTGRESQL)
        rows = _fetch_all(db, result)
        mapper = create_mapper(Employee)
        employees = mapper.map_rows(rows)
        assert len(employees) == 1
        assert employees[0] == Employee(id=2, name="Bob", dept_id=20)


class TestLineRemoval:
    """行削除 → 実行 → マッピング."""

    def test_none_param_removes_condition(self, db: Any) -> None:
        """None パラメータで条件行が削除され、全件返る."""
        sql = "SELECT * FROM employees\nWHERE\n    name = /* $name */'default'"
        result = parse_sql(sql, {"name": None}, dialect=Dialect.POSTGRESQL)
        assert "WHERE" not in result.sql
        rows = _fetch_all(db, result)
        assert len(rows) == 4

    def test_partial_removal(self, db: Any) -> None:
        """一部条件のみ削除、残った条件でフィルタリング."""
        sql = (
            "SELECT * FROM employees\n"
            "WHERE\n"
            "    dept_id = /* $dept_id */999\n"
            "    AND name = /* $name */'default'"
        )
        result = parse_sql(sql, {"dept_id": 10, "name": None}, dialect=Dialect.POSTGRESQL)
        rows = _fetch_all(db, result)
        mapper = create_mapper(Employee)
        employees = mapper.map_rows(rows)
        assert len(employees) == 2
        assert all(e.dept_id == 10 for e in employees)

    def test_all_conditions_none(self, db: Any) -> None:
        """全条件 None で WHERE ごと削除、全件返る."""
        sql = (
            "SELECT * FROM employees\n"
            "WHERE\n"
            "    dept_id = /* $dept_id */999\n"
            "    AND name = /* $name */'default'"
        )
        result = parse_sql(sql, {"dept_id": None, "name": None}, dialect=Dialect.POSTGRESQL)
        assert "WHERE" not in result.sql
        rows = _fetch_all(db, result)
        assert len(rows) == 4


class TestInClause:
    """IN 句展開 → 実行 → マッピング."""

    def test_in_clause_list(self, db: Any) -> None:
        """IN 句でリスト検索."""
        sql = "SELECT * FROM employees WHERE id IN /* $ids */(999)"
        result = parse_sql(sql, {"ids": [1, 3]}, dialect=Dialect.POSTGRESQL)
        rows = _fetch_all(db, result)
        mapper = create_mapper(Employee)
        employees = mapper.map_rows(rows)
        assert len(employees) == 2
        assert {e.id for e in employees} == {1, 3}

    def test_in_clause_single(self, db: Any) -> None:
        """IN 句で単一要素リスト."""
        sql = "SELECT * FROM employees WHERE id IN /* $ids */(999)"
        result = parse_sql(sql, {"ids": [2]}, dialect=Dialect.POSTGRESQL)
        rows = _fetch_all(db, result)
        assert len(rows) == 1
        assert rows[0]["name"] == "Bob"

    def test_in_clause_empty_list(self, db: Any) -> None:
        """IN 句で空リスト → NULL → 0件."""
        sql = "SELECT * FROM employees WHERE id IN /* $ids */(999)"
        result = parse_sql(sql, {"ids": []}, dialect=Dialect.POSTGRESQL)
        rows = _fetch_all(db, result)
        assert len(rows) == 0


class TestAnnotatedColumnMapping:
    """Annotated[T, Column('X')] によるカラムマッピング統合テスト."""

    def test_annotated_mapping(self, db_aliased: Any) -> None:
        """DB カラム名→フィールド名のマッピングが動作する."""
        sql = "SELECT * FROM employees_aliased"
        result = parse_sql(sql, {}, dialect=Dialect.POSTGRESQL)
        rows = _fetch_all(db_aliased, result)
        mapper = create_mapper(AnnotatedEmployee)
        employees = mapper.map_rows(rows)
        assert len(employees) == 2
        assert employees[0] == AnnotatedEmployee(id=1, name="Alice", dept_id=10)


class TestEntityDecorator:
    """@entity デコレータ統合テスト."""

    def test_naming_convention_mapping(self, pg_conn: Any) -> None:
        """Snake_to_camel naming でカラムマッピング."""
        cur = pg_conn.cursor()
        cur.execute('DROP TABLE IF EXISTS "camelEmployees"')
        cur.execute("""
            CREATE TABLE "camelEmployees" (
                "empId" INTEGER PRIMARY KEY,
                "empName" TEXT NOT NULL
            )
        """)
        cur.execute("""INSERT INTO "camelEmployees" ("empId", "empName") VALUES (1, 'Alice')""")
        pg_conn.commit()

        sql = 'SELECT * FROM "camelEmployees"'
        result = parse_sql(sql, {}, dialect=Dialect.POSTGRESQL)
        rows = _fetch_all(pg_conn, result)
        mapper = create_mapper(CamelEmployee)
        employees = mapper.map_rows(rows)
        assert len(employees) == 1
        assert employees[0] == CamelEmployee(emp_id=1, emp_name="Alice")

        cur.execute('DROP TABLE IF EXISTS "camelEmployees"')
        pg_conn.commit()


class TestSqlLoaderIntegration:
    """SqlLoader → パース → 実行 → マッピングの一連フロー."""

    def test_load_and_execute(self, db: Any, tmp_path: Path) -> None:
        """SQL ファイルを読み込んでパース・実行・マッピング."""
        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()
        (sql_dir / "find_by_dept.sql").write_text(
            "SELECT * FROM employees\nWHERE\n    dept_id = /* $dept_id */999",
            encoding="utf-8",
        )

        loader = SqlLoader(sql_dir)
        sql_template = loader.load("find_by_dept.sql")
        result = parse_sql(sql_template, {"dept_id": 10}, dialect=Dialect.POSTGRESQL)
        rows = _fetch_all(db, result)
        mapper = create_mapper(Employee)
        employees = mapper.map_rows(rows)
        assert len(employees) == 2
        assert all(e.dept_id == 10 for e in employees)

    def test_load_with_none_param(self, db: Any, tmp_path: Path) -> None:
        """SQL ファイルを読み込み、None パラメータで条件削除."""
        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()
        (sql_dir / "search.sql").write_text(
            "SELECT * FROM employees\n"
            "WHERE\n"
            "    dept_id = /* $dept_id */999\n"
            "    AND name = /* $name */'default'",
            encoding="utf-8",
        )

        loader = SqlLoader(sql_dir)
        sql_template = loader.load("search.sql")
        result = parse_sql(
            sql_template, {"dept_id": None, "name": "Alice"}, dialect=Dialect.POSTGRESQL
        )
        rows = _fetch_all(db, result)
        mapper = create_mapper(Employee)
        employees = mapper.map_rows(rows)
        assert len(employees) == 1
        assert employees[0].name == "Alice"


class TestMultipleParams:
    """複数パラメータの組み合わせ."""

    def test_multiple_conditions(self, db: Any) -> None:
        """複数条件でフィルタリング."""
        sql = (
            "SELECT * FROM employees\n"
            "WHERE\n"
            "    dept_id = /* $dept_id */999\n"
            "    AND name = /* $name */'default'"
        )
        result = parse_sql(sql, {"dept_id": 10, "name": "Alice"}, dialect=Dialect.POSTGRESQL)
        rows = _fetch_all(db, result)
        mapper = create_mapper(Employee)
        employees = mapper.map_rows(rows)
        assert len(employees) == 1
        assert employees[0] == Employee(id=1, name="Alice", dept_id=10)

    def test_in_clause_with_regular_param(self, db: Any) -> None:
        """IN 句と通常パラメータの混在."""
        sql = (
            "SELECT * FROM employees\n"
            "WHERE dept_id = /* $dept_id */999\n"
            "  AND id IN /* $ids */(999)"
        )
        result = parse_sql(sql, {"dept_id": 10, "ids": [1, 3]}, dialect=Dialect.POSTGRESQL)
        rows = _fetch_all(db, result)
        mapper = create_mapper(Employee)
        employees = mapper.map_rows(rows)
        assert len(employees) == 2
        assert {e.name for e in employees} == {"Alice", "Charlie"}


class TestNullHandling:
    """NULL 値の扱い."""

    def test_non_removable_null_param(self, db: Any) -> None:
        """非 removable パラメータの None は NULL バインド."""
        sql = "SELECT * FROM employees WHERE dept_id = /* dept_id */999"
        result = parse_sql(sql, {"dept_id": None}, dialect=Dialect.POSTGRESQL)
        rows = _fetch_all(db, result)
        # PostgreSQL の WHERE dept_id = NULL は0件（IS NULL が必要）
        assert len(rows) == 0

    def test_select_null_field(self, db: Any) -> None:
        """NULL フィールドを持つレコードのマッピング."""
        sql = "SELECT * FROM employees WHERE id = /* $id */999"
        result = parse_sql(sql, {"id": 4}, dialect=Dialect.POSTGRESQL)
        rows = _fetch_all(db, result)
        mapper = create_mapper(Employee)
        employees = mapper.map_rows(rows)
        assert len(employees) == 1
        assert employees[0] == Employee(id=4, name="Diana", dept_id=None)
