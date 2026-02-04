# SQL 構文リファレンス

[English](SQL_SYNTAX.md)

sqly で使用する SQL テンプレートの書き方を説明します。

## 基本的な考え方

sqly の SQL テンプレートは **2way SQL** です。

- sqly を通すとパラメータがバインドされた SQL になる
- DB ツール（pgAdmin、DBeaver 等）でそのまま実行するとデフォルト値で
  動作する

```sql
SELECT * FROM users WHERE name = /* $name */'山田太郎'
```

| 実行方法 | 結果 |
| --- | --- |
| DB ツールで直接実行 | `WHERE name = '山田太郎'`（デフォルト値が使われる） |
| sqly 経由で実行 | `WHERE name = ?` + バインド値 `['山田太郎']` |

SQL コメント `/* ... */` の中にパラメータを書き、コメント直後に
デフォルト値を置く。DB ツールはコメントを無視するのでデフォルト値が
そのまま使われます。

---

## パラメータの書き方

### 削除可能パラメータ（`$` 付き）

```sql
/* $パラメータ名 */デフォルト値
```

パラメータが `None`（または未指定）の場合、**その行全体が削除されます**。
検索条件の動的な ON/OFF に使います。

```sql
SELECT * FROM employee
WHERE
    dept_id = /* $dept_id */1
    AND name = /* $name */'山田'
    AND status = /* $status */'active'
```

```python
result = parse_sql(sql, {"dept_id": 10, "name": None, "status": "active"})
```

`name` が `None` なので、その行が削除されます：

```sql
SELECT * FROM employee
WHERE
    dept_id = ?
    AND status = ?
-- params: [10, 'active']
```

先頭の条件を `None` にした場合：

```python
result = parse_sql(sql, {"dept_id": None, "name": "山田", "status": "active"})
```

`dept_id` の行が削除され、先頭に残った `AND` が自動除去されます：

```sql
SELECT * FROM employee
WHERE
    name = ?
    AND status = ?
-- params: ['山田', 'active']
```

### 非削除パラメータ（`$` なし）

```sql
/* パラメータ名 */デフォルト値
```

パラメータが `None` でも行は削除されず、**NULL としてバインド**されます。
値が NULL になり得るカラムの更新・検索に使います。

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

### デフォルト値の形式

| 形式 | 例 | 用途 |
| --- | --- | --- |
| 文字列 | `'山田太郎'` | 文字列パラメータ |
| 数値 | `123`, `45.67` | 数値パラメータ |
| NULL | `NULL` | NULL チェック |
| 識別子 | `column_name` | カラム参照等 |
| リスト | `(1, 2, 3)` | IN 句 |

---

## 行の削除と親子関係

sqly は **行単位** で SQL を処理します。動的な条件の組み立ては行の削除で
実現します。

### Rule 1：行単位処理

SQL は 1 行ずつ `LineUnit` として処理されます。
パラメータコメントを含む行が削除の判定対象になります。

### Rule 2：インデントで親子関係を定義する

インデントの深さで親子関係が決まります。

```sql
WHERE                          -- 親（indent=0）
    dept_id = /* $dept_id */1  -- 子（indent=4）
    AND name = /* $name */'山田' -- 子（indent=4）
```

### Rule 3：子が全て削除されたら親も削除される

```sql
WHERE
    dept_id = /* $dept_id */1
    AND name = /* $name */'山田'
```

`dept_id` と `name` が両方 `None` の場合：

- 2 行とも削除 → 子が全て削除
- `WHERE` 行も削除

```sql
SELECT * FROM employee
-- WHERE 自体が消える
```

### Rule 4：`$` 付きパラメータが None なら行を削除する

`$` 付きのパラメータが `None`（または params に存在しない）場合、
その行全体が削除されます。

---

## 括弧のネスト

括弧を使った条件グループも、インデントに基づいて削除が伝播します。

```sql
SELECT * FROM employee
WHERE
    id = /* $id */1
    AND (
        status = /* $status1 */'active'
        OR status = /* $status2 */'pending'
    )
```

`status1` と `status2` が両方 `None` の場合：

1. `status1`、`status2` の行が削除される（Rule 4）
2. `AND (` の子が全て削除される → `AND (` も削除（Rule 3）
3. 閉じ括弧 `)` も対応する開き括弧が削除されたため削除
4. 最終結果：

```sql
SELECT * FROM employee
WHERE
    id = ?
```

---

## AND/OR の自動除去

行が削除された結果、先頭に AND や OR が残る場合は自動的に除去されます。

```sql
WHERE
    id = /* $id */1
    AND name = /* $name */'山田'
    AND status = /* $status */'active'
```

