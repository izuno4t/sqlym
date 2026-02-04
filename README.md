# sqly

[日本語](README.ja.md)

A SQL template engine for Python. Inspired by Java's [Clione-SQL](https://github.com/tauty/clione-sql) / [Doma2](https://github.com/domaframework/doma), it provides a 2-way SQL parser and row-to-object mapping.

- **SQL-first** — Write SQL directly, not through an ORM. sqly never auto-generates SQL
- **2-way SQL** — SQL files remain directly executable by DB tools
- **Zero dependencies** — Core runs on the Python standard library only (Pydantic is optional)
- **Flexible mapping** — Auto-mapping for dataclass / Pydantic, or bring your own function

## Quick Start

```bash
pip install sqly
```

### 1. Define an Entity

```python
from dataclasses import dataclass
from typing import Annotated
from sqly import Column

@dataclass
class Employee:
    id: int
    name: Annotated[str, Column("EMP_NAME")]  # when column name differs
    dept_id: int | None = None
```

### 2. Write a SQL File

`sql/employee/find_by_dept.sql`:

```sql
SELECT
    id,
    EMP_NAME,
    dept_id
FROM
    employee
WHERE
    id = /* $id */0
    AND dept_id = /* $dept_id */1
    AND status = /* $status */'active'
```

### 3. Execute

```python
from sqly import SqlExecutor, create_mapper

executor = SqlExecutor(connection)
mapper = create_mapper(Employee)

# Lines with None parameters are automatically removed
result = executor.query(
    "sql/employee/find_by_dept.sql",
    {"id": 100, "dept_id": None, "status": "active"},  # dept_id line is removed
    mapper=mapper
)

for emp in result:
    print(emp.name)
```

## Features

### 2-way SQL (Clione-SQL Style)

Parameters are written as SQL comments. The SQL file can be executed directly by DB tools.

```sql
-- None removes the line ($ prefix)
WHERE name = /* $name */'default'

-- None binds as NULL (no $ prefix)
WHERE name = /* name */'default'
```

### Indent-based Parent-Child Relationships

When all children are removed, the parent is also removed.

```sql
WHERE
    id = /* $id */0
    AND (
        status = /* $status1 */'a'
        OR status = /* $status2 */'b'
    )
-- If both status1 and status2 are None, the entire parenthesized block is removed
```

### Automatic IN Clause Expansion

```sql
WHERE dept_id IN /* $dept_ids */(1, 2, 3)
-- dept_ids=[10,20,30] → WHERE dept_id IN (?, ?, ?)
```

### Mappers

```python
# Auto-mapping (dataclass / Pydantic)
mapper = create_mapper(Employee)

# Manual mapping (when column names differ significantly)
mapper = create_mapper(Employee, mapper=lambda row: Employee(
    id=row['EMP_ID'],
    name=row['EMP_NM'],
    dept_id=row['DEPT_CODE'],
))
```

### Column Name Mapping

```python
from typing import Annotated
from sqly import Column, entity

@dataclass
class Employee:
    # Per-field mapping
    id: Annotated[int, Column("EMP_ID")]
    name: Annotated[str, Column("EMP_NAME")]

    # No mapping — uses field name as-is
    email: str

# Or apply a naming convention
@entity(naming="snake_to_camel")  # dept_id → deptId
@dataclass
class Employee:
    dept_id: int  # → deptId
```

## RDBMS Support

Supports SQLite, PostgreSQL, MySQL, and Oracle.

| RDBMS | Driver | Placeholder | Extras |
|---|---|---|---|
| SQLite | [sqlite3](https://docs.python.org/3/library/sqlite3.html) (stdlib) | `?` | — |
| PostgreSQL | [psycopg](https://www.psycopg.org/) 3.1+ | `%s` | `sqly[postgresql]` |
| MySQL | [PyMySQL](https://pymysql.readthedocs.io/) 1.1+ | `%s` | `sqly[mysql]` |
| Oracle | [python-oracledb](https://python-oracledb.readthedocs.io/) 3.0+ | `:name` | `sqly[oracle]` |

For RDBMS other than SQLite, install with extras. The driver will be installed automatically.

```bash
pip install sqly[postgresql]
```

| Feature | Description |
|---|---|
| LIKE escaping | Handles differences in LIKE escape characters across databases |
| IN clause limit | Automatically splits when exceeding Oracle's 1000-element limit |
| RDBMS-specific SQL file loading | Falls back from `find.sql-oracle` to `find.sql` |

When SQL syntax differs across databases, you can provide database-specific SQL files:

```
sql/employee/
├── find.sql              # Common SQL
├── find.sql-oracle       # Oracle-specific (loaded preferentially)
└── find.sql-postgresql   # PostgreSQL-specific (loaded preferentially)
```

## What sqly Does Not Provide

sqly is a SQL template engine. The following features are out of scope.
Write SQL directly or combine with other libraries.

- SQL generation (INSERT/UPDATE/DELETE/UPSERT, etc.)
- Pagination SQL generation (`LIMIT/OFFSET`, `ROWNUM`, etc.)
- DDL management / migrations
- Connection management / connection pooling
- Transaction management

## Acknowledgments

sqly's 2-way SQL parser is based on the design of [Clione-SQL](https://github.com/tauty/clione-sql) by tauty. The four rules for line-based SQL processing, indent-driven parent-child relationships, and parameter comment syntax all originate from Clione-SQL.

The dialect design and RDBMS-specific behavior handling draw from [Doma2](https://github.com/domaframework/doma) by the Doma Framework team.

We are grateful to both projects for their pioneering work in 2-way SQL.

## License

MIT
