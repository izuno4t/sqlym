# SQL Syntax Reference

[日本語](SQL_SYNTAX.ja.md)

This document describes how to write SQL templates for sqlym.

## Basic Concept

sqlym SQL templates are **2-way SQL**.

- Through sqlym, parameters are bound and the SQL is executed
- Through a DB tool (pgAdmin, DBeaver, etc.), the default values are used
  as-is

```sql
SELECT * FROM users WHERE name = /* $name */'Yamada'
```

| Execution method | Result |
| --- | --- |
| Directly in a DB tool | `WHERE name = 'Yamada'` (default value is used) |
| Via sqlym | `WHERE name = ?` + bind value `['Yamada']` |

Parameters are written inside SQL comments `/* ... */`, with a default value
placed immediately after. DB tools ignore comments, so the default value is
used as-is.

---

## Parameter Syntax

### Removable Parameters (`$` prefix)

```sql
/* $param_name */default_value
```

When the parameter is `None` (or not provided), **the entire line is removed**.
Use this for dynamically toggling search conditions.

```sql
SELECT * FROM employee
WHERE
    dept_id = /* $dept_id */1
    AND name = /* $name */'Yamada'
    AND status = /* $status */'active'
```

```python
result = parse_sql(sql, {"dept_id": 10, "name": None, "status": "active"})
```

`name` is `None`, so that line is removed:

```sql
SELECT * FROM employee
WHERE
    dept_id = ?
    AND status = ?
-- params: [10, 'active']
```

When the first condition is `None`:

```python
result = parse_sql(sql, {"dept_id": None, "name": "Yamada", "status": "active"})
```

The `dept_id` line is removed, and the leading `AND` before `name` is
automatically stripped:

```sql
SELECT * FROM employee
WHERE
    name = ?
    AND status = ?
-- params: ['Yamada', 'active']
```

### Non-removable Parameters (no `$` prefix)

```sql
/* param_name */default_value
```

Even when the parameter is `None`, the line is **not removed** — the value is
bound as NULL. Use this for columns that can legitimately be NULL.

```sql
UPDATE employee SET
    deleted_at = /* deleted_at */NULL
WHERE
    id = /* $id */1
```

```python
result = parse_sql(sql, {"deleted_at": None, "id": 100})
```

```sql
UPDATE employee SET
    deleted_at = ?
WHERE
    id = ?
-- params: [None, 100]
```

### Default Value Formats

| Format | Example | Use case |
| --- | --- | --- |
| String | `'Yamada'` | String parameters |
| Number | `123`, `45.67` | Numeric parameters |
| NULL | `NULL` | NULL checks |
| Identifier | `column_name` | Column references, etc. |
| List | `(1, 2, 3)` | IN clauses |

---

## Line Removal and Parent-Child Relationships

sqlym processes SQL **line by line**. Dynamic condition building is achieved
through line removal.

### Rule 1: Line-by-line Processing

SQL is processed one line at a time as a `LineUnit`.
Lines containing parameter comments are candidates for removal.

### Rule 2: Indentation Defines Parent-Child Relationships

Indentation depth determines parent-child relationships.

```sql
WHERE                          -- parent (indent=0)
    dept_id = /* $dept_id */1  -- child (indent=4)
    AND name = /* $name */'Yamada' -- child (indent=4)
```

### Rule 3: When All Children Are Removed, the Parent Is Also Removed

```sql
WHERE
    dept_id = /* $dept_id */1
    AND name = /* $name */'Yamada'
```

When both `dept_id` and `name` are `None`:

- Both lines are removed → all children are removed
- The `WHERE` line is also removed

```sql
SELECT * FROM employee
-- WHERE itself is removed
```

### Rule 4: Lines with `$`-prefixed Parameters Set to None Are Removed

When a `$`-prefixed parameter is `None` (or missing from params), the entire
line is removed.

---

## Nested Parentheses

Parenthesized condition groups also follow indent-based removal propagation.

```sql
SELECT * FROM employee
WHERE
    id = /* $id */1
    AND (
        status = /* $status1 */'active'
        OR status = /* $status2 */'pending'
    )
```

When both `status1` and `status2` are `None`:

1. The `status1` and `status2` lines are removed (Rule 4)
2. All children of `AND (` are removed → `AND (` is also removed (Rule 3)
3. The closing `)` is also removed since its matching open parenthesis was
   removed
4. Final result:

```sql
SELECT * FROM employee
WHERE
    id = ?
```

---

## Automatic AND/OR Removal

When line removal leaves a leading AND or OR, it is automatically stripped.

```sql
WHERE
    id = /* $id */1
    AND name = /* $name */'Yamada'
    AND status = /* $status */'active'
```

When `id` is `None`:

```sql
WHERE
    name = ?
    AND status = ?
-- The leading AND is removed
```

---

## IN Clauses

### Basic Usage

When a list parameter is provided, the IN clause placeholders are automatically
expanded.

```sql
SELECT * FROM employee
WHERE dept_id IN /* $dept_ids */(1, 2, 3)
```

```python
result = parse_sql(sql, {"dept_ids": [10, 20, 30]})
```

```sql
SELECT * FROM employee
WHERE dept_id IN (?, ?, ?)
-- params: [10, 20, 30]
```