`id` が `None` の場合：

```sql
WHERE
    name = ?
    AND status = ?
-- 先頭の AND が除去される
```

---

## IN 句

### 基本

リストパラメータを渡すと、IN 句のプレースホルダが自動展開されます。

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

`(1, 2, 3)` はデフォルト値で、DB ツールでの直接実行時に使われます。

### 空リスト

空リストを渡すと `IN (NULL)` に置換されます（結果は 0 件）。

```python
result = parse_sql(sql, {"dept_ids": []})
```

```sql
WHERE dept_id IN (NULL)
```

### IN 句と行削除の組み合わせ

`$` 付きの IN 句パラメータが `None` の場合は行ごと削除されます。

```sql
WHERE
    name = /* $name */'山田'
    AND dept_id IN /* $dept_ids */(1, 2, 3)
```

```python
result = parse_sql(sql, {"name": "山田", "dept_ids": None})
```

```sql
WHERE
    name = ?
-- dept_ids の行が削除される
```

---

## プレースホルダ形式

RDBMS に応じてプレースホルダ形式を切り替えます。

### `?` 形式（SQLite）— デフォルト

```python
result = parse_sql(sql, params)
# または
result = parse_sql(sql, params, dialect=Dialect.SQLITE)
```

```sql
WHERE name = ? AND age = ?
-- result.params = ['山田', 30]
```

### `%s` 形式（PostgreSQL / MySQL）

```python
result = parse_sql(sql, params, dialect=Dialect.POSTGRESQL)
```

```sql
WHERE name = %s AND age = %s
-- result.params = ['山田', 30]
```

### `:name` 形式（Oracle）

```python
result = parse_sql(sql, params, dialect=Dialect.ORACLE)
```

```sql
WHERE name = :name AND age = :age
-- result.named_params = {'name': '山田', 'age': 30}
```

`:name` 形式では `result.named_params` を使用してバインドします。

#### Oracle の IN 句

`:name` 形式の場合、IN 句は連番の名前付きパラメータに展開されます。

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

## RDBMS 別 SQL ファイル

RDBMS ごとに SQL 構文が異なる場合は、ファイルを分けて対応します。

```text
sql/employee/
├── find.sql              # 共通 SQL
├── find.sql-oracle       # Oracle 固有（優先ロード）
└── find.sql-postgresql   # PostgreSQL 固有（優先ロード）
```

```python
loader = SqlLoader("sql")

# Dialect を指定すると、まず find.sql-oracle を探し、なければ find.sql に
# フォールバック
sql = loader.load("employee/find.sql", dialect=Dialect.ORACLE)
```

ページネーション（`LIMIT/OFFSET`、`ROWNUM` 等）や UPSERT 構文など
RDBMS 固有の SQL 構文はこの仕組みで切り替えてください。

---

## エラーメッセージ

SQL パースに失敗した場合（例: IN 句分割ができない場合）、
`SqlParseError` が発生します。デフォルトでは行番号と SQL 断片が
含まれます。SQL 断片を表示したくない場合は設定で無効化してください。

```python
from sqly import config

config.ERROR_INCLUDE_SQL = False
config.ERROR_MESSAGE_LANGUAGE = "en"
```

`ERROR_MESSAGE_LANGUAGE` は `ja` / `en` を指定できます。

例:

```text
IN句分割の列式を抽出できません: line=12 sql='...'
```

---

## 実践例

### 複数条件の動的検索

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
    AND e.name LIKE /* $name_pattern */'%山田%'
    AND e.dept_id IN /* $dept_ids */(1, 2, 3)
    AND e.status = /* $status */'active'
    AND (
        e.hire_date >= /* $hire_from */'2020-01-01'
        OR e.hire_date <= /* $hire_to */'2024-12-31'
    )
ORDER BY e.id
```

```python
# 全条件指定
result = parse_sql(
    sql,
    {
        "id": 100,
        "name_pattern": "%山田%",
        "dept_ids": [10, 20],
        "status": "active",
        "hire_from": "2023-01-01",
        "hire_to": "2023-12-31",
    },
)

# 一部条件のみ（指定しない条件は None で行削除）
result = parse_sql(
    sql,
    {
        "id": None,
        "name_pattern": "%山田%",
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

INSERT 文のパラメータは行削除が不要なので `$` なしで記述します。

### UPDATE

```sql
UPDATE employee SET
    name = /* name */'',
    dept_id = /* dept_id */0,
    updated_at = /* updated_at */CURRENT_TIMESTAMP
WHERE
    id = /* $id */1
```

SET 句は `$` なし、WHERE 句は `$` 付きで記述するのが一般的です。
