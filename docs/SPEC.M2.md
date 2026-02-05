# sqlym M2 仕様書

本ドキュメントは sqlym v0.1.0 で未実装の機能を整理したものである。

---

## 0. Sqlym（高レベル API）

### 0.1 現状の課題

現在の API は低レベルで、利用者が多くのステップを書く必要がある。

```python
# 現在の実装
loader = SqlLoader("sql")
sql_template = loader.load("users/find.sql")
result = parse_sql(sql_template, {"status": "active"})

cursor = conn.execute(result.sql, result.params)
rows = [dict(row) for row in cursor.fetchall()]
mapper = create_mapper(User)
users = mapper.map_rows(rows)
```

### 0.2 目標 API

```python
# 目標の実装
db = Sqlym(connection)
users = db.query(User, "users/find.sql", {"status": "active"})
```

または:

```python
db = Sqlym(connection, sql_dir="sql")
users = db.query(User, "users/find.sql", {"status": "active"})

# 単一行取得
user = db.query_one(User, "users/find_by_id.sql", {"id": 1})

# 更新系
affected = db.execute("users/update.sql", {"id": 1, "name": "new"})
```

### 0.3 設計案

```python
class Sqlym:
    def __init__(
        self,
        connection: Any,
        *,
        sql_dir: str | Path = "sql",
        dialect: Dialect | None = None,
    ) -> None:
        """初期化.

        Args:
            connection: DB 接続オブジェクト（PEP 249 DB-API 2.0 準拠）
            sql_dir: SQL ファイルのベースディレクトリ
            dialect: RDBMS 方言（自動検出も検討）
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
```

### 0.4 Dialect 自動検出（オプション）

connection オブジェクトから RDBMS を自動検出する案:

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

### 0.5 トランザクション管理の方針

**sqlym はトランザクション管理を行わない。**

sqlym の責務は SQL パース、ファイル読み込み、パラメータバインド、オブジェクトマッピングである。
トランザクション管理（savepoint、ネスト、commit/rollback のタイミング制御）は
アプリケーション層（Service 層、UnitOfWork パターン等）の責務とする。

#### 0.5.1 connection への委譲

Sqlym はコンテキストマネージャプロトコルを connection に委譲する。
これにより、各 DB ドライバーのトランザクション動作をそのまま利用できる。

```python
db = Sqlym(connection, sql_dir="sql")

# sqlite3 の場合: with connection で自動 commit/rollback
with db:
    db.execute("users/update.sql", {"id": 1})
    db.execute("users/update.sql", {"id": 2})
# 正常終了 → connection の __exit__ が commit
# 例外発生 → connection の __exit__ が rollback
```

#### 0.5.2 明示的な commit/rollback（便利メソッド）

connection の commit/rollback への薄いラッパーを提供する。
これはトランザクション管理ロジックではなく、単なる便利メソッドである。

```python
db = Sqlym(connection)
db.execute("users/update.sql", {"id": 1})
db.execute("users/update.sql", {"id": 2})
db.commit()  # connection.commit() を呼ぶだけ

# エラー時
try:
    db.execute("users/delete.sql", {"id": 1})
except Exception:
    db.rollback()  # connection.rollback() を呼ぶだけ
```

#### 0.5.3 設計案

```python
class Sqlym:
    def __init__(self, connection: Any, *, sql_dir: str | Path = "sql", dialect: Dialect | None = None) -> None:
        self._connection = connection
        ...

    def __enter__(self) -> Self:
        """コンテキストマネージャ: connection に委譲."""
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any) -> bool | None:
        """コンテキストマネージャ: connection に委譲."""
        return self._connection.__exit__(exc_type, exc_val, exc_tb)

    def commit(self) -> None:
        """connection.commit() のラッパー."""
        self._connection.commit()

    def rollback(self) -> None:
        """connection.rollback() のラッパー."""
        self._connection.rollback()
```

#### 0.5.4 アプリケーション側でのトランザクション管理例

複雑なトランザクション管理が必要な場合は、アプリケーション側で UnitOfWork パターン等を実装する。

```python
# アプリケーション側の実装例
class UnitOfWork:
    def __init__(self, connection):
        self.connection = connection
        self.db = Sqlym(connection, sql_dir="sql")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()

# 使用例
with UnitOfWork(connection) as uow:
    uow.db.execute("users/update.sql", {"id": 1})
    uow.db.execute("logs/insert.sql", {"action": "update"})
```

