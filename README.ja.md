# sqly

[English](README.md)

Python 用の SQL テンプレートエンジン。Java の [Clione-SQL](https://github.com/tauty/clione-sql) / [Doma2](https://github.com/domaframework/doma) にインスパイアされた 2way SQL パーサーと、結果行のオブジェクトマッピングを提供します。

- **SQL ファースト** — ORM ではなく SQL を直接書く。sqly は SQL を自動生成しない
- **2way SQL** — SQL ファイルはそのまま DB ツールでも実行可能
- **ゼロ依存** — コアは Python 標準ライブラリのみで動作（Pydantic はオプション）
- **柔軟なマッピング** — dataclass / Pydantic の自動マッピングも、自前関数も選べる

## クイックスタート

```bash
pip install sqly
```

### 1. エンティティ定義

```python
from dataclasses import dataclass
from typing import Annotated
from sqly import Column

@dataclass
class Employee:
    id: int
    name: Annotated[str, Column("EMP_NAME")]  # カラム名が違う場合
    dept_id: int | None = None
```

### 2. SQL ファイル作成

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

### 3. 実行

```python
from sqly import SqlExecutor, create_mapper

executor = SqlExecutor(connection)
mapper = create_mapper(Employee)

# パラメータがNoneの行は自動削除される
result = executor.query(
    "sql/employee/find_by_dept.sql",
    {"id": 100, "dept_id": None, "status": "active"},  # dept_idの行は消える
    mapper=mapper
)

for emp in result:
    print(emp.name)
```

## 主な機能

### 2way SQL（Clione-SQL 方式）

SQL コメント形式でパラメータを記述。DB ツールでそのまま実行可能。

```sql
-- パラメータがNoneなら行を削除（$付き）
WHERE name = /* $name */'default'

-- パラメータがNoneでもNULLとしてバインド（$なし）
WHERE name = /* name */'default'
```

### インデントベースの親子関係

子が全て削除されたら親も削除される。

```sql
WHERE
    id = /* $id */0
    AND (
        status = /* $status1 */'a'
        OR status = /* $status2 */'b'
    )
-- status1, status2が両方Noneなら括弧ごと消える
```

### IN 句の自動展開

```sql
WHERE dept_id IN /* $dept_ids */(1, 2, 3)
-- dept_ids=[10,20,30] → WHERE dept_id IN (?, ?, ?)
```

### マッパー

```python
# 自動マッピング（dataclass/Pydantic）
mapper = create_mapper(Employee)

# 自前マッピング（カラム名が大きく違う場合など）
mapper = create_mapper(Employee, mapper=lambda row: Employee(
    id=row['EMP_ID'],
    name=row['EMP_NM'],
    dept_id=row['DEPT_CODE'],
))
```

### カラム名マッピング

```python
from typing import Annotated
from sqly import Column, entity

@dataclass
class Employee:
    # 個別指定
    id: Annotated[int, Column("EMP_ID")]
    name: Annotated[str, Column("EMP_NAME")]

    # 指定なしはフィールド名そのまま
    email: str

# または一括指定
@entity(naming="snake_to_camel")  # dept_id → deptId
@dataclass
class Employee:
    dept_id: int  # → deptId
```

## RDBMS 対応

SQLite、PostgreSQL、MySQL、Oracle をサポートしています。

| RDBMS | ドライバー | プレースホルダ | extras |
|---|---|---|---|
| SQLite | [sqlite3](https://docs.python.org/3/library/sqlite3.html)（標準ライブラリ） | `?` | 不要 |
| PostgreSQL | [psycopg](https://www.psycopg.org/) 3.1+ | `%s` | `sqly[postgresql]` |
| MySQL | [PyMySQL](https://pymysql.readthedocs.io/) 1.1+ | `%s` | `sqly[mysql]` |
| Oracle | [python-oracledb](https://python-oracledb.readthedocs.io/) 3.0+ | `:name` | `sqly[oracle]` |

SQLite 以外の RDBMS を利用する場合は extras 付きでインストールしてください。ドライバーが自動的にインストールされます。

```bash
pip install sqly[postgresql]
```

| 機能 | 説明 |
|---|---|
| LIKE エスケープ | DB ごとのエスケープ対象文字の差異を吸収 |
| IN 句要素数上限 | Oracle の 1000 件制限を超える場合に自動分割 |
| RDBMS 別 SQL ファイルロード | `find.sql-oracle` → `find.sql` のフォールバック |

DB ごとに SQL 構文が異なる場合は、SQL ファイルを分けて対応できます：

```
sql/employee/
├── find.sql              # 共通 SQL
├── find.sql-oracle       # Oracle 固有（優先ロード）
└── find.sql-postgresql   # PostgreSQL 固有（優先ロード）
```

## sqly が提供しないもの

sqly は SQL テンプレートエンジンであり、以下の機能は提供しません。
SQL で直接記述するか、他のライブラリと組み合わせてください。

- SQL の自動生成（INSERT/UPDATE/DELETE/UPSERT 等）
- ページネーション SQL の自動生成（`LIMIT/OFFSET`、`ROWNUM` 等）
- DDL 管理・マイグレーション
- コネクション管理・コネクションプーリング
- トランザクション管理

## 謝辞

sqly の 2way SQL パーサーは、tauty 氏の [Clione-SQL](https://github.com/tauty/clione-sql) の設計に基づいています。行単位の SQL 処理、インデントによる親子関係、パラメータコメント構文はいずれも Clione-SQL に由来します。

Dialect 設計と RDBMS 固有の動作差異の扱いは、Doma Framework チームの [Doma2](https://github.com/domaframework/doma) を参考にしています。

2way SQL の先駆的な取り組みに感謝します。

## ライセンス

MIT
