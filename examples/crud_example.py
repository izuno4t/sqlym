#!/usr/bin/env python3
"""sqlym CRUD Example.

This example demonstrates the basic usage of sqlym:
- Entity definition (dataclass + Column mapping)
- SQL file loading with SqlLoader
- Dynamic conditional search (None parameters remove condition lines)
- IN clause expansion
- LIKE escape
- Row mapping with create_mapper

Usage:
    uv run python examples/crud_example.py
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated

from sqlym import Column, Dialect, SqlLoader, create_mapper, escape_like, parse_sql


# =============================================================================
# Entity Definition
# =============================================================================


@dataclass
class User:
    """User entity.

    Use Annotated[T, Column("DB_COLUMN_NAME")] to define
    mapping between DB column names and field names.
    """

    id: int
    name: str
    email: str
    department: str | None = None
    created_at: Annotated[datetime | None, Column("created_at")] = None


# =============================================================================
# Database Setup
# =============================================================================


def setup_database() -> sqlite3.Connection:
    """Set up SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row  # Enable dict-like access

    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            department TEXT,
            created_at TEXT
        )
    """)

    # Insert sample data
    sample_data = [
        ("Tanaka Taro", "tanaka@example.com", "Sales", "2024-01-15 09:00:00"),
        ("Suzuki Hanako", "suzuki@example.com", "Development", "2024-02-01 10:30:00"),
        ("Sato Ichiro", "sato@example.com", "Sales", "2024-02-15 14:00:00"),
        ("Yamada Misaki", "yamada@example.com", "Development", "2024-03-01 11:00:00"),
        ("Takahashi 100% Achieved", "takahashi@example.com", "Sales", "2024-03-15 16:00:00"),
    ]
    conn.executemany(
        "INSERT INTO users (name, email, department, created_at) VALUES (?, ?, ?, ?)",
        sample_data,
    )
    conn.commit()
    return conn


# =============================================================================
# CRUD Operations
# =============================================================================


def demo_select_all(conn: sqlite3.Connection) -> None:
    """Demo: Select all records."""
    print("=" * 60)
    print("[SELECT ALL]")
    print("=" * 60)

    sql = "SELECT * FROM users ORDER BY id"
    result = parse_sql(sql, {})

    print(f"SQL: {result.sql}")
    print(f"Parameters: {result.params}")
    print()

    cursor = conn.execute(result.sql, result.params)
    rows = [dict(row) for row in cursor.fetchall()]

    mapper = create_mapper(User)
    users = mapper.map_rows(rows)

    for user in users:
        print(f"  {user}")
    print()


def demo_dynamic_search(conn: sqlite3.Connection, loader: SqlLoader) -> None:
    """Demo: Dynamic conditional search.

    When a parameter is None, that condition line is automatically removed
    (for parameters with $ prefix).
    """
    print("=" * 60)
    print("[DYNAMIC SEARCH] Only department specified (other conditions removed)")
    print("=" * 60)

    sql_template = loader.load("find_users.sql")
    print("SQL Template:")
    print(sql_template)
    print()

    # Only department specified, others are None -> those condition lines are removed
    result = parse_sql(
        sql_template,
        {
            "id": None,  # This line is removed
            "name_pattern": None,  # This line is removed
            "department": "Sales",  # This condition remains
            "ids": None,  # This line is removed
        },
    )

    print(f"Generated SQL:\n{result.sql}")
    print(f"Parameters: {result.params}")
    print()

    cursor = conn.execute(result.sql, result.params)
    rows = [dict(row) for row in cursor.fetchall()]
    mapper = create_mapper(User)
    users = mapper.map_rows(rows)

    print("Results:")
    for user in users:
        print(f"  {user}")
    print()


def demo_in_clause(conn: sqlite3.Connection, loader: SqlLoader) -> None:
    """Demo: IN clause expansion.

    List parameters are automatically expanded.
    Example: IN /* $ids */(1) -> IN (?, ?, ?)
    """
    print("=" * 60)
    print("[IN CLAUSE] Search by multiple IDs")
    print("=" * 60)

    sql_template = loader.load("find_users.sql")

    # Only ids specified, others are None
    result = parse_sql(
        sql_template,
        {
            "id": None,
            "name_pattern": None,
            "department": None,
            "ids": [1, 3, 5],  # Expanded to IN clause
        },
    )

    print(f"Generated SQL:\n{result.sql}")
    print(f"Parameters: {result.params}")
    print()

    cursor = conn.execute(result.sql, result.params)
    rows = [dict(row) for row in cursor.fetchall()]
    mapper = create_mapper(User)
    users = mapper.map_rows(rows)

    print("Results:")
    for user in users:
        print(f"  {user}")
    print()


def demo_like_escape(conn: sqlite3.Connection, loader: SqlLoader) -> None:
    """Demo: LIKE escape.

    Use escape_like() to safely search strings containing
    special characters (%, _, #).
    """
    print("=" * 60)
    print("[LIKE ESCAPE] Search for names containing '100%'")
    print("=" * 60)

    sql_template = loader.load("find_users.sql")

    # Search for users containing "100%" (% is a LIKE special char, needs escaping)
    search_term = escape_like("100%", Dialect.SQLITE)
    print(f"Search term: '100%' -> After escape: '{search_term}'")

    result = parse_sql(
        sql_template,
        {
            "id": None,
            "name_pattern": f"%{search_term}%",  # Add % for partial match
            "department": None,
            "ids": None,
        },
        dialect=Dialect.SQLITE,
    )

    print(f"Generated SQL:\n{result.sql}")
    print(f"Parameters: {result.params}")
    print()

    cursor = conn.execute(result.sql, result.params)
    rows = [dict(row) for row in cursor.fetchall()]
    mapper = create_mapper(User)
    users = mapper.map_rows(rows)

    print("Results:")
    for user in users:
        print(f"  {user}")
    print()


def demo_insert(conn: sqlite3.Connection, loader: SqlLoader) -> None:
    """Demo: INSERT."""
    print("=" * 60)
    print("[INSERT] Register new user")
    print("=" * 60)

    sql_template = loader.load("insert_user.sql")

    result = parse_sql(
        sql_template,
        {
            "name": "New User",
            "email": "newuser@example.com",
            "department": "General Affairs",
            "created_at": "2024-04-01 09:00:00",
        },
    )

    print(f"Generated SQL:\n{result.sql}")
    print(f"Parameters: {result.params}")
    print()

    cursor = conn.execute(result.sql, result.params)
    conn.commit()
    print(f"Inserted ID: {cursor.lastrowid}")
    print()


def demo_update(conn: sqlite3.Connection, loader: SqlLoader) -> None:
    """Demo: UPDATE."""
    print("=" * 60)
    print("[UPDATE] Update user information")
    print("=" * 60)

    sql_template = loader.load("update_user.sql")

    result = parse_sql(
        sql_template,
        {
            "id": 1,
            "name": "Tanaka Taro (Updated)",
            "email": "tanaka-updated@example.com",
            "department": "Sales (Transferred)",
        },
    )

    print(f"Generated SQL:\n{result.sql}")
    print(f"Parameters: {result.params}")
    print()

    conn.execute(result.sql, result.params)
    conn.commit()

    # Verify update result
    cursor = conn.execute("SELECT * FROM users WHERE id = 1")
    row = dict(cursor.fetchone())
    mapper = create_mapper(User)
    user = mapper.map_row(row)
    print(f"After update: {user}")
    print()


def demo_delete(conn: sqlite3.Connection, loader: SqlLoader) -> None:
    """Demo: DELETE."""
    print("=" * 60)
    print("[DELETE] Delete user")
    print("=" * 60)

    sql_template = loader.load("delete_user.sql")

    result = parse_sql(
        sql_template,
        {"id": 6},  # User inserted by demo_insert
    )

    print(f"Generated SQL:\n{result.sql}")
    print(f"Parameters: {result.params}")
    print()

    cursor = conn.execute(result.sql, result.params)
    conn.commit()
    print(f"Deleted rows: {cursor.rowcount}")
    print()


def demo_named_placeholder(conn: sqlite3.Connection) -> None:
    """Demo: Named placeholder (:name format).

    Supports :name format placeholders used by Oracle, etc.
    """
    print("=" * 60)
    print("[NAMED PLACEHOLDER] :name format")
    print("=" * 60)

    sql = "SELECT * FROM users WHERE department = /* $department */'default'"
    result = parse_sql(
        sql,
        {"department": "Development"},
        placeholder=":name",  # Specify named placeholder
    )

    print(f"Generated SQL: {result.sql}")
    print(f"Named parameters: {result.named_params}")
    print()

    # sqlite3 supports :name format
    cursor = conn.execute(result.sql, result.named_params)
    rows = [dict(row) for row in cursor.fetchall()]
    mapper = create_mapper(User)
    users = mapper.map_rows(rows)

    print("Results:")
    for user in users:
        print(f"  {user}")
    print()


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """Run the examples."""
    print("sqlym CRUD Example")
    print("=" * 60)
    print()

    # Set up database and SqlLoader
    conn = setup_database()
    sql_dir = Path(__file__).parent / "sql"
    loader = SqlLoader(sql_dir)

    # Run each demo
    demo_select_all(conn)
    demo_dynamic_search(conn, loader)
    demo_in_clause(conn, loader)
    demo_like_escape(conn, loader)
    demo_insert(conn, loader)
    demo_update(conn, loader)
    demo_delete(conn, loader)
    demo_named_placeholder(conn)

    print("=" * 60)
    print("Example completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