`(1, 2, 3)` is the default value, used when executing directly in a DB tool.

### Empty Lists

An empty list is replaced with `IN (NULL)` (returns 0 rows).

```python
result = parse_sql(sql, {"dept_ids": []})
```

```sql
WHERE dept_id IN (NULL)
```

### IN Clauses with Line Removal

When a `$`-prefixed IN clause parameter is `None`, the entire line is removed.

```sql
WHERE
    name = /* $name */'Yamada'
    AND dept_id IN /* $dept_ids */(1, 2, 3)
```

```python
result = parse_sql(sql, {"name": "Yamada", "dept_ids": None})
```

```sql
WHERE
    name = ?
-- The dept_ids line is removed
```

---

## Placeholder Formats

Switch the placeholder format depending on the RDBMS.

### `?` Format (SQLite) — Default

```python
result = parse_sql(sql, params)
# or
result = parse_sql(sql, params, dialect=Dialect.SQLITE)
```

```sql
WHERE name = ? AND age = ?
-- result.params = ['Yamada', 30]
```

### `%s` Format (PostgreSQL / MySQL)

```python
result = parse_sql(sql, params, dialect=Dialect.POSTGRESQL)
```

```sql
WHERE name = %s AND age = %s
-- result.params = ['Yamada', 30]
```

### `:name` Format (Oracle)

```python
result = parse_sql(sql, params, dialect=Dialect.ORACLE)
```

```sql
WHERE name = :name AND age = :age
-- result.named_params = {'name': 'Yamada', 'age': 30}
```

With the `:name` format, use `result.named_params` for binding.

#### Oracle IN Clauses

With the `:name` format, IN clauses are expanded into sequentially numbered
named parameters.

```sql
WHERE dept_id IN /* $dept_ids */(1, 2, 3)
```

```python
result = parse_sql(
    sql,
    {"dept_ids": [10, 20, 30]},
    dialect=Dialect.ORACLE,
)
```

```sql
WHERE dept_id IN (:dept_ids_0, :dept_ids_1, :dept_ids_2)
-- result.named_params = {
--   'dept_ids_0': 10,
--   'dept_ids_1': 20,
--   'dept_ids_2': 30,
-- }
```

---

## RDBMS-specific SQL Files

When SQL syntax differs across databases, provide separate files.

```text
sql/employee/
├── find.sql              # Common SQL
├── find.oracle.sql       # Oracle-specific (loaded preferentially)
└── find.postgresql.sql   # PostgreSQL-specific (loaded preferentially)
```

```python
loader = SqlLoader("sql")

# With a dialect specified, find.oracle.sql is tried first, falling back to
# find.sql
sql = loader.load("employee/find.sql", dialect=Dialect.ORACLE)
```

Use this mechanism for RDBMS-specific SQL syntax such as pagination
(`LIMIT/OFFSET`, `ROWNUM`, etc.) or UPSERT.

---

## Error Messages

When SQL parsing fails (e.g., invalid IN clause split), sqlym raises
`SqlParseError`. By default, the error message includes the line number and a
SQL snippet. To hide the SQL snippet, disable it via config:

```python
from sqlym import config

config.ERROR_INCLUDE_SQL = False
config.ERROR_MESSAGE_LANGUAGE = "en"
```

Set `ERROR_MESSAGE_LANGUAGE` to `ja` or `en`.

Example:

```text
IN句分割の列式を抽出できません: line=12 sql='...'
```

---

## Examples

### Dynamic Search with Multiple Conditions

```sql
SELECT
    e.id,
    e.name,
    e.dept_id,
    d.dept_name
FROM
    employee e
    INNER JOIN department d ON e.dept_id = d.id
WHERE
    e.id = /* $id */1
    AND e.name LIKE /* $name_pattern */'%Yamada%'
    AND e.dept_id IN /* $dept_ids */(1, 2, 3)
    AND e.status = /* $status */'active'
    AND (
        e.hire_date >= /* $hire_from */'2020-01-01'
        OR e.hire_date <= /* $hire_to */'2024-12-31'
    )
ORDER BY e.id
```

```python
# All conditions specified
result = parse_sql(
    sql,
    {
        "id": 100,
        "name_pattern": "%Yamada%",
        "dept_ids": [10, 20],
        "status": "active",
        "hire_from": "2023-01-01",
        "hire_to": "2023-12-31",
    },
)

# Only some conditions (None removes the line)
result = parse_sql(
    sql,
    {
        "id": None,
        "name_pattern": "%Yamada%",
        "dept_ids": None,
        "status": None,
        "hire_from": None,
        "hire_to": None,
    },
)
# → WHERE e.name LIKE ? ORDER BY e.id
```

### INSERT

```sql
INSERT INTO employee (name, dept_id, status)
VALUES (/* name */'', /* dept_id */0, /* status */'')
```

INSERT parameters do not need line removal, so use the non-removable form
(no `$` prefix).

### UPDATE

```sql
UPDATE employee SET
    name = /* name */'',
    dept_id = /* dept_id */0,
    updated_at = /* updated_at */CURRENT_TIMESTAMP
WHERE
    id = /* $id */1
```

Typically, SET clause parameters use the non-removable form, while WHERE clause
parameters use the removable form with `$`.