#### 0.5.5 auto_commit モード

ツールやライトなアプリケーション向けに、execute() 実行ごとに自動コミットするモードを提供する。

```python
# auto_commit=True で各 execute() 後に自動コミット
db = Sqlym(connection, sql_dir="sql", auto_commit=True)

db.execute("users/update.sql", {"id": 1})  # 即座に commit
db.execute("users/update.sql", {"id": 2})  # 即座に commit
# 個別にコミットされるため、2つ目が失敗しても1つ目は確定済み
```

設計案:

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
        self._connection = connection
        self._auto_commit = auto_commit
        ...

    def execute(self, sql_path: str, params: dict[str, Any] | None = None) -> int:
        """INSERT/UPDATE/DELETE を実行し、影響行数を返す."""
        ...
        affected = cursor.rowcount
        if self._auto_commit:
            self._connection.commit()
        return affected
```

注意事項:
- `auto_commit=True` の場合、コンテキストマネージャ (`with db:`) は使用しない想定
- 複数の操作をアトミックに実行したい場合は `auto_commit=False`（デフォルト）を使用する

#### 0.5.6 アーキテクチャ別の実装例

Clean Architecture / Onion Architecture での実装パターンは `examples/` ディレクトリを参照。

- `examples/clean_architecture/` - レイヤード構成での UnitOfWork 実装例
- `examples/simple_tool/` - auto_commit を使ったシンプルな CLI ツール例

### 0.6 その他の考慮事項

- **カーソル管理**: 内部で cursor を生成・クローズ
- **行の dict 変換**: DB-API の cursor.description を使用して自動変換

---

## 1. パラメータ修飾記号（Clione-SQL 未実装）

### 1.1 `&` 修飾記号（バインドなし行削除）

`$` と同様に negative 時に行削除するが、positive 時にプレースホルダ付与・値バインドを行わない。

```sql
SELECT * FROM people
WHERE
    SEX = 'female' /* &!is_gender_free */
    AND age /* $!age */= 25
```

用途: 条件フラグによる行の有効/無効切り替え

### 1.2 `@` 修飾記号（必須パラメータ）

パラメータが negative のとき例外をスローする。

```sql
SELECT * FROM TABLE1 WHERE ID = /* @id */'11'
```

### 1.3 `?` 修飾記号（フォールバック）

パラメータが negative のとき、右隣のパラメータを使用。全て negative ならデフォルト値を使用。

```sql
UPDATE people SET
    hometown = /* ?prefecture ?country */'unknown'
