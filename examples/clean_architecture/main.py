#!/usr/bin/env python3
"""Clean Architecture example with sqlym.

Structure:
    domain/models/       - Entities
    application/use_cases/ - Use cases
    infrastructure/repositories/ - Repository implementations (sqlym)
    sql/                 - SQL files

Usage:
    cd examples/clean_architecture
    PYTHONPATH="../../src:." uv run python main.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from application.use_cases import CreateOrderUseCase, CreateUserUseCase
from infrastructure.dao import OrderDAO, UserDAO
from infrastructure.repositories import OrderRepository, UserRepository

from sqlym import Sqlym


def setup_database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            department TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            total_price INTEGER NOT NULL,
            ordered_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.executemany(
        "INSERT INTO users (name, email, department, created_at) VALUES (?, ?, ?, ?)",
        [
            ("Tanaka Taro", "tanaka@example.com", "Sales", "2024-01-15 09:00:00"),
            ("Suzuki Hanako", "suzuki@example.com", "Development", "2024-02-01 10:30:00"),
            ("Sato Ichiro", "sato@example.com", "Sales", "2024-02-15 14:00:00"),
        ],
    )
    conn.commit()
    return conn


class Container:
    """Composition Root - dependency injection container."""

    def __init__(self, conn: sqlite3.Connection, sql_dir: Path) -> None:
        self.conn = conn
        db = Sqlym(conn, sql_dir=sql_dir)

        # DAOs
        user_dao = UserDAO(db)
        order_dao = OrderDAO(db)

        # Repositories
        self.user_repo = UserRepository(user_dao)
        self.order_repo = OrderRepository(order_dao)

        # Use Cases
        self.create_user = CreateUserUseCase(self.user_repo)
        self.create_order = CreateOrderUseCase(self.user_repo, self.order_repo)


def main() -> None:
    print("=" * 60)
    print("Clean Architecture Example")
    print("=" * 60)

    conn = setup_database()
    sql_dir = Path(__file__).parent / "sql"

    # Composition Root
    container = Container(conn, sql_dir)

    # 1. Query
    print("\n1. Query users")
    print("-" * 40)
    for user in container.user_repo.find_all():
        print(f"  - {user.name} ({user.department})")

    # 2. Use case: Create user
    print("\n2. Create user")
    print("-" * 40)
    new_user = container.create_user.execute("Yamada", "yamada@example.com", "Marketing")
    print(f"Created: {new_user.name} (ID: {new_user.id})")
    conn.commit()

    # 3. Use case: Create order
    print("\n3. Create order")
    print("-" * 40)
    order = container.create_order.execute(new_user.id, "Premium Widget", 5, 3000)  # type: ignore[arg-type]
    print(f"Order: {order.product_name} x {order.quantity} = {order.total_price} yen")
    conn.commit()

    # 4. Error handling
    print("\n4. Error handling")
    print("-" * 40)
    try:
        container.create_order.execute(999, "Test", 1, 100)
    except ValueError as e:
        print(f"Error: {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
