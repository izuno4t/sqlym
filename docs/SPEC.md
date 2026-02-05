# sqlym 機能仕様書

## 1. 概要

sqlym は Python 用の SQL 重視データベースアクセスライブラリである。
Java の Clione-SQL と Doma2 の設計思想を参考に、Python らしい実装を目指す。

### 1.1 設計思想

- **SQL ファースト**: ORM のように SQL を隠蔽しない。SQL を直接書く。
- **2way SQL**: SQL ファイルはそのまま DB クライアントツールでも実行可能。
- **選択の自由**: 自動マッピングも自前マッピングも選べる。
- **シンプル**: 最小限の API で必要十分な機能を提供。

### 1.2 参考ライブラリ

| ライブラリ | 採用する要素 |
|-----------|-------------|
| Clione-SQL | 行単位処理、インデント親子関係、自動行削除 |
| Doma2 | 2way SQL の記法、カラムマッピング |

---

## 2. Sqlym（高レベル API）

### 2.1 概要

Sqlym クラスは SQL ファイルの読み込み、パース、実行、結果マッピングを統合した高レベル API を提供する。

```python
from sqlym import Sqlym

db = Sqlym(connection, sql_dir="sql")
users = db.query(User, "users/find.sql", {"status": "active"})
```

### 2.2 基本メソッド

```python
class Sqlym:
    def __init__(
        self,
        connection: Any,
        *,
        sql_dir: str | Path = "sql",
        dialect: Dialect | None = None,
        auto_commit: bool = False,
    ) -> None:
        """初期化.

        Args:
            connection: DB 接続オブジェクト（PEP 249 DB-API 2.0 準拠）
            sql_dir: SQL ファイルのベースディレクトリ
            dialect: RDBMS 方言（None の場合は自動検出）
            auto_commit: True の場合、execute() 後に自動コミット
        """
        ...

    def query(
        self,
        entity: type[T],
        sql_path: str,
        params: dict[str, Any] | None = None,
        *,
        mapper: RowMapper[T] | Callable | None = None,
    ) -> list[T]:
        """SELECT を実行し、結果をエンティティのリストで返す."""
        ...

    def query_one(
        self,
        entity: type[T],
        sql_path: str,
        params: dict[str, Any] | None = None,
        *,
        mapper: RowMapper[T] | Callable | None = None,
    ) -> T | None:
        """SELECT を実行し、最初の1行をエンティティで返す."""
        ...

    def execute(
        self,
        sql_path: str,
        params: dict[str, Any] | None = None,
    ) -> int:
        """INSERT/UPDATE/DELETE を実行し、影響行数を返す."""
        ...

    def insert(
        self,
        sql_path: str,
        params: dict[str, Any] | None = None,
    ) -> int | None:
        """INSERT を実行し、自動生成された ID を返す."""
        ...

    def commit(self) -> None:
        """connection.commit() のラッパー."""
        ...

    def rollback(self) -> None:
        """connection.rollback() のラッパー."""
        ...
```

### 2.3 Dialect 自動検出

connection オブジェクトから RDBMS を自動検出する。

```python
def _detect_dialect(connection: Any) -> Dialect:
    module = type(connection).__module__
    if "sqlite3" in module:
        return Dialect.SQLITE
    elif "psycopg" in module:
        return Dialect.POSTGRESQL
    elif "pymysql" in module:
        return Dialect.MYSQL
    elif "oracledb" in module:
        return Dialect.ORACLE
    return Dialect.SQLITE  # デフォルト
```

### 2.4 トランザクション管理

**sqlym はトランザクション管理を行わない。**

sqlym の責務は SQL パース、ファイル読み込み、パラメータバインド、オブジェクトマッピングである。
トランザクション管理はアプリケーション層の責務とする。

#### 2.4.1 コンテキストマネージャ

Sqlym はコンテキストマネージャを connection に委譲する。

```python
with Sqlym(connection, sql_dir="sql") as db:
    db.execute("users/update.sql", {"id": 1})
    db.execute("users/update.sql", {"id": 2})
# 正常終了 → connection の __exit__ が commit
# 例外発生 → connection の __exit__ が rollback
```

#### 2.4.2 auto_commit モード

ツールやライトなアプリケーション向けに、execute() 実行ごとに自動コミットするモードを提供する。

```python
db = Sqlym(connection, sql_dir="sql", auto_commit=True)
db.execute("users/update.sql", {"id": 1})  # 即座に commit
db.execute("users/update.sql", {"id": 2})  # 即座に commit
```

---

## 3. 低レベル API