WHERE ID = /* @id */'11'
```

### 1.4 `!` による否定

修飾記号の挙動を反転させる。

```sql
-- age が positive なら行削除、negative なら残す
AND age /* $!age */= 25
```

---

## 2. 比較演算子の自動変換

パラメータを比較演算子の**前**に置いた場合、値に応じて演算子を自動変換する。

```sql
FIELD1 /* param */= 100
```

| param の値 | 変換結果 |
|------------|----------|
| `null` | `FIELD1 IS NULL` |
| スカラー値 | `FIELD1 = ?` |
| 要素数1のリスト | `FIELD1 = ?` |
| 要素数2以上のリスト | `FIELD1 IN (?, ?, ...)` |
| 空リスト | `FIELD1 IS NULL` |

否定演算子（`<>`, `!=`, `IS NOT`, `NOT IN`）の前に置いた場合:

| param の値 | 変換結果 |
|------------|----------|
| `null` | `FIELD1 IS NOT NULL` |
| リスト | `FIELD1 NOT IN (?, ?, ...)` |

---

## 3. IN 句の部分展開

IN 句内の一部のみをパラメータ化できる。

```sql
FIELD1 IN ('aaa', 'bbb', /* param */'ccc')
```

`param = [10, 20, 30]` の場合:

```sql
FIELD1 IN ('aaa', 'bbb', ?, ?, ?)
```

---

## 4. LIKE 句のリスト展開

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

---

## 5. 行末区切りの除去

行末に区切り（AND, OR, カンマ等）がある場合、行削除後に残った行末区切りを除去する。

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

（行末の `AND` が自動除去される）

---

## 6. 区切りのみの行の結合

AND, OR, UNION, UNION ALL 等の区切りのみの行は、次の行と結合して1ノードとして扱う。

```sql
SELECT id FROM table1
UNION
SELECT id FROM table2
UNION ALL
SELECT id FROM table3
```

UNION/UNION ALL 行は次の SELECT と同一ノードになり、ブロック単位での削除が可能。

---

## 7. negative/positive の拡張判定

現在は `None` のみを negative として扱うが、Clione-SQL では以下も negative:

- `False`（Boolean）
- 空リスト `[]`
- 全要素が negative のリスト

---

## 8. 補助関数

### 8.1 `%concat` / `%C`（文字列連結）

パラメータと文字列を連結して1つの値にする。

```sql
WHERE name LIKE /* %concat('%', part_of_name, '%') */'%山田%'
```

または短縮形:

```sql
WHERE name LIKE /*%C '%' part_of_name '%' */'%山田%'
```

### 8.2 `%esc_like` / `%L`（LIKE エスケープ）

LIKE 句のワイルドカード文字（`%`, `_`）をエスケープする。

```sql
WHERE lyrics LIKE /*%L '%' keyword '%' */'%100#%病気%'
```

`%L` は自動で `escape '#'` を SQL に付与する。

※ 現在 `escape_like()` ユーティリティは存在するが、SQL テンプレート内での補助関数形式は未対応。

### 8.3 `%if-%elseif-%else`（インライン条件分岐）

```sql
/* %if cond1 'AAA' %elseif cond2 'BBB' %else 'CCC' */'default'
```

### 8.4 `%include`（SQL インクルード）

別の SQL ファイルをインクルードする。

```sql
/* %include('./Sub_Query') */
```

### 8.5 `%STR` / `%SQL`（直接埋め込み）

パラメータ値を SQL に直接展開する（SQLインジェクション注意）。

```sql
ORDER BY /* %STR(order_column) */id
```

---

## 9. ブロック切り替え（`-- %IF` / `-- %ELSE`）

行コメント形式での条件分岐。

```sql
WHERE
    title = /* $title */'chief'
    -- %IF useDateEmployed
      AND date_employed >= /* $date_from */'19980401'
    -- %ELSE
      AND date_of_promotion >= /* $date_from */'20080401'
```

---

## 10. 複数行文字列リテラルの解析

文字列リテラル内の改行を正しく認識し、1つの論理行として扱う。

```sql
INSERT INTO PEOPLE (ID, NAME, ADDRESS)
VALUES (
    /* ID */'0001'
    ,/* NAME */'Yoko'
    ,/* $ADDRESS */'Ocean-Child''s House
123-4
Tokyo
Japan'
)
```

`ADDRESS = None` の場合、6行分がまとめて削除される。

---

## 11. 既知の問題

### 11.1 WITH 句（CTE）内での過剰削除

WITH 句内の WHERE 条件が全て None の場合、CTE 全体が削除されてしまう。

```sql
WITH filtered AS (
    SELECT * FROM users
    WHERE
        status = /* $status */'active'
        AND dept_id = /* $dept_id */1
)
SELECT * FROM filtered
```

`status = None, dept_id = None` の場合:

- **現状**: `SELECT * FROM filtered`（不正な SQL）
- **期待**: `WITH filtered AS (SELECT * FROM users) SELECT * FROM filtered`

原因: 親子関係の伝播ルールにより、WHERE が削除されると CTE 全体が削除される。

対応案: CTE の SELECT 行はパラメータを含まない場合、削除対象外とする特別処理が必要。

---

## 優先度の提案

| 優先度 | 機能 | 理由 |
|--------|------|------|
| **最高** | Sqlym | API の使いやすさ向上、README との整合性 |
| 高 | 行末区切りの除去 | 既存機能の自然な拡張 |
| 高 | `&` 修飾記号 | 条件フラグで頻出 |
| 中 | `!` 否定 | 表現力向上 |
| 中 | 比較演算子の自動変換 | Clione-SQL の特徴的機能 |
| 中 | IN 句の部分展開 | 固定値との混在ケース |
| 低 | 補助関数全般 | 複雑度が高い |
| 低 | `%include` | スコープが大きい |
