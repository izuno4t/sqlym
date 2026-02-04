# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

sqly is a SQL-first database access library for Python, inspired by Java's Clione-SQL and Doma2. It provides 2way SQL parsing (SQL files remain directly executable by DB tools) and flexible row-to-object mapping.

- **Language**: Python 3.10+
- **Dependencies**: None (stdlib only); Pydantic is optional
- **License**: MIT
- **Status**: Design/specification phase — no implementation code yet

## Architecture

```
src/sqly/
├── __init__.py          # Public API (parse_sql, create_mapper, Column, entity, etc.)
├── parser/
│   ├── tokenizer.py     # SQL tokenizer
│   ├── line_unit.py     # LineUnit: line-level processing unit
│   └── twoway.py        # TwoWaySQLParser: Clione-SQL 2way SQL engine
├── mapper/
│   ├── protocol.py      # RowMapper Protocol (runtime_checkable)
│   ├── dataclass.py     # DataclassMapper (auto-mapping with caching)
│   ├── pydantic.py      # PydanticMapper (optional)
│   └── column.py        # Column annotation & @entity decorator
├── executor.py          # SQL execution
├── loader.py            # SqlLoader: file-based SQL template loading
└── exceptions.py        # SqlyError, SqlParseError, MappingError, SqlFileNotFoundError
```

### Core Concepts

**Clione-SQL 4 Rules** govern the parser:
1. SQL is processed line-by-line (LineUnit)
2. Indentation defines parent/child relationships
3. If all children are removed, parent is also removed (bottom-up propagation)
4. `$`-prefixed parameters that are None cause line removal

**Parameter syntax in SQL comments**:
- `/* $name */default` — removable (None removes the line)
- `/* name */default` — non-removable (None binds as NULL)
- `IN /* $ids */(1,2,3)` — auto-expands list parameters

**Parser pipeline**: parse lines → build tree from indentation → evaluate params & mark removal → propagate removal upward → rebuild SQL → clean dangling WHERE/AND/OR/empty parens

**Mapper hierarchy** (via `create_mapper()` factory):
- `DataclassMapper` — auto-maps using field introspection with caching
- `PydanticMapper` — auto-detected via `model_validate()`
- `ManualMapper` — wraps user-provided function/lambda

**Column mapping priority**: `Annotated[T, Column("X")]` > `@entity(column_map={})` > `@entity(naming="...")` > field name as-is

### Placeholder formats
Supports `?` (SQLite/JDBC), `%s` (psycopg2), `:name` (Oracle) — configurable per parser instance.

## Implementation Phases (from DESIGN.md)

1. Parser foundation (LineUnit, line parsing, basic parameter substitution)
2. Parser completion (line removal, IN clause expansion, SQL cleanup)
3. Mappers (RowMapper, DataclassMapper, Column/entity)
4. Integration (SqlLoader, public API)

## Key Design Decisions

- Zero external dependencies for core — Pydantic support is optional and lazy-imported
- Protocol-based mapper interface with `@runtime_checkable` for duck typing
- Class-level mapping cache in DataclassMapper for performance
- Indentation carries semantic meaning (parent/child relationships for cascading removal)

## Specifications

- `docs/SPEC.md` — Functional specification (Japanese)
- `docs/DESIGN.md` — Implementation design with class-level details (Japanese)