Sqlym クラスを使わずに個々の機能を直接利用できる。

### 3.1 parse_sql（SQL パース）

SQL テンプレートをパースし、プレースホルダ置換とパラメータ抽出を行う。

```python
from sqlym import parse_sql, Dialect

result = parse_sql(
    "SELECT * FROM users WHERE id = /* $id */1",
    {"id": 100},
    dialect=Dialect.SQLITE,
)

print(result.sql)     # "SELECT * FROM users WHERE id = ?"
print(result.params)  # [100]
```

#### 3.1.1 ParseResult

```python
@dataclass
class ParseResult:
    sql: str                        # パース後の SQL
    params: list[Any]               # バインドパラメータ（位置パラメータ形式）
    named_params: dict[str, Any]    # 名前付きパラメータ（Oracle 用）
```

### 3.2 SqlLoader（SQL ファイル読み込み）

ファイルシステムから SQL テンプレートを読み込む。

```python
from sqlym import SqlLoader, Dialect

loader = SqlLoader("sql")

# 基本的な読み込み
sql = loader.load("employee/find.sql")

# Dialect 指定時は RDBMS 固有ファイルを優先
sql = loader.load("employee/find.sql", dialect=Dialect.ORACLE)
# → sql/employee/find.oracle.sql があればそれを、なければ find.sql を読み込む
```

### 3.3 create_mapper（マッパー生成）

行データをオブジェクトに変換するマッパーを生成する。

```python
from sqlym import create_mapper

# 自動マッパー（dataclass / Pydantic を自動判定）
mapper = create_mapper(Employee)

# カスタムマッパー（関数指定）
mapper = create_mapper(
    Employee,
    mapper=lambda row: Employee(
        id=row["EMP_ID"],
        name=row["EMP_NAME"],
    )
)

# 使用例
rows = [{"id": 1, "name": "山田"}, {"id": 2, "name": "佐藤"}]
employees = mapper.map_rows(rows)
```

### 3.4 低レベル API の組み合わせ

```python
import sqlite3
from sqlym import SqlLoader, parse_sql, create_mapper, Dialect

# 1. SQL ファイル読み込み
loader = SqlLoader("sql")
sql_template = loader.load("employee/find_by_dept.sql")

# 2. SQL パース
result = parse_sql(sql_template, {"dept_id": 10}, dialect=Dialect.SQLITE)

# 3. DB 実行
conn = sqlite3.connect("example.db")
cursor = conn.cursor()
cursor.execute(result.sql, result.params)
rows = [dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()]

# 4. オブジェクトマッピング
mapper = create_mapper(Employee)
employees = mapper.map_rows(rows)
```

---

## 4. 2way SQL パーサー

### 3.1 Clione-SQL の 4 ルール

| ルール | 説明 |
|--------|------|
| Rule 1 | SQL は行単位（LineUnit）で処理する |
| Rule 2 | インデントにより親子関係を定義する |
| Rule 3 | 子が全て除去されたら親も除去される |
| Rule 4 | `$` 付きパラメータが None なら行を除去する |

### 3.2 パラメータ記法

#### 3.2.1 バインド変数（削除可能）

```sql
/* $パラメータ名 */デフォルト値
```

- パラメータが None の場合、その行全体を削除する
- デフォルト値は DB ツールで直接実行する際に使用される

```sql
WHERE name = /* $name */'山田太郎'
```

#### 3.2.2 バインド変数（削除不可）

```sql
/* パラメータ名 */デフォルト値
```

- パラメータが None でも行は削除されない
- None は NULL としてバインドされる

```sql
WHERE deleted_at = /* deleted_at */NULL
```

#### 3.2.3 デフォルト値の形式

| 形式 | 例 |
|------|-----|
| 文字列 | `'string'` または `"string"` |
| 数値 | `123` または `45.67` |
| 識別子 | `column_name` |
| リスト | `(1, 2, 3)` |
| NULL | `NULL` |

### 3.3 パラメータ修飾記号

#### 3.3.1 `&` 修飾記号（バインドなし行削除）

`$` と同様に negative 時に行削除するが、positive 時にプレースホルダ付与・値バインドを行わない。

```sql
SELECT * FROM people
WHERE
    SEX = 'female' /* &!is_gender_free */
    AND age /* $!age */= 25
```

#### 3.3.2 `@` 修飾記号（必須パラメータ）

パラメータが negative のとき例外をスローする。

```sql
SELECT * FROM TABLE1 WHERE ID = /* @id */'11'
```

#### 3.3.3 `?` 修飾記号（フォールバック）

パラメータが negative のとき、右隣のパラメータを使用。全て negative ならデフォルト値を使用。

```sql
UPDATE people SET
    hometown = /* ?prefecture ?country */'unknown'
WHERE ID = /* @id */'11'
```

#### 3.3.4 `!` による否定

修飾記号の挙動を反転させる。

```sql
-- age が positive なら行削除、negative なら残す
AND age /* $!age */= 25
```

### 3.4 negative/positive の拡張判定

以下の値を negative として扱う:

- `None`
- `False`（Boolean）
- 空リスト `[]`
- 全要素が negative のリスト

### 3.5 IN 句の自動展開

```sql
WHERE id IN /* $ids */(1, 2, 3)
```

パラメータ `ids` がリスト `[10, 20, 30]` の場合:

```sql
WHERE id IN (?, ?, ?)
-- バインド値: [10, 20, 30]
```

空リストの場合:

```sql
WHERE id IN (NULL)
```

#### 3.5.1 IN 句の部分展開

IN 句内の一部のみをパラメータ化できる。

```sql
FIELD1 IN ('aaa', 'bbb', /* param */'ccc')
```

`param = [10, 20, 30]` の場合:

```sql
FIELD1 IN ('aaa', 'bbb', ?, ?, ?)
```

### 3.6 比較演算子の自動変換

パラメータを比較演算子の**前**に置いた場合、値に応じて演算子を自動変換する。

```sql
FIELD1 /* param */= 100
```

| param の値 | 変換結果 |
|------------|----------|
| `null` | `FIELD1 IS NULL` |
| スカラー値 | `FIELD1 = ?` |
| 要素数 1 のリスト | `FIELD1 = ?` |
| 要素数 2 以上のリスト | `FIELD1 IN (?, ?, ...)` |
| 空リスト | `FIELD1 IS NULL` |

否定演算子（`<>`, `!=`）の前に置いた場合:

| param の値 | 変換結果 |
|------------|----------|
| `null` | `FIELD1 IS NOT NULL` |
| リスト | `FIELD1 NOT IN (?, ?, ...)` |

### 3.7 LIKE 句のリスト展開

LIKE の前にリストパラメータを置いた場合、OR に展開する。

```sql
FIELD1 /* param */LIKE 'pattern'
```

`param = ['a%', 'b%', 'c%']` の場合:

```sql
FIELD1 LIKE ?
OR FIELD1 LIKE ?
OR FIELD1 LIKE ?
```

### 3.8 自動除去

#### 3.8.1 WHERE 句の除去

条件が全て削除された場合、WHERE 自体も削除する。

#### 3.8.2 AND/OR の除去

先頭の AND/OR を自動削除する。

#### 3.8.3 行末区切りの除去

行末に区切り（AND, OR, カンマ等）がある場合、次行削除後に残った行末区切りを除去する。

```sql
WHERE
    age >= /* $age_from */25 AND
    age <= /* $age_to */50
```

`age_to = None` の場合:

```sql
WHERE
    age >= ?
```

#### 3.8.4 空括弧の除去

中身が全て削除された括弧は括弧ごと削除する。

#### 3.8.5 区切りのみの行の結合

UNION, UNION ALL 等の区切りのみの行は、次の行と結合して 1 ノードとして扱う。

```sql
SELECT id FROM table1
UNION
SELECT id FROM table2
```

UNION 行は次の SELECT と同一ノードになり、ブロック単位での削除が可能。

### 3.9 プレースホルダ形式

| 形式 | 用途 |
|------|------|
| `?` | SQLite, JDBC 互換 |
| `%s` | MySQL, PostgreSQL (psycopg2) |
| `:name` | Oracle, 名前付きパラメータ |

---

## 5. 補助関数

### 5.1 `%concat` / `%C`（文字列連結）

パラメータと文字列を連結して 1 つの値にする。

```sql
WHERE name LIKE /* %concat('%', part_of_name, '%') */'%山田%'
```

または短縮形:

```sql
WHERE name LIKE /*%C '%' part_of_name '%' */'%山田%'
```

### 5.2 `%L`（LIKE エスケープ）

LIKE 句のワイルドカード文字（`%`, `_`）をエスケープし、`ESCAPE '#'` を自動付与する。

```sql
WHERE lyrics LIKE /*%L '%' keyword '%' */'%100#%病気%'
```

### 5.3 `%STR` / `%SQL`（直接埋め込み）

パラメータ値を SQL に直接展開する（SQL インジェクション注意）。

```sql
ORDER BY /* %STR(order_column) */id
```

### 5.4 `%if-%elseif-%else`（インライン条件分岐）

```sql
/*%if cond1 */ 'AAA' /*%elseif cond2 */ 'BBB' /*%else */ 'CCC' /*%end*/
```

### 5.5 `%include`（SQL インクルード）

別の SQL ファイルをインクルードする。

```sql
/* %include "common/where_clause.sql" */
```

---

## 6. ブロック切り替え（`-- %IF` / `-- %ELSE`）

行コメント形式での条件分岐。

```sql
WHERE
    title = /* $title */'chief'
    -- %IF useDateEmployed
      AND date_employed >= /* $date_from */'19980401'
    -- %ELSE
      AND date_of_promotion >= /* $date_from */'20080401'
    -- %END
```

---

## 7. マッパー

### 7.1 概要

SQL 実行結果（行）を Python オブジェクトに変換する機能。

### 7.2 マッパーの種類

#### 7.2.1 自動マッパー

dataclass または Pydantic BaseModel を自動的にマッピングする。

```python
from sqlym import create_mapper

mapper = create_mapper(Employee)  # 自動判定
```

- dataclass: `dataclasses.fields()` でフィールド情報取得
- Pydantic: `model_validate()` でマッピング
- リフレクション結果はキャッシュ（初回のみ解析）

#### 7.2.2 自前マッパー（関数）

```python
mapper = create_mapper(
    Employee,
    mapper=lambda row: Employee(
        id=row['EMP_ID'],
        name=row['EMP_NM'],
    )
)
```

### 7.3 マッパーインターフェース

```python
from typing import Protocol, TypeVar

T = TypeVar('T')

@runtime_checkable
class RowMapper(Protocol[T]):
    def map_row(self, row: dict[str, Any]) -> T: ...
    def map_rows(self, rows: list[dict[str, Any]]) -> list[T]: ...
```

---

## 8. カラムマッピング

### 8.1 個別指定（Annotated）

```python
from typing import Annotated
from sqlym import Column

@dataclass
class Employee:
    id: Annotated[int, Column("EMP_ID")]
    name: Annotated[str, Column("EMP_NAME")]
    email: str  # カラム名 = フィールド名
```

### 8.2 一括指定（デコレータ）

```python
from sqlym import entity

@entity(column_map={
    "id": "EMP_ID",
    "name": "EMP_NAME",
})
@dataclass
class Employee:
    id: int
    name: str
```

### 8.3 命名規則

```python
@entity(naming="snake_to_camel")
@dataclass
class Employee:
    dept_id: int  # → deptId
```

| naming 値 | 変換 |
|----------|------|
| `as_is` | そのまま（デフォルト） |
| `snake_to_camel` | snake_case → camelCase |
| `camel_to_snake` | camelCase → snake_case |

### 8.4 優先順位

1. `Annotated[..., Column("X")]` の指定
2. `@entity(column_map={...})` の指定
3. `@entity(naming="...")` の変換
4. フィールド名そのまま

---

## 9. SQL ファイル管理

### 9.1 パス規約

```text
project/
├── sql/
│   ├── employee/
│   │   ├── find_all.sql
│   │   ├── find_by_id.sql
│   │   └── find_by_dept.sql
│   └── department/
│       └── find_all.sql
```

### 9.2 RDBMS 別 SQL ファイル

RDBMS ごとに SQL 構文が異なる場合は、ファイルを分けて対応する。

```text
sql/employee/
├── find.sql              # 共通 SQL
├── find.oracle.sql       # Oracle 固有（優先ロード）
└── find.postgresql.sql   # PostgreSQL 固有（優先ロード）
```

---

## 10. エラーハンドリング

### 10.1 例外クラス

| 例外 | 説明 |
|------|------|
| `SqlyError` | 基底例外 |
| `SqlParseError` | SQL パースエラー |
| `MappingError` | マッピングエラー |
| `SqlFileNotFoundError` | SQL ファイルが見つからない |

---

## 11. 対応環境

- Python 3.10+
- 依存ライブラリ: なし（標準ライブラリのみ）
- オプション依存: Pydantic（Pydantic マッパー使用時）

### 11.1 対応 RDBMS

| RDBMS | ドライバー | プレースホルダ |
|-------|----------|--------------|
| SQLite | sqlite3 | `?` |
| PostgreSQL | psycopg 3.1+ | `%s` |
| MySQL | PyMySQL 1.1+ | `%s` |
| Oracle | python-oracledb 3.0+ | `:name` |
